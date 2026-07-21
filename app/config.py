# Минимальный спред для поиска (%)
MIN_SPREAD = 0.01

# Минимальный спред для отображения (%)
DISPLAY_SPREAD = 0.50

# Минимальный объем (USDT)
MIN_VOLUME_USDT = 500_000

# Минимальный funding-спред для поиска (%), за один период
MIN_FUNDING_SPREAD = 0.01

# Размер позиции (USDT)
POSITION_SIZE_USDT = 1000

# Фильтр монет: [] = весь рынок, иначе например ["BTC", "ETH", "SOL"]
FILTER_COINS = []

# Биржи
EXCHANGES = {
    "binance": {
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    },
    "bybit": {
        "enableRateLimit": True,
        "options": {"defaultType": "linear"},
    },
    "mexc": {
        "enableRateLimit": True,
        "options": {"defaultType": "swap"},
    },
}
