import asyncio
import logging

from app.core.symbol_normalizer import normalize_coin
from app.models.ticker import Ticker

logger = logging.getLogger(__name__)


class BaseExchangeAdapter:
    """
    Базовый класс для всех адаптеров бирж.

    Дочерние классы задают:
      NAME, MARKET, SYMBOL_SUFFIX
      extract_coin() (при нестандартном суффиксе)
      fetch_tickers() с вызовом одного из helper'ов ниже.
    """

    NAME = ""
    MARKET = ""
    SYMBOL_SUFFIX = "USDT"

    def __init__(self, http):
        self.http = http

    def extract_coin(self, symbol: str) -> str:
        return symbol[: -len(self.SYMBOL_SUFFIX)]

    def make_ticker(self, symbol, bid, ask, last, volume_usdt, funding_rate=0.0) -> Ticker:
        coin = normalize_coin(self.extract_coin(symbol))
        return Ticker(
            exchange=self.NAME,
            market=self.MARKET,
            coin=coin,
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volume_usdt=volume_usdt,
            funding_rate=funding_rate,
        )

    def _safe_ticker(self, symbol, bid_raw, ask_raw, last_raw, volume_raw, funding_raw=0.0):
        try:
            bid = float(bid_raw)
            ask = float(ask_raw)
            last = float(last_raw or 0)
            volume = float(volume_raw or 0)
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug("%s: пропуск тикера %s (%s)", self.NAME, symbol, exc)
            return None

        # Ошибка парсинга funding rate не должна ронять весь тикер —
        # цена и объём для арбитража важнее funding.
        try:
            funding_rate = float(funding_raw or 0) * 100
        except (ValueError, TypeError):
            funding_rate = 0.0

        return self.make_ticker(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volume_usdt=volume,
            funding_rate=funding_rate,
        )

    async def fetch_funding_map(self, url):
        """
        Биржи с bulk-эндпоинтом funding rate (список {symbol, lastFundingRate}
        по всем контрактам одним запросом).
        """
        data = await self.http.get_json(url)

        funding = {}
        for item in data:
            try:
                funding[item["symbol"]] = float(item["lastFundingRate"]) * 100
            except (KeyError, ValueError, TypeError):
                continue

        return funding

    async def fetch_merged_book_and_stats(self, book_url, stats_url, bid_key, ask_key, volume_key):
        """
        Биржи, отдающие цены и объём двумя разными эндпоинтами
        (order-book ticker + 24h stats), которые нужно смержить по symbol.
        """
        book, stats = await asyncio.gather(
            self.http.get_json(book_url),
            self.http.get_json(stats_url),
        )

        volumes = {}
        for item in stats:
            try:
                volumes[item["symbol"]] = float(item[volume_key])
            except (KeyError, ValueError, TypeError):
                volumes[item["symbol"]] = 0.0

        tickers = []
        for item in book:
            symbol = item.get("symbol", "")
            if not symbol.endswith(self.SYMBOL_SUFFIX):
                continue

            ticker = self._safe_ticker(
                symbol,
                item.get(bid_key),
                item.get(ask_key),
                last_raw=0.0,
                volume_raw=volumes.get(symbol, 0.0),
            )
            if ticker:
                tickers.append(ticker)

        return tickers

    async def fetch_flat_tickers(
        self, url, params, items_path, bid_key, ask_key, volume_key,
        last_key=None, funding_key=None,
    ):
        """
        Биржи, отдающие все нужные поля (bid/ask/last/volume[/funding]) одним эндпоинтом.
        items_path — путь до списка тикеров внутри ответа, например ("result", "list").
        """
        response = await self.http.get_json(url, params=params)

        items = response
        for key in items_path:
            items = items.get(key, {}) if isinstance(items, dict) else items

        tickers = []
        for item in items:
            symbol = item.get("symbol", "")
            if not symbol.endswith(self.SYMBOL_SUFFIX):
                continue

            ticker = self._safe_ticker(
                symbol,
                item.get(bid_key),
                item.get(ask_key),
                last_raw=item.get(last_key) if last_key else 0.0,
                volume_raw=item.get(volume_key),
                funding_raw=item.get(funding_key) if funding_key else 0.0,
            )
            if ticker:
                tickers.append(ticker)

        return tickers
