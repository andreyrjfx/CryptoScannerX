import asyncio
import logging

from app.clients.http import HttpClient

from app.exchanges.binance_futures import BinanceFuturesAdapter
from app.exchanges.binance_spot import BinanceSpotAdapter

from app.exchanges.bybit_futures import BybitFuturesAdapter
from app.exchanges.bybit_spot import BybitSpotAdapter

from app.exchanges.mexc_futures import MexcFuturesAdapter
from app.exchanges.mexc_spot import MexcSpotAdapter

logger = logging.getLogger(__name__)


class ExchangeCollector:

    def __init__(self):
        self.http = HttpClient()

        self.adapters = [
            # Futures
            BinanceFuturesAdapter(self.http),
            BybitFuturesAdapter(self.http),
            MexcFuturesAdapter(self.http),
            # Spot
            BinanceSpotAdapter(self.http),
            BybitSpotAdapter(self.http),
            MexcSpotAdapter(self.http),
        ]

    async def fetch_all(self):
        await self.http.connect()

        try:
            tasks = [adapter.fetch_tickers() for adapter in self.adapters]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            tickers = []
            for adapter, result in zip(self.adapters, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Ошибка %s (%s): %s",
                        adapter.NAME, adapter.MARKET, result,
                    )
                    continue

                tickers.extend(result)

            return tickers

        finally:
            await self.http.close()
