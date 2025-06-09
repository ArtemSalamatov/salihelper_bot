import logging
import utils.logger # noqa: F401
from datetime import datetime

import requests
from typing import Tuple, List

from telegram.ext import ContextTypes

from config import OPENMETEO_LATITUDE, OPENMETEO_LONGITUDE, WORK_START_HOUR, WORK_END_HOUR
from utils.models.messages import BotMessage
from utils.models import User

logger = logging.getLogger(__name__)

def _get_weather(date_str: str) -> dict | None:
    def _weather_request() -> Tuple[List[float], List[int], List[float]] | None:
        params = {
            'latitude': OPENMETEO_LATITUDE,
            'longitude': OPENMETEO_LONGITUDE,
            'hourly': 'temperature_2m,precipitation,cloudcover',
            'timezone': 'auto',
            'start_date': formatted_date,
            'end_date': formatted_date
        }
        logger.debug(f"Params: {params}")

        try:
            res = requests.get('https://api.open-meteo.com/v1/forecast', params=params, timeout=10)
            data = res.json()
        except Exception as e:
            logger.error(f"[get_weather._weather_request] Ошибка при запросе в Open-Meteo за {date_str} - {e}")
            return None

        hourly = data.get('hourly', {})
        times   = hourly.get('time', [])
        temps   = hourly.get('temperature_2m', [])
        clouds  = hourly.get('cloudcover', [])
        precips = hourly.get('precipitation', [])

        temps_list, clouds_list, precips_list = [], [], []
        for time_str, temp, cloud, precip in zip(times, temps, clouds, precips):
            hour = int(time_str[11:13])
            if WORK_START_HOUR <= hour < WORK_END_HOUR:
                temps_list.append(temp)
                clouds_list.append(cloud)
                precips_list.append(precip)

        return temps_list, clouds_list, precips_list

    def _analyze_weather(weather_lists: Tuple[List[float], List[float], List[float]]) -> dict:
        temps, clouds, precips = weather_lists

        # Вторая по величине температура
        sorted_temps = sorted(temps, reverse=True)
        second_highest = sorted_temps[1] if len(sorted_temps) >= 2 else sorted_temps[0]
        second_highest_temp = round(second_highest, 1)

        # Параметры порогов
        precip_min = 0.1
        strong_rain = 2.0
        hours = len(temps)
        total_precip = sum(precips)
        rainy_hours = sum(1 for p in precips if p >= precip_min)
        strong_hours = sum(1 for p in precips if p >= strong_rain)
        clear_hours = sum(1 for c in clouds if c <= 50)
        avg_cloud = sum(clouds) / hours if hours else 0

        # Классификация
        if strong_hours >= 2 or total_precip >= 5.0:
            label = "Пасмурно с сильными осадками"
        elif rainy_hours >= 1:
            if clear_hours > hours / 2:
                label = "Ясно или малооблачно (был кратковременный дождь)"
            else:
                label = "Пасмурно с кратковременными осадками"
        else:
            if avg_cloud <= 50:
                label = "Ясно или малооблачно"
            elif avg_cloud <= 80:
                label = "Облачно с прояснениями"
            else:
                label = "Пасмурно без осадков"

        return {"temp": second_highest_temp, "weather_label": label}

    logger.info(f"[get_weather] Запрос погоды на {date_str}")
    weather = None
    formatted_date = datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")

    weather_data = _weather_request()
    if weather_data:
        try:
            weather = _analyze_weather(weather_data)
        except Exception as e:
            logger.error(f"[get_weather] Ошибка при попытке анализа погодных данных "
                         f"за {date_str}: {weather_data} - {e}")
    return weather

async def daily_report_weather(user: User, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    user.set_state("daily_report.weather")
    text = "<b>📋 Отчёт по смене</b>\n\n⏳ Подожди, загружаю данные о погоде..."
    await BotMessage(user=user,chat_id=chat_id, text=text, reply_markup=False).edit(context)

    date = user.daily_report_draft["date"]
    weather = _get_weather(date)

    if weather:
        temp, weather_label = weather["temp"], weather["weather_label"]
        comment = f"{date}:\n🌡 <b>Температура:</b> {temp}°C\n🌤️ <b>Погодные условия:</b> {weather_label}\n\n"
        user.write_to_draft(temp=temp, weather_label=weather_label)
    else:
        user.set_state("daily_report.manual_temp")
        comment = f"Не удалось загрузить данные о погоде 😕\n"

    await BotMessage(user, chat_id, comment=comment).edit(context)

