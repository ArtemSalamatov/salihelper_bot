import os
import atexit
import shutil
import glob
import logging
import utils.logger # noqa: F401
from datetime import datetime
from config import BOT_TOKEN, DATABASE_PATH
from utils.models.base import engine
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers.common_handlers import back_button_callback_handler, nope_button_callback_handler, \
    yes_button_callback_handler
from handlers.manage_bot import manage_bot_callback_handler
from handlers.commands import command_handler
from handlers.daily_report import daily_report_message_handler, daily_report_callback_handler
from handlers.main_menu import main_menu_callback_handler
from dotenv import load_dotenv
from utils.db_sync import update_from_google_to_db


logger = logging.getLogger(__name__)
load_dotenv()

def shutdown_hook() -> None:
    """
    Эта функция будет автоматически вызвана при нормальном завершении процесса.
    """
    logger.info("[shutdown_hook] 🛑 Начинаю процедуру завершения работы бота…")

    # 1) Корректно «слить» соединения SQLAlchemy
    try:
        engine.dispose()
        logger.info("[shutdown_hook] ✅ SQLAlchemy engine.dispose() выполнен")
    except Exception as e:
        logger.error(f"[shutdown_hook] ❌ Ошибка при отключении от БД: {e}")

    # 2) Создать бэкап файла SQLite
    try:
        # получаем путь к файлу базы
        db_file = DATABASE_PATH.replace("sqlite:///", "")
        base, ext = os.path.splitext(db_file)
        backup_dir = os.path.dirname(db_file)

        # шаблон для поиска старых бэкапов
        pattern = os.path.join(backup_dir, f"{os.path.basename(base)}_backup_*{ext}")
        backups = glob.glob(pattern)

        # сортируем по имени (метка времени в формате YYYYMMDD_HHMMSS даёт правильный порядок)
        backups.sort()

        # если бэкапов больше трёх — удаляем самые старые лишние
        if len(backups) >= 3:
            to_delete = backups[:len(backups) - 2]  # оставляем 2 старых + новый (будет 3)
            for old in to_delete:
                try:
                    os.remove(old)
                    logger.info(f"🗑 Удалён старый бэкап: {old}")
                except Exception as e:
                    logger.warning(f"Не смог удалить {old}: {e}")

        # создаём новый бэкап
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_file = os.path.join(
            backup_dir,
            f"{os.path.basename(base)}_backup_{timestamp}{ext}"
        )
        shutil.copy(db_file, backup_file)
        logger.info(f"✅ Создан бэкап БД: {backup_file}")

    except Exception as e:
        logger.error(f"❌ Ошибка при бэкапе и ротации БД: {e}")

    # 3) Сброс и закрытие всех логгеров
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
    logger.info("[shutdown_hook] ✅ Все логгеры закрыты")

# Регистрируем наш hook — он выполнится при выходе из процесса
atexit.register(shutdown_hook)


def main():
    logger.info("[bot.py] Инициализация базы данных...")
    try:
        update_from_google_to_db()
        # init_db()

        logger.info("[bot.py] ✅ База данных инициализирована")
    except Exception as e:
        logger.exception(f"[bot.py] ❌ Ошибка при инициализации базы: {e}")

    logger.info("[main] Запуск бота...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start", "daily_report"], command_handler))
    app.add_handler(CallbackQueryHandler(main_menu_callback_handler, pattern="^main_menu."))
    app.add_handler(CallbackQueryHandler(daily_report_callback_handler, pattern="^daily_report."))
    app.add_handler(CallbackQueryHandler(yes_button_callback_handler, pattern="^yes"))
    app.add_handler(CallbackQueryHandler(nope_button_callback_handler, pattern="^nope"))
    app.add_handler(CallbackQueryHandler(back_button_callback_handler, pattern="^back"))
    app.add_handler(CallbackQueryHandler(manage_bot_callback_handler, pattern="^manage_bot."))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, daily_report_message_handler))
    logger.info("Бот запущен. Ждём обновлений...")
    app.run_polling()

if __name__ == "__main__":
    main()
