from itertools import combinations
import logging

from app.config import MIN_SPREAD, DISPLAY_SPREAD, MIN_VOLUME_USDT, MAX_SANE_SPREAD, ALLOW_SHORT_SPOT
from app.models.opportunity import Opportunity
from app.calculators.trade_calculator import TradeCalculator

logger = logging.getLogger(__name__)


class ArbitrageScanner:
    """
    Ищет спред между парами тикеров (buy - открываем длинную позицию,
    sell - закрываем/шортим). По умолчанию (ALLOW_SHORT_SPOT=False)
    исключаются сделки, где sell.market == "spot" — это означало бы шорт
    спота (продажу актива, которого нет), что обычным способом на биржах
    недоступно. Поэтому "spot-spot" и "future-spot" по умолчанию не
    встречаются в выдаче — остаются только сделки, где шортится фьючерс
    (spot-future, future-future, часть basis).
    """

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

        if not ALLOW_SHORT_SPOT and sell.market == "spot":
            # "Продажная" нога — спот, то есть нужно шортить актив, которого
            # нет. Обычным способом на большинстве бирж это невозможно, а
            # маржинальный шорт (с процентами по займу) мы не считаем.
            return

        if buy.ask <= 0 or sell.bid <= 0:
            return

        spread = (sell.bid - buy.ask) / buy.ask * 100

        if spread < MIN_SPREAD:
            return

        # Пока фильтруем по сырому спреду. Позже перейдем на net_spread.
        if spread < DISPLAY_SPREAD:
            return

        if spread > MAX_SANE_SPREAD:
            # Скорее всего разные активы под одинаковым тикером на разных
            # биржах либо битые данные — а не реальная возможность.
            logger.warning(
                "%s: спред %.2f%% (%s %s -> %s %s) выглядит нереалистично — "
                "пропущено (проверь вручную, что это один и тот же актив)",
                buy.coin, spread, buy.exchange, buy.market, sell.exchange, sell.market,
            )
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
            buy_symbol=buy.symbol,
            buy_price=buy.ask,
            buy_volume=buy.volume_usdt,
            sell_exchange=sell.exchange,
            sell_market=sell.market,
            sell_symbol=sell.symbol,
            sell_price=sell.bid,
            sell_volume=sell.volume_usdt,
            trade_type=self._get_trade_type(buy, sell),
            spread=spread,
            fee_percent=trade["fee_percent"],
            funding_percent=trade["funding_percent"],
            net_spread=trade["net_spread"],
            expected_profit_usdt=trade["expected_profit_usdt"],
        ))
