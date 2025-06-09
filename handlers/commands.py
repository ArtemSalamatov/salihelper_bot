from telegram import Update
from telegram.ext import ContextTypes, CallbackContext

from handlers.daily_report import daily_report_start
from utils.models.user import User
from utils.models.messages import BotMessage
import logging
import utils.logger # noqa: F401
from utils.tools import delete_message_from_user

logger = logging.getLogger(__name__)

async def command_handler(update: Update, context: CallbackContext):
    await delete_message_from_user(update, context)
    user = User.get(update.effective_user.id)
    chat_id = update.effective_chat.id
    command = update.effective_message.text.split()[0][1:]

    if command == "start":
        try:
            user = User.get(user.user_id)
            if user:
                user.set_state("main_menu")
            else:
                user = User.create(user_id=user.user_id,
                                   role="guest",
                                   state="guest",
                                   first_name=update.effective_user.first_name,
                                   last_name=update.effective_user.last_name)
            await BotMessage(user, chat_id).send(context)
            return
        except Exception as e:
            logger.exception(f"[command_handler] Ошибка у пользователя {user.name}({user.user_id}) - {e}")

    elif command == "daily_report":
        try:
            await daily_report_start(update, context)
        except Exception as e:
            logger.error(f"[command_handler] ошибка при вызове daily_report_start у пользователя "
                         f"{user.name}({user.user_id}) - '{e}'")
        return

    else:
        logger.error(f"[command_handler] От пользователя {user.name}({user.user_id}) получена "
                     f"неизвестныая команда: {command}. "
                     f"Сообщаю об ошибке и направляю в основное меню.")
        comment = "❌ Неизвестная ошибка. Обратитесь к администратору.\n"
        user.set_state("main_menu")
        await BotMessage(user, chat_id, comment=comment).send(context)



