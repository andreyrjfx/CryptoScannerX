# CryptoScanner

## Версия

Текущая стабильная версия: **v0.3**

Следующая версия в разработке: **v0.4**

---

# Цель проекта

Построить высокопроизводительный терминал поиска арбитражных возможностей
между криптовалютными биржами.

Проект должен поддерживать:

- Inter-Exchange Futures Arbitrage
- Spot ↔ Futures Basis
- Spot ↔ Spot Arbitrage
- Funding Arbitrage
- WebSocket Streaming

---

# Структура проекта

app/

    clients/
        http.py

    config.py

    core/
        symbol_normalizer.py

    exchanges/
        base.py
        binance.py
        bybit.py
        mexc.py
        manager.py

    models/
        ticker.py
        opportunity.py

    services/
        collector.py
        market_filter.py
        scanner.py

    main.py

---

# Поток данных

Биржи
    │
    ▼

REST / WebSocket

    │
    ▼

Exchange Adapter

    │
    ▼

Ticker

    │
    ▼

Market Filter

    │
    ▼

Scanner

    │
    ▼

Opportunity

---

# Типы сканеров

BaseScanner

├── InterExchangeScanner

├── BasisScanner

├── SpotScanner

└── FundingScanner

---

# Основная модель данных

Ticker

exchange

market

coin

symbol

bid

ask

last

volume

---

Opportunity

coin

buy_exchange

sell_exchange

buy_price

sell_price

spread

buy_volume

sell_volume

---

# Roadmap

v0.3

✔ Получение данных через REST

✔ Межбиржевой поиск спредов

✔ Унификация моделей

---

v0.4

□ Spot

□ Basis Scanner

□ Symbol Normalizer

□ Base Adapter

□ Market Filter

---

v0.5

□ Funding

□ Fees

□ Net Spread

---

v0.6

□ WebSocket

□ Live Scanner

□ Alerts

---

# Принципы разработки

Один класс — одна ответственность.

Один адаптер — одна биржа.

Все модели находятся в models/.

Вся логика поиска находится в services/.

Биржи не знают о Scanner.

Scanner не знает о REST.

Collector не знает о логике поиска.