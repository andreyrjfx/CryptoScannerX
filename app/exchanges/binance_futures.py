import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class BinanceFuturesAdapter(BaseExchangeAdapter):

    NAME = "binance"
    MARKET = "future"

    BOOK_TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/bookTicker"
    STATS_24H_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    PREMIUM_INDEX_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"

    async def fetch_tickers(self):
        logger.info("Получение тикеров: Binance Futures")

        tickers = await self.fetch_merged_book_and_stats(
            book_url=self.BOOK_TICKER_URL,
            stats_url=self.STATS_24H_URL,
            bid_key="bidPrice",
            ask_key="askPrice",
            volume_key="quoteVolume",
        )

        try:
            funding_map = await self.fetch_funding_map(self.PREMIUM_INDEX_URL)
            for ticker in tickers:
                ticker.funding_rate = funding_map.get(ticker.symbol, 0.0)
        except Exception as exc:
            logger.warning("Binance Futures: не удалось получить funding rate: %s", exc)

        logger.info("Binance Futures: получено %d", len(tickers))
        return tickers
