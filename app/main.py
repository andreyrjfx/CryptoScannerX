import argparse
import asyncio
import logging

from app.__version__ import __version__
from app.config import FILTER_COINS, COINGECKO_API_KEY
from app.clients.http import HttpClient
from app.exchanges.manager import ExchangeManager

from app.services.collector import ExchangeCollector
from app.services.market_filter import MarketFilter
from app.services.arbitrage_scanner import ArbitrageScanner
from app.services.funding_enricher import MexcFundingEnricher
from app.services.funding_scanner import FundingScanner
from app.services.depth_checker import DepthChecker
from app.services.coin_identity import CoinIdentityChecker

logger = logging.getLogger(__name__)

# Сколько лучших возможностей показываем и проверяем на реальную глубину стакана
PRINT_LIMIT = 50


def parse_args():
    parser = argparse.ArgumentParser(description="CryptoScannerX — поиск арбитражных возможностей")
    parser.add_argument(
        "coins", nargs="*",
        help="Монеты для фильтрации (например BTC ETH SOL). По умолчанию — FILTER_COINS из config.py",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Показывать технические логи (подключение к биржам, количество тикеров, "
             "причины неудачных запросов funding/order book и т.д.)",
    )
    parser.add_argument(
        "--version", action="version", version=f"CryptoScannerX {__version__}",
    )
    return parser.parse_args()


def identity_marker(value):
    """✅ подтверждено CoinGecko, ⚠️ не подтверждено (риск разных активов), ? не проверялось."""
    if value is True:
        return "✅"
    if value is False:
        return "⚠️"
    return "?"


def print_opportunities(opportunities):
    print("\n==============================================================")
    print("ARBITRAGE")
    print("==============================================================\n")
    print(f"Найдено возможностей: {len(opportunities)}\n")

    if not opportunities:
        print("Арбитражных возможностей нет.")
        return

    print(
        f"{'TYPE':<16}{'COIN':<10}{'BUY':<24}{'SELL':<24}"
        f"{'RAW':>8}{'FEE':>8}{'NET':>8}{'PNL':>10}"
        f"{'SLIP':>8}{'REAL NET':>10}{'REAL PNL':>10}  {'ID':<3}"
    )
    print("-" * 141)

    for item in opportunities[:PRINT_LIMIT]:
        buy = f"{item.buy_exchange} {item.buy_market}"
        sell = f"{item.sell_exchange} {item.sell_market}"

        if item.effective_spread is not None:
            slip = f"{item.slippage_pct:>7.2f}%"
            real_net = f"{item.real_net_spread:>9.2f}%"
            real_pnl = f"{item.real_expected_profit_usdt:>10.2f}"
        else:
            # Глубина стакана не проверялась (не входит в топ-N) или запрос не удался
            slip = f"{'—':>8}"
            real_net = f"{'—':>10}"
            real_pnl = f"{'—':>10}"

        print(
            f"{item.trade_type:<16}{item.coin:<10}{buy:<24}{sell:<24}"
            f"{item.spread:>7.2f}%{item.fee_percent:>7.2f}%"
            f"{item.net_spread:>7.2f}%{item.expected_profit_usdt:>9.2f}"
            f"{slip}{real_net}{real_pnl}  {identity_marker(item.identity_verified):<3}"
        )

    print(
        "\nRAW/FEE/NET/PNL — по top-of-book цене (без учёта глубины стакана).\n"
        "SLIP/REAL NET/REAL PNL — с учётом VWAP-исполнения на "
        "POSITION_SIZE_USDT (реальная глубина стакана).\n"
        "ID — подтверждение через CoinGecko, что тикер на обеих биржах — один "
        "и тот же актив: ✅ подтверждено, ⚠️ не подтверждено (проверь вручную!), "
        "? не проверялось (нет ключа CoinGecko или сеть недоступна)."
    )


def print_funding_opportunities(opportunities):
    print("\n==============================================================")
    print("FUNDING ARBITRAGE")
    print("==============================================================\n")
    print(f"Найдено возможностей: {len(opportunities)}\n")

    if not opportunities:
        print("Funding-арбитражных возможностей нет.")
        return

    print(
        f"{'COIN':<10}{'SHORT':<14}{'LONG':<14}"
        f"{'SHORT %':>10}{'LONG %':>10}{'SPREAD %':>10}  {'ID':<3}"
    )
    print("-" * 71)

    for item in opportunities[:50]:
        print(
            f"{item.coin:<10}{item.short_exchange:<14}{item.long_exchange:<14}"
            f"{item.short_funding_rate:>9.4f}%{item.long_funding_rate:>9.4f}%"
            f"{item.funding_spread:>9.4f}%  {identity_marker(item.identity_verified):<3}"
        )


async def main(args):
    coins = [c.upper() for c in args.coins] if args.coins else FILTER_COINS

    logger.info("Фильтр монет: %s", ", ".join(coins) if coins else "весь рынок")

    manager = ExchangeManager()

    try:
        await manager.connect()
        await manager.test_connections()

        collector = ExchangeCollector()
        logger.info("Получение тикеров...")

        tickers = await collector.fetch_all()
        logger.info("Получено тикеров до фильтрации: %d", len(tickers))

        market_filter = MarketFilter(manager.exchanges)
        tickers = market_filter.filter(tickers)
        logger.info("Получено тикеров после фильтрации: %d", len(tickers))

        if coins:
            tickers = [t for t in tickers if t.coin.upper() in coins]
            logger.info("После фильтра монет: %d", len(tickers))

        scanner = ArbitrageScanner(tickers, coins)
        opportunities = scanner.scan()

        # Глубину стакана проверяем только у тех возможностей, что реально
        # попадут в таблицу — запрос стакана это отдельный вызов на символ.
        await DepthChecker().check(opportunities[:PRINT_LIMIT])

        # ----------------------------------------
        # Funding rate арбитраж
        # ----------------------------------------

        funding_http = HttpClient()
        await funding_http.connect()

        try:
            await MexcFundingEnricher(funding_http).enrich(tickers)
        finally:
            await funding_http.close()

        funding_scanner = FundingScanner(tickers)
        funding_opportunities = funding_scanner.scan()

        # ----------------------------------------
        # Проверка идентичности актива (CoinGecko)
        # ----------------------------------------

        if COINGECKO_API_KEY:
            async with CoinIdentityChecker(COINGECKO_API_KEY) as identity_checker:
                for opp in opportunities[:PRINT_LIMIT]:
                    opp.identity_verified = await identity_checker.verify(
                        opp.coin, {opp.buy_exchange, opp.sell_exchange},
                    )
                for fopp in funding_opportunities[:PRINT_LIMIT]:
                    fopp.identity_verified = await identity_checker.verify(
                        fopp.coin, {fopp.short_exchange, fopp.long_exchange},
                    )
        else:
            logger.warning(
                "COINGECKO_API_KEY не задан — проверка идентичности актива пропущена "
                "(см. .env.example). Колонка ID будет показывать '?' для всех строк.",
            )

        print_opportunities(opportunities)
        print_funding_opportunities(funding_opportunities)

    finally:
        await manager.close()


if __name__ == "__main__":
    cli_args = parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if cli_args.verbose:
        # DEBUG только для нашего кода — иначе сторонние библиотеки (aiohttp,
        # ccxt) на этом уровне могут выводить сырые HTTP-ответы целиком.
        # "__main__" — имя логгера самого main.py при запуске как `python -m app.main`.
        logging.getLogger("app").setLevel(logging.DEBUG)
        logging.getLogger("__main__").setLevel(logging.DEBUG)
    asyncio.run(main(cli_args))
