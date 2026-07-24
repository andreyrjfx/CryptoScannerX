import argparse
import asyncio
import logging
import time

from app.__version__ import __version__
from app.config import FILTER_COINS, COINGECKO_API_KEY, COINGECKO_RATE_LIMIT_PER_MINUTE
from app.clients.http import HttpClient
from app.exchanges.manager import ExchangeManager

from app.services.collector import ExchangeCollector
from app.services.market_filter import MarketFilter
from app.services.arbitrage_scanner import ArbitrageScanner
from app.services.funding_enricher import MexcFundingEnricher
from app.services.funding_scanner import FundingScanner
from app.services.depth_checker import DepthChecker
from app.services.coin_identity import CoinIdentityChecker
from app.services.history_store import HistoryStore

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
    parser.add_argument(
        "--history", type=int, nargs="?", const=20, metavar="N", default=None,
        help="Показать последние N записей из истории (по умолчанию 20) вместо обычного скана",
    )
    return parser.parse_args()


def identity_marker(value):
    """✅ подтверждено CoinGecko, ⚠️ не подтверждено (риск разных активов), ? не проверялось."""
    if value is True:
        return "✅"
    if value is False:
        return "⚠️"
    return "?"


def format_time_until(next_funding_time_ms):
    """Unix ms -> 'Xh YYm' до начисления, или '—' если время неизвестно/уже прошло."""
    if not next_funding_time_ms:
        return "—"

    remaining_seconds = next_funding_time_ms / 1000 - time.time()
    if remaining_seconds <= 0:
        return "—"

    hours = int(remaining_seconds // 3600)
    minutes = int((remaining_seconds % 3600) // 60)
    return f"{hours}h{minutes:02d}m"


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
        "ID — подтверждение через CoinGecko: ✅ подтверждено, ⚠️ не подтверждено, "
        "? не проверялось (нет ключа/сеть/лимит запросов). CoinGecko видит в "
        "основном spot-листинги — для чисто-фьючерсных пар и токенизированных "
        "акций (тикеры вроде TQQQ, NVDL, SMCI) ⚠️/? не обязательно значит "
        "'разные активы', может просто значить 'не смогли проверить' — сверяй вручную.\n"
        "Сделки, где шортится спот (spot-spot и часть future-spot/basis), "
        "по умолчанию не показываются — см. ALLOW_SHORT_SPOT в config.py."
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
        f"{'$/PERIOD':>10}{'FEE $':>8}{'NET(1st)':>10}{'B/E':>6}"
        f"{'SHORT IN':>10}{'LONG IN':>10}  {'ID':<3}"
    )
    print("-" * 133)

    for item in opportunities[:50]:
        breakeven = f"{item.breakeven_periods:>5.1f}" if item.breakeven_periods is not None else f"{'—':>5}"
        print(
            f"{item.coin:<10}{item.short_exchange:<14}{item.long_exchange:<14}"
            f"{item.short_funding_rate:>9.4f}%{item.long_funding_rate:>9.4f}%"
            f"{item.funding_spread:>9.4f}%"
            f"{item.profit_per_period_usdt:>10.2f}{item.fee_usdt:>8.2f}"
            f"{item.net_first_period_usdt:>10.2f}{breakeven}"
            f"{format_time_until(item.short_next_funding_time):>10}"
            f"{format_time_until(item.long_next_funding_time):>10}  "
            f"{identity_marker(item.identity_verified):<3}"
        )

    print(
        "\n$/PERIOD — валовая прибыль за один период начисления в USDT при "
        "позиции POSITION_SIZE_USDT (повторяется каждый период, пока funding "
        "rate не изменится). FEE $ — разовая комиссия на вход в USDT "
        "(закрытие позже — ещё одна такая же, здесь не учтена).\n"
        "NET(1st) — чистый результат, если продержать позицию ровно один "
        "период ($/PERIOD - FEE $), может быть отрицательным. Чистый PnL за "
        "N периодов ≈ $/PERIOD × N - FEE $.\n"
        "B/E (breakeven) — сколько периодов начисления нужно продержать позицию, "
        "чтобы funding окупил комиссию на вход. Периоды у разных бирж могут "
        "отличаться по длительности (обычно 8ч, у части монет 1ч/4ч).\n"
        "SHORT IN/LONG IN — время до следующего начисления funding на каждой "
        "стороне (по умолчанию показываются только пары с совпадающим временем "
        "выплаты — см. REQUIRE_MATCHING_FUNDING_TIME в config.py).\n"
        "ID — подтверждение через CoinGecko: ✅ подтверждено, ⚠️ не подтверждено, "
        "? не проверялось. Эта таблица сравнивает только фьючерсные стороны — "
        "CoinGecko же в основном видит spot-листинги, поэтому здесь ⚠️/? "
        "встречается гораздо чаще и не обязательно значит 'разные активы' — "
        "проверяй вручную, особенно для не-крипто тикеров (акции/ETF)."
    )


def print_history(history_store, limit):
    arbitrage_rows = history_store.recent_arbitrage(limit)
    funding_rows = history_store.recent_funding(limit)

    print("\n==============================================================")
    print(f"ИСТОРИЯ — последние {limit} записей")
    print("==============================================================\n")

    print(f"-- ARBITRAGE ({len(arbitrage_rows)}) --\n")
    if not arbitrage_rows:
        print("Пусто.")
    else:
        print(
            f"{'RUN AT':<20}{'TYPE':<16}{'COIN':<10}{'BUY':<20}{'SELL':<20}"
            f"{'NET':>8}{'REAL NET':>10}  {'ID':<3}"
        )
        print("-" * 107)
        for row in arbitrage_rows:
            buy = f"{row['buy_exchange']} {row['buy_market']}"
            sell = f"{row['sell_exchange']} {row['sell_market']}"
            real_net = f"{row['real_net_spread']:>9.2f}%" if row["real_net_spread"] is not None else f"{'—':>10}"
            print(
                f"{row['run_at'][:19]:<20}{row['trade_type']:<16}{row['coin']:<10}"
                f"{buy:<20}{sell:<20}{row['net_spread']:>7.2f}%{real_net}  "
                f"{identity_marker(row['identity_verified']):<3}"
            )

    print(f"\n-- FUNDING ARBITRAGE ({len(funding_rows)}) --\n")
    if not funding_rows:
        print("Пусто.")
    else:
        print(
            f"{'RUN AT':<20}{'COIN':<10}{'SHORT':<14}{'LONG':<14}"
            f"{'SPREAD %':>10}{'$/PERIOD':>10}{'FEE $':>8}{'NET(1st)':>10}{'B/E':>6}"
            f"{'SHORT IN':>10}{'LONG IN':>10}  {'ID':<3}"
        )
        print("-" * 136)
        for row in funding_rows:
            profit = f"{row['profit_per_period_usdt']:>9.2f}" if row["profit_per_period_usdt"] is not None else f"{'—':>9}"
            fee = f"{row['fee_usdt']:>7.2f}" if row["fee_usdt"] is not None else f"{'—':>7}"
            net_first = f"{row['net_first_period_usdt']:>9.2f}" if row["net_first_period_usdt"] is not None else f"{'—':>9}"
            breakeven = f"{row['breakeven_periods']:>5.1f}" if row["breakeven_periods"] is not None else f"{'—':>5}"
            print(
                f"{row['run_at'][:19]:<20}{row['coin']:<10}{row['short_exchange']:<14}"
                f"{row['long_exchange']:<14}{row['funding_spread']:>9.4f}%"
                f"{profit}{fee}{net_first}{breakeven}"
                f"{format_time_until(row['short_next_funding_time']):>10}"
                f"{format_time_until(row['long_next_funding_time']):>10}  "
                f"{identity_marker(row['identity_verified']):<3}"
            )


async def main(args):
    if args.history is not None:
        print_history(HistoryStore(), args.history)
        return

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
            unique_checks = {
                (opp.coin.upper(), frozenset({opp.buy_exchange, opp.sell_exchange}))
                for opp in opportunities[:PRINT_LIMIT]
            } | {
                (fopp.coin.upper(), frozenset({fopp.short_exchange, fopp.long_exchange}))
                for fopp in funding_opportunities[:PRINT_LIMIT]
            }
            # На пару обычно уходит 2 запроса (по одному на биржу) + 2 разовых
            # на справочники CoinGecko; при большом количестве уникальных пар
            # и лимите биржи это может занять заметное время.
            estimated_seconds = len(unique_checks) * 2 / COINGECKO_RATE_LIMIT_PER_MINUTE * 60
            logger.info(
                "CoinGecko: проверка идентичности для %d уникальных пар "
                "(монета+биржи), ориентировочно ~%.0f сек при лимите %d/мин",
                len(unique_checks), estimated_seconds, COINGECKO_RATE_LIMIT_PER_MINUTE,
            )

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

        history_store = HistoryStore()
        history_store.save_arbitrage(opportunities)
        history_store.save_funding(funding_opportunities)

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
