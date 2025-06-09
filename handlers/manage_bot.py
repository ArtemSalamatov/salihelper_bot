import logging
import utils.logger # noqa: F401
from telegram import Update
from telegram.ext import ContextTypes

from utils.models.messages import BotMessage
from utils.db_sync import rewrite_users_on_google_from_db
from utils.models import User

logger = logging.getLogger(__name__)

async def manage_bot_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = User.get(query.from_user.id)
    chat_id = update.effective_chat.id
    comment = None
    data = query.data

    if data == "manage_bot.rewrite_users":
        rewrite_users_on_google_from_db()

    # if data == "manage_bot.shutdown_bot":
    #     user.set_state("manage_bot.shutdown_bot")
    #
    else:
        logger.error(f"[manage_bot_callback_handler] От пользователя {user.name}({user.user_id}) получены "
                     f"неизвестные для состояния {user.state} callback data ({data}). "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"
        user.set_state("main_menu")

    await query.answer()
    await BotMessage(user, chat_id, comment=comment).edit(context)
