import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import HISTORY_DB_PATH

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS arbitrage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    trade_type TEXT,
    coin TEXT,
    buy_exchange TEXT,
    buy_market TEXT,
    buy_symbol TEXT,
    buy_price REAL,
    buy_volume REAL,
    sell_exchange TEXT,
    sell_market TEXT,
    sell_symbol TEXT,
    sell_price REAL,
    sell_volume REAL,
    spread REAL,
    fee_percent REAL,
    funding_percent REAL,
    net_spread REAL,
    expected_profit_usdt REAL,
    effective_spread REAL,
    slippage_pct REAL,
    real_net_spread REAL,
    real_expected_profit_usdt REAL,
    depth_filled REAL,
    identity_verified INTEGER
);

CREATE INDEX IF NOT EXISTS idx_arbitrage_run_at ON arbitrage_history (run_at);
CREATE INDEX IF NOT EXISTS idx_arbitrage_coin ON arbitrage_history (coin);

CREATE TABLE IF NOT EXISTS funding_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    coin TEXT,
    short_exchange TEXT,
    short_funding_rate REAL,
    short_volume REAL,
    short_next_funding_time INTEGER,
    long_exchange TEXT,
    long_funding_rate REAL,
    long_volume REAL,
    long_next_funding_time INTEGER,
    funding_spread REAL,
    identity_verified INTEGER
);

CREATE INDEX IF NOT EXISTS idx_funding_run_at ON funding_history (run_at);
CREATE INDEX IF NOT EXISTS idx_funding_coin ON funding_history (coin);
"""


def _bool_to_int(value):
    """True/False/None -> 1/0/NULL для хранения в SQLite."""
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value):
    """Обратное преобразование при чтении."""
    if value is None:
        return None
    return bool(value)


class HistoryStore:
    """
    Пишет найденные возможности (arbitrage + funding) в локальную SQLite базу
    при каждом запуске сканера — история для последующего анализа/бэктеста.

    Синхронный sqlite3 используется намеренно: объём данных за запуск
    небольшой (десятки-сотни строк), блокировка event loop на миллисекунды
    не критична, а асинхронная библиотека — лишняя зависимость ради этого.
    """

    def __init__(self, db_path=HISTORY_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def save_arbitrage(self, opportunities):
        if not opportunities:
            return

        run_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                run_at, o.trade_type, o.coin,
                o.buy_exchange, o.buy_market, o.buy_symbol, o.buy_price, o.buy_volume,
                o.sell_exchange, o.sell_market, o.sell_symbol, o.sell_price, o.sell_volume,
                o.spread, o.fee_percent, o.funding_percent, o.net_spread, o.expected_profit_usdt,
                o.effective_spread, o.slippage_pct, o.real_net_spread, o.real_expected_profit_usdt,
                o.depth_filled, _bool_to_int(o.identity_verified),
            )
            for o in opportunities
        ]

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO arbitrage_history (
                    run_at, trade_type, coin,
                    buy_exchange, buy_market, buy_symbol, buy_price, buy_volume,
                    sell_exchange, sell_market, sell_symbol, sell_price, sell_volume,
                    spread, fee_percent, funding_percent, net_spread, expected_profit_usdt,
                    effective_spread, slippage_pct, real_net_spread, real_expected_profit_usdt,
                    depth_filled, identity_verified
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )

        logger.debug("HistoryStore: сохранено %d строк arbitrage_history", len(rows))

    def save_funding(self, opportunities):
        if not opportunities:
            return

        run_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                run_at, o.coin,
                o.short_exchange, o.short_funding_rate, o.short_volume, o.short_next_funding_time,
                o.long_exchange, o.long_funding_rate, o.long_volume, o.long_next_funding_time,
                o.funding_spread, _bool_to_int(o.identity_verified),
            )
            for o in opportunities
        ]

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO funding_history (
                    run_at, coin,
                    short_exchange, short_funding_rate, short_volume, short_next_funding_time,
                    long_exchange, long_funding_rate, long_volume, long_next_funding_time,
                    funding_spread, identity_verified
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )

        logger.debug("HistoryStore: сохранено %d строк funding_history", len(rows))

    def recent_arbitrage(self, limit=20):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM arbitrage_history
                ORDER BY run_at DESC, net_spread DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        for row in rows:
            row["identity_verified"] = _int_to_bool(row["identity_verified"])
        return rows

    def recent_funding(self, limit=20):
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM funding_history
                ORDER BY run_at DESC, funding_spread DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        for row in rows:
            row["identity_verified"] = _int_to_bool(row["identity_verified"])
        return rows
