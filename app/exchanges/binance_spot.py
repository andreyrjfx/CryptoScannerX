import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class BinanceSpotAdapter(BaseExchangeAdapter):

    NAME = "binance"
    MARKET = "spot"

    BOOK_TICKER_URL = "https://api.binance.com/api/v3/ticker/bookTicker"
    STATS_24H_URL = "https://api.binance.com/api/v3/ticker/24hr"
    DEPTH_URL = "https://api.binance.com/api/v3/depth"

    async def fetch_tickers(self):
        logger.info("Получение тикеров: Binance Spot")

        tickers = await self.fetch_merged_book_and_stats(
            book_url=self.BOOK_TICKER_URL,
            stats_url=self.STATS_24H_URL,
            bid_key="bidPrice",
            ask_key="askPrice",
            volume_key="quoteVolume",
        )

        logger.info("Binance Spot: получено %d", len(tickers))
        return tickers

    async def fetch_order_book(self, symbol, limit=50):
        return await self.fetch_order_book_binance_style(self.DEPTH_URL, symbol, limit)
