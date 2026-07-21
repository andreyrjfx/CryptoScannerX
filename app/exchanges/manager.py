import logging

import ccxt.async_support as ccxt

from app.config import EXCHANGES

logger = logging.getLogger(__name__)


class ExchangeManager:

    def __init__(self):
        self.exchanges = {}

    async def connect(self):
        logger.info("Подключение к биржам...")

        self.exchanges = {
            name: getattr(ccxt, name)(params)
            for name, params in EXCHANGES.items()
        }

    async def test_connections(self):
        failed = []

        for name, exchange in list(self.exchanges.items()):
            try:
                await exchange.load_markets()
                logger.info("✅ %-10s | рынков: %d", name, len(exchange.markets))

            except Exception:
                logger.exception("❌ Ошибка подключения к %s", name)

                try:
                    await exchange.close()
                except Exception:
                    logger.debug("Не удалось корректно закрыть %s", name)

                failed.append(name)

        for name in failed:
            del self.exchanges[name]

        if failed:
            logger.warning("Отключены биржи: %s", ", ".join(failed))

    async def close(self):
        for name, exchange in self.exchanges.items():
            try:
                await exchange.close()
            except Exception:
                logger.debug("Не удалось корректно закрыть %s", name)
