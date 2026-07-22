import asyncio
import logging

logger = logging.getLogger(__name__)


class MexcFundingEnricher:
    """
    У MEXC нет bulk-эндпоинта funding rate — только один символ за запрос
    (GET /api/v1/contract/funding_rate/{symbol}), с официальным лимитом
    20 запросов/2 секунды.

    Донабираем funding_rate для всех переданных MEXC futures тикеров,
    батчами с паузой между ними, чтобы не пробивать лимит биржи — иначе
    MEXC начинает отвечать ошибками без "data" и лог заполняется этим
    построчно. При полном скане рынка (без фильтра монет) это всё равно
    может занять время — при большом количестве тикеров стоит запускать
    с фильтром по конкретным монетам.
    """

    URL_TEMPLATE = "https://contract.mexc.com/api/v1/contract/funding_rate/{symbol}"

    # Официальный лимит биржи — 20 запросов/2с. Берём с запасом.
    BATCH_SIZE = 15
    BATCH_PAUSE_SECONDS = 2.1

    def __init__(self, http):
        self.http = http

    async def enrich(self, tickers):
        targets = [
            ticker for ticker in tickers
            if ticker.exchange == "mexc" and ticker.market == "future"
        ]

        if not targets:
            return

        logger.info("MEXC: получение funding rate для %d тикеров...", len(targets))

        succeeded = 0
        for start in range(0, len(targets), self.BATCH_SIZE):
            batch = targets[start:start + self.BATCH_SIZE]
            results = await asyncio.gather(*(self._enrich_one(t) for t in batch))
            succeeded += sum(results)

            if start + self.BATCH_SIZE < len(targets):
                await asyncio.sleep(self.BATCH_PAUSE_SECONDS)

        failed = len(targets) - succeeded
        if failed:
            logger.warning(
                "MEXC funding rate: получено %d/%d, не удалось для %d "
                "(подробности см. с -v; вероятная причина — rate limit биржи "
                "при большом количестве тикеров без фильтра монет)",
                succeeded, len(targets), failed,
            )
        else:
            logger.info("MEXC funding rate: получено для всех %d тикеров", len(targets))

    async def _enrich_one(self, ticker):
        """Возвращает True/False — удалось ли получить funding rate для этого тикера."""
        url = self.URL_TEMPLATE.format(symbol=ticker.symbol)

        try:
            response = await self.http.get_json(url)
            ticker.funding_rate = float(response["data"]["fundingRate"]) * 100
            return True
        except Exception as exc:
            logger.debug("MEXC funding rate %s: %s", ticker.symbol, exc)
            return False
