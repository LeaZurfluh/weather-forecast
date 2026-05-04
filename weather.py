"""
weather.py — fetches and parses today's hourly forecast for London from Open-Meteo.

Open-Meteo is free and requires no API key. Documentation: https://open-meteo.com/en/docs
"""

import requests

# London coordinates
LATITUDE = 51.5074
LONGITUDE = -0.1278
TIMEZONE = "Europe/London"

# The Open-Meteo API endpoint
API_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_forecast() -> dict:
    """
    Call the Open-Meteo API and return the raw JSON response as a Python dict.

    We request four hourly variables for today only (forecast_days=1):
      - temperature_2m: air temperature at 2 metres above ground, in °C
      - apparent_temperature: "feels like" temperature accounting for wind + humidity, in °C
      - precipitation_probability: chance of precipitation each hour, as a percentage (0–100)
      - weathercode: WMO code describing the weather type (0 = clear, 61 = rain, etc.)
    """
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weathercode",
        "timezone": TIMEZONE,
        "forecast_days": 1,  # Only fetch today — keeps the data simple
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        # raise_for_status() throws an exception if the server returned an error (4xx or 5xx).
        # Without this, a failed request would silently return bad data.
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to Open-Meteo. Check your internet connection.")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: Open-Meteo returned an error: {e}")
        raise
    except requests.exceptions.Timeout:
        print("ERROR: The request to Open-Meteo timed out. Try again in a moment.")
        raise

    return response.json()


def parse_hourly(raw: dict) -> list:
    """
    Convert the raw API response into a flat list of 24 dicts, one per hour.

    The API returns parallel arrays — all indexed the same way. For example:
        raw["hourly"]["time"][3]                   == "2026-05-04T03:00"
        raw["hourly"]["temperature_2m"][3]         == 11.2
        raw["hourly"]["apparent_temperature"][3]   == 9.4
        ... and so on for index 3.

    We zip them together into a list of per-hour dicts for easier processing downstream.
    """
    hourly = raw["hourly"]

    result = []
    for i, time_str in enumerate(hourly["time"]):
        # Extract the integer hour from strings like "2026-05-04T07:00"
        # Split on "T" → ["2026-05-04", "07:00"], take "07:00", split on ":" → ["07", "00"]
        hour = int(time_str.split("T")[1].split(":")[0])

        result.append({
            "time": time_str,
            "hour": hour,
            "temperature": hourly["temperature_2m"][i],
            "apparent_temperature": hourly["apparent_temperature"][i],
            "precipitation_probability": hourly["precipitation_probability"][i],
            "weathercode": hourly["weathercode"][i],
        })

    return result  # A list of 24 dicts, one for each hour of today


def summarise_period(hours: list, period_name: str) -> dict:
    """
    Compress a list of hourly dicts for one time period into a single summary dict.

    Instead of passing raw hour-by-hour data to the advisor, we pre-compute the
    values that matter for clothing decisions:
      - avg_temp / avg_apparent: mean temperature — what the period feels like overall
      - min_temp: the coldest moment — useful for "will I freeze at any point?"
      - max_precip_prob: worst-case rain chance — if it might rain at 4pm, bring an umbrella
      - dominant_weathercode: the most common code — characterises the period's weather type

    Why dominant (most common) rather than worst-case for the weathercode?
    Using worst-case would trigger "thunderstorm" advice for an otherwise sunny day with
    one bad hour. The umbrella decision already uses max_precip_prob to catch that bad hour.
    """
    temps = [h["temperature"] for h in hours]
    apparents = [h["apparent_temperature"] for h in hours]
    precips = [h["precipitation_probability"] for h in hours]
    codes = [h["weathercode"] for h in hours]

    # most-common weathercode: max() with key=codes.count returns the value that appears most
    dominant_code = max(set(codes), key=codes.count)

    return {
        "period_name": period_name,
        "avg_temp": round(sum(temps) / len(temps), 1),
        "min_temp": min(temps),
        "avg_apparent": round(sum(apparents) / len(apparents), 1),
        "max_precip_prob": max(precips),
        "dominant_weathercode": dominant_code,
    }


def split_into_periods(hourly_list: list) -> dict:
    """
    Split the 24-hour list into three named time windows and summarise each.

    Period definitions (hours are inclusive):
      - morning:   6am–11am  (when you're getting dressed)
      - afternoon: 12pm–5pm  (midday / going out)
      - evening:   6pm–9pm   (heading home or going out)
    """
    morning_hours   = [h for h in hourly_list if 6  <= h["hour"] <= 11]
    afternoon_hours = [h for h in hourly_list if 12 <= h["hour"] <= 17]
    evening_hours   = [h for h in hourly_list if 18 <= h["hour"] <= 21]

    return {
        "morning":   summarise_period(morning_hours,   "morning"),
        "afternoon": summarise_period(afternoon_hours, "afternoon"),
        "evening":   summarise_period(evening_hours,   "evening"),
    }


def get_weather_periods() -> dict:
    """
    Public entry point. Call this from other modules.

    Returns a dict with three keys — "morning", "afternoon", "evening" — each containing
    a summary dict ready to be passed to advisor.get_recommendation().

    Example usage:
        from weather import get_weather_periods
        periods = get_weather_periods()
        print(periods["morning"]["avg_temp"])  # e.g. 11.4
    """
    raw = fetch_forecast()
    hourly_list = parse_hourly(raw)
    return split_into_periods(hourly_list)
