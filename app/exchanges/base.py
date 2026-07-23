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

    def make_ticker(self, symbol, bid, ask, last, volume_usdt, funding_rate=0.0, next_funding_time=None) -> Ticker:
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
            next_funding_time=next_funding_time,
        )

    def _safe_ticker(self, symbol, bid_raw, ask_raw, last_raw, volume_raw, funding_raw=0.0, next_funding_raw=None):
        try:
            bid = float(bid_raw)
            ask = float(ask_raw)
            last = float(last_raw or 0)
            volume = float(volume_raw or 0)
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug("%s: пропуск тикера %s (%s)", self.NAME, symbol, exc)
            return None

        # Ошибка парсинга funding rate/времени не должна ронять весь тикер —
        # цена и объём для арбитража важнее.
        try:
            funding_rate = float(funding_raw or 0) * 100
        except (ValueError, TypeError):
            funding_rate = 0.0

        try:
            next_funding_time = int(next_funding_raw) if next_funding_raw else None
        except (ValueError, TypeError):
            next_funding_time = None

        return self.make_ticker(
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            volume_usdt=volume,
            funding_rate=funding_rate,
            next_funding_time=next_funding_time,
        )

    async def fetch_funding_map(self, url):
        """
        Биржи с bulk-эндпоинтом funding rate (список {symbol, lastFundingRate,
        nextFundingTime} по всем контрактам одним запросом).
        Возвращает symbol -> (funding_rate_percent, next_funding_time_ms).
        """
        data = await self.http.get_json(url)

        funding = {}
        for item in data:
            try:
                rate = float(item["lastFundingRate"]) * 100
            except (KeyError, ValueError, TypeError):
                continue

            next_time = item.get("nextFundingTime") or None
            funding[item["symbol"]] = (rate, next_time)

        return funding

    @staticmethod
    def _parse_levels(raw_levels):
        """[[price, qty], ...] -> [(float, float), ...], пропуская некорректные записи."""
        levels = []
        for level in raw_levels or []:
            try:
                levels.append((float(level[0]), float(level[1])))
            except (IndexError, ValueError, TypeError, KeyError):
                continue
        return levels

    async def fetch_order_book_binance_style(self, url, symbol, limit):
        """Binance/MEXC-spot: {"bids": [[p,q],...], "asks": [[p,q],...]}."""
        response = await self.http.get_json(url, params={"symbol": symbol, "limit": limit})
        return {
            "bids": self._parse_levels(response.get("bids")),
            "asks": self._parse_levels(response.get("asks")),
        }

    async def fetch_order_book_bybit_style(self, url, category, symbol, limit):
        """Bybit: {"result": {"b": [[p,q],...], "a": [[p,q],...]}}."""
        response = await self.http.get_json(url, params={
            "category": category, "symbol": symbol, "limit": limit,
        })
        result = response.get("result", {})
        return {
            "bids": self._parse_levels(result.get("b")),
            "asks": self._parse_levels(result.get("a")),
        }

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
        last_key=None, funding_key=None, funding_time_key=None,
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
                next_funding_raw=item.get(funding_time_key) if funding_time_key else None,
            )
            if ticker:
                tickers.append(ticker)

        return tickers
