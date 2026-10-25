"""Interactive CLI; delegates business operations to UseCases."""

import shlex
from prettytable import PrettyTable
from valutatrade_hub.core.currencies import supported_currencies
from valutatrade_hub.core.exceptions import ApiRequestError, CurrencyNotFoundError, InsufficientFundsError
from valutatrade_hub.logging_config import configure_logging
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.updater import RatesUpdater
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.core.usecases import UseCases
from valutatrade_hub.infra.database import DatabaseManager

HELP = (
    "Команды:\n"
    "  register --username NAME --password PASS\n"
    "  login --username NAME --password PASS\n"
    "  show-portfolio [--base USD]\n"
    "  deposit --amount 1000\n"
    "  buy --currency BTC --amount 0.05\n"
    "  sell --currency BTC --amount 0.01\n"
    "  get-rate --from BTC --to USD\n"
    "  update-rates [--source coingecko|exchangerate]\n"
    "  show-rates [--currency BTC] [--top N] [--base USD]\n"
    "  help, exit\n"
)


def _options(tokens: list[str]) -> dict[str, str]:
    result = {}
    index = 0
    while index < len(tokens):
        key = tokens[index]
        if not key.startswith("--") or index + 1 >= len(tokens):
            raise ValueError(f"Некорректный аргумент: {key}")
        result[key[2:]] = tokens[index + 1]
        index += 2
    return result


def _required(options: dict[str, str], *names: str) -> None:
    missing = [name for name in names if name not in options]
    if missing:
        raise ValueError("Обязательные аргументы: " + ", ".join(f"--{name}" for name in missing))


def main() -> None:
    configure_logging()
    usecases = UseCases()
    db = DatabaseManager()
    print("ValutaTrade Hub. Введите help для списка команд.")
    while True:
        try:
            line = input("valutatrade> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        try:
            tokens = shlex.split(line)
            command, args = (tokens[0].lower(), tokens[1:])
            if command in {"exit", "quit"}:
                break
            if command == "help":
                print(HELP)
            elif command == "register":
                opts = _options(args)
                _required(opts, "username", "password")
                user = usecases.register(opts["username"], opts["password"])
                print(f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). Войдите: login --username {user.username} --password ****")
            elif command == "login":
                opts = _options(args)
                _required(opts, "username", "password")
                user = usecases.login(opts["username"], opts["password"])
                print(f"Вы вошли как '{user.username}'")
            elif command == "deposit":
                opts = _options(args)
                _required(opts, "amount")
                result = usecases.deposit(usecases.current_user.user_id if usecases.current_user else 0, float(opts["amount"]))
                print(f"USD-кошелёк пополнен на {result['amount']:.2f} USD: {result['before']:.2f} → {result['after']:.2f} USD")
            elif command == "buy":
                opts = _options(args)
                _required(opts, "currency", "amount")
                result = usecases.buy(usecases.current_user.user_id if usecases.current_user else 0, opts["currency"], float(opts["amount"]))
                print(f"Покупка выполнена: {result['amount']:.4f} {result['currency']} по курсу {result['rate']:.2f} USD/{result['currency']}")
                print(f"Оценочная стоимость покупки: {result['cost']:.2f} USD")
            elif command == "sell":
                opts = _options(args)
                _required(opts, "currency", "amount")
                result = usecases.sell(usecases.current_user.user_id if usecases.current_user else 0, opts["currency"], float(opts["amount"]))
                print(f"Продажа выполнена: {result['amount']:.4f} {result['currency']} по курсу {result['rate']:.2f} USD/{result['currency']}")
                print(f"Оценочная выручка: {result['revenue']:.2f} USD")
            elif command == "show-portfolio":
                opts = _options(args)
                base = opts.get("base", "USD").upper()
                result = usecases.show_portfolio(base)
                portfolio = result["portfolio"]
                print(f"Портфель пользователя '{usecases.current_user.username}' (база: {base}):")
                if not portfolio.wallets:
                    print("Портфель пуст.")
                else:
                    for code, wallet in sorted(portfolio.wallets.items()):
                        rate = 1.0 if code == base else usecases.get_rate(code, base)["rate"]
                        print(f"- {code}: {wallet.balance:.4f} → {wallet.balance * rate:.2f} {base}")
                    print("---------------------------------")
                    print(f"ИТОГО: {result['total']:,.2f} {base}")
            elif command == "get-rate":
                opts = _options(args)
                _required(opts, "from", "to")
                result = usecases.get_rate(opts["from"], opts["to"])
                print(f"Курс {result['from']}→{result['to']}: {result['rate']:.8g} (обновлено: {result['updated_at']})")
                print(f"Обратный курс {result['to']}→{result['from']}: {1 / result['rate']:.8g}")
            elif command == "update-rates":
                opts = _options(args)
                result = RatesUpdater([CoinGeckoClient(), ExchangeRateApiClient()], RatesStorage()).run_update(opts.get("source"))
                if result["errors"]:
                    print("Update completed with errors. Check logs/actions.log for details.")
                else:
                    print(f"Update successful. Total rates updated: {result['updated']}. Last refresh: {result['last_refresh']}")
            elif command == "show-rates":
                opts = _options(args)
                cache = db.read("rates.json", {"pairs": {}, "last_refresh": None})
                pairs = cache.get("pairs", {})
                if not pairs:
                    print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
                    continue
                base = opts.get("base", "USD").upper()
                rows = []
                for pair, data in pairs.items():
                    from_code, to_code = pair.split("_", 1)
                    if "currency" in opts and opts["currency"].upper() not in {from_code, to_code}:
                        continue
                    rate = data.get("rate", 0) if isinstance(data, dict) else data
                    if to_code != base:
                        try:
                            rate = usecases.get_rate(from_code, base)["rate"]
                        except (ApiRequestError, CurrencyNotFoundError, ValueError, KeyError):
                            continue
                    rows.append((pair if to_code == base else f"{from_code}_{base}", float(rate), data.get("updated_at", "unknown") if isinstance(data, dict) else "unknown"))
                if "currency" in opts and (not rows):
                    print(f"Курс для '{opts['currency'].upper()}' не найден в кеше.")
                    continue
                if "top" in opts:
                    rows = sorted([row for row in rows if row[0].split("_")[0] in {"BTC", "ETH", "SOL"}], key=lambda row: row[1], reverse=True)[: max(0, int(opts["top"]))]
                else:
                    rows.sort()
                table = PrettyTable(["Пара", "Курс", "Обновлено"])
                for row in rows:
                    table.add_row([row[0], f"{row[1]:.8g}", row[2]])
                last_refresh = cache.get("last_refresh", "unknown")
                print(f"Rates from cache (updated at {last_refresh}):")
                print(table)
            else:
                print(f"Неизвестная команда: {command}. Введите help.")
        except InsufficientFundsError as exc:
            print(str(exc))
        except CurrencyNotFoundError as exc:
            print(f"{exc}. Поддерживаемые коды: {', '.join(supported_currencies())}. Используйте help get-rate.")
        except ApiRequestError as exc:
            print(f"{exc}. Повторите попытку позже / проверьте сеть.")
        except (ValueError, TypeError, PermissionError, KeyError, RuntimeError) as exc:
            print(str(exc))


if __name__ == "__main__":
    main()
