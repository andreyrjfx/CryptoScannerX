from app.services.arbitrage_scanner import ArbitrageScanner
from tests.conftest import make_ticker


def test_finds_spot_future_opportunity_above_display_spread():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=101, ask=101.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.coin == "BTC"
    assert opp.buy_exchange == "binance"
    assert opp.sell_exchange == "bybit"
    assert opp.trade_type == "spot-future"


def test_ignores_low_volume_tickers():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1, volume_usdt=1000),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=101, ask=101.1, volume_usdt=1000),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert opportunities == []


def test_ignores_spread_below_display_threshold():
    # спред ~0.1%, ниже DISPLAY_SPREAD=0.50%
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=100.1, ask=100.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert opportunities == []


def test_coin_filter_restricts_results():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=101, ask=101.1),
        make_ticker(exchange="binance", market="spot", coin="ETH", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="ETH", bid=101, ask=101.1),
    ]

    opportunities = ArbitrageScanner(tickers, coins=["ETH"]).scan()

    assert len(opportunities) == 1
    assert opportunities[0].coin == "ETH"


def test_same_exchange_same_market_is_not_an_opportunity():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=101, ask=101.1, symbol="BTCUSDT2"),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert opportunities == []


def test_basis_trade_type_same_exchange_different_market():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="binance", market="future", coin="BTC", bid=101, ask=101.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert len(opportunities) == 1
    assert opportunities[0].trade_type == "basis"


def test_results_sorted_by_net_spread_descending():
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=101, ask=101.1),
        make_ticker(exchange="binance", market="spot", coin="ETH", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="ETH", bid=105, ask=105.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    spreads = [o.net_spread for o in opportunities]
    assert spreads == sorted(spreads, reverse=True)


def test_implausibly_large_spread_is_filtered_out():
    """
    Регрессионный тест: если один и тот же тикер на двух биржах — на самом деле
    разные активы (или пришли битые данные), спред может быть в тысячи процентов.
    Это не реальный арбитраж, и такие строки не должны попадать в результаты.
    """
    tickers = [
        make_ticker(exchange="mexc", market="future", coin="ON", symbol="ON_USDT", bid=0.01, ask=0.01),
        make_ticker(exchange="bybit", market="future", coin="ON", symbol="ONUSDT", bid=6.5, ask=6.5),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert opportunities == []


def test_spot_spot_is_excluded_by_default_short_spot_not_possible():
    """
    На большинстве бирж нельзя шортить спот (продать актив, которого нет)
    обычным способом — spot-spot арбитраж всегда требует шорта одной из ног.
    """
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="spot", coin="BTC", bid=101, ask=101.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert opportunities == []


def test_future_spot_excluded_but_spot_future_kept():
    """
    "future-spot" (продажная нога — спот) требует шорта спота и исключается.
    "spot-future" (продажная нога — фьючерс) шортит фьючерс — это стандартно
    и доступно всегда, такие сделки остаются.
    """
    tickers = [
        make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
        make_ticker(exchange="bybit", market="future", coin="BTC", bid=105, ask=105.1),
    ]

    opportunities = ArbitrageScanner(tickers).scan()

    assert len(opportunities) == 1
    assert opportunities[0].trade_type == "spot-future"
    assert opportunities[0].sell_market == "future"


def test_allow_short_spot_flag_reenables_spot_short_trades():
    import app.services.arbitrage_scanner as scanner_module
    original = scanner_module.ALLOW_SHORT_SPOT
    scanner_module.ALLOW_SHORT_SPOT = True

    try:
        tickers = [
            make_ticker(exchange="binance", market="spot", coin="BTC", bid=100, ask=100.1),
            make_ticker(exchange="bybit", market="spot", coin="BTC", bid=101, ask=101.1),
        ]

        opportunities = ArbitrageScanner(tickers).scan()

        assert len(opportunities) == 1
        assert opportunities[0].trade_type == "spot-spot"
    finally:
        scanner_module.ALLOW_SHORT_SPOT = original
