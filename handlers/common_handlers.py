from telegram import Update
import logging
import utils.logger # noqa: F401
from telegram.ext import ContextTypes

from handlers.daily_report import daily_report_start
from utils.models.messages import BotMessage
from utils.db_sync import add_report_to_google
from utils.models import User
from utils.weather import daily_report_weather

logger = logging.getLogger(__name__)

async def yes_button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query


    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    comment = None
    state = user.state

    if state == "daily_report.saving":
        await add_report_to_google(User.get(query.from_user.id), update, context)
        await query.answer("Отчет записан")
        return

    elif state == "daily_report.confirm_overwrite":
        user.write_to_draft(overwrite=True)
        user.set_state("daily_report.wolt")

    elif state == "daily_report.weather":
        user.set_state("daily_report.saving")

    # elif state == "manage_bot_shutdown_bot":
    #     await context.application.stop()
    #     await context.application.shutdown()
    #
    else:
        logger.error(f"[yes_button_callback_handler] Пользователь {user.name}({user.user_id}) нажал 'yes' "
                     f"в состоянии {state}, для которого не предусмотрено такое нажатие. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        user.set_state("main_menu")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"

    await query.answer()
    await BotMessage(user=user, chat_id=chat_id, comment=comment).edit(context)

async def nope_button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    comment = None
    state = user.state

    if state == "daily_report.confirm_overwrite":
        user.write_to_draft(overwrite=False)
        user.set_state("daily_report.date_entering")

    elif state == "daily_report.weather":
        user.set_state("daily_report.manual_temp")

    else:
        logger.error(f"[nope_button_callback_handler] Пользователь {user.name}({user.user_id}) нажал 'nope' "
                     f"в состоянии {state}, для которого не предусмотрено такое нажатие. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        user.set_state("main_menu")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"

    await BotMessage(user=user, chat_id=chat_id, comment=comment).edit(context)

async def back_button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    comment = None
    state = user.state

    if state == "daily_report.confirm_overwrite":
        try:
            await daily_report_start(update, context)
        except Exception as e:
            logger.error(f"[back_button_callback_handler] ошибка при вызове daily_report_start(update, context): '{e}'")
        return

    elif state == "daily_report.wolt":
        user.set_state("daily_report.date_entering")

    elif state == "daily_report.bolt":
        user.set_state("daily_report.wolt")

    elif state == "daily_report.yandex":
        user.set_state("daily_report.bolt")

    elif state == "daily_report.weather":
        user.set_state("daily_report.yandex")

    elif state == "daily_report.manual_temp":
        await daily_report_weather(user, chat_id, context)
        return

    elif state == "daily_report.manual_weather_label":
        user.set_state("daily_report.manual_temp")

    elif state == "daily_report.saving":
        await daily_report_weather(user, chat_id, context)
        return

    # elif state == "manage_bot_shutdown_bot":
    #     user.set_state("main_menu_manage_bot")
    #
    else:
        logger.error(f"[back_button_callback_handler] Пользователь {user.name}({user.user_id}) нажал back "
                     f"в состоянии {state}, для которого не предусмотрено такое нажатие. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        user.set_state("main_menu")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"

    await BotMessage(user=user, chat_id=chat_id, comment=comment).edit(context)

