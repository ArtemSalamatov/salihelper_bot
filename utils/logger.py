import os
import logging
from logging.handlers import RotatingFileHandler

# Создаём папку data, если она ещё не существует
os.makedirs("data", exist_ok=True)

# Настраиваем обработчик логов с ротацией
log_file_handler = RotatingFileHandler(
    filename="data/bot.log",
    maxBytes=2_000_000,       # максимум 2 МБ
    backupCount=5,            # храним до 5 архивов
    encoding="utf-8"
)

# Настраиваем формат
log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log_file_handler.setFormatter(log_formatter)

# Настраиваем корневой логгер (один раз)
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        log_file_handler,
        logging.StreamHandler()  # для вывода в консоль
    ]
)
