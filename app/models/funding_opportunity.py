from dataclasses import dataclass


@dataclass(slots=True)
class FundingOpportunity:
    """
    Возможность funding rate арбитража: шорт фьючерса на одной бирже +
    лонг того же фьючерса на другой — рыночно-нейтрально по цене,
    прибыль — разница funding rate между биржами за период.
    """

    coin: str

    short_exchange: str
    short_funding_rate: float
    short_volume: float

    long_exchange: str
    long_funding_rate: float
    long_volume: float

    # short_funding_rate - long_funding_rate (%), за один период
    funding_spread: float

    # Разовая комиссия на открытие обеих позиций (шорт+лонг), % от объёма.
    # Не путать с funding_spread — это разовая плата за вход, а не за период.
    fee_percent: float = 0.0

    # Сколько периодов начисления нужно продержать позицию, чтобы funding
    # окупил комиссию на вход (fee_percent / funding_spread). None, если
    # funding_spread <= 0 (не должно происходить — уже отфильтровано выше).
    breakeven_periods: float = None

    # Те же fee_percent/funding_spread в USDT при позиции POSITION_SIZE_USDT.
    # profit_per_period_usdt — повторяется каждый период (пока funding
    # rate не меняется); fee_usdt — платится один раз при входе.
    profit_per_period_usdt: float = 0.0
    fee_usdt: float = 0.0

    # funding_spread - fee_percent (%) / profit_per_period_usdt - fee_usdt ($):
    # чистый результат, если продержать позицию всего один период. Может быть
    # отрицательным (комиссия больше, чем спред за один период) — тогда
    # breakeven_periods > 1 и нужно держать дольше, чтобы выйти в плюс.
    net_first_period_percent: float = 0.0
    net_first_period_usdt: float = 0.0

    # Время следующего начисления на каждой стороне, unix ms (расписания
    # начисления у разных бирж могут не совпадать)
    short_next_funding_time: int = None
    long_next_funding_time: int = None

    # True/False/None — заполняется CoinIdentityChecker'ом (None = не проверялось)
    identity_verified: bool = None
