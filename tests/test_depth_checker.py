from app.services.depth_checker import SlippageCalculator, DepthChecker
from app.models.opportunity import Opportunity
from tests.conftest import FakeHttpClient


class FakeHttpClientWithLifecycle(FakeHttpClient):
    """DepthChecker сам вызывает connect()/close() у HttpClient — фейку нужны эти методы."""

    async def connect(self):
        pass

    async def close(self):
        pass


def make_opportunity(**overrides):
    base = dict(
        coin="BTC",
        buy_exchange="binance", buy_market="spot", buy_symbol="BTCUSDT",
        buy_price=100.0, buy_volume=1_000_000.0,
        sell_exchange="bybit", sell_market="future", sell_symbol="BTCUSDT",
        sell_price=101.0, sell_volume=1_000_000.0,
        trade_type="spot-future",
        spread=1.0,
        fee_percent=0.1, funding_percent=0.0,
        net_spread=0.9, expected_profit_usdt=9.0,
    )
    base.update(overrides)
    return Opportunity(**base)


class TestSlippageCalculator:

    def test_fills_entirely_from_single_level(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        # 10 BTC доступно по 100 -> $1000 легко покрывается первым уровнем
        avg_price, filled = calc.effective_buy_price([(100.0, 10.0)])

        assert avg_price == 100.0
        assert filled == 1.0

    def test_walks_multiple_levels_and_averages(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        # уровень 1: $500 по 100, уровень 2: остаток $500 по 110
        asks = [(100.0, 5.0), (110.0, 10.0)]
        avg_price, filled = calc.effective_buy_price(asks)

        # 5 BTC по 100 = $500, ещё 500/110 = 4.5454 BTC по 110
        expected_qty = 5.0 + 500 / 110
        expected_avg = (5.0 * 100 + (500 / 110) * 110) / expected_qty
        assert abs(avg_price - expected_avg) < 1e-6
        assert filled == 1.0

    def test_insufficient_depth_returns_partial_fill(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        # всего $200 глубины в стакане -> не хватает на позицию $1000
        avg_price, filled = calc.effective_buy_price([(100.0, 2.0)])

        assert avg_price == 100.0
        assert abs(filled - 0.2) < 1e-9

    def test_empty_book_returns_none(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        avg_price, filled = calc.effective_buy_price([])

        assert avg_price is None
        assert filled == 0.0

    def test_sell_side_walks_bids_highest_first(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        # bids намеренно не отсортированы -> должны сами отсортировать по убыванию
        bids = [(95.0, 20.0), (99.0, 5.0), (97.0, 10.0)]
        avg_price, filled = calc.effective_sell_price(bids)

        # лучший бид 99 покрывает 5*99=495, остаток 505 идёт по 97
        expected_qty = 5.0 + 505 / 97
        expected_avg = (5.0 * 99 + (505 / 97) * 97) / expected_qty
        assert abs(avg_price - expected_avg) < 1e-6
        assert filled == 1.0

    def test_ignores_invalid_levels(self):
        calc = SlippageCalculator(position_size_usdt=1000)
        avg_price, filled = calc.effective_buy_price([(0.0, 10.0), (-5.0, 3.0), (100.0, 20.0)])

        assert avg_price == 100.0
        assert filled == 1.0


class TestDepthChecker:

    async def test_enriches_opportunity_with_real_spread(self):
        opp = make_opportunity(
            buy_exchange="binance", buy_market="spot", buy_symbol="BTCUSDT",
            sell_exchange="bybit", sell_market="future", sell_symbol="BTCUSDT",
            spread=1.0, fee_percent=0.1, funding_percent=0.0,
        )

        checker = DepthChecker(position_size_usdt=1000)

        binance_depth_url = checker.ADAPTER_CLASSES[("binance", "spot")].DEPTH_URL
        bybit_orderbook_url = checker.ADAPTER_CLASSES[("bybit", "future")].ORDERBOOK_URL

        http = FakeHttpClientWithLifecycle({
            binance_depth_url: {"bids": [["99.9", "50"]], "asks": [["100.0", "50"]]},
            bybit_orderbook_url: {"result": {"b": [["100.9", "50"]], "a": [["101.0", "50"]]}},
        })

        # подменяем HttpClient внутри check() руками, не поднимая настоящую сеть
        import app.services.depth_checker as depth_checker_module
        original_http_client = depth_checker_module.HttpClient
        depth_checker_module.HttpClient = lambda: http
        try:
            await checker.check([opp])
        finally:
            depth_checker_module.HttpClient = original_http_client

        assert opp.effective_spread is not None
        # buy по ask=100.0, sell по bid=100.9 -> эффективный спред 0.9%
        assert abs(opp.effective_spread - 0.9) < 1e-6
        assert opp.real_net_spread is not None
        assert opp.depth_filled == 1.0

    async def test_missing_adapter_leaves_opportunity_unchanged(self):
        opp = make_opportunity(buy_exchange="unknown_exchange", buy_market="spot")

        checker = DepthChecker(position_size_usdt=1000)
        await checker.check([opp])

        assert opp.effective_spread is None
        assert opp.real_net_spread is None

    async def test_empty_opportunity_list_is_a_noop(self):
        checker = DepthChecker(position_size_usdt=1000)
        result = await checker.check([])
        assert result == []
