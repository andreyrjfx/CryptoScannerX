import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class BybitSpotAdapter(BaseExchangeAdapter):

    NAME = "bybit"
    MARKET = "spot"

    URL = "https://api.bybit.com/v5/market/tickers"

    async def fetch_tickers(self):
        logger.info("Получение тикеров: Bybit Spot")

        tickers = await self.fetch_flat_tickers(
            url=self.URL,
            params={"category": "spot"},
            items_path=("result", "list"),
            bid_key="bid1Price",
            ask_key="ask1Price",
            last_key="lastPrice",
            volume_key="turnover24h",
        )

        logger.info("Bybit Spot: получено %d", len(tickers))
        return tickers
