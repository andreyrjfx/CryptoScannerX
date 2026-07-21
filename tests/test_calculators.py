import pytest

from app.calculators.fee_calculator import FeeCalculator
from app.calculators.profit_calculator import ProfitCalculator
from app.calculators.trade_calculator import TradeCalculator
from app.config import POSITION_SIZE_USDT


class TestFeeCalculator:

    def test_calculate_sums_both_legs(self):
        fees = FeeCalculator()

        buy_fee, sell_fee, total = fees.calculate(
            buy_exchange="binance", buy_market="spot",
            sell_exchange="bybit", sell_market="future",
        )

        assert buy_fee == FeeCalculator.FEES["binance"]["spot"]
        assert sell_fee == FeeCalculator.FEES["bybit"]["future"]
        assert total == pytest.approx(buy_fee + sell_fee)

    def test_unknown_exchange_raises(self):
        fees = FeeCalculator()

        with pytest.raises(KeyError):
            fees.calculate(
                buy_exchange="unknown", buy_market="spot",
                sell_exchange="bybit", sell_market="spot",
            )


class TestProfitCalculator:

    def test_net_spread_subtracts_fee_adds_funding(self):
        profit = ProfitCalculator()

        net_spread, expected_profit = profit.calculate(
            spread=1.0, fee_percent=0.2, funding_percent=0.05,
        )

        assert net_spread == pytest.approx(0.85)
        assert expected_profit == pytest.approx(POSITION_SIZE_USDT * 0.85 / 100)

    def test_funding_defaults_to_zero(self):
        profit = ProfitCalculator()
        net_spread, _ = profit.calculate(spread=1.0, fee_percent=0.3)
        assert net_spread == pytest.approx(0.7)


class TestTradeCalculator:

    def test_calculate_returns_all_expected_keys(self):
        trade = TradeCalculator()

        result = trade.calculate(
            spread=1.0,
            buy_exchange="binance", buy_market="spot",
            sell_exchange="bybit", sell_market="future",
        )

        assert set(result.keys()) == {
            "fee_percent", "funding_percent", "net_spread", "expected_profit_usdt",
        }
        assert result["fee_percent"] == pytest.approx(0.10 + 0.055)
        assert result["net_spread"] == pytest.approx(1.0 - (0.10 + 0.055))
