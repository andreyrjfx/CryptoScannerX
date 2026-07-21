class FeeCalculator:

    FEES = {
        "binance": {"spot": 0.10, "future": 0.05},
        "bybit": {"spot": 0.10, "future": 0.055},
        "mexc": {"spot": 0.20, "future": 0.02},
    }

    def calculate(self, buy_exchange, buy_market, sell_exchange, sell_market):
        buy_fee = self.FEES[buy_exchange][buy_market]
        sell_fee = self.FEES[sell_exchange][sell_market]
        return buy_fee, sell_fee, buy_fee + sell_fee
