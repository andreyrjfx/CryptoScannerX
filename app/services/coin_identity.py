import asyncio
import logging

from app.clients.http import HttpClient

logger = logging.getLogger(__name__)

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Подстроки для поиска нужных бирж в /exchanges/list CoinGecko (по имени,
# т.к. сами id там не всегда совпадают с тем, что используем мы: например
# у MEXC id может быть "mxc" по историческим причинам).
EXCHANGE_NAME_HINTS = {
    "binance": "binance",
    "bybit": "bybit",
    "mexc": "mexc",
}


class CoinIdentityChecker:
    """
    Проверяет через CoinGecko, что монета с одинаковым тикером на разных
    биржах — действительно один и тот же актив, а не разные проекты под
    одинаковым символом (см. случай "ON" на MEXC vs Bybit).

    Метод: для кандидатов с совпадающим тикером (/coins/list) проверяем через
    /exchanges/{exchange_id}/tickers?coin_ids=<id>, реально ли эта биржа
    торгует именно этим coin id. Если находится кандидат, которого торгуют
    ВСЕ нужные биржи — считаем подтверждённым.

    Ограничение: сверка идёт по данным, которые видит CoinGecko (в основном
    spot-рынки) — для контрактов, существующих только как фьючерсы без
    спот-листинга, покрытие может быть слабее. Результат None означает
    "не удалось проверить" (например, нет ключа или сеть недоступна) —
    не путать с False ("проверили и не совпадает").
    """

    def __init__(self, api_key, http=None):
        self.api_key = api_key
        self.http = http or HttpClient()
        self._owns_http = http is None

        self._coins_by_symbol = None   # symbol(lower) -> [coingecko_id, ...]
        self._exchange_ids = None      # наше имя биржи -> coingecko exchange id
        self._listing_cache = {}       # (coingecko_id, exchange_id) -> bool
        self._verdict_cache = {}       # (coin, frozenset(exchanges)) -> True/False/None

    async def __aenter__(self):
        if self._owns_http:
            await self.http.connect()
        return self

    async def __aexit__(self, *exc_info):
        if self._owns_http:
            await self.http.close()

    async def _get(self, path, params=None):
        headers = {"x-cg-demo-api-key": self.api_key}
        return await self.http.get_json(f"{COINGECKO_BASE_URL}{path}", params=params, headers=headers)

    async def _ensure_coins_list(self):
        if self._coins_by_symbol is not None:
            return

        data = await self._get("/coins/list")
        by_symbol = {}
        for coin in data:
            by_symbol.setdefault(coin["symbol"].lower(), []).append(coin["id"])
        self._coins_by_symbol = by_symbol

    async def _ensure_exchange_ids(self):
        if self._exchange_ids is not None:
            return

        data = await self._get("/exchanges/list")
        resolved = {}
        for our_name, hint in EXCHANGE_NAME_HINTS.items():
            for exchange in data:
                if hint in exchange.get("name", "").lower():
                    resolved[our_name] = exchange["id"]
                    break
        self._exchange_ids = resolved

    async def _lists_coin(self, coingecko_exchange_id, coingecko_coin_id):
        cache_key = (coingecko_coin_id, coingecko_exchange_id)
        if cache_key in self._listing_cache:
            return self._listing_cache[cache_key]

        try:
            data = await self._get(
                f"/exchanges/{coingecko_exchange_id}/tickers",
                params={"coin_ids": coingecko_coin_id},
            )
            result = bool(data.get("tickers"))
        except Exception as exc:
            logger.debug(
                "CoinGecko: не удалось проверить листинг %s на %s (%s)",
                coingecko_coin_id, coingecko_exchange_id, exc,
            )
            result = False

        self._listing_cache[cache_key] = result
        return result

    async def verify(self, coin, exchanges):
        """
        coin: символ монеты, например "LA".
        exchanges: биржи, которые нужно сверить, например {"mexc", "binance"}.

        True  — подтверждено: есть coin id на CoinGecko, который торгуется
                на всех указанных биржах.
        False — не подтверждено: не нашли ни одного такого кандидата
                (высокий риск, что это разные активы под одним тикером).
        None  — проверка не смогла выполниться технически (нет ключа, сеть,
                монета не найдена ни в одном справочнике CoinGecko и т.д.) —
                не означает, что актив разный, просто мы не знаем.
        """
        exchanges = frozenset(e.lower() for e in exchanges)
        cache_key = (coin.upper(), exchanges)
        if cache_key in self._verdict_cache:
            return self._verdict_cache[cache_key]

        try:
            await self._ensure_coins_list()
            await self._ensure_exchange_ids()
        except Exception as exc:
            logger.debug("CoinGecko: не удалось получить справочники (%s)", exc)
            self._verdict_cache[cache_key] = None
            return None

        candidate_ids = self._coins_by_symbol.get(coin.lower(), [])
        if not candidate_ids:
            self._verdict_cache[cache_key] = None
            return None

        target_exchange_ids = [self._exchange_ids.get(e) for e in exchanges]
        if any(e_id is None for e_id in target_exchange_ids):
            # Не нашли одну из бирж в справочнике CoinGecko вообще
            self._verdict_cache[cache_key] = None
            return None

        for candidate_id in candidate_ids:
            listed = await asyncio.gather(*(
                self._lists_coin(exchange_id, candidate_id) for exchange_id in target_exchange_ids
            ))
            if all(listed):
                self._verdict_cache[cache_key] = True
                return True

        self._verdict_cache[cache_key] = False
        return False
