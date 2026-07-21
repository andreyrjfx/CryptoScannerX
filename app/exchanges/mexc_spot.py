import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class MexcSpotAdapter(BaseExchangeAdapter):

    NAME = "mexc"
    MARKET = "spot"

    BOOK_TICKER_URL = "https://api.mexc.com/api/v3/ticker/bookTicker"
    STATS_24H_URL = "https://api.mexc.com/api/v3/ticker/24hr"

    async def fetch_tickers(self):
        logger.info("Получение тикеров: MEXC Spot")

        tickers = await self.fetch_merged_book_and_stats(
            book_url=self.BOOK_TICKER_URL,
            stats_url=self.STATS_24H_URL,
            bid_key="bidPrice",
            ask_key="askPrice",
            volume_key="quoteVolume",
        )

        logger.info("MEXC Spot: получено %d", len(tickers))
        return tickers
