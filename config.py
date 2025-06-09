import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
WEATHER_ASSISTANT_ID = os.environ.get("WEATHER_ASSISTANT_ID")

DAILY_REPORT_SHEET_ID = os.environ.get("DAILY_REPORT_SHEET_ID")
BOT_CONFIG_SHEET_ID = os.environ.get("BOT_CONFIG_SHEET_ID")

CREDS_FILE_PATH = os.environ.get("CREDS_FILE_PATH")
DATABASE_PATH=os.environ.get("DATABASE_PATH")
DAILY_REPORT_LOG_FILE=os.environ.get("DAILY_REPORT_LOG_FILE")

OPENMETEO_LATITUDE = 41.7223
OPENMETEO_LONGITUDE = 44.8046
WORK_START_HOUR = 9
WORK_END_HOUR = 19
