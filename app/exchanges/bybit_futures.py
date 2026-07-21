import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class BybitFuturesAdapter(BaseExchangeAdapter):

    NAME = "bybit"
    MARKET = "future"

    URL = "https://api.bybit.com/v5/market/tickers"

    async def fetch_tickers(self):
        logger.info("Получение тикеров: Bybit Futures")

        tickers = await self.fetch_flat_tickers(
            url=self.URL,
            params={"category": "linear"},
            items_path=("result", "list"),
            bid_key="bid1Price",
            ask_key="ask1Price",
            last_key="lastPrice",
            volume_key="turnover24h",
            funding_key="fundingRate",
        )

        logger.info("Bybit Futures: получено %d", len(tickers))
        return tickers
