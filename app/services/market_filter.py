from collections import defaultdict


class MarketFilter:
    """
    Оставляет только тикеры, для которых на бирже
    действительно существует активный рынок нужного типа
    (spot или future) с котировкой в USDT.
    """

    def __init__(self, exchanges):
        # ключ: (exchange_name, market_type) -> set монет
        self.allowed = defaultdict(set)

        for exchange_name, exchange in exchanges.items():
            for market in exchange.markets.values():

                if not market.get("active"):
                    continue

                if market.get("quote") != "USDT":
                    continue

                if market.get("swap"):
                    market_type = "future"
                elif market.get("spot"):
                    market_type = "spot"
                else:
                    continue

                coin = market["base"]
                self.allowed[(exchange_name, market_type)].add(coin)

    def filter(self, tickers):
        return [
            ticker
            for ticker in tickers
            if ticker.coin in self.allowed.get((ticker.exchange, ticker.market), set())
        ]
