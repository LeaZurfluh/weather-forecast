"""
advisor.py — rule-based outfit recommendations.

This module has no external dependencies and no imports from other project files.
You can test it on its own by passing hand-crafted period dicts to get_recommendation().

HOW TO TUNE THIS:
  - Change COLD_OFFSET to shift ALL temperature thresholds up or down in one go.
    0 = standard (average person), 2 = default (slightly cold-sensitive), 4 = very cold-sensitive
  - You can also override individual thresholds below COLD_OFFSET if you want finer control.
  - Rain and wind thresholds are separate constants further down.
"""

# ---------------------------------------------------------------------------
# COLD SENSITIVITY OFFSET (degrees Celsius)
#
# This single number is added to every standard temperature threshold.
# Raise it if the advice still feels too light; lower it (or set to 0) if it's too heavy.
#
#   0  → standard thresholds (calibrated for an average person)
#   2  → default here — slightly cold-sensitive (recommended starting point)
#   4  → noticeably cold-sensitive
# ---------------------------------------------------------------------------

COLD_OFFSET = 2  # ← change this first if advice feels too warm or too cold

# Standard baseline thresholds for an average person (°C).
# You don't normally need to touch these — adjust COLD_OFFSET instead.
_VERY_COLD_BASE = 4
_COLD_BASE      = 10
_COOL_BASE      = 15
_MILD_BASE      = 18

# Effective thresholds after applying the offset
VERY_COLD_THRESHOLD = _VERY_COLD_BASE + COLD_OFFSET  # Below: thermals + heavy jumper
COLD_THRESHOLD      = _COLD_BASE      + COLD_OFFSET  # Below: coat required
COOL_THRESHOLD      = _COOL_BASE      + COLD_OFFSET  # Below: jacket or cardigan
MILD_THRESHOLD      = _MILD_BASE      + COLD_OFFSET  # Below: at least a light layer
# Above MILD_THRESHOLD: no extra layer needed

# ---------------------------------------------------------------------------
# RAIN THRESHOLDS (precipitation_probability as a percentage, 0–100)
# ---------------------------------------------------------------------------

RAIN_LIKELY   = 50   # At or above: definitely bring umbrella
RAIN_POSSIBLE = 30   # At or above: umbrella just in case

# ---------------------------------------------------------------------------
# WIND CHILL SENSITIVITY
# If apparent_temperature is this many degrees below avg_temp, add a wind warning.
# e.g. 18°C actual but 14°C apparent → feels much colder, worth noting.
# ---------------------------------------------------------------------------

WIND_CHILL_DIFF = 3


# ---------------------------------------------------------------------------
# WEATHERCODE CLASSIFICATION
# Open-Meteo uses WMO (World Meteorological Organisation) weather codes.
# Full list: https://open-meteo.com/en/docs#weathervariables
# ---------------------------------------------------------------------------

def classify_weathercode(code: int) -> str:
    """
    Map a WMO numeric code to a plain-English category string.

    Returns one of: "clear", "cloudy", "fog", "drizzle", "freezing_drizzle",
    "rain", "freezing_rain", "snow", "showers", "snow_showers", "thunderstorm", "hail"

    If we receive an unknown code, we default to "cloudy" — a safe, non-alarmist fallback.
    """
    if code == 0:
        return "clear"
    elif code in (1, 2, 3):
        return "cloudy"
    elif code in (45, 48):
        return "fog"
    elif code in (51, 53, 55):
        return "drizzle"
    elif code in (56, 57):
        return "freezing_drizzle"
    elif code in (61, 63, 65):
        return "rain"
    elif code in (66, 67):
        return "freezing_rain"
    elif code in (71, 73, 75, 77):
        return "snow"
    elif code in (80, 81, 82):
        return "showers"
    elif code in (85, 86):
        return "snow_showers"
    elif code == 95:
        return "thunderstorm"
    elif code in (96, 99):
        # Officially "thunderstorm with hail" — mainly Central Europe, but still severe
        return "hail"
    else:
        return "cloudy"  # Unknown code — default to cloudy


# Emoji for each weather category — used in the notification header
WEATHER_EMOJI = {
    "clear":            "☀️",
    "cloudy":           "☁️",
    "fog":              "🌫️",
    "drizzle":          "🌦️",
    "freezing_drizzle": "🌧️",
    "rain":             "🌧️",
    "freezing_rain":    "🌨️",
    "snow":             "❄️",
    "showers":          "🌦️",
    "snow_showers":     "🌨️",
    "thunderstorm":     "⛈️",
    "hail":             "🌩️",
}

# Emoji for the time of day
PERIOD_EMOJI = {
    "morning":   "🌅",
    "afternoon": "☀️",
    "evening":   "🌆",
}

# Emoji for temperature feel — keyed by threshold bucket
def _temp_emoji(avg_apparent: float) -> str:
    if avg_apparent < VERY_COLD_THRESHOLD:
        return "🥶"
    elif avg_apparent < COLD_THRESHOLD:
        return "🧥"
    elif avg_apparent < COOL_THRESHOLD:
        return "🧣"
    elif avg_apparent < MILD_THRESHOLD:
        return "🌤️"
    else:
        return "🌸"


# ---------------------------------------------------------------------------
# CLOTHING LOGIC
# Each function handles one "layer" of the outfit independently.
# All temperature comparisons use avg_apparent (feels-like), not raw temperature,
# because perceived temperature is more actionable for dressing decisions.
# ---------------------------------------------------------------------------

def recommend_base_layer(avg_apparent: float) -> str:
    """Return a description of what to wear closest to the skin."""
    if avg_apparent < VERY_COLD_THRESHOLD:
        return "thermal underlayer + heavy jumper"
    elif avg_apparent < COLD_THRESHOLD:
        return "warm jumper or fleece"
    elif avg_apparent < COOL_THRESHOLD:
        return "light-to-mid jumper or thick cardigan"
    elif avg_apparent < MILD_THRESHOLD:
        return "light cardigan or long-sleeve top"
    else:
        return "short-sleeve top or light blouse"


def recommend_outer_layer(avg_apparent: float, weather_category: str) -> str:
    """Return a coat/jacket recommendation, taking weather type into account."""

    # Frozen or severe precipitation always calls for a heavy coat regardless of temperature
    if weather_category in ("snow", "snow_showers", "freezing_rain", "freezing_drizzle"):
        return "heavy winter coat (waterproof if possible)"

    if weather_category in ("thunderstorm", "hail"):
        return "waterproof coat — severe weather expected"

    # For everything else, base the decision on how cold it feels
    if avg_apparent < COLD_THRESHOLD:
        return "heavy coat"
    elif avg_apparent < COOL_THRESHOLD:
        return "jacket or warm coat"
    elif avg_apparent < MILD_THRESHOLD:
        return "light jacket"
    else:
        return "no coat needed"


def recommend_rain_gear(max_precip_prob: int, weather_category: str) -> str:
    """
    Return an umbrella/waterproof recommendation, or an empty string if none needed.

    Weather categories that imply rain always warrant an umbrella, regardless of
    the probability number (the code already tells us it's raining).
    """
    # These categories mean it IS raining or drizzling — umbrella is certain
    wet_categories = ("rain", "showers", "drizzle", "thunderstorm", "hail",
                      "freezing_rain", "freezing_drizzle")

    if weather_category in wet_categories:
        return "bring umbrella — rain expected"
    elif max_precip_prob >= RAIN_LIKELY:
        return "bring umbrella — high chance of rain"
    elif max_precip_prob >= RAIN_POSSIBLE:
        return "umbrella just in case"
    else:
        return ""  # No rain gear note — leave blank, caller will skip it


def recommend_extras(avg_apparent: float, weather_category: str) -> list:
    """
    Return a list of extra items/notes that don't fit the base/outer layer buckets.
    Returns an empty list when there's nothing to add.
    """
    extras = []

    # Cold-weather accessories
    if avg_apparent < COLD_THRESHOLD:
        extras.append("warm scarf")
        extras.append("gloves")
        extras.append("beanie or warm hat")
    elif avg_apparent < COOL_THRESHOLD:
        extras.append("scarf (optional)")

    # Condition-specific extras
    if weather_category == "fog":
        extras.append("allow extra travel time — foggy conditions")
    elif weather_category in ("snow", "snow_showers"):
        extras.append("waterproof boots or warm wellies")
        extras.append("extra layers — snow expected")

    return extras


# ---------------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------------

def get_recommendation(period: dict) -> str:
    """
    Given a period summary dict (from weather.summarise_period), return a
    formatted multi-line outfit recommendation string.

    Expected keys in period:
        period_name, avg_temp, min_temp, avg_apparent, max_precip_prob, dominant_weathercode

    Example output:
        Morning (avg 11.2°C, feels like 8.9°C) — cloudy, rain 72%
        Base layer:  warm jumper or fleece
        Outer layer: jacket or warm coat
        Rain gear:   bring umbrella — high chance of rain
        Extras:      scarf (optional)
    """
    period_name   = period["period_name"].capitalize()
    avg_temp      = period["avg_temp"]
    avg_apparent  = period["avg_apparent"]
    max_precip    = period["max_precip_prob"]
    code          = period["dominant_weathercode"]

    weather_category = classify_weathercode(code)

    # Build each recommendation component
    base   = recommend_base_layer(avg_apparent)
    outer  = recommend_outer_layer(avg_apparent, weather_category)
    rain   = recommend_rain_gear(max_precip, weather_category)
    extras = recommend_extras(avg_apparent, weather_category)

    # Pick emojis
    w_emoji = WEATHER_EMOJI.get(weather_category, "🌡️")
    p_emoji = PERIOD_EMOJI.get(period["period_name"], "🕐")
    t_emoji = _temp_emoji(avg_apparent)

    # --- Assemble the output string ---

    # Header line: period name, temperatures, weather type at a glance
    header = (
        f"{p_emoji} {period_name} {t_emoji} {avg_temp}°C (feels like {avg_apparent}°C)"
        f" {w_emoji} {weather_category.replace('_', ' ')}"
    )
    # Append rain probability if it's notable (30%+)
    if max_precip >= RAIN_POSSIBLE:
        header += f" · 🌂 {max_precip}%"

    lines = [
        header,
        f"  👕 Base:  {base}",
        f"  🧥 Outer: {outer}",
    ]

    if rain:
        lines.append(f"  ☂️  Rain:  {rain}")

    if extras:
        lines.append(f"  ✨ Extra: {', '.join(extras)}")

    # Wind chill note: if it feels significantly colder than the actual temperature
    if avg_temp - avg_apparent >= WIND_CHILL_DIFF:
        lines.append(
            f"  💨 Feels {avg_temp - avg_apparent:.1f}°C colder than it looks"
            f" — consider an extra layer"
        )

    return "\n".join(lines)
