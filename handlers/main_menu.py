import logging
import utils.logger # noqa: F401
from telegram import Update
from telegram.ext import ContextTypes
from utils.models.messages import BotMessage
from utils.models.user import User
from handlers.daily_report import daily_report_start

logger = logging.getLogger(__name__)

async def main_menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    comment = None
    data = query.data
    logger.debug(f"Поймал {data}")
    if data == "main_menu.daily_report":
        try:
            await daily_report_start(update, context)
        except Exception as e:
            logger.error(f"[main_menu_callback_handler] ошибка при вызове daily_report_start(update, context): '{e}'")
        return

    elif data == "main_menu.knowledge_base":
        user.set_state("main_menu.knowledge_base")

    elif data == "main_menu.manage_bot":
        user.set_state("main_menu.manage_bot")

    elif data == "main_menu.exit":
        user.set_state("main_menu")

    else:
        logger.error(f"[main_menu_callback_handler] От пользователя {user.name}({user.user_id}) получены "
                     f"неизвестные для состояния {user.state} callback data: {data}. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"
        user.set_state("main_menu")

    await query.answer()
    await BotMessage(user, chat_id, comment=comment).edit(context)
