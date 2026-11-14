"""ВКонтакте-бот для подбора настроек сварочного полуавтомата (MIG/MAG).

Работает через LongPoll API библиотеки vkbottle.
Команда запуска: «начать» (или кнопка «Начать»).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Не падать, если консоль Windows не умеет печатать эмодзи из сообщений.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# aiohttp создаёт SSL-контексты при импорте, поэтому CA-бандл нужно
# подключить до импорта vkbottle. Иначе на Windows возможна ошибка
# CERTIFICATE_VERIFY_FAILED при подключении к api.vk.ru.
def _configure_https_certificates() -> None:
    try:
        import certifi
    except ModuleNotFoundError:
        return

    bundle = certifi.where()
    if Path(bundle).is_file():
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)


_configure_https_certificates()

try:
    from dotenv import load_dotenv
    from vkbottle import Keyboard, KeyboardButtonColor, Text
    from vkbottle.bot import Bot, Message
except ModuleNotFoundError as error:
    sys.exit(
        f"Не установлены зависимости: {error.name}.\n"
        "Не запускайте bot.py системным Python напрямую — используйте run.ps1:\n"
        "    powershell -ExecutionPolicy Bypass -File .\\run.ps1\n"
        "Скрипт сам создаст окружение Python 3.14 и установит всё нужное."
    )

from welding import (
    MODE_ORDER,
    MODES,
    THICKNESS_BUTTONS,
    calculate,
    fmt_thickness,
    format_calculation,
    format_table,
)

# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

if "--check" in sys.argv:
    print("Зависимости установлены, расчёт работает. Пример для стали 4 мм:\n")
    print(format_calculation(calculate("steel", 4.0)))
    sys.exit(0)

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

# Значения из README/примера, которые легко скопировать вместо настоящего токена.
TOKEN_PLACEHOLDERS = {
    "ваш_токен",
    "ваш_токен_сообщества",
    "токен",
    "token",
    "your_token",
    "xxx",
    "...",
}


def clean_token(raw: str) -> str:
    """Убирает кавычки, префикс Bearer и случайные пробелы вокруг токена."""
    token = raw.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        token = token[1:-1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def describe_token_problem(token: str) -> str | None:
    if not token:
        return "строка VK_TOKEN в .env пустая"
    if token.lower() in TOKEN_PLACEHOLDERS or "ваш" in token.lower():
        return "в .env остался пример вместо настоящего токена"
    if any(ch.isspace() for ch in token):
        return "токен содержит пробелы или переносы строк"
    if len(token) < 20:
        return "токен слишком короткий — похоже, он скопирован не полностью"
    return None


TOKEN = clean_token(os.getenv("VK_TOKEN", ""))

token_problem = describe_token_problem(TOKEN)
if token_problem:
    sys.exit(
        f"Не удалось запустить бота: {token_problem}.\n\n"
        f"1. Откройте файл {ENV_FILE}\n"
        "2. Заполните строку так: VK_TOKEN=vk1.a....\n"
        "3. Токен создаётся в сообществе:\n"
        "   Управление → Работа с API → Ключи доступа → Создать ключ\n"
        "   и должен иметь доступ к сообщениям (Messages).\n\n"
        "Токен нельзя брать из личной страницы — нужен ключ сообщества."
    )

bot = Bot(token=TOKEN, skip_old_events=False)

LOGGER = logging.getLogger("welding-bot")


async def _fetch_community() -> dict:
    try:
        return await bot.api.request("groups.getById", {})
    finally:
        # Иначе на старте появляются пугающие ошибки «Unclosed client session».
        await bot.api.http_client.close()


def check_token() -> tuple[str | None, str | None]:
    """Проверяет токен и возвращает (текст ошибки, название сообщества)."""
    try:
        response = asyncio.run(_fetch_community())
    except KeyboardInterrupt:
        raise
    except Exception as error:  # noqa: BLE001 - нужен текст любой сетевой/API-ошибки
        code = getattr(error, "code", None)
        if code == 5:
            return (
                "VK отклонил токен: ключ неверный, отозван или перевыпущен (код 5).\n"
                f"Откройте {ENV_FILE} и вставьте действующий токен сообщества."
            ), None
        if code == 6:
            return (
                "VK ограничил частоту запросов (код 6). Подождите минуту и запустите снова."
            ), None
        return (
            f"Не удалось подключиться к VK API: {type(error).__name__}: {error}"
        ), None

    groups = (response.get("response") or {}).get("groups") or []
    name = groups[0].get("name") if groups else None
    return None, name


START_WORDS = {
    "начать",
    "/начать",
    "start",
    "/start",
    "привет",
    "меню",
    "/menu",
    "сначала",
    "начать заново",
}
HELP_WORDS = {"помощь", "help", "/help", "?", "что ты умеешь"}
TABLE_WORDS = {"таблица", "таблица режимов", "режимы", "режим"}
OTHER_WORDS = {"другая толщина", "другая", "другой размер"}
MODE_TEXT = {
    "сталь": "steel",
    "steel": "steel",
    "нержавейка": "stainless",
    "нержавеющая сталь": "stainless",
    "нерж": "stainless",
    "stainless": "stainless",
    "алюминий": "aluminium",
    "алюминиевый сплав": "aluminium",
    "aluminium": "aluminium",
    "aluminum": "aluminium",
}
THICKNESS_RE = re.compile(r"^(?:толщина\s*:?\s*)?(\d+(?:[.,]\d+)?)\s*(?:мм|mm)?$")

START_TEXT = (
    "👋 Привет! Я подберу настройки сварочного полуавтомата по толщине металла.\n\n"
    "1. Выберите материал: «Сталь», «Нержавейка» или «Алюминий».\n"
    "2. Нажмите кнопку с толщиной или отправьте число в мм (например, 2,5).\n"
    "3. Получите ток, напряжение, проволоку, подачу и расход газа.\n\n"
    "Сейчас выбран режим «Сталь». Поехали! 🔧"
)

HELP_TEXT = (
    "🤖 Как пользоваться ботом:\n\n"
    "• «Сталь», «Нержавейка», «Алюминий» — переключение режима.\n"
    "• Кнопки 1–12 мм — сразу показать расчёт.\n"
    "• «Другая толщина» — отправьте любое число в мм, например 2,5 или 7.\n"
    "• «Таблица» — все режимы для выбранного материала.\n"
    "• «Начать» — сбросить настройки и вернуться в начало.\n\n"
    "Толщину можно писать текстом: «3», «3,5 мм», «толщина 4».\n\n"
    "⚠️ Расчёт ориентировочный: проверяйте режим на обрезке "
    "и подстраивайте под свой аппарат."
)


# ---------------------------------------------------------------------------
# Состояние пользователей
# ---------------------------------------------------------------------------


@dataclass
class UserState:
    mode: str = "steel"
    last_thickness: float | None = None


STATES: dict[int, UserState] = {}


def get_state(message: Message) -> UserState:
    user_id = message.from_id or message.peer_id
    return STATES.setdefault(user_id, UserState())


# ---------------------------------------------------------------------------
# Клавиатура
# ---------------------------------------------------------------------------


def _thickness_button_color(state: UserState, thickness: float) -> KeyboardButtonColor:
    if state.last_thickness is not None and abs(state.last_thickness - thickness) < 1e-9:
        return KeyboardButtonColor.POSITIVE
    return KeyboardButtonColor.SECONDARY


def main_keyboard(state: UserState) -> str:
    keyboard = Keyboard(one_time=False, inline=False)

    for mode_key in MODE_ORDER:
        mode = MODES[mode_key]
        keyboard.add(
            Text(mode.title, payload={"a": "mode", "v": mode_key}),
            color=(
                KeyboardButtonColor.POSITIVE
                if state.mode == mode_key
                else KeyboardButtonColor.SECONDARY
            ),
        )

    keyboard.row()
    for thickness in THICKNESS_BUTTONS[:5]:
        keyboard.add(
            Text(fmt_thickness(thickness), payload={"a": "thickness", "v": thickness}),
            color=_thickness_button_color(state, thickness),
        )

    keyboard.row()
    for thickness in THICKNESS_BUTTONS[5:]:
        keyboard.add(
            Text(fmt_thickness(thickness), payload={"a": "thickness", "v": thickness}),
            color=_thickness_button_color(state, thickness),
        )

    keyboard.row()
    keyboard.add(
        Text("Другая толщина", payload={"a": "other"}),
        color=KeyboardButtonColor.PRIMARY,
    )
    keyboard.add(Text("Таблица", payload={"a": "table"}))
    keyboard.add(Text("Помощь", payload={"a": "help"}))
    keyboard.add(Text("Начать", payload={"a": "start"}))

    return keyboard.get_json()


# ---------------------------------------------------------------------------
# Ответы бота
# ---------------------------------------------------------------------------


async def send_start(message: Message, state: UserState) -> None:
    state.mode = "steel"
    state.last_thickness = None
    await message.answer(START_TEXT, keyboard=main_keyboard(state))


async def send_help(message: Message, state: UserState) -> None:
    await message.answer(HELP_TEXT, keyboard=main_keyboard(state))


async def send_table(message: Message, state: UserState) -> None:
    await message.answer(format_table(state.mode), keyboard=main_keyboard(state))


async def switch_mode(message: Message, state: UserState, mode_key: str) -> None:
    if mode_key not in MODES:
        await message.answer(
            "Неизвестный режим. Выберите материал кнопкой ниже.",
            keyboard=main_keyboard(state),
        )
        return

    state.mode = mode_key
    state.last_thickness = None
    mode = MODES[mode_key]
    text = (
        f"✅ Режим: {mode.title}\n"
        f"{mode.subtitle}\n\n"
        f"Газ: {mode.gas}\n"
        f"Проволока: {mode.wire_type}\n\n"
        "Выберите толщину металла кнопкой или отправьте число в мм "
        "(например, 2,5)."
    )
    await message.answer(text, keyboard=main_keyboard(state))


async def send_calculation(message: Message, state: UserState, thickness: float) -> None:
    if thickness <= 0:
        await message.answer(
            "Толщина должна быть больше нуля. Отправьте число в мм, например 2,5.",
            keyboard=main_keyboard(state),
        )
        return

    if thickness > 50:
        await message.answer(
            "Более 50 мм — это уже не полуавтомат в бытовых условиях. "
            "Проверьте толщину или выберите режим для более тонкого металла.",
            keyboard=main_keyboard(state),
        )
        return

    try:
        text = format_calculation(calculate(state.mode, thickness))
    except ValueError as error:
        await message.answer(f"⚠️ {error}.", keyboard=main_keyboard(state))
        return
    except Exception:
        LOGGER.exception(
            "Ошибка расчёта: режим=%s, толщина=%s",
            state.mode,
            thickness,
        )
        await message.answer(
            "⚠️ Не удалось рассчитать режим для этой толщины. "
            "Попробуйте другое значение или нажмите «Помощь».",
            keyboard=main_keyboard(state),
        )
        return

    state.last_thickness = thickness
    await message.answer(text, keyboard=main_keyboard(state))


async def send_other_thickness_prompt(message: Message, state: UserState) -> None:
    await message.answer(
        "📏 Отправьте толщину металла числом в миллиметрах — например: 2,5 или 7.",
        keyboard=main_keyboard(state),
    )


# ---------------------------------------------------------------------------
# Разбор сообщений
# ---------------------------------------------------------------------------


def message_payload(message: Message) -> dict[str, object]:
    payload = message.get_payload_json()
    return payload if isinstance(payload, dict) else {}


def parse_thickness(text: str) -> float | None:
    match = THICKNESS_RE.match(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def payload_to_float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


@bot.on.message()
async def handle_message(message: Message) -> None:
    state = get_state(message)
    payload = message_payload(message)
    action = str(payload.get("a", "")).lower()
    command = str(payload.get("command", "")).lower()
    LOGGER.info(
        "Сообщение от %s: %r (payload=%s)",
        message.from_id or message.peer_id,
        (message.text or "")[:200],
        payload or None,
    )

    # Кнопка «Начать» в интерфейсе сообщества присылает command=start.
    if command == "start":
        await send_start(message, state)
        return

    if action == "mode":
        await switch_mode(message, state, str(payload.get("v", "")))
        return

    if action == "thickness":
        thickness = payload_to_float(payload.get("v"))
        if thickness is not None:
            await send_calculation(message, state, thickness)
            return

    if action == "other":
        await send_other_thickness_prompt(message, state)
        return

    if action == "table":
        await send_table(message, state)
        return

    if action == "help":
        await send_help(message, state)
        return

    if action == "start":
        await send_start(message, state)
        return

    text = (message.text or "").strip()
    normalized = text.lower().replace("ё", "е").strip(" \t\n.,!?;:")

    if not normalized:
        await message.answer(
            "Выберите материал и толщину кнопками ниже или отправьте толщину числом в мм.",
            keyboard=main_keyboard(state),
        )
        return

    if normalized in START_WORDS:
        await send_start(message, state)
        return

    if normalized in HELP_WORDS:
        await send_help(message, state)
        return

    if normalized in TABLE_WORDS:
        await send_table(message, state)
        return

    if normalized in OTHER_WORDS:
        await send_other_thickness_prompt(message, state)
        return

    if normalized in MODE_TEXT:
        await switch_mode(message, state, MODE_TEXT[normalized])
        return

    thickness = parse_thickness(normalized)
    if thickness is not None:
        await send_calculation(message, state, thickness)
        return

    await message.answer(
        "Не понял 🤔\n\n"
        "Выберите материал и толщину кнопками ниже или отправьте толщину "
        "числом в мм (например, 2,5).",
        keyboard=main_keyboard(state),
    )


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        from loguru import logger as loguru_logger
    except ModuleNotFoundError:
        return

    # vkbottle включает DEBUG-уровень loguru; оставляем только полезные строки.
    loguru_logger.remove()
    loguru_logger.add(
        sys.stderr,
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="{time:HH:mm:ss} | {level: <8} | {message}",
        colorize=False,
        enqueue=True,
    )


def main() -> None:
    configure_logging()

    problem, community = check_token()
    if problem:
        sys.exit(
            f"\n{problem}\n\n"
            "Если токен точно новый, проверьте в сообществе:\n"
            "1. «Сообщения → Сообщения сообщества» — включены.\n"
            "2. «Работа с API → LongPoll API» — включён.\n"
            "3. У ключа есть доступ к сообщениям (Messages).\n"
            "4. «Сообщения → Настройки для бота» — боту разрешено отвечать."
        )

    if community:
        LOGGER.info("Подключено к сообществу: %s", community)
    LOGGER.info("Бот запущен. Отправьте «начать» в сообщения сообщества.")
    try:
        bot.run()
    except KeyboardInterrupt:
        LOGGER.info("Бот остановлен.")
    except Exception:
        LOGGER.exception("Не удалось запустить или продолжить работу бота")
        sys.exit(
            "\nПроверьте настройки сообщества:\n"
            "1. Токен создан в разделе «Работа с API → Ключи доступа»\n"
            "   и у него включён доступ к сообщениям (Messages).\n"
            "2. В сообществе включены сообщения: «Сообщения → Сообщения сообщества».\n"
            "3. Включён LongPoll API: «Работа с API → LongPoll API».\n"
            "4. Боту разрешено отвечать: «Сообщения → Настройки для бота».\n"
            "5. Если токен перевыпускали, вставьте новый в .env."
        )


if __name__ == "__main__":
    main()
