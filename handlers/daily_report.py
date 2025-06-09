import logging
import utils.logger # noqa: F401
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from utils.models.messages import BotMessage
from utils.db_sync import report_exists, add_report_to_google
from utils.models.user import User
from utils.tools import delete_message_from_user
from utils.weather import daily_report_weather

logger = logging.getLogger(__name__)

def _parse_number(text: str) -> float | None:
    text = text.replace("-", ".").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None

def _is_valid_date_format(date: str) -> bool:
    try:
        datetime.strptime(date, "%d.%m")
        return True
    except ValueError:
        return False

async def daily_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User.get(update.effective_user.id)
    user.set_state("daily_report.date_entering")
    await BotMessage(user, update.effective_chat.id).edit(context)

async def handle_date(user: User, chat_id: int, context: ContextTypes.DEFAULT_TYPE, date: str):
    if not _is_valid_date_format(date):
        await BotMessage(user, chat_id, comment="Неверный формат даты!\n").edit(context)
        return

    full_date = f"{date}.{datetime.now().year}"
    user.write_to_draft(date=full_date, author=f"{user.name}({user.user_id})")

    await BotMessage(
        user=user,
        chat_id=chat_id,
        text="<b>📋 Отчёт по смене</b>\n\n⏳ Подожди, проверяю дату...",
        reply_markup=False
    ).edit(context)

    if report_exists(full_date):
        user.set_state("daily_report.confirm_overwrite")
        await BotMessage(user, chat_id, comment=full_date).edit(context)
        return

    user.set_state("daily_report.wolt")
    await BotMessage(user, chat_id).edit(context)

async def daily_report_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_message_from_user(update, context)

    user = User.get(update.effective_user.id)
    chat_id = update.effective_chat.id
    comment = None
    state = user.state

    if state == "daily_report.date":
        await handle_date(user, chat_id, context, update.message.text.strip())
        return

    elif state == "daily_report.wolt":
        value = _parse_number(update.message.text.strip())
        if value is None:
            comment = "<b>⚠️ Неверный формат суммы выручки</b>\nПример корректного ввода: 1200.50\n\n"
        else:
            user.write_to_draft(wolt=value)
            user.set_state("daily_report.bolt")

    elif state == "daily_report.bolt":
        value = _parse_number(update.message.text.strip())
        if value is None:
            comment = "<b>⚠️ Неверный формат суммы выручки</b>\nПример корректного ввода: 1200.50\n\n"
        else:
            user.write_to_draft(bolt=value)
            user.set_state("daily_report.yandex")

    elif state == "daily_report.yandex":
        value = _parse_number(update.message.text.strip())
        if value is None:
            comment = "<b>⚠️ Неверный формат суммы выручки</b>\nПример корректного ввода: 1200.50\n\n"
        else:
            user.write_to_draft(yandex=value)
            await daily_report_weather(user, chat_id, context)
            return

    elif state == "daily_report.manual_temp":
        value = _parse_number(update.message.text.strip())
        if value is None:
            comment = "<b>⚠️ Неверный формат температуры воздуха</b>\nПример корректного ввода: 26\n\n"
            return
        else:
            user.write_to_draft(temp=value)
            user.set_state("daily_report.manual_weather_label")

    else:
        logger.error(f"[daily_report_message_handler] Пользователь {user.name}({user.user_id}) отправил сообщение "
                     f"в состоянии {state}, для которого отправка сообщений не предусмотрена. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        user.set_state("main_menu")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"

    await BotMessage(user, chat_id, comment=comment).edit(context)


async def daily_report_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    state = user.state

    if state == "daily_report.date_entering":
        if data == "daily_report.today":
            date = datetime.now().strftime("%d.%m")
        elif data == "daily_report.yesterday":
            date = (datetime.now() - timedelta(days=1)).strftime("%d.%m")
        else:
            logger.error(f"[daily_report_callback_handler] От пользователя {user.name}({user.user_id}) получены "
                         f"неизвестные для состояния {state} callback data ({data}). "
                         f"Сообщаю об ошибке и направляю в основное меню.")
            comment = "❌ Не удалось составить отчёт. Обратитесь к администратору.\n"
            user.set_state("main_menu")
            await BotMessage(user, chat_id, comment=comment).edit(context)
            return
        await handle_date(user, chat_id, context, date)
        return

    elif state == "daily_report.manual_weather_label":
        if data == "daily_report.weather_label.clear":
            value = "Ясно или малооблачно"

        elif data == "daily_report.weather_label.partly_cloudy":
            value = "Облачно с прояснениями"

        elif data == "daily_report.weather_label.cloudy":
            value = "Пасмурно без осадков"

        elif data == "daily_report.weather_label.precipitation":
            value = "Пасмурно с кратковременными осадками"

        elif data == "daily_report.weather_label.heavy_precipitation":
            value = "Пасмурно с сильными осадками"

        else:
            logger.error(f"[daily_report_callback_handler] От пользователя {user.name}({user.user_id}) получены "
                         f"неизвестные для состояния {state} callback data ({data}). "
                         f"Сообщаю об ошибке и направляю в основное меню.")
            comment = "❌ Не удалось составить отчёт. Обратитесь к администратору.\n"
            user.set_state("main_menu")
            await BotMessage(user, chat_id, comment=comment).edit(context)
            return

        user.write_to_draft(weather_label=value)
        user.set_state("daily_report.saving")
        await BotMessage(user, chat_id).edit(context)

async def daily_report_weather_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await add_report_to_google(User.get(query.from_user.id), update.effective_chat.id, context)

