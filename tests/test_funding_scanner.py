from app.services.funding_scanner import FundingScanner
from tests.conftest import make_ticker

# Общее время следующей выплаты для тестов, где обе стороны должны совпадать
# (иначе REQUIRE_MATCHING_FUNDING_TIME отфильтрует пару).
SAME_TIME = 1700000000000


def test_finds_funding_spread_between_exchanges():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.short_exchange == "binance"  # более высокий funding rate -> шортим тут
    assert opp.long_exchange == "bybit"     # более низкий/отрицательный -> лонгуем тут
    assert opp.funding_spread == 0.07


def test_ignores_spot_tickers():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_ignores_spread_below_threshold():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.01, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=0.005, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.05).scan()

    assert opportunities == []


def test_same_exchange_is_not_an_opportunity():
    tickers = [
        make_ticker(
            exchange="binance", market="future", coin="BTC", symbol="BTCUSDT",
            funding_rate=0.05, next_funding_time=SAME_TIME,
        ),
        make_ticker(
            exchange="binance", market="future", coin="BTC", symbol="BTCUSD_PERP",
            funding_rate=-0.02, next_funding_time=SAME_TIME,
        ),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_low_volume_tickers_are_ignored():
    tickers = [
        make_ticker(
            exchange="binance", market="future", coin="BTC",
            funding_rate=0.05, volume_usdt=100, next_funding_time=SAME_TIME,
        ),
        make_ticker(
            exchange="bybit", market="future", coin="BTC",
            funding_rate=-0.02, volume_usdt=100, next_funding_time=SAME_TIME,
        ),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_results_sorted_by_spread_descending():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
        make_ticker(exchange="binance", market="future", coin="ETH", funding_rate=0.10, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="ETH", funding_rate=-0.10, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    spreads = [o.funding_spread for o in opportunities]
    assert spreads == sorted(spreads, reverse=True)
    assert opportunities[0].coin == "ETH"


def test_next_funding_time_is_propagated_from_both_sides():
    tickers = [
        make_ticker(
            exchange="binance", market="future", coin="BTC",
            funding_rate=0.05, next_funding_time=SAME_TIME,
        ),
        make_ticker(
            exchange="bybit", market="future", coin="BTC",
            funding_rate=-0.02, next_funding_time=SAME_TIME,
        ),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.short_next_funding_time == SAME_TIME
    assert opp.long_next_funding_time == SAME_TIME


def test_fee_percent_is_sum_of_both_futures_legs():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    # binance future 0.05% + bybit future 0.055% (см. FeeCalculator.FEES)
    assert abs(opp.fee_percent - 0.105) < 1e-9


def test_breakeven_periods_is_fee_divided_by_spread():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    opp = opportunities[0]
    assert opp.funding_spread == 0.07
    assert abs(opp.breakeven_periods - (opp.fee_percent / 0.07)) < 1e-9


def test_dollar_fields_use_position_size_usdt():
    from app.config import POSITION_SIZE_USDT

    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()
    opp = opportunities[0]

    assert abs(opp.profit_per_period_usdt - POSITION_SIZE_USDT * opp.funding_spread / 100) < 1e-6
    assert abs(opp.fee_usdt - POSITION_SIZE_USDT * opp.fee_percent / 100) < 1e-6


def test_net_first_period_is_spread_minus_fee():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, next_funding_time=SAME_TIME),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, next_funding_time=SAME_TIME),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()
    opp = opportunities[0]

    assert abs(opp.net_first_period_percent - (opp.funding_spread - opp.fee_percent)) < 1e-9
    assert abs(opp.net_first_period_usdt - (opp.profit_per_period_usdt - opp.fee_usdt)) < 1e-9


class TestFundingTimeMatching:
    """
    Регрессионные тесты: раньше funding_spread сравнивался даже если время
    выплаты по шорту и лонгу не совпадало — часть времени экспозиция была бы
    только по одной ноге, и спред не отражал честный за-период результат.
    """

    def test_mismatched_funding_times_excluded_by_default(self):
        tickers = [
            make_ticker(
                exchange="binance", market="future", coin="BTC",
                funding_rate=0.05, next_funding_time=SAME_TIME,
            ),
            make_ticker(
                exchange="bybit", market="future", coin="BTC",
                funding_rate=-0.02, next_funding_time=SAME_TIME + 3_600_000,  # +1 час
            ),
        ]

        opportunities = FundingScanner(tickers, min_spread=0.01).scan()

        assert opportunities == []

    def test_unknown_funding_time_excluded_by_default(self):
        tickers = [
            make_ticker(
                exchange="binance", market="future", coin="BTC",
                funding_rate=0.05, next_funding_time=SAME_TIME,
            ),
            make_ticker(
                exchange="bybit", market="future", coin="BTC",
                funding_rate=-0.02, next_funding_time=None,
            ),
        ]

        opportunities = FundingScanner(tickers, min_spread=0.01).scan()

        assert opportunities == []

    def test_small_difference_within_tolerance_is_allowed(self):
        tickers = [
            make_ticker(
                exchange="binance", market="future", coin="BTC",
                funding_rate=0.05, next_funding_time=SAME_TIME,
            ),
            make_ticker(
                exchange="bybit", market="future", coin="BTC",
                funding_rate=-0.02, next_funding_time=SAME_TIME + 5_000,  # +5 секунд, в пределах допуска
            ),
        ]

        opportunities = FundingScanner(tickers, min_spread=0.01).scan()

        assert len(opportunities) == 1

    def test_flag_disabled_allows_mismatched_times(self):
        import app.services.funding_scanner as scanner_module
        original = scanner_module.REQUIRE_MATCHING_FUNDING_TIME
        scanner_module.REQUIRE_MATCHING_FUNDING_TIME = False

        try:
            tickers = [
                make_ticker(
                    exchange="binance", market="future", coin="BTC",
                    funding_rate=0.05, next_funding_time=SAME_TIME,
                ),
                make_ticker(
                    exchange="bybit", market="future", coin="BTC",
                    funding_rate=-0.02, next_funding_time=SAME_TIME + 3_600_000,
                ),
            ]

            opportunities = FundingScanner(tickers, min_spread=0.01).scan()

            assert len(opportunities) == 1
        finally:
            scanner_module.REQUIRE_MATCHING_FUNDING_TIME = original
