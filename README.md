# ValutaTrade Hub

Консольное учебное приложение для регистрации пользователей, управления виртуальными валютными кошельками и просмотра курсов фиатных и криптовалют.

## Установка

Требуется Python 3.11+ и [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run valutatrade
# или
uv run python main.py
```

Для проверки стиля:
```bash
uv run ruff check .
uv run ruff format --check .
```

## Команды

Команды вводятся в интерактивном CLI без префикса `valutatrade`:

```text
register --username alice --password 1234
login --username alice --password 1234
deposit --amount 1000
buy --currency BTC --amount 0.05
sell --currency BTC --amount 0.01
show-portfolio
get-rate --from BTC --to USD
show-rates --top 2
update-rates
help
exit
```

`deposit --amount 1000` добавляет виртуальные средства в USD-кошелёк (имитация пополнения). `buy` списывает эквивалент покупки с USD-кошелька по актуальному курсу; `sell` начисляет выручку в USD. Валютный кошелёк при первой покупке создаётся автоматически. Если курс отсутствует, устарел и не удалось обновить данные, операция завершается понятной ошибкой; устаревший курс не выдаётся как актуальный.

## Данные и курсы

JSON-хранилища находятся в `data/`: `users.json`, `portfolios.json`, `rates.json` и `exchange_rates.json`. Кеш курсов использует TTL из `pyproject.toml` (`tool.valutatrade.rates_ttl_seconds`, по умолчанию 300 секунд). Устаревший кеш вызывает попытку обновления через Parser Service; если API недоступно, выводится понятная ошибка.

Для ExchangeRate-API задайте переменную окружения `EXCHANGERATE_API_KEY`. Ключ не следует помещать в код или коммитить в Git. CoinGecko используется для курсов криптовалют.

## Архитектура

- `core/` — модели, валюты, исключения и бизнес-сценарии.
- `infra/` — настройки и JSON-хранилище (Singleton).
- `parser_service/` — API-клиенты, обновление курсов, история и планировщик.
- `cli/` — разбор команд и отображение результатов.
- `logging_config.py`, `decorators.py` — логирование доменных операций.

## Демо-сценарий

1. `register --username alice --password 1234`
2. `login --username alice --password 1234`
3. `buy --currency BTC --amount 0.05`
4. `show-portfolio`
5. `sell --currency BTC --amount 0.01`
6. `get-rate --from BTC --to USD`
7. `update-rates`
8. `show-rates --top 2`

Parser Service обращается к внешним API по команде `update-rates`; сетевые ошибки одного источника не мешают обновлению из другого. Для периодического обновления планировщик можно запустить из Python-кода через `run_scheduler(RatesUpdater([...]), interval_seconds=300)`.
