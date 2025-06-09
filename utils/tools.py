from telegram import Update
from telegram.ext import ContextTypes

from utils.models import User
import logging
import utils.logger # noqa: F401

logger = logging.getLogger(__name__)

async def delete_message_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = User.get(update.effective_user.id)
    chat_id = update.effective_chat.id

    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except Exception as e:
        logger.error(f"[daily_report_message_handler] Ошибка при удалении сообщения пользователя "
                     f"{user.name}({user.user_id}): {e}")
