import json
import re
from datetime import date, timedelta

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from langgraph_outdoor_activity_agent.utils import get_env_var


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class GeocodeInput(BaseModel):
    """Schema for the geocode location tool input."""

    location: str = Field(
        description="The place name to geocode, e.g. 'Colorado', 'Denver, CO', 'Yosemite National Park'"
    )


class WeatherInput(BaseModel):
    """Schema for the weather forecast tool input."""

    latitude: float = Field(description="Latitude of the location (WGS84)")
    longitude: float = Field(description="Longitude of the location (WGS84)")
    forecast_days: int = Field(
        default=7,
        description="Number of forecast days (1-16, default 7)",
    )
    timezone: str = Field(
        default="auto",
        description="Timezone for daily data, e.g. 'America/Denver'. Use 'auto' for automatic detection.",
    )


class AirQualityInput(BaseModel):
    """Schema for the air quality tool input."""

    latitude: float = Field(description="Latitude of the location (WGS84)")
    longitude: float = Field(description="Longitude of the location (WGS84)")
    forecast_days: int = Field(
        default=5,
        description="Number of forecast days (1-7, default 5)",
    )
    timezone: str = Field(
        default="auto",
        description="Timezone, e.g. 'America/Denver'. Use 'auto' for automatic detection.",
    )


class SunriseSunsetInput(BaseModel):
    """Schema for the sunrise/sunset tool input."""

    latitude: float = Field(description="Latitude of the location (WGS84)")
    longitude: float = Field(description="Longitude of the location (WGS84)")
    date_str: str = Field(description="The specific date in YYYY-MM-DD format, e.g. '2026-03-07'. Can also use 'today' or 'tomorrow'.")
    timezone: str = Field(
        default="auto",
        description="Timezone, e.g. 'America/Denver'. Use 'auto' for automatic detection.",
    )


class NationalParksInput(BaseModel):
    """Schema for the search national parks tool input."""

    state_code: str = Field(
        default="",
        description="Two-letter state code to filter parks, e.g. 'CO' for Colorado, 'CA' for California. Leave empty to search all states.",
    )
    query: str = Field(
        default="",
        description="Search term to filter parks by name or activity, e.g. 'hiking', 'Yellowstone'.",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of parks to return (default 5).",
    )


class ParkAlertsInput(BaseModel):
    """Schema for the get park alerts tool input."""

    park_code: str = Field(
        description="The NPS park code, e.g. 'romo' for Rocky Mountain, 'yose' for Yosemite."
    )
    limit: int = Field(
        default=10,
        description="Maximum number of alerts to return (default 10).",
    )


# ---------------------------------------------------------------------------
# Tool 1 — Geocode Location (Open-Meteo Geocoding API)
# ---------------------------------------------------------------------------


@tool("geocode_location", args_schema=GeocodeInput)
def geocode_location(location: str) -> str:
    """Convert a place name to geographic coordinates (latitude, longitude, timezone).

    Always call this tool first to get coordinates needed by the weather,
    air quality, and sunrise/sunset tools.

    Args:
        location: The place name to geocode.

    Returns:
        JSON string with coordinates, timezone, and location details.
    """
    # Strip state/country suffixes like "Denver, CO" -> "Denver"
    # Open-Meteo geocoding works better with just the city name
    clean_location = re.split(r"[,;]", location)[0].strip()

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": clean_location, "count": 5, "language": "en", "format": "json"}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])

        # If the original input had a state/country hint, try to filter results
        location_lower = location.lower()
        if "," in location and results:
            hint = location.split(",", 1)[1].strip().upper()
            filtered = [
                r for r in results
                if hint in (r.get("admin1", "") or "").upper()
                or hint in (r.get("country_code", "") or "").upper()
                or hint in (r.get("country", "") or "").upper()
            ]
            if filtered:
                results = filtered

        if not results:
            return json.dumps(
                {"error": f"No locations found for '{location}'. Try a more specific name like 'Denver' instead of 'Denver, CO'."}
            )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "name": r.get("name"),
                    "latitude": r.get("latitude"),
                    "longitude": r.get("longitude"),
                    "elevation": r.get("elevation"),
                    "timezone": r.get("timezone"),
                    "country": r.get("country"),
                    "state": r.get("admin1"),
                }
            )

        return json.dumps({"top_result": formatted[0], "alternatives": formatted[1:]})

    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"Geocoding API error (HTTP {e.response.status_code}): {e.response.text}"}
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Geocoding request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error during geocoding: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 2 — Weather Forecast (Open-Meteo Forecast API)
# ---------------------------------------------------------------------------


@tool("get_weather_forecast", args_schema=WeatherInput)
def get_weather_forecast(
    latitude: float,
    longitude: float,
    forecast_days: int = 7,
    timezone: str = "auto",
) -> str:
    """Get daily weather forecast including temperature, precipitation, wind, and UV index.

    Call this after geocoding to assess weather conditions for outdoor activities.

    Args:
        latitude: Latitude of the location (WGS84).
        longitude: Longitude of the location (WGS84).
        forecast_days: Number of forecast days (1-16, default 7).
        timezone: Timezone string, e.g. 'America/Denver'. Use 'auto' for automatic.

    Returns:
        JSON string with daily forecast data for each day.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max,"
            "wind_speed_10m_max,wind_gusts_10m_max,"
            "uv_index_max,weathercode"
        ),
        "timezone": timezone,
        "forecast_days": min(max(forecast_days, 1), 16),
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})
        units = data.get("daily_units", {})
        days = []

        for i, day_date in enumerate(daily.get("time", [])):
            days.append(
                {
                    "date": day_date,
                    "temp_max": daily.get("temperature_2m_max", [None])[i],
                    "temp_min": daily.get("temperature_2m_min", [None])[i],
                    "precipitation_sum_mm": daily.get("precipitation_sum", [None])[i],
                    "precipitation_probability_pct": daily.get(
                        "precipitation_probability_max", [None]
                    )[i],
                    "wind_speed_max_kmh": daily.get("wind_speed_10m_max", [None])[i],
                    "wind_gusts_max_kmh": daily.get("wind_gusts_10m_max", [None])[i],
                    "uv_index_max": daily.get("uv_index_max", [None])[i],
                    "weather_code": daily.get("weathercode", [None])[i],
                }
            )

        return json.dumps(
            {
                "location": {
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                },
                "timezone": data.get("timezone"),
                "units": {
                    "temperature": units.get("temperature_2m_max", "°C"),
                    "precipitation": units.get("precipitation_sum", "mm"),
                    "wind_speed": units.get("wind_speed_10m_max", "km/h"),
                },
                "daily_forecast": days,
            }
        )

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Weather API error (HTTP {e.response.status_code})"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Weather request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected weather error: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 3 — Air Quality (Open-Meteo Air Quality API)
# ---------------------------------------------------------------------------


@tool("get_air_quality", args_schema=AirQualityInput)
def get_air_quality(
    latitude: float,
    longitude: float,
    forecast_days: int = 5,
    timezone: str = "auto",
) -> str:
    """Get air quality index (AQI) and pollutant data for outdoor activity safety.

    Provides daily max AQI values aggregated from hourly data. AQI above 100
    is concerning for strenuous outdoor activity.

    Args:
        latitude: Latitude of the location (WGS84).
        longitude: Longitude of the location (WGS84).
        forecast_days: Number of forecast days (1-7, default 5).
        timezone: Timezone string, e.g. 'America/Denver'. Use 'auto' for automatic.

    Returns:
        JSON string with daily air quality summaries and AQI interpretation guide.
    """
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "us_aqi,us_aqi_pm2_5,us_aqi_pm10,uv_index,dust",
        "timezone": timezone,
        "forecast_days": min(max(forecast_days, 1), 7),
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])

        # Aggregate hourly data to daily max values
        daily_data: dict[str, dict[str, list]] = {}
        for i, t in enumerate(times):
            day = t[:10]  # Extract YYYY-MM-DD
            if day not in daily_data:
                daily_data[day] = {
                    "us_aqi": [],
                    "us_aqi_pm2_5": [],
                    "us_aqi_pm10": [],
                    "uv_index": [],
                    "dust": [],
                }

            for key in daily_data[day]:
                vals = hourly.get(key, [])
                val = vals[i] if i < len(vals) else None
                if val is not None:
                    daily_data[day][key].append(val)

        daily_summaries = []
        for day_date in sorted(daily_data.keys()):
            vals = daily_data[day_date]
            daily_summaries.append(
                {
                    "date": day_date,
                    "max_us_aqi": max(vals["us_aqi"]) if vals["us_aqi"] else None,
                    "max_us_aqi_pm2_5": max(vals["us_aqi_pm2_5"])
                    if vals["us_aqi_pm2_5"]
                    else None,
                    "max_us_aqi_pm10": max(vals["us_aqi_pm10"])
                    if vals["us_aqi_pm10"]
                    else None,
                    "max_uv_index": max(vals["uv_index"]) if vals["uv_index"] else None,
                    "max_dust": max(vals["dust"]) if vals["dust"] else None,
                }
            )

        return json.dumps(
            {
                "daily_air_quality": daily_summaries,
                "aqi_scale": {
                    "0-50": "Good",
                    "51-100": "Moderate",
                    "101-150": "Unhealthy for Sensitive Groups",
                    "151-200": "Unhealthy",
                    "201-300": "Very Unhealthy",
                    "301+": "Hazardous",
                },
            }
        )

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Air Quality API error (HTTP {e.response.status_code})"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Air quality request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected air quality error: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 4 — Sunrise / Sunset (Open-Meteo Forecast API)
# ---------------------------------------------------------------------------


@tool("get_sunrise_sunset", args_schema=SunriseSunsetInput)
def get_sunrise_sunset(
    latitude: float,
    longitude: float,
    date_str: str,
    timezone: str = "auto",
) -> str:
    """Get sunrise, sunset, and daylight duration for a specific date.

    Use this to determine the best start time for outdoor activities and
    available daylight hours.

    Args:
        latitude: Latitude of the location (WGS84).
        longitude: Longitude of the location (WGS84).
        date_str: The date in YYYY-MM-DD format, e.g. '2026-03-07'. Can also use 'today' or 'tomorrow'.
        timezone: Timezone string, e.g. 'America/Denver'. Use 'auto' for automatic.

    Returns:
        JSON string with sunrise, sunset, daylight duration, and sunshine duration.
    """
    # Validate and parse the date - handle common LLM mistakes
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            parsed_date = date_str
        elif date_str.lower() in ("today", "now"):
            parsed_date = date.today().isoformat()
        elif date_str.lower() in ("tomorrow",):
            parsed_date = (date.today() + timedelta(days=1)).isoformat()
        else:
            return json.dumps(
                {"error": f"Invalid date format '{date_str}'. Use YYYY-MM-DD format, e.g. '2026-03-07'. Today is {date.today().isoformat()}."}
            )
    except Exception:
        return json.dumps(
            {"error": f"Could not parse date '{date_str}'. Use YYYY-MM-DD format. Today is {date.today().isoformat()}."}
        )

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "sunrise,sunset,daylight_duration,sunshine_duration",
        "timezone": timezone,
        "start_date": parsed_date,
        "end_date": parsed_date,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})

        daylight_secs = daily.get("daylight_duration", [0])[0] or 0
        sunshine_secs = daily.get("sunshine_duration", [0])[0] or 0

        daylight_hours = int(daylight_secs // 3600)
        daylight_mins = int((daylight_secs % 3600) // 60)
        sunshine_hours = int(sunshine_secs // 3600)
        sunshine_mins = int((sunshine_secs % 3600) // 60)

        return json.dumps(
            {
                "date": parsed_date,
                "sunrise": daily.get("sunrise", [None])[0],
                "sunset": daily.get("sunset", [None])[0],
                "daylight_duration": f"{daylight_hours}h {daylight_mins}m",
                "sunshine_duration": f"{sunshine_hours}h {sunshine_mins}m",
                "daylight_seconds": daylight_secs,
                "sunshine_seconds": sunshine_secs,
            }
        )

    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"Sunrise/Sunset API error (HTTP {e.response.status_code})"}
        )
    except httpx.RequestError as e:
        return json.dumps({"error": f"Sunrise/sunset request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected sunrise/sunset error: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 5 — Search National Parks (NPS API)
# ---------------------------------------------------------------------------


@tool("search_national_parks", args_schema=NationalParksInput)
def search_national_parks(
    state_code: str = "",
    query: str = "",
    limit: int = 5,
) -> str:
    """Search for national parks by state and/or activity keyword.

    Returns park details including coordinates, activities, and weather info.
    Use the parkCode from results to call get_park_alerts.

    Args:
        state_code: Two-letter state code, e.g. 'CO' for Colorado.
        query: Search term, e.g. 'hiking' or 'Yellowstone'.
        limit: Maximum number of parks to return (default 5).

    Returns:
        JSON string with matching parks and their details.
    """
    nps_api_key = get_env_var("NPS_API_KEY")
    if not nps_api_key:
        return json.dumps(
            {
                "error": "NPS_API_KEY environment variable is not set. "
                "Get a free key at https://developer.nps.gov"
            }
        )

    url = "https://developer.nps.gov/api/v1/parks"
    params = {"limit": min(max(limit, 1), 50)}
    headers = {"X-Api-Key": nps_api_key}

    if state_code:
        params["stateCode"] = state_code
    if query:
        params["q"] = query

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        parks = []
        for p in data.get("data", []):
            activities = [a.get("name") for a in p.get("activities", []) if a.get("name")]
            parks.append(
                {
                    "parkCode": p.get("parkCode"),
                    "fullName": p.get("fullName"),
                    "description": p.get("description"),
                    "states": p.get("states"),
                    "latitude": p.get("latitude"),
                    "longitude": p.get("longitude"),
                    "activities": activities[:15],  # Limit to avoid overwhelming context
                    "weatherInfo": p.get("weatherInfo"),
                    "url": p.get("url"),
                }
            )

        return json.dumps({"total": data.get("total"), "parks": parks})

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"NPS API error (HTTP {e.response.status_code}): {e.response.text}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"NPS request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected NPS error: {str(e)}"})


# ---------------------------------------------------------------------------
# Tool 6 — Park Alerts (NPS API)
# ---------------------------------------------------------------------------


@tool("get_park_alerts", args_schema=ParkAlertsInput)
def get_park_alerts(park_code: str, limit: int = 10) -> str:
    """Get active alerts for a specific national park.

    Returns closures, cautions, and other safety information. Call this
    after search_national_parks to check conditions at a recommended park.

    Args:
        park_code: The NPS park code, e.g. 'romo' for Rocky Mountain.
        limit: Maximum number of alerts to return (default 10).

    Returns:
        JSON string with active alerts for the park.
    """
    if not park_code or park_code.lower() in ("null", "none", ""):
        return json.dumps(
            {"error": "park_code is required. Use a code from search_national_parks results, e.g. 'romo' for Rocky Mountain."}
        )

    nps_api_key = get_env_var("NPS_API_KEY")
    if not nps_api_key:
        return json.dumps(
            {
                "error": "NPS_API_KEY environment variable is not set. "
                "Get a free key at https://developer.nps.gov"
            }
        )

    url = "https://developer.nps.gov/api/v1/alerts"
    params = {"parkCode": park_code, "limit": min(max(limit, 1), 50)}
    headers = {"X-Api-Key": nps_api_key}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        alerts = []
        for a in data.get("data", []):
            alerts.append(
                {
                    "title": a.get("title"),
                    "category": a.get("category"),
                    "description": a.get("description"),
                    "parkCode": a.get("parkCode"),
                }
            )

        return json.dumps(
            {
                "total": data.get("total"),
                "park_code": park_code,
                "alerts": alerts,
            }
        )

    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"NPS Alerts API error (HTTP {e.response.status_code}): {e.response.text}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"NPS alerts request failed: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected NPS alerts error: {str(e)}"})
