from itertools import combinations

from app.config import MIN_SPREAD, DISPLAY_SPREAD, MIN_VOLUME_USDT
from app.models.opportunity import Opportunity
from app.calculators.trade_calculator import TradeCalculator


class ArbitrageScanner:

    def __init__(self, tickers, coins=None):
        self.tickers = tickers
        self.trade = TradeCalculator()
        self.coins = {coin.upper() for coin in coins} if coins else None

    def scan(self):
        grouped = {}

        for ticker in self.tickers:
            if ticker.volume_usdt < MIN_VOLUME_USDT:
                continue

            if self.coins is not None and ticker.coin.upper() not in self.coins:
                continue

            grouped.setdefault(ticker.coin, []).append(ticker)

        opportunities = []

        for coin_tickers in grouped.values():
            if len(coin_tickers) < 2:
                continue

            for first, second in combinations(coin_tickers, 2):
                self._check(opportunities, first, second)
                self._check(opportunities, second, first)

        opportunities.sort(
            key=lambda x: (x.net_spread, min(x.buy_volume, x.sell_volume)),
            reverse=True,
        )

        return opportunities

    def _get_trade_type(self, buy, sell):
        if buy.market == "spot" and sell.market == "spot":
            return "spot-spot"

        if buy.market == "future" and sell.market == "future":
            return "future-future"

        if buy.exchange == sell.exchange and buy.market != sell.market:
            return "basis"

        if buy.market == "spot" and sell.market == "future":
            return "spot-future"

        return "future-spot"

    def _check(self, opportunities, buy, sell):
        if buy.exchange == sell.exchange and buy.market == sell.market:
            return

        if buy.ask <= 0 or sell.bid <= 0:
            return

        spread = (sell.bid - buy.ask) / buy.ask * 100

        if spread < MIN_SPREAD:
            return

        # Пока фильтруем по сырому спреду. Позже перейдем на net_spread.
        if spread < DISPLAY_SPREAD:
            return

        trade = self.trade.calculate(
            spread=spread,
            buy_exchange=buy.exchange,
            buy_market=buy.market,
            sell_exchange=sell.exchange,
            sell_market=sell.market,
        )

        opportunities.append(Opportunity(
            coin=buy.coin,
            buy_exchange=buy.exchange,
            buy_market=buy.market,
            buy_price=buy.ask,
            buy_volume=buy.volume_usdt,
            sell_exchange=sell.exchange,
            sell_market=sell.market,
            sell_price=sell.bid,
            sell_volume=sell.volume_usdt,
            trade_type=self._get_trade_type(buy, sell),
            spread=spread,
            fee_percent=trade["fee_percent"],
            funding_percent=trade["funding_percent"],
            net_spread=trade["net_spread"],
            expected_profit_usdt=trade["expected_profit_usdt"],
        ))
