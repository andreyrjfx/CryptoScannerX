from app.config import POSITION_SIZE_USDT


class ProfitCalculator:

    def calculate(self, spread, fee_percent, funding_percent=0.0):
        net_spread = spread - fee_percent + funding_percent
        expected_profit = POSITION_SIZE_USDT * net_spread / 100
        return net_spread, expected_profit
