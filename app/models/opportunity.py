from dataclasses import dataclass


@dataclass(slots=True)
class Opportunity:
    """Возможность арбитражной сделки."""

    coin: str

    # Покупка
    buy_exchange: str
    buy_market: str
    buy_symbol: str
    buy_price: float
    buy_volume: float

    # Продажа
    sell_exchange: str
    sell_market: str
    sell_symbol: str
    sell_price: float
    sell_volume: float

    trade_type: str

    spread: float  # сырой спред по top-of-book (%)

    fee_percent: float = 0.0
    funding_percent: float = 0.0
    net_spread: float = 0.0
    expected_profit_usdt: float = 0.0

    # Заполняется DepthChecker'ом отдельно — после проверки реальной
    # глубины стакана (VWAP-исполнение на POSITION_SIZE_USDT).
    # None, пока проверка не выполнена (или не удалась).
    effective_spread: float = None
    slippage_pct: float = None
    real_net_spread: float = None
    real_expected_profit_usdt: float = None
    depth_filled: float = None

    # True/False/None — заполняется CoinIdentityChecker'ом (None = не проверялось)
    identity_verified: bool = None
