import logging

from app.exchanges.base import BaseExchangeAdapter

logger = logging.getLogger(__name__)


class MexcFuturesAdapter(BaseExchangeAdapter):

    NAME = "mexc"
    MARKET = "future"

    URL = "https://contract.mexc.com/api/v1/contract/ticker"
    DEPTH_URL_TEMPLATE = "https://contract.mexc.com/api/v1/contract/depth/{symbol}"
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

    async def fetch_order_book(self, symbol, limit=50):
        # У MEXC futures символ — часть пути, а не query-параметр. Формат ответа
        # у этого эндпоинта на практике встречается и "плоским" ({"bids":...}),
        # и обёрнутым в {"data": {...}}, как у большинства других эндпоинтов
        # MEXC — поэтому принимаем оба варианта.
        url = self.DEPTH_URL_TEMPLATE.format(symbol=symbol)
        response = await self.http.get_json(url, params={"limit": limit})
        payload = response.get("data", response) if isinstance(response.get("data"), dict) else response

        return {
            "bids": self._parse_levels(payload.get("bids")),
            "asks": self._parse_levels(payload.get("asks")),
        }
