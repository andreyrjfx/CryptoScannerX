from app.services.funding_scanner import FundingScanner
from tests.conftest import make_ticker


def test_finds_funding_spread_between_exchanges():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.short_exchange == "binance"  # более высокий funding rate -> шортим тут
    assert opp.long_exchange == "bybit"     # более низкий/отрицательный -> лонгуем тут
    assert opp.funding_spread == 0.07


def test_ignores_spot_tickers():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", funding_rate=0.05),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_ignores_spread_below_threshold():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.01),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=0.005),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.05).scan()

    assert opportunities == []


def test_same_exchange_is_not_an_opportunity():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", symbol="BTCUSDT", funding_rate=0.05),
        make_ticker(exchange="binance", market="future", coin="BTC", symbol="BTCUSD_PERP", funding_rate=-0.02),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_low_volume_tickers_are_ignored():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05, volume_usdt=100),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02, volume_usdt=100),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert opportunities == []


def test_results_sorted_by_spread_descending():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02),
        make_ticker(exchange="binance", market="future", coin="ETH", funding_rate=0.10),
        make_ticker(exchange="bybit", market="future", coin="ETH", funding_rate=-0.10),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    spreads = [o.funding_spread for o in opportunities]
    assert spreads == sorted(spreads, reverse=True)
    assert opportunities[0].coin == "ETH"


def test_next_funding_time_is_propagated_from_both_sides():
    tickers = [
        make_ticker(
            exchange="binance", market="future", coin="BTC",
            funding_rate=0.05, next_funding_time=1700000000000,
        ),
        make_ticker(
            exchange="bybit", market="future", coin="BTC",
            funding_rate=-0.02, next_funding_time=1700003600000,
        ),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.short_next_funding_time == 1700000000000
    assert opp.long_next_funding_time == 1700003600000


def test_fee_percent_is_sum_of_both_futures_legs():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    # binance future 0.05% + bybit future 0.055% (см. FeeCalculator.FEES)
    assert abs(opp.fee_percent - 0.105) < 1e-9


def test_breakeven_periods_is_fee_divided_by_spread():
    tickers = [
        make_ticker(exchange="binance", market="future", coin="BTC", funding_rate=0.05),
        make_ticker(exchange="bybit", market="future", coin="BTC", funding_rate=-0.02),
    ]

    opportunities = FundingScanner(tickers, min_spread=0.01).scan()

    opp = opportunities[0]
    assert opp.funding_spread == 0.07
    assert abs(opp.breakeven_periods - (opp.fee_percent / 0.07)) < 1e-9
