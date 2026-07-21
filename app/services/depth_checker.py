import asyncio
import logging

from app.config import POSITION_SIZE_USDT, DEPTH_LIMIT
from app.clients.http import HttpClient
from app.calculators.profit_calculator import ProfitCalculator

from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.exchanges.binance_spot import BinanceSpotAdapter
from app.exchanges.bybit_futures import BybitFuturesAdapter
from app.exchanges.bybit_spot import BybitSpotAdapter
from app.exchanges.mexc_futures import MexcFuturesAdapter
from app.exchanges.mexc_spot import MexcSpotAdapter

logger = logging.getLogger(__name__)


class SlippageCalculator:
    """
    Считает средневзвешенную (VWAP) цену исполнения фиксированного объёма
    в USDT, "проходя" по уровням стакана — вместо наивного предположения,
    что вся позиция исполнится по top-of-book цене.
    """

    def __init__(self, position_size_usdt=POSITION_SIZE_USDT):
        self.position_size_usdt = position_size_usdt

    def effective_buy_price(self, asks):
        """Покупка — идём от самого дешёвого ask вверх."""
        return self._walk(sorted(asks, key=lambda level: level[0]))

    def effective_sell_price(self, bids):
        """Продажа — идём от самого дорогого bid вниз."""
        return self._walk(sorted(bids, key=lambda level: level[0], reverse=True))

    def _walk(self, levels):
        """
        Возвращает (средняя_цена, доля_исполненного_объёма).
        Если стакан пуст/не удалось получить данных — (None, 0.0).
        """
        remaining = self.position_size_usdt
        total_qty = 0.0
        total_cost = 0.0

        for price, qty in levels:
            if price <= 0 or qty <= 0:
                continue

            level_usdt = price * qty
            take_usdt = min(remaining, level_usdt)
            take_qty = take_usdt / price

            total_qty += take_qty
            total_cost += take_qty * price
            remaining -= take_usdt

            if remaining <= 1e-9:
                break

        if total_qty <= 0:
            return None, 0.0

        avg_price = total_cost / total_qty
        filled_fraction = 1 - remaining / self.position_size_usdt
        return avg_price, filled_fraction


class DepthChecker:
    """
    Пересчитывает найденные ArbitrageScanner возможности с учётом реальной
    глубины стакана — вместо top-of-book bid/ask берёт VWAP-цену исполнения
    на POSITION_SIZE_USDT.

    У order book нет bulk-эндпоинта (только один символ за запрос), поэтому
    проверяются только уже найденные кандидаты — не весь рынок.
    """

    ADAPTER_CLASSES = {
        ("binance", "future"): BinanceFuturesAdapter,
        ("binance", "spot"): BinanceSpotAdapter,
        ("bybit", "future"): BybitFuturesAdapter,
        ("bybit", "spot"): BybitSpotAdapter,
        ("mexc", "future"): MexcFuturesAdapter,
        ("mexc", "spot"): MexcSpotAdapter,
    }

    def __init__(self, position_size_usdt=POSITION_SIZE_USDT, depth_limit=DEPTH_LIMIT):
        self.slippage = SlippageCalculator(position_size_usdt)
        self.profit = ProfitCalculator()
        self.depth_limit = depth_limit

    async def check(self, opportunities):
        if not opportunities:
            return opportunities

        http = HttpClient()
        await http.connect()

        adapters = {key: cls(http) for key, cls in self.ADAPTER_CLASSES.items()}

        try:
            await asyncio.gather(*(
                self._check_one(opp, adapters) for opp in opportunities
            ))
        finally:
            await http.close()

        return opportunities

    async def _check_one(self, opp, adapters):
        buy_adapter = adapters.get((opp.buy_exchange, opp.buy_market))
        sell_adapter = adapters.get((opp.sell_exchange, opp.sell_market))

        if buy_adapter is None or sell_adapter is None:
            return

        try:
            buy_book, sell_book = await asyncio.gather(
                buy_adapter.fetch_order_book(opp.buy_symbol, self.depth_limit),
                sell_adapter.fetch_order_book(opp.sell_symbol, self.depth_limit),
            )
        except Exception as exc:
            logger.debug("%s: не удалось получить стакан (%s)", opp.coin, exc)
            return

        buy_price, buy_fill = self.slippage.effective_buy_price(buy_book["asks"])
        sell_price, sell_fill = self.slippage.effective_sell_price(sell_book["bids"])

        if buy_price is None or sell_price is None:
            return

        opp.effective_spread = (sell_price - buy_price) / buy_price * 100
        opp.slippage_pct = opp.spread - opp.effective_spread
        opp.depth_filled = min(buy_fill, sell_fill)

        opp.real_net_spread, opp.real_expected_profit_usdt = self.profit.calculate(
            spread=opp.effective_spread,
            fee_percent=opp.fee_percent,
            funding_percent=opp.funding_percent,
        )
