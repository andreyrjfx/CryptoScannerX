from dataclasses import dataclass


@dataclass(slots=True)
class Ticker:
    """Унифицированный тикер."""

    exchange: str
    market: str  # spot / future
    coin: str
    symbol: str
    bid: float
    ask: float
    last: float
    volume_usdt: float

    # Funding rate за один период (%), только для futures.
    funding_rate: float = 0.0

    # Время следующего начисления funding, unix ms. Только для futures.
    next_funding_time: int = None
