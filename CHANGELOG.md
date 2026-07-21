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

v0.6
-----
+ Проект переименован в CryptoScannerX
+ По умолчанию тихий вывод: только статус подключения к биржам (✅/❌) и таблицы результатов
+ Флаг -v/--verbose для технических логов (кол-во тикеров на каждом шаге и т.д.)
+ Флаг --version
+ app/__version__.py — номер версии теперь есть в коде, не только в CHANGELOG

v0.7
-----
+ Проверка реальной глубины стакана (DepthChecker) для найденных возможностей —
  VWAP-цена исполнения на POSITION_SIZE_USDT вместо наивного top-of-book bid/ask
+ Новые поля в Opportunity: effective_spread, slippage_pct, real_net_spread,
  real_expected_profit_usdt, depth_filled
+ fetch_order_book() у всех адаптеров бирж (спот и фьючерсы)
+ В таблице ARBITRAGE — колонки SLIP/REAL NET/REAL PNL
+ Тесты: SlippageCalculator, DepthChecker (43 теста всего)