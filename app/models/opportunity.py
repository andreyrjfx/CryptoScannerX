from dataclasses import dataclass


@dataclass(slots=True)
class Opportunity:
    """Возможность арбитражной сделки."""

    coin: str

    # Покупка
    buy_exchange: str
    buy_market: str
    buy_price: float
    buy_volume: float

    # Продажа
    sell_exchange: str
    sell_market: str
    sell_price: float
    sell_volume: float

    trade_type: str

    spread: float  # сырой спред (%)

    fee_percent: float = 0.0
    funding_percent: float = 0.0
    net_spread: float = 0.0
    expected_profit_usdt: float = 0.0
