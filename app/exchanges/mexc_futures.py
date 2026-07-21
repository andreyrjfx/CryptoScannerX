import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class MexcFuturesAdapter(BaseExchangeAdapter):

    NAME = "mexc"
    MARKET = "future"

    URL = "https://contract.mexc.com/api/v1/contract/ticker"
    SYMBOL_SUFFIX = "_USDT"

    def extract_coin(self, symbol: str) -> str:
        return symbol.replace(self.SYMBOL_SUFFIX, "")

    async def fetch_tickers(self):
        logger.info("Получение тикеров: MEXC Futures")

        tickers = await self.fetch_flat_tickers(
            url=self.URL,
            params=None,
            items_path=("data",),
            bid_key="bid1",
            ask_key="ask1",
            last_key="lastPrice",
            volume_key="amount24",
        )

        logger.info("MEXC Futures: получено %d", len(tickers))
        return tickers
