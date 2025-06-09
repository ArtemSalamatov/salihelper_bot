from telegram.error import BadRequest

from utils.models import Button
from telegram import InlineKeyboardButton
import logging
import utils.logger # noqa: F401
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.models.base import SessionLocal
from utils.models.state import State
from utils.models.user import User
import json

logger = logging.getLogger(__name__)

@dataclass
class BotMessage:
    user: User
    chat_id: int
    text: Optional[str] = None
    message_id: Optional[int] = None
    reply_markup: InlineKeyboardMarkup | bool | None = None
    parse_mode: str = "HTML"
    comment: Optional[str] = ""

    def __post_init__(self):
        def _build_text()-> str | None:
            text = None
            if role == "admin":
                text = state.phrase_admin
            elif role == "manager":
                text = state.phrase_manager
            elif role == "user":
                text = state.phrase_user
            if text is None:
                logger.error(f"[_build_text] Текст для состояния '{state_key}' и роли '{role}' пустой.")
                text = ""

            text = text.replace(r'\n', '\n')
            placeholders = {
                "name": self.user.name or "",
                "id": str(self.user.user_id),
                "role": self.user.role,
                "comment": self.comment if self.comment else "",
                "daily_report_date": self.user.daily_report_draft["date"],
                "wolt": self.user.daily_report_draft["wolt"],
                "bolt": self.user.daily_report_draft["bolt"],
                "yandex": self.user.daily_report_draft["yandex"],
                "daily_report_temp": self.user.daily_report_draft["temp"],
                "daily_report_weather_label": self.user.daily_report_draft["weather_label"]
                # Добавляй сюда другие переменные по мере необходимости
            }
            try:
                text = text.format(**placeholders)
            except KeyError as e:
                logger.warning(f"[BotMessage._format_placeholders] Не удалось заменить плейсхолдер: {e}")
            return text

        def _build_keyboard() -> InlineKeyboardMarkup | None:
            if self.reply_markup is False:
                return None

            raw_buttons = None
            if role == "admin":
                raw_buttons = state.buttons_admin
            elif role == "manager":
                raw_buttons = state.buttons_manager
            elif role == "user":
                raw_buttons = state.buttons_user

            if not raw_buttons:
                logger.error(f"[_build_keyboard] Кнопки для состояния '{state_key}' и роли '{role}' не заданы.")
                return None
            else:
                buttons_from_db = session.query(Button).all()
                labels = {btn.key: btn.label for btn in buttons_from_db}
                try:
                    buttons_list = json.loads(raw_buttons)
                except Exception as e:
                    logger.error(f"[build_keyboard] Не удалось распарсить JSON '{raw_buttons}': {e}")
                    return None
                keyboard = []
                for row_index, row in enumerate(buttons_list):
                    keyboard_row = []
                    for key in row:
                        label = labels.get(key)
                        if label is None:
                            label = f"❓{key}"
                            logger.warning(f"[build_keyboard] Не найдена кнопка с ключом '{key}' в БД")
                        keyboard_row.append(InlineKeyboardButton(text=label, callback_data=key))
                    keyboard.append(keyboard_row)
                return InlineKeyboardMarkup(keyboard)

        state_key = self.user.state
        role = self.user.role

        session = SessionLocal()

        try:
            state = session.query(State).filter(State.state_key == state_key).first()

            if not self.text:
                self.text = _build_text()

            if not self.reply_markup:
                self.reply_markup = _build_keyboard()

        except Exception as e:
            logger.exception(f"[BotMessage] Ошибка в __post_init__ для user_id={self.user.user_id}: {e}")
        finally:
            session.close()

    async def send(self, context: ContextTypes.DEFAULT_TYPE):
        try:
            msg = await context.bot.send_message(
            chat_id=self.chat_id,
            text=self.text or "",
            reply_markup=self.reply_markup,
            parse_mode=self.parse_mode
            )
        except Exception as e:
            logger.warning(
                f"[BotMessage.send] Не удалось отправить сообщение "
                f"user_id={self.user.user_id}, message_id={self.user.last_message_id}: {e}"
            )
        try:
            self.user.set_last_message_id(msg.message_id)
        except Exception as e:
            logger.error(f"[BotMessage.send] Не удалось сохранить last_message_id: {e}")

    async def edit(self, context: ContextTypes.DEFAULT_TYPE):
        last_msg_id = self.user.last_message_id
        if last_msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=last_msg_id,
                    text=self.text,
                    reply_markup=self.reply_markup,
                    parse_mode=self.parse_mode
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    pass  # просто пропускаем
                else:
                    logger.warning(
                        f"[BotMessage.edit] Ошибка BadRequest при редактировании сообщения (message_id={last_msg_id}) "
                        f"для пользователя {self.user.name}({self.user.user_id}) - {e}"
                    )
                    await self.send(context)
            except Exception as e:
                logger.warning(
                    f"[BotMessage.edit] Ошибка при редактировании сообщения (message_id={last_msg_id}) "
                    f"для пользователя {self.user.name}({self.user.user_id}) - {e}"
                )
                await self.send(context)
        else:
            await self.send(context)
