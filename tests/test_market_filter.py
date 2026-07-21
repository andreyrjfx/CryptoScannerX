from app.services.market_filter import MarketFilter
from tests.conftest import make_ticker


class FakeExchange:
    def __init__(self, markets):
        self.markets = markets


def test_keeps_ticker_when_matching_market_exists():
    exchanges = {
        "binance": FakeExchange({
            "BTC/USDT": {"active": True, "swap": False, "spot": True, "quote": "USDT", "base": "BTC"},
        }),
    }

    tickers = [make_ticker(exchange="binance", market="spot", coin="BTC")]

    result = MarketFilter(exchanges).filter(tickers)

    assert result == tickers


def test_regression_spot_ticker_not_dropped_when_only_futures_market_exists():
    """
    Регрессионный тест бага: раньше allowed-список строился только
    по фьючерсным (swap) рынкам и применялся ко всем тикерам —
    из-за этого spot-тикер монеты без фьючерса на бирже терялся,
    а тут наоборот: ETH есть только как spot, поэтому future-тикер
    ETH должен быть отфильтрован, а spot — нет.
    """
    exchanges = {
        "binance": FakeExchange({
            "ETH/USDT": {"active": True, "swap": False, "spot": True, "quote": "USDT", "base": "ETH"},
        }),
    }

    tickers = [
        make_ticker(exchange="binance", market="spot", coin="ETH"),
        make_ticker(exchange="binance", market="future", coin="ETH"),
    ]

    result = MarketFilter(exchanges).filter(tickers)

    assert len(result) == 1
    assert result[0].market == "spot"


def test_inactive_market_is_excluded():
    exchanges = {
        "binance": FakeExchange({
            "BTC/USDT": {"active": False, "swap": False, "spot": True, "quote": "USDT", "base": "BTC"},
        }),
    }

    tickers = [make_ticker(exchange="binance", market="spot", coin="BTC")]

    result = MarketFilter(exchanges).filter(tickers)

    assert result == []


def test_non_usdt_quote_is_excluded():
    exchanges = {
        "binance": FakeExchange({
            "BTC/BUSD": {"active": True, "swap": False, "spot": True, "quote": "BUSD", "base": "BTC"},
        }),
    }

    tickers = [make_ticker(exchange="binance", market="spot", coin="BTC")]

    result = MarketFilter(exchanges).filter(tickers)

    assert result == []


def test_unknown_exchange_has_no_allowed_coins():
    result = MarketFilter({}).filter([make_ticker(exchange="binance", market="spot", coin="BTC")])
    assert result == []
