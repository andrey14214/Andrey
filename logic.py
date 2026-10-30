import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# 1. БАЗА ДАННЫХ КУЛЬТУР (из Excel)
# ==========================================
CROPS_DB = {
    "tomato": {
        "name": "Томат",
        "ph_min": 6.0, "ph_max": 7.0,
        "frost_sensitive": True,
        "min_temp": 15, "max_temp": 35,
        "varieties": [
            {"name": "Санька", "days": 80, "seeding_days": 45, "description": "Раннеспелый, компактный (высота 40–60 см)"},
            {"name": "Бычье сердце", "days": 125, "seeding_days": 60, "description": "Позднеспелый, крупноплодный (до 400 г)"},
            {"name": "Сливка", "days": 105, "seeding_days": 45, "description": "Раннеспелый, для консервирования (плоды 30–50 г)"}
        ]
    },
    "cucumber": {
        "name": "Огурец",
        "ph_min": 6.0, "ph_max": 7.0,
        "frost_sensitive": True,
        "min_temp": 16, "max_temp": 32,
        "varieties": [
            {"name": "Зозуля", "days": 48, "seeding_days": 25, "description": "Раннеспелый, преимущественно для теплиц (требует опыления)"},
            {"name": "Кураж", "days": 48, "seeding_days": 25, "description": "Скороспелый, партенокарпический (не требует опыления)"},
            {"name": "Герман", "days": 42, "seeding_days": 25, "description": "Ультраранний, партенокарпический (для теплиц и открытого грунта)"}
        ]
    },
    "carrot": {
        "name": "Морковь",
        "ph_min": 6.0, "ph_max": 7.0,
        "frost_sensitive": False,
        "min_temp": 8, "max_temp": 28,
        "varieties": [
            {"name": "Королева осени", "days": 125, "seeding_days": 90, "description": "Позднеспелая, для хранения (сладкая, крупная)"},
            {"name": "Нантская", "days": 95, "seeding_days": 70, "description": "Среднеспелая, сладкая, сочная"},
            {"name": "Лосиноостровская", "days": 100, "seeding_days": 70, "description": "Среднеспелая, с повышенным содержанием каротина"}
        ]
    },
    "potato": {
        "name": "Картофель",
        "ph_min": 5.0, "ph_max": 6.0,
        "frost_sensitive": True,
        "min_temp": 10, "max_temp": 28,
        "varieties": [
            {"name": "Ривьера", "days": 60, "seeding_days": 65, "description": "Ранний, устойчив к болезням"},
            {"name": "Лада", "days": 75, "seeding_days": 70, "description": "Ранний, устойчив к болезням"},
            {"name": "Пикассо", "days": 105, "seeding_days": 80, "description": "Среднеранний, устойчив к болезням"}
        ]
    }
}

# ==========================================
# 2. ИНТЕГРАЦИЯ С OPEN-METEO API
# ==========================================
CACHE_FILE = Path("weather_cache.json")
CACHE_DURATION = timedelta(hours=24)

def get_weather_from_api(lat, lon):
    """Получает реальные данные погоды с Open-Meteo API."""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m",
            "daily": ["temperature_2m_min", "temperature_2m_max"],
            "forecast_days": 14,
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current_temp = data["current"]["temperature_2m"]
        daily_min = data["daily"]["temperature_2m_min"]
        daily_max = data["daily"]["temperature_2m_max"]
        
        # Проверяем риск заморозков в ближайшие 7 дней
        frost_risk = any(temp < 2 for temp in daily_min[:7])
        
        # Средняя температура за сезон (упрощённо)
        avg_temp = sum(daily_max[:14]) / len(daily_max[:14])
        
        return {
            "current_temp": current_temp,
            "min_temp_today": daily_min[0],
            "max_temp_today": daily_max[0],
            "avg_temp_season": round(avg_temp, 1),
            "frost_risk_next_7_days": frost_risk,
            "source": "api"
        }
    except Exception as e:
        print(f"Ошибка API: {e}")
        return None

def get_cached_weather(lat, lon):
    """Получает данные из кэша, если они свежие."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        
        cached_time = datetime.fromisoformat(cache["timestamp"])
        if datetime.now() - cached_time < CACHE_DURATION:
            if abs(cache["lat"] - lat) < 0.1 and abs(cache["lon"] - lon) < 0.1:
                return cache["data"]
    return None

def save_to_cache(lat, lon, data):
    """Сохраняет данные в кэш."""
    cache = {
        "lat": lat,
        "lon": lon,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

def get_weather(lat, lon):
    """Главная функция получения погоды: кэш -> API -> fallback."""
    cached = get_cached_weather(lat, lon)
    if cached:
        cached["source"] = "cache"
        return cached
    
    api_data = get_weather_from_api(lat, lon)
    if api_data:
        save_to_cache(lat, lon, api_data)
        return api_data
    
    # Fallback на базовые данные (если API недоступен)
    print("Используем базовые данные (API недоступен)")
    return {
        "current_temp": 15.0,
        "min_temp_today": 10.0,
        "max_temp_today": 20.0,
        "avg_temp_season": 18.0,
        "frost_risk_next_7_days": False,
        "source": "fallback"
    }

# ==========================================
# 3. ОПРЕДЕЛЕНИЕ КЛИМАТИЧЕСКОЙ ЗОНЫ
# ==========================================
def get_climate_zone(lat, lon):
    """Определяет базовые агроклиматические параметры по широте."""
    if lat < 45:
        return {"zone": "Юг", "last_frost": "2024/04/15", "first_frost": "2024/10/20", "days": 180}
    elif lat < 56:
        return {"zone": "Средняя полоса", "last_frost": "2024/05/15", "first_frost": "2024/09/20", "days": 125}
    else:
        return {"zone": "Сибирь/Север", "last_frost": "2024/06/01", "first_frost": "2024/09/01", "days": 90}

# ==========================================
# 4. РАСЧЁТ ДАТ ПОСАДКИ И УРОЖАЯ
# ==========================================
def calculate_dates(crop_data, variety, climate, weather):
    """Рассчитывает даты посева рассады, высадки и урожая."""
    last_frost = datetime.strptime(climate["last_frost"], "%Y/%m/%d")
    
    # Для теплолюбивых культур ждём стабильного тепла
    if crop_data["frost_sensitive"]:
        planting_date = last_frost + timedelta(days=10)
    else:
        # Холодостойкие можно сажать раньше
        planting_date = last_frost - timedelta(days=14)
    
    # Дата посева рассады (за seeding_days до высадки)
    seeding_date = planting_date - timedelta(days=variety.get("seeding_days", 45))
    
    return {
        "seeding": seeding_date.strftime("%d %B"),
        "planting": planting_date.strftime("%d %B"),
        "harvest": (planting_date + timedelta(days=variety["days"])).strftime("%d %B")
    }

# ==========================================
# 5. ОЦЕНКА РИСКОВ
# ==========================================
def assess_risks(crop_data, soil_ph, weather, climate):
    """Оценивает риски для культуры."""
    risks = []
    
    # Проверка pH
    if soil_ph < crop_data["ph_min"]:
        risks.append({
            "level": "high",
            "text": f"Почва слишком кислая (pH {soil_ph}). Нужно раскисление.",
            "recommendation": "Внесите доломитовую муку или известь осенью (300-500 г/м²)."
        })
    elif soil_ph > crop_data["ph_max"]:
        risks.append({
            "level": "high",
            "text": f"Почва слишком щелочная (pH {soil_ph}).",
            "recommendation": "Добавьте торф или серу для подкисления."
        })
    else:
        risks.append({
            "level": "low",
            "text": "Уровень pH идеален для этой культуры.",
            "recommendation": None
        })
    
    # Проверка риска заморозков
    if crop_data["frost_sensitive"] and weather["frost_risk_next_7_days"]:
        risks.append({
            "level": "high",
            "text": "В ближайшие 7 дней возможны заморозки!",
            "recommendation": "Используйте укрывной материал или отложите высадку на 1-2 недели."
        })
    else:
        risks.append({
            "level": "low",
            "text": "Заморозков в прогнозе нет.",
            "recommendation": None
        })
    
    # Проверка температурного режима
    if weather["avg_temp_season"] < crop_data["min_temp"]:
        risks.append({
            "level": "medium",
            "text": f"Средняя температура сезона ({weather['avg_temp_season']}°C) ниже минимальной для культуры ({crop_data['min_temp']}°C).",
            "recommendation": "Рассмотрите выращивание в теплице или выберите более холодостойкий сорт."
        })
    
    return risks

# ==========================================
# 6. ГЛАВНАЯ ФУНКЦИЯ ЯДРА
# ==========================================
def calculate_recommendation(user_input):
    """
    Принимает данные от пользователя, возвращает JSON с рекомендациями.
    
    user_input = {
        "lat": 55.75,
        "lon": 37.61,
        "ph": 6.5,
        "soil_type": "loam",
        "crop": "tomato",  # или "discover" для подбора
        "mode": "check"  # или "discover"
    }
    """
    lat = user_input.get("lat", 55.75)
    lon = user_input.get("lon", 37.61)
    soil_ph = user_input.get("ph", 6.5)
    soil_type = user_input.get("soil_type", "loam")
    crop_key = user_input.get("crop", "tomato")
    mode = user_input.get("mode", "check")

    # Получаем реальную погоду
    weather = get_weather(lat, lon)
    climate = get_climate_zone(lat, lon)
    
    # Режим "Подобрать культуры"
    if mode == "discover" or crop_key == "discover":
        suitable = []
        for key, data in CROPS_DB.items():
            # Проверка pH
            if data["ph_min"] <= soil_ph <= data["ph_max"]:
                # Проверка вегетационного периода
                min_days = min([v["days"] for v in data["varieties"]])
                if min_days <= climate["days"]:
                    # Проверка температуры
                    if weather["avg_temp_season"] >= data["min_temp"]:
                        suitable.append({
                            "culture": data["name"],
                            "score": 95,
                            "reason": f"Подходит по pH ({soil_ph}) и климату ({climate['zone']}, {weather['avg_temp_season']}°C)",
                            "best_variety": data["varieties"][0]["name"]
                        })
        
        return {
            "status": "success",
            "zone": climate["zone"],
            "weather": weather,
            "crops": sorted(suitable, key=lambda x: x["score"], reverse=True)
        }

    # Режим "Проверка конкретной культуры"
    if crop_key not in CROPS_DB:
        return {"status": "error", "message": "Культура не найдена в базе"}
    
    crop_data = CROPS_DB[crop_key]
    
    # Оценка рисков
    risks = assess_risks(crop_data, soil_ph, weather, climate)
    
    # Поиск лучшего сорта
    best_variety = None
    for v in crop_data["varieties"]:
        if v["days"] <= climate["days"]:
            best_variety = v
            break
    
    # Если ни один сорт не подходит
    if not best_variety:
        min_required = min([v["days"] for v in crop_data["varieties"]])
        return {
            "status": "danger",
            "zone": climate["zone"],
            "weather": weather,
            "message": f"К сожалению, {crop_data['name']} не успеет вызреть в регионе {climate['zone']}. Доступно {climate['days']} дней, а нужно минимум {min_required}.",
            "recommendations": [
                "Рассмотрите выращивание в отапливаемой теплице",
                "Выберите другую культуру (например, морковь или картофель)"
            ]
        }
    
    # Расчёт дат
    dates = calculate_dates(crop_data, best_variety, climate, weather)
    
    # Рекомендации по типу почвы
    soil_recommendations = []
    if soil_type == "clay":
        soil_recommendations.append("Глина: добавьте песок и компост для дренажа (10-15 кг/м²).")
    elif soil_type == "sand":
        soil_recommendations.append("Песок: требуется частый полив и внесение перегноя (5-7 кг/м²).")
    elif soil_type == "chernozem":
        soil_recommendations.append("Чернозём: идеальная почва, дополнительно удобрять не требуется.")
    
    # Собираем все рекомендации
    all_recommendations = soil_recommendations
    for risk in risks:
        if risk.get("recommendation"):
            all_recommendations.append(risk["recommendation"])
    
    return {
        "status": "success",
        "zone": climate["zone"],
        "weather": weather,
        "culture": crop_data["name"],
        "best_variety": {
            "name": best_variety["name"],
            "days": best_variety["days"],
            "description": best_variety["description"]
        },
        "dates": dates,
        "risks": risks,
        "recommendations": all_recommendations
    }

# ==========================================
# ТЕСТОВЫЙ ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ 1: Москва, Томат, pH 6.5")
    print("=" * 60)
    result1 = calculate_recommendation({
        "lat": 55.75, "lon": 37.61, "ph": 6.5, "soil_type": "loam",
        "crop": "tomato", "mode": "check"
    })
    print(json.dumps(result1, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Сибирь, Перец (должен быть danger)")
    print("=" * 60)
    result2 = calculate_recommendation({
        "lat": 60.0, "lon": 90.0, "ph": 6.0, "soil_type": "clay",
        "crop": "tomato", "mode": "check"
    })
    print(json.dumps(result2, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Подбор культур для Москвы")
    print("=" * 60)
    result3 = calculate_recommendation({
        "lat": 55.75, "lon": 37.61, "ph": 6.5, "soil_type": "loam",
        "mode": "discover"
    })
    print(json.dumps(result3, ensure_ascii=False, indent=2))