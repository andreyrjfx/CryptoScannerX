import asyncio
import logging

logger = logging.getLogger(__name__)


class MexcFundingEnricher:
    """
    У MEXC нет bulk-эндпоинта funding rate — только один символ за запрос
    (GET /api/v1/contract/funding_rate/{symbol}).

    Поэтому донабираем funding_rate только для тикеров, которые уже прошли
    фильтрацию по объёму/монетам (небольшой набор), а не для всего рынка —
    иначе на весь MEXC futures рынок ушли бы сотни запросов.
    """

    URL_TEMPLATE = "https://contract.mexc.com/api/v1/contract/funding_rate/{symbol}"
    CONCURRENCY = 10

    def __init__(self, http):
        self.http = http
        self._semaphore = asyncio.Semaphore(self.CONCURRENCY)

    async def enrich(self, tickers):
        targets = [
            ticker for ticker in tickers
            if ticker.exchange == "mexc" and ticker.market == "future"
        ]

        if not targets:
            return

        logger.info("MEXC: получение funding rate для %d тикеров...", len(targets))

        await asyncio.gather(*(self._enrich_one(t) for t in targets))

    async def _enrich_one(self, ticker):
        async with self._semaphore:
            url = self.URL_TEMPLATE.format(symbol=ticker.symbol)

            try:
                response = await self.http.get_json(url)
                ticker.funding_rate = float(response["data"]["fundingRate"]) * 100

            except Exception as exc:
                logger.debug("MEXC funding rate %s: %s", ticker.symbol, exc)
