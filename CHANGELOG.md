v0.3
-----
+ Получение тикеров через REST
+ Binance
+ Bybit
+ MEXC
+ Scanner Futures-Futures

v0.4
-----
+ Spot API
+ Basis Scanner
+ BaseExchangeAdapter
+ Symbol Normalizer

v0.5
-----
+ Funding Rate Arbitrage (FundingScanner)
+ Funding rate в Ticker (Binance/Bybit — bulk, MEXC — donabor по фильтрованному набору)
+ Тесты (pytest): калькуляторы, ArbitrageScanner, FundingScanner, MarketFilter, адаптеры
+ Исправлен баг MarketFilter (смешивание spot/future рынков)
+ Дедупликация адаптеров бирж через BaseExchangeAdapter
+ Логирование вместо print(), argparse CLI, requirements.txt