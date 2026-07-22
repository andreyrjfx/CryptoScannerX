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

v0.7.1
-----
+ Багфикс: -v теперь включает уровень DEBUG (раньше был INFO) — иначе причины
  молчаливых сбоев funding/depth-запросов (logger.debug) были не видны даже с -v
+ MEXC futures order book: устойчивый парсинг и "плоского", и обёрнутого в
  {"data": {...}} формата ответа (на практике встречались оба)
+ Тесты на fetch_order_book всех 6 адаптеров (50 тестов всего)

v0.7.2
-----
+ Багфикс: -v включал DEBUG глобально (для root-логгера), из-за чего сторонние
  библиотеки (ccxt, aiohttp) на этом уровне выводили сырые HTTP-ответы целиком
  (например, огромный JSON от ccxt load_markets()). Теперь DEBUG применяется
  только к логгерам самого приложения (app.*), сторонние остаются на WARNING

v0.7.3
-----
+ Защита от "бредовых" спредов (MAX_SANE_SPREAD, по умолчанию 20%): если одинаковый
  тикер на двух биржах даёт спред в тысячи процентов, это почти наверняка разные
  активы под одним тикером (или битые данные), а не реальный арбитраж — такие
  строки теперь отбрасываются с предупреждением в логах, а не попадают в таблицу
+ В работе: проверка идентичности актива через CoinGecko API (сверка листингов
  по всем биржам для одного и того же coin id) — более основательное решение той
  же проблемы, MAX_SANE_SPREAD — временная защита до её готовности

v0.8.0
-----
+ Проверка идентичности актива через CoinGecko API (CoinIdentityChecker):
  подтверждает, что тикер с одинаковым названием на разных биржах — реально
  один и тот же проект, а не разные активы под одним символом
+ Требует бесплатный CoinGecko Demo API-ключ в .env (COINGECKO_API_KEY,
  см. .env.example) — без ключа проверка тихо пропускается
+ Новая колонка ID в таблицах ARBITRAGE и FUNDING ARBITRAGE:
  ✅ подтверждено, ⚠️ не подтверждено (риск), ? не проверялось
+ python-dotenv в зависимостях для загрузки .env
+ Тесты: CoinIdentityChecker (57 тестов всего)
