"""
Единая точка нормализации символов.

Все биржи должны использовать одинаковые названия монет.
"""

ALIASES = {
    # Bitcoin
    "XBT": "BTC",
    # Bitcoin Cash
    "BCC": "BCH",
    "BCHABC": "BCH",
    # Terra
    "LUNA2": "LUNA",
    # При необходимости сюда будут добавляться новые правила.
}


def normalize_coin(coin: str) -> str:
    """Приводит название монеты к единому виду."""
    coin = coin.upper()
    return ALIASES.get(coin, coin)
