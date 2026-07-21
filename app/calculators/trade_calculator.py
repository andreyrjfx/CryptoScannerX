from app.calculators.fee_calculator import FeeCalculator
from app.calculators.profit_calculator import ProfitCalculator


class TradeCalculator:

    def __init__(self):
        self.fees = FeeCalculator()
        self.profit = ProfitCalculator()

    def calculate(self, spread, buy_exchange, buy_market, sell_exchange, sell_market):
        buy_fee, sell_fee, total_fee = self.fees.calculate(
            buy_exchange=buy_exchange,
            buy_market=buy_market,
            sell_exchange=sell_exchange,
            sell_market=sell_market,
        )

        net_spread, expected_profit = self.profit.calculate(
            spread=spread,
            fee_percent=total_fee,
        )

        return {
            "fee_percent": total_fee,
            "funding_percent": 0.0,
            "net_spread": net_spread,
            "expected_profit_usdt": expected_profit,
        }
