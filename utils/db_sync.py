import logging

from telegram import Update

import utils.logger # noqa: F401
from typing import Dict, Any, List
import json
import pytz

from datetime import datetime
from ast import literal_eval

import gspread
from google.oauth2.service_account import Credentials

from sqlalchemy import delete
from telegram.ext import ContextTypes

from config import BOT_CONFIG_SHEET_ID, CREDS_FILE_PATH, DAILY_REPORT_SHEET_ID, DAILY_REPORT_LOG_FILE
from utils.models.messages import BotMessage
from utils.models.base import init_db, SessionLocal
from utils.models.state import State
from utils.models.button import Button
from utils.models.user import User

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# === Работа с Google Sheets ===
def _get_spreadsheet(spreadsheet_id: str) -> gspread.Spreadsheet:
    try:
        logger.info("[_get_worksheet] Авторизация по service account...")
        creds = Credentials.from_service_account_file(
            CREDS_FILE_PATH,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(spreadsheet_id)
        return spreadsheet

    except Exception as e:
        logger.error("[_get_worksheet] Не удалось получить лист %s: %s", spreadsheet_id, e)
        raise

def _get_tbilisi_datetime():
    tbilisi_tz = pytz.timezone("Asia/Tbilisi")
    now = datetime.now(tbilisi_tz)
    return now.strftime("%d.%m.%y %H:%M")

def fetch_states_from_google(spreadsheet: gspread.Spreadsheet, worksheet_name: str) -> List[Dict[str, Any]]:
    worksheet = spreadsheet.worksheet(worksheet_name)
    logger.info("[fetch_states_from_google] Лист получен: %s", worksheet.title)

    rows = worksheet.get_all_records()
    result: List[Dict[str, Any]] = []
    for row in rows:
        state_name = row.get("state_key")
        if not state_name:
            continue
        entry: Dict[str, Any] = {
            "state_key": state_name,
            "comment": row.get("comment") or None,
            "phrase_admin": row.get("phrase_admin") or "",
            "phrase_manager": row.get("phrase_manager") or "",
            "phrase_user": row.get("phrase_user") or "",
            "buttons_admin": row.get("buttons_admin") or None,
            "buttons_manager": row.get("buttons_manager") or None,
            "buttons_user": row.get("buttons_user") or None,
        }
        result.append(entry)
    logger.info("[fetch_states_from_google] Загружено %d состояний из Google Sheets", len(result))
    return result

def fetch_buttons_from_google(spreadsheet: gspread.Spreadsheet, worksheet_name: str) -> List[Dict[str, Any]]:
    worksheet = spreadsheet.worksheet(worksheet_name)
    logger.info("[fetch_buttons_from_google] Лист получен: %s", worksheet.title)

    rows = worksheet.get_all_records()
    result: List[Dict[str, Any]] = []
    for row in rows:
        key = row.get("key")
        label = row.get("label")
        if not key or label is None:
            continue
        result.append({"key": key, "label": label})
    logger.info("[fetch_buttons_from_google] Загружено %d кнопок из Google Sheets", len(result))
    return result

def fetch_users_from_google(spreadsheet: gspread.Spreadsheet, worksheet_name: str) -> List[Dict[str, Any]]:
    worksheet = spreadsheet.worksheet(worksheet_name)
    logger.info("[fetch_users_from_google] Лист получен: %s", worksheet.title)

    rows = worksheet.get_all_records()
    result: List[Dict[str, Any]] = []
    for row in rows:
        user_id = row.get("user_id")
        if not user_id:
            continue

        raw = row.get("daily_report_draft") or ""
        # сначала пробуем JSON
        if raw:
            try:
                daily_report_draft = json.loads(raw)
            except json.JSONDecodeError:
                # если JSON не прогнался — fallback на ast.literal_eval
                try:
                    daily_report_draft = literal_eval(raw)
                except Exception as e:
                    logger.warning(
                        f"[fetch_users_from_google] Не смогли распарсить черновик пользователя "
                        f"{user_id!r} ни через JSON, ни через AST: {e}"
                    )
                    daily_report_draft = {}
        else:
            daily_report_draft = {}

        # и ещё убеждаемся, что это dict
        if not isinstance(daily_report_draft, dict):
            logger.warning(
                f"[fetch_users_from_google] Некорректный тип черновика у пользователя {user_id}: "
                f"{type(daily_report_draft)}"
            )
            daily_report_draft = {}

        entry = {
            "user_id":            user_id,
            "name":               row.get("name") or "",
            "role":               row.get("role") or "guest",
            "state":              row.get("state") or None,
            "last_message_id":    row.get("last_message_id") or None,
            "is_workday":         row.get("is_workday") in ("TRUE", "True", True),
            "daily_report_draft": daily_report_draft,
        }
        result.append(entry)

    logger.info("[fetch_users_from_google] Загружено %d пользователей из Google Sheets", len(result))
    return result

def report_exists(date: str) -> bool:
    spreadsheet = _get_spreadsheet(DAILY_REPORT_SHEET_ID)
    worksheet = spreadsheet.worksheet("reports")
    values = worksheet.get_all_values()
    for row in values[1:]:
        if row and row[0].strip() == date:
            return True
    return False

async def add_report_to_google(user: User, update: Update, context: ContextTypes.DEFAULT_TYPE):
    def _log_report():
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        log_entry = f"[{timestamp}] {user.name} ({user.user_id}): отчёт — {report}\n"

        try:
            with open(DAILY_REPORT_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"[add_report_to_google._log_report] Ошибка при записи информации об отчете от пользователя "
                         f"{user.name}({user.user_id}) в лог: {e}")

    text = "<b>📋 Отчёт по смене</b>\n\n⏳ Подожди, сохраняю отчет..."
    await BotMessage(user=user, chat_id=update.effective_chat.id, text=text, reply_markup=False).edit(context)

    report = user.daily_report_draft
    try:
        spreadsheet = _get_spreadsheet(DAILY_REPORT_SHEET_ID)
        worksheet = spreadsheet.worksheet("reports")
        values = worksheet.get_all_values()

        row_data = [
            report["date"],
            report.get("author"),
            report.get("wolt"),
            report.get("bolt"),
            report.get("yandex"),
            report.get("temp"),
            report.get("weather_label"),
            _get_tbilisi_datetime()
        ]

        if user.daily_report_draft["overwrite"]:
            for i, row in enumerate(values[1:], start=2):
                if row and row[0].strip() == report["date"]:
                    worksheet.update(f"A{i}:H{i}", [row_data])
        else:
            worksheet.append_row(row_data)

        _log_report()
        user.clear_draft()
        logger.info(f"[add_report_to_google] Пользователь {user.name}({user.user_id}) "
                    f"заполнил отчет за {report.get('date')}. Отчет сохранен.")
        user.set_state("main_menu")
        await update.callback_query.answer("✅ Отчёт сохранён. Спасибо!", show_alert=True)
        # comment = "✅ Отчёт сохранён. Спасибо!\n"
    except Exception as e:
        log_text = (f"[add_report_to_google] Пользователю {user.name}({user.user_id}) "
                    f"не удалось сохранить отчёт за {user.daily_report_draft['date']}: {e}")
        logger.error(log_text)
        await update.callback_query.answer(f"❌ Не удалось сохранить отчёт. Пожалуйста, отправьте администратору "
                                           f"скриншот данного сообщения: {log_text}",
                                           show_alert=True
                                           )
        # comment = "❌ Не удалось сохранить отчёт. Обратитесь к администратору.\n"

    await BotMessage(user, chat_id=update.effective_chat.id).edit(context)

# === Работа с БД ===
def upsert_states(states_data: List[Dict[str, Any]]):
    """
    Полностью перезаписывает таблицу 'states'.
    """
    with SessionLocal.begin() as session:
        session.execute(delete(State))

        for entry in states_data:
            state = State(
                state_key=entry["state_key"],
                comment=entry.get("comment"),
                phrase_admin=entry.get("phrase_admin"),
                phrase_manager=entry.get("phrase_manager"),
                phrase_user=entry.get("phrase_user"),
                buttons_admin=entry.get("buttons_admin"),
                buttons_manager=entry.get("buttons_manager"),
                buttons_user=entry.get("buttons_user"),
            )
            session.add(state)
    logger.info("[upsert_states] Таблица 'states' перезаписана")

def upsert_buttons(buttons_data: List[Dict[str, Any]]):
    """
    Полностью перезаписывает таблицу 'ru_buttons'.
    """
    with SessionLocal.begin() as session:
        session.execute(delete(Button))

        for entry in buttons_data:
            button_obj = Button(key=entry["key"], label=entry["label"])
            session.add(button_obj)
    logger.info("[upsert_buttons] Таблица 'ru_buttons' перезаписана")

def upsert_users(states_data: List[Dict[str, Any]]):
    """
    Полностью перезаписывает таблицу 'users'.
    """
    with SessionLocal.begin() as session:
        session.execute(delete(User))

        for entry in states_data:
            user = User(
                user_id=entry["user_id"],
                name=entry.get("name"),
                role=entry.get("role"),
                state=entry.get("state"),
                last_message_id=entry.get("last_message_id"),
                is_workday=entry.get("is_workday") in ("TRUE", "True"),
                daily_report_draft=entry.get("daily_report_draft")
            )
            session.add(user)
    logger.info("[upsert_states] Таблица 'users' перезаписана")

def update_from_google_to_db():
    init_db()
    spreadsheet = _get_spreadsheet(BOT_CONFIG_SHEET_ID)
    states_data = fetch_states_from_google(spreadsheet, "states")
    upsert_states(states_data)
    buttons_data = fetch_buttons_from_google(spreadsheet, "ru_buttons")
    upsert_buttons(buttons_data)
    users_data = fetch_users_from_google(spreadsheet, "users")
    upsert_users(users_data)
    logger.info("[update_from_google_to_db] Синхронизация завершена")

def rewrite_users_on_google_from_db():
    """
    Перезаписывает лист 'users' в Google Sheets данными из таблицы User в БД.
    """
    # 1. Открываем Google Spreadsheet и лист
    spreadsheet = _get_spreadsheet(BOT_CONFIG_SHEET_ID)
    worksheet = spreadsheet.worksheet("users")

    # 2. Читаем всех пользователей из БД и сразу упаковываем в list of dict
    users_data = []
    with SessionLocal() as session:
        db_users = session.query(User).all()
        for u in db_users:
            users_data.append({
                "user_id":            u.user_id,
                "name":               u.name or "",
                "role":               u.role or "",
                "state":              u.state or "",
                "last_message_id":    u.last_message_id or "",
                "is_workday":         "TRUE" if u.is_workday else "FALSE",
                "daily_report_draft": json.dumps(u.daily_report_draft or {}, ensure_ascii=False)
            })

    # 3. Собираем строки для Google Sheets
    header = [
        "user_id",
        "name",
        "role",
        "state",
        "last_message_id",
        "is_workday",
        "daily_report_draft"
    ]
    rows = [header]
    for entry in users_data:
        rows.append([
            entry["user_id"],
            entry["name"],
            entry["role"],
            entry["state"],
            entry["last_message_id"],
            entry["is_workday"],
            entry["daily_report_draft"],
        ])

    # 4. Публикуем в Google Sheets
    worksheet.clear()
    worksheet.update(rows)
    logger.info("[rewrite_users_on_google_from_db] Лист 'users' перезаписан данными из БД")
