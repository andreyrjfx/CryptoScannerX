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

    # Время следующего начисления на каждой стороне, unix ms (расписания
    # начисления у разных бирж могут не совпадать)
    short_next_funding_time: int = None
    long_next_funding_time: int = None

    # True/False/None — заполняется CoinIdentityChecker'ом (None = не проверялось)
    identity_verified: bool = None
