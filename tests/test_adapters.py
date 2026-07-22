from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.exchanges.binance_spot import BinanceSpotAdapter
from app.exchanges.bybit_futures import BybitFuturesAdapter
from app.exchanges.bybit_spot import BybitSpotAdapter
from app.exchanges.mexc_futures import MexcFuturesAdapter
from app.exchanges.mexc_spot import MexcSpotAdapter
from app.services.funding_enricher import MexcFundingEnricher

from tests.conftest import FakeHttpClient, make_ticker


async def test_binance_futures_merges_book_stats_and_funding():
    http = FakeHttpClient({
        BinanceFuturesAdapter.BOOK_TICKER_URL: [
            {"symbol": "BTCUSDT", "bidPrice": "50000", "askPrice": "50010"},
            {"symbol": "ETHBUSD", "bidPrice": "1", "askPrice": "1"},  # не USDT -> должен быть отфильтрован
        ],
        BinanceFuturesAdapter.STATS_24H_URL: [
            {"symbol": "BTCUSDT", "quoteVolume": "1000000"},
        ],
        BinanceFuturesAdapter.PREMIUM_INDEX_URL: [
            {"symbol": "BTCUSDT", "lastFundingRate": "0.0001"},
        ],
    })

    tickers = await BinanceFuturesAdapter(http).fetch_tickers()

    assert len(tickers) == 1
    ticker = tickers[0]
    assert ticker.coin == "BTC"
    assert ticker.exchange == "binance"
    assert ticker.market == "future"
    assert ticker.bid == 50000.0
    assert ticker.ask == 50010.0
    assert ticker.volume_usdt == 1_000_000.0
    assert ticker.funding_rate == 0.01


async def test_binance_futures_survives_funding_endpoint_failure():
    http = FakeHttpClient({
        BinanceFuturesAdapter.BOOK_TICKER_URL: [
            {"symbol": "BTCUSDT", "bidPrice": "50000", "askPrice": "50010"},
        ],
        BinanceFuturesAdapter.STATS_24H_URL: [
            {"symbol": "BTCUSDT", "quoteVolume": "1000000"},
        ],
        # PREMIUM_INDEX_URL намеренно отсутствует -> FakeHttpClient бросит KeyError
    })

    tickers = await BinanceFuturesAdapter(http).fetch_tickers()

    assert len(tickers) == 1
    assert tickers[0].funding_rate == 0.0  # деградация без падения


async def test_binance_spot_alias_normalization():
    http = FakeHttpClient({
        BinanceSpotAdapter.BOOK_TICKER_URL: [
            {"symbol": "XBTUSDT", "bidPrice": "50000", "askPrice": "50010"},
        ],
        BinanceSpotAdapter.STATS_24H_URL: [
            {"symbol": "XBTUSDT", "quoteVolume": "1000000"},
        ],
    })

    tickers = await BinanceSpotAdapter(http).fetch_tickers()

    assert tickers[0].coin == "BTC"  # XBT -> BTC alias


async def test_bybit_futures_extracts_funding_rate():
    http = FakeHttpClient({
        BybitFuturesAdapter.URL: {"result": {"list": [
            {
                "symbol": "ETHUSDT", "bid1Price": "3000", "ask1Price": "3001",
                "lastPrice": "3000.5", "turnover24h": "2000000", "fundingRate": "-0.005",
            },
        ]}},
    })

    tickers = await BybitFuturesAdapter(http).fetch_tickers()

    assert len(tickers) == 1
    assert tickers[0].funding_rate == -0.5


async def test_bybit_spot_has_no_funding_rate():
    http = FakeHttpClient({
        BybitSpotAdapter.URL: {"result": {"list": [
            {
                "symbol": "ETHUSDT", "bid1Price": "3000", "ask1Price": "3001",
                "lastPrice": "3000.5", "turnover24h": "2000000",
            },
        ]}},
    })

    tickers = await BybitSpotAdapter(http).fetch_tickers()

    assert tickers[0].funding_rate == 0.0


async def test_mexc_futures_uses_underscore_suffix():
    http = FakeHttpClient({
        MexcFuturesAdapter.URL: {"data": [
            {"symbol": "SOL_USDT", "bid1": "150", "ask1": "150.5", "lastPrice": "150.2", "amount24": "500000"},
            {"symbol": "BADSYMBOL", "bid1": "1", "ask1": "1"},  # не *_USDT -> отфильтрован
        ]},
    })

    tickers = await MexcFuturesAdapter(http).fetch_tickers()

    assert len(tickers) == 1
    assert tickers[0].coin == "SOL"
    assert tickers[0].funding_rate == 0.0  # бирже нужен отдельный enrich-запрос


async def test_mexc_spot_book_and_stats():
    http = FakeHttpClient({
        MexcSpotAdapter.BOOK_TICKER_URL: [
            {"symbol": "SOLUSDT", "bidPrice": "150", "askPrice": "150.5"},
        ],
        MexcSpotAdapter.STATS_24H_URL: [
            {"symbol": "SOLUSDT", "quoteVolume": "500000"},
        ],
    })

    tickers = await MexcSpotAdapter(http).fetch_tickers()

    assert len(tickers) == 1
    assert tickers[0].coin == "SOL"


async def test_mexc_funding_enricher_only_touches_mexc_futures():
    future_ticker = make_ticker(exchange="mexc", market="future", coin="SOL", symbol="SOL_USDT")
    spot_ticker = make_ticker(exchange="mexc", market="spot", coin="SOL", symbol="SOLUSDT")
    other_exchange_ticker = make_ticker(exchange="binance", market="future", coin="SOL", symbol="SOLUSDT")

    url = MexcFundingEnricher.URL_TEMPLATE.format(symbol="SOL_USDT")
    http = FakeHttpClient({url: {"data": {"fundingRate": 0.00015}}})

    await MexcFundingEnricher(http).enrich([future_ticker, spot_ticker, other_exchange_ticker])

    assert future_ticker.funding_rate == 0.015
    assert spot_ticker.funding_rate == 0.0
    assert other_exchange_ticker.funding_rate == 0.0
    assert len(http.calls) == 1  # только один запрос — для future mexc тикера


async def test_mexc_funding_enricher_processes_multiple_batches_without_gaps():
    """
    Регрессионный тест: раньше все тикеры запрашивались одним asyncio.gather
    без учёта лимита биржи (20 запросов/2с) — при большом количестве тикеров
    без фильтра монет это приводило к массовым ошибкам rate limit. Теперь
    донабор идёт батчами; здесь просто проверяем, что batching не теряет
    и не дублирует тикеры на границах батчей.
    """
    tickers = [
        make_ticker(exchange="mexc", market="future", coin=f"COIN{i}", symbol=f"COIN{i}_USDT")
        for i in range(23)  # больше одного BATCH_SIZE (15), захватывает границу батчей
    ]

    responses = {
        MexcFundingEnricher.URL_TEMPLATE.format(symbol=t.symbol): {"data": {"fundingRate": 0.0001 * i}}
        for i, t in enumerate(tickers)
    }
    http = FakeHttpClient(responses)

    enricher = MexcFundingEnricher(http)
    enricher.BATCH_PAUSE_SECONDS = 0  # не ждать реальные секунды в тесте

    await enricher.enrich(tickers)

    for i, ticker in enumerate(tickers):
        assert abs(ticker.funding_rate - 0.01 * i) < 1e-9
