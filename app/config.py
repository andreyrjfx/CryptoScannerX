import os

from dotenv import load_dotenv

load_dotenv()

# Минимальный спред для поиска (%)
MIN_SPREAD = 0.01

# Минимальный спред для отображения (%)
DISPLAY_SPREAD = 0.50

# Минимальный объем (USDT)
MIN_VOLUME_USDT = 500_000

# Минимальный funding-спред для поиска (%), за один период
MIN_FUNDING_SPREAD = 0.01

# Сколько уровней стакана запрашивать при проверке проскальзывания
DEPTH_LIMIT = 50

# Спред выше этого порога (%) почти наверняка означает не реальный арбитраж,
# а ошибку данных или два разных актива под одинаковым тикером на разных биржах
MAX_SANE_SPREAD = 20

# Ключ CoinGecko Demo API (бесплатный, https://www.coingecko.com/en/api/pricing).
# Берётся из переменной окружения/.env — никогда не хранится в коде.
# Если не задан, проверка идентичности актива (CoinIdentityChecker) отключается.
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "")

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
