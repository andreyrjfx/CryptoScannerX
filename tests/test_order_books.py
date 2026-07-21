from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.exchanges.binance_spot import BinanceSpotAdapter
from app.exchanges.bybit_futures import BybitFuturesAdapter
from app.exchanges.bybit_spot import BybitSpotAdapter
from app.exchanges.mexc_futures import MexcFuturesAdapter
from app.exchanges.mexc_spot import MexcSpotAdapter

from tests.conftest import FakeHttpClient


async def test_binance_futures_order_book():
    http = FakeHttpClient({
        BinanceFuturesAdapter.DEPTH_URL: {
            "bids": [["100.0", "5"], ["99.0", "10"]],
            "asks": [["101.0", "5"], ["102.0", "10"]],
        },
    })

    book = await BinanceFuturesAdapter(http).fetch_order_book("BTCUSDT", limit=50)

    assert book["bids"] == [(100.0, 5.0), (99.0, 10.0)]
    assert book["asks"] == [(101.0, 5.0), (102.0, 10.0)]


async def test_binance_spot_order_book():
    http = FakeHttpClient({
        BinanceSpotAdapter.DEPTH_URL: {"bids": [["100.0", "5"]], "asks": [["101.0", "5"]]},
    })

    book = await BinanceSpotAdapter(http).fetch_order_book("BTCUSDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]


async def test_mexc_spot_order_book():
    http = FakeHttpClient({
        MexcSpotAdapter.DEPTH_URL: {"bids": [["100.0", "5"]], "asks": [["101.0", "5"]]},
    })

    book = await MexcSpotAdapter(http).fetch_order_book("SOLUSDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]


async def test_bybit_futures_order_book():
    http = FakeHttpClient({
        BybitFuturesAdapter.ORDERBOOK_URL: {"result": {
            "b": [["100.0", "5"]], "a": [["101.0", "5"]],
        }},
    })

    book = await BybitFuturesAdapter(http).fetch_order_book("BTCUSDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]


async def test_bybit_spot_order_book():
    http = FakeHttpClient({
        BybitSpotAdapter.ORDERBOOK_URL: {"result": {
            "b": [["100.0", "5"]], "a": [["101.0", "5"]],
        }},
    })

    book = await BybitSpotAdapter(http).fetch_order_book("BTCUSDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]


async def test_mexc_futures_order_book_flat_shape():
    """Некоторые ответы contract/depth приходят без обёртки data."""
    url = MexcFuturesAdapter.DEPTH_URL_TEMPLATE.format(symbol="LA_USDT")
    http = FakeHttpClient({
        url: {"bids": [[100.0, 5]], "asks": [[101.0, 5]], "version": 1, "timestamp": 123},
    })

    book = await MexcFuturesAdapter(http).fetch_order_book("LA_USDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]


async def test_mexc_futures_order_book_wrapped_shape():
    """А некоторые — обёрнуты в {"data": {...}}, как у большинства других эндпоинтов MEXC."""
    url = MexcFuturesAdapter.DEPTH_URL_TEMPLATE.format(symbol="LA_USDT")
    http = FakeHttpClient({
        url: {"success": True, "code": 0, "data": {
            "bids": [[100.0, 5]], "asks": [[101.0, 5]],
        }},
    })

    book = await MexcFuturesAdapter(http).fetch_order_book("LA_USDT", limit=50)

    assert book["bids"] == [(100.0, 5.0)]
    assert book["asks"] == [(101.0, 5.0)]
