from app.models.ticker import Ticker


class FakeHttpClient:
    """
    Подменяет HttpClient в тестах: вместо реального запроса
    возвращает заранее заданный ответ по URL.
    """

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def get_json(self, url, params=None):
        self.calls.append((url, params))

        if url not in self.responses:
            raise KeyError(f"Нет фейкового ответа для {url}")

        return self.responses[url]


def make_ticker(
    exchange="binance",
    market="spot",
    coin="BTC",
    symbol="BTCUSDT",
    bid=100.0,
    ask=100.1,
    last=100.0,
    volume_usdt=1_000_000.0,
    funding_rate=0.0,
    next_funding_time=None,
):
    return Ticker(
        exchange=exchange,
        market=market,
        coin=coin,
        symbol=symbol,
        bid=bid,
        ask=ask,
        last=last,
        volume_usdt=volume_usdt,
        funding_rate=funding_rate,
        next_funding_time=next_funding_time,
    )
