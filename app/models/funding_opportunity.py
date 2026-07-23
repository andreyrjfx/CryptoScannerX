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

    # Время следующего начисления на каждой стороне, unix ms (расписания
    # начисления у разных бирж могут не совпадать)
    short_next_funding_time: int = None
    long_next_funding_time: int = None

    # True/False/None — заполняется CoinIdentityChecker'ом (None = не проверялось)
    identity_verified: bool = None
