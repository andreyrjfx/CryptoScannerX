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

    # True/False/None — заполняется CoinIdentityChecker'ом (None = не проверялось)
    identity_verified: bool = None
