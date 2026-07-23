from itertools import combinations

from app.config import MIN_VOLUME_USDT, MIN_FUNDING_SPREAD
from app.models.funding_opportunity import FundingOpportunity
from app.calculators.fee_calculator import FeeCalculator


class FundingScanner:
    """
    Ищет funding rate арбитраж: шорт фьючерса на бирже с более высоким
    funding rate + лонг того же коина на бирже с более низким (или
    отрицательным) funding rate. Цена при этом не имеет значения —
    позиция рыночно-нейтральна, прибыль — разница funding-выплат.
    """

    def __init__(self, tickers, min_spread=MIN_FUNDING_SPREAD):
        self.tickers = [t for t in tickers if t.market == "future"]
        self.min_spread = min_spread
        self.fees = FeeCalculator()

    def scan(self):
        grouped = {}

        for ticker in self.tickers:
            if ticker.volume_usdt < MIN_VOLUME_USDT:
                continue

            grouped.setdefault(ticker.coin, []).append(ticker)

        opportunities = []

        for group in grouped.values():
            if len(group) < 2:
                continue

            for first, second in combinations(group, 2):
                self._check(opportunities, short_side=first, long_side=second)
                self._check(opportunities, short_side=second, long_side=first)

        opportunities.sort(key=lambda o: o.funding_spread, reverse=True)

        return opportunities

    def _check(self, opportunities, short_side, long_side):
        if short_side.exchange == long_side.exchange:
            return

        spread = short_side.funding_rate - long_side.funding_rate

        if spread < self.min_spread:
            return

        # Разовая комиссия на открытие обеих ног (шорт+лонг) — funding_spread
        # начисляется каждый период, а комиссия платится один раз при входе.
        _, _, fee_percent = self.fees.calculate(
            buy_exchange=long_side.exchange, buy_market="future",
            sell_exchange=short_side.exchange, sell_market="future",
        )
        breakeven_periods = fee_percent / spread if spread > 0 else None

        opportunities.append(FundingOpportunity(
            coin=short_side.coin,
            short_exchange=short_side.exchange,
            short_funding_rate=short_side.funding_rate,
            short_volume=short_side.volume_usdt,
            long_exchange=long_side.exchange,
            long_funding_rate=long_side.funding_rate,
            long_volume=long_side.volume_usdt,
            funding_spread=spread,
            fee_percent=fee_percent,
            breakeven_periods=breakeven_periods,
            short_next_funding_time=short_side.next_funding_time,
            long_next_funding_time=long_side.next_funding_time,
        ))
