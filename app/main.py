import argparse
import asyncio
import logging

from app.__version__ import __version__
from app.config import FILTER_COINS
from app.clients.http import HttpClient
from app.exchanges.manager import ExchangeManager

from app.services.collector import ExchangeCollector
from app.services.market_filter import MarketFilter
from app.services.arbitrage_scanner import ArbitrageScanner
from app.services.funding_enricher import MexcFundingEnricher
from app.services.funding_scanner import FundingScanner

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="CryptoScannerX — поиск арбитражных возможностей")
    parser.add_argument(
        "coins", nargs="*",
        help="Монеты для фильтрации (например BTC ETH SOL). По умолчанию — FILTER_COINS из config.py",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Показывать технические логи (подключение к биржам, количество тикеров и т.д.)",
    )
    parser.add_argument(
        "--version", action="version", version=f"CryptoScannerX {__version__}",
    )
    return parser.parse_args()


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
        f"{'RAW':>8}{'FEE':>8}{'NET':>8}{'PNL':>12}"
    )
    print("-" * 112)

    for item in opportunities[:50]:
        buy = f"{item.buy_exchange} {item.buy_market}"
        sell = f"{item.sell_exchange} {item.sell_market}"

        print(
            f"{item.trade_type:<16}{item.coin:<10}{buy:<24}{sell:<24}"
            f"{item.spread:>7.2f}%{item.fee_percent:>7.2f}%"
            f"{item.net_spread:>7.2f}%{item.expected_profit_usdt:>11.2f}"
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
        f"{'SHORT %':>10}{'LONG %':>10}{'SPREAD %':>10}"
    )
    print("-" * 68)

    for item in opportunities[:50]:
        print(
            f"{item.coin:<10}{item.short_exchange:<14}{item.long_exchange:<14}"
            f"{item.short_funding_rate:>9.4f}%{item.long_funding_rate:>9.4f}%"
            f"{item.funding_spread:>9.4f}%"
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

        print_opportunities(opportunities)

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

        print_funding_opportunities(funding_opportunities)

    finally:
        await manager.close()


if __name__ == "__main__":
    cli_args = parse_args()

    logging.basicConfig(
        level=logging.INFO if cli_args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(main(cli_args))
