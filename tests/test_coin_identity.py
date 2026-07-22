from app.services.coin_identity import CoinIdentityChecker, _RateLimiter
from tests.conftest import FakeHttpClient


COINS_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
EXCHANGES_LIST_URL = "https://api.coingecko.com/api/v3/exchanges/list"


def exchange_tickers_url(exchange_id):
    return f"https://api.coingecko.com/api/v3/exchanges/{exchange_id}/tickers"


class FakeHttpClientWithParams(FakeHttpClient):
    """
    CoinIdentityChecker вызывает один и тот же URL с разными query-параметрами
    (coin_ids=...) для разных бирж — обычный FakeHttpClient матчит только по URL,
    без учёта params. Этот вариант хранит ответы по (url, params) вместе.
    """

    def __init__(self, responses_by_url_and_params):
        super().__init__({})
        self.responses_by_url_and_params = responses_by_url_and_params

    async def get_json(self, url, params=None, headers=None):
        self.calls.append((url, params))
        key = (url, tuple(sorted((params or {}).items())))
        if key not in self.responses_by_url_and_params:
            raise KeyError(f"Нет фейкового ответа для {key}")
        return self.responses_by_url_and_params[key]


def build_http(coins_list, exchanges_list, tickers_by_exchange_and_coin):
    """
    tickers_by_exchange_and_coin: {(exchange_id, coin_id): bool_has_tickers}
    """
    responses = {
        (COINS_LIST_URL, ()): coins_list,
        (EXCHANGES_LIST_URL, ()): exchanges_list,
    }
    for (exchange_id, coin_id), has_tickers in tickers_by_exchange_and_coin.items():
        url = exchange_tickers_url(exchange_id)
        params = (("coin_ids", coin_id),)
        responses[(url, params)] = {"tickers": [{"base": "X"}] if has_tickers else []}
    return FakeHttpClientWithParams(responses)


async def test_confirms_same_asset_across_exchanges():
    coins_list = [{"id": "la-token", "symbol": "la", "name": "LA Token"}]
    exchanges_list = [
        {"id": "binance", "name": "Binance"},
        {"id": "mexc_global", "name": "MEXC Global"},
    ]
    http = build_http(coins_list, exchanges_list, {
        ("binance", "la-token"): True,
        ("mexc_global", "la-token"): True,
    })

    checker = CoinIdentityChecker(api_key="fake-key", http=http)
    result = await checker.verify("LA", {"binance", "mexc"})

    assert result is True


async def test_returns_false_when_no_candidate_matches_all_exchanges():
    coins_list = [
        {"id": "on-project-a", "symbol": "on", "name": "On Project A"},
        {"id": "on-project-b", "symbol": "on", "name": "On Project B"},
    ]
    exchanges_list = [
        {"id": "binance", "name": "Binance"},
        {"id": "bybit_spot", "name": "Bybit"},
    ]
    # ни один кандидат не торгуется одновременно на обеих биржах
    http = build_http(coins_list, exchanges_list, {
        ("binance", "on-project-a"): True,
        ("bybit_spot", "on-project-a"): False,
        ("binance", "on-project-b"): False,
        ("bybit_spot", "on-project-b"): True,
    })

    checker = CoinIdentityChecker(api_key="fake-key", http=http)
    result = await checker.verify("ON", {"binance", "bybit"})

    assert result is False


async def test_returns_none_when_symbol_unknown_to_coingecko():
    coins_list = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"}]
    exchanges_list = [{"id": "binance", "name": "Binance"}]
    http = build_http(coins_list, exchanges_list, {})

    checker = CoinIdentityChecker(api_key="fake-key", http=http)
    result = await checker.verify("NOT_A_REAL_SYMBOL", {"binance"})

    assert result is None


async def test_returns_none_when_exchange_not_found_in_coingecko():
    coins_list = [{"id": "la-token", "symbol": "la", "name": "LA Token"}]
    exchanges_list = [{"id": "binance", "name": "Binance"}]  # bybit отсутствует
    http = build_http(coins_list, exchanges_list, {})

    checker = CoinIdentityChecker(api_key="fake-key", http=http)
    result = await checker.verify("LA", {"binance", "bybit"})

    assert result is None


async def test_verdict_is_cached_for_same_coin_and_exchanges():
    coins_list = [{"id": "la-token", "symbol": "la", "name": "LA Token"}]
    exchanges_list = [
        {"id": "binance", "name": "Binance"},
        {"id": "mexc_global", "name": "MEXC Global"},
    ]
    http = build_http(coins_list, exchanges_list, {
        ("binance", "la-token"): True,
        ("mexc_global", "la-token"): True,
    })

    checker = CoinIdentityChecker(api_key="fake-key", http=http)
    first = await checker.verify("LA", {"binance", "mexc"})
    calls_after_first = len(http.calls)
    second = await checker.verify("LA", {"binance", "mexc"})

    assert first is True
    assert second is True
    assert len(http.calls) == calls_after_first  # второй вызов взят из кэша, без новых запросов


async def test_missing_registries_return_none_gracefully():
    class BrokenHttp:
        async def get_json(self, url, params=None, headers=None):
            raise RuntimeError("сеть недоступна")

    checker = CoinIdentityChecker(api_key="fake-key", http=BrokenHttp())
    result = await checker.verify("LA", {"binance", "mexc"})

    assert result is None


class TestRateLimiter:

    async def test_allows_calls_up_to_limit_without_delay(self):
        import time

        limiter = _RateLimiter(limit_per_minute=3, window_seconds=10)
        start = time.monotonic()

        for _ in range(3):
            await limiter.acquire()

        assert time.monotonic() - start < 0.5  # первые 3 вызова — без ожидания

    async def test_blocks_once_limit_is_reached_within_window(self):
        import time

        limiter = _RateLimiter(limit_per_minute=2, window_seconds=0.3)
        start = time.monotonic()

        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()  # третий вызов должен подождать, пока окно не освободится

        elapsed = time.monotonic() - start
        assert elapsed >= 0.25  # с запасом ниже полного окна, но заметно больше нуля

    async def test_identity_checker_respects_rate_limit(self):
        """
        Регрессионный тест: раньше CoinIdentityChecker вообще не троттлился,
        из-за чего полный скан рынка мгновенно упирался в 429 Too Many Requests
        от CoinGecko. Проверяем, что запросы реально проходят через лимитер.
        """
        coins_list = [{"id": "la-token", "symbol": "la", "name": "LA Token"}]
        exchanges_list = [
            {"id": "binance", "name": "Binance"},
            {"id": "mexc_global", "name": "MEXC Global"},
        ]
        http = build_http(coins_list, exchanges_list, {
            ("binance", "la-token"): True,
            ("mexc_global", "la-token"): True,
        })

        checker = CoinIdentityChecker(api_key="fake-key", http=http, rate_limit_per_minute=1000)
        assert checker._rate_limiter.limit == 1000

        result = await checker.verify("LA", {"binance", "mexc"})
        assert result is True
