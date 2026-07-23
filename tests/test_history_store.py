import os
import tempfile

from app.services.history_store import HistoryStore
from app.models.opportunity import Opportunity
from app.models.funding_opportunity import FundingOpportunity


def make_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # HistoryStore сам создаёт файл и папку при необходимости
    return HistoryStore(db_path=path)


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


def make_funding_opportunity(**overrides):
    base = dict(
        coin="BTC",
        short_exchange="binance", short_funding_rate=0.05, short_volume=1_000_000.0,
        long_exchange="bybit", long_funding_rate=-0.02, long_volume=1_000_000.0,
        funding_spread=0.07,
    )
    base.update(overrides)
    return FundingOpportunity(**base)


def test_creates_db_file_and_schema():
    store = make_store()
    assert store.db_path.exists()
    # recent_* не должны падать на пустой, только что созданной базе
    assert store.recent_arbitrage() == []
    assert store.recent_funding() == []


def test_save_and_read_arbitrage_opportunity():
    store = make_store()
    opp = make_opportunity(identity_verified=True)

    store.save_arbitrage([opp])
    rows = store.recent_arbitrage()

    assert len(rows) == 1
    row = rows[0]
    assert row["coin"] == "BTC"
    assert row["buy_exchange"] == "binance"
    assert row["sell_exchange"] == "bybit"
    assert row["net_spread"] == 0.9
    assert row["identity_verified"] is True


def test_save_and_read_funding_opportunity():
    store = make_store()
    fopp = make_funding_opportunity(identity_verified=False)

    store.save_funding([fopp])
    rows = store.recent_funding()

    assert len(rows) == 1
    row = rows[0]
    assert row["coin"] == "BTC"
    assert row["short_exchange"] == "binance"
    assert row["long_exchange"] == "bybit"
    assert abs(row["funding_spread"] - 0.07) < 1e-9
    assert row["identity_verified"] is False


def test_funding_opportunity_next_funding_time_round_trips():
    store = make_store()
    fopp = make_funding_opportunity(
        short_next_funding_time=1700000000000,
        long_next_funding_time=1700003600000,
    )

    store.save_funding([fopp])
    rows = store.recent_funding()

    assert rows[0]["short_next_funding_time"] == 1700000000000
    assert rows[0]["long_next_funding_time"] == 1700003600000


def test_identity_verified_none_is_preserved_as_none():
    store = make_store()
    opp = make_opportunity(identity_verified=None)

    store.save_arbitrage([opp])
    rows = store.recent_arbitrage()

    assert rows[0]["identity_verified"] is None


def test_empty_list_is_a_noop():
    store = make_store()
    store.save_arbitrage([])
    store.save_funding([])

    assert store.recent_arbitrage() == []
    assert store.recent_funding() == []


def test_recent_respects_limit_and_order():
    store = make_store()
    for i in range(5):
        store.save_arbitrage([make_opportunity(coin=f"COIN{i}")])

    rows = store.recent_arbitrage(limit=3)

    assert len(rows) == 3
    # Самые новые — первыми
    assert rows[0]["coin"] == "COIN4"
    assert rows[1]["coin"] == "COIN3"
    assert rows[2]["coin"] == "COIN2"


def test_multiple_opportunities_in_one_run_share_run_at():
    store = make_store()
    opps = [make_opportunity(coin="BTC"), make_opportunity(coin="ETH")]

    store.save_arbitrage(opps)
    rows = store.recent_arbitrage()

    assert len(rows) == 2
    assert rows[0]["run_at"] == rows[1]["run_at"]


def test_within_same_run_ordered_best_spread_first_regardless_of_insert_order():
    """
    Регрессионный тест: раньше recent_arbitrage() сортировал по id DESC —
    это переворачивало порядок строк внутри одного запуска (последняя
    вставленная запись оказывалась первой), из-за чего в истории лучший
    спред показывался последним, а не первым, как в живом выводе.
    """
    store = make_store()
    # Намеренно вставляем в "неправильном" порядке — от худшего к лучшему,
    # как если бы список не был предварительно отсортирован
    opps = [
        make_opportunity(coin="WORST", net_spread=0.5),
        make_opportunity(coin="MIDDLE", net_spread=2.0),
        make_opportunity(coin="BEST", net_spread=5.0),
    ]

    store.save_arbitrage(opps)
    rows = store.recent_arbitrage()

    assert [row["coin"] for row in rows] == ["BEST", "MIDDLE", "WORST"]


def test_reopening_existing_db_does_not_lose_data():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)

    store1 = HistoryStore(db_path=path)
    store1.save_arbitrage([make_opportunity(coin="BTC")])

    store2 = HistoryStore(db_path=path)  # как будто новый запуск скрипта
    rows = store2.recent_arbitrage()

    assert len(rows) == 1
    assert rows[0]["coin"] == "BTC"
