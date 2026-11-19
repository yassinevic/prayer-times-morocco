import asyncio
import json
import logging
import os
import re
from datetime import date, timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.aiohttp_client as client
from .const import DOMAIN, PRAYERS, CITIES_MAP, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data")


def _save_cache(month: int, data: dict) -> None:
    """Save month prayer data to local disk cache named after the month."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        file_path = os.path.join(CACHE_DIR, f"horaires-{month:02d}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _LOGGER.debug("Cached prayer times for month %02d to %s", month, file_path)
    except Exception as err:
        _LOGGER.warning("Could not save local cache for month %02d: %s", month, err)


def _load_cache(month: int) -> dict | None:
    """Load month prayer data from local disk cache if available."""
    paths_to_check = [
        os.path.join(CACHE_DIR, f"horaires-{month:02d}.json"),
        os.path.join(CACHE_DIR, f"{month:02d}.json"),
        os.path.join(CACHE_DIR, f"horaires-{month}.json"),
        os.path.join(CACHE_DIR, f"{month}.json"),
    ]
    for path in paths_to_check:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _LOGGER.info("Loaded prayer times for month %02d from local cache: %s", month, path)
                return data
            except Exception as err:
                _LOGGER.warning("Failed to read cache file %s: %s", path, err)
    return None


async def _fetch_month_data(session: aiohttp.ClientSession, year: int, month: int, city_id: int) -> dict:
    url = f"https://www.habous.gov.ma/data/horaires-{year}-{month:02d}.js?v={city_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    text = None
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
            resp.raise_for_status()
            text = await resp.text(encoding="utf-8")
    except Exception as err:
        _LOGGER.debug("Fetch with ssl=False failed (%s), retrying with default SSL context", err)
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                text = await resp.text(encoding="utf-8")
        except Exception as retry_err:
            _LOGGER.warning("Network request to Habous failed (%s) — falling back to local cache", retry_err)

    if text is not None:
        try:
            match = re.search(r"push\s*\(\s*(\{.*\})\s*\)", text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
            else:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start != -1 and end > start:
                    data = json.loads(text[start:end])
                else:
                    raise ValueError(f"Impossible d'extraire les données JSON de {url}")

            # Persist to local disk cache asynchronously
            await asyncio.to_thread(_save_cache, month, data)
            return data
        except Exception as parse_err:
            _LOGGER.warning("Failed to parse remote response (%s) — falling back to local cache", parse_err)

    # Fallback to local disk cache if offline or parse error
    cached_data = await asyncio.to_thread(_load_cache, month)
    if cached_data is not None:
        return cached_data

    raise ValueError(f"Impossible de récupérer les horaires pour le mois {month} (site injoignable et aucun cache local disponible)")


def _extract_city_prayers(month_data: dict, city_id: int, city_name: str, day: int) -> list:
    villes = month_data.get("villes", [])
    city_data = next((v for v in villes if v.get("c") == city_id or str(v.get("c")) == str(city_id)), None)
    if not city_data:
        raise ValueError(f"Ville avec l'identifiant {city_id} ({city_name}) introuvable")

    days = city_data.get("h", [])
    day_idx = day - 1
    if day_idx < 0 or day_idx >= len(days):
        raise ValueError(f"Données introuvables pour le jour {day} (total jours: {len(days)})")

    times = [t[:5] for t in days[day_idx]]
    if len(times) < len(PRAYERS):
        raise ValueError(f"Horaires incomplets pour le jour {day}: {times}")

    return times


async def fetch_prayer_times(session: aiohttp.ClientSession, city_id: int, city_name: str) -> dict:
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Fetch current month data
        month_data = await _fetch_month_data(session, today.year, today.month, city_id)
        today_times = _extract_city_prayers(month_data, city_id, city_name, today.day)

        result = {
            "city": city_name,
            "date": today.isoformat(),
            "prayers": dict(zip(PRAYERS, today_times)),
        }

        # Check if tomorrow is in the same month
        if tomorrow.month == today.month:
            tomorrow_times = _extract_city_prayers(month_data, city_id, city_name, tomorrow.day)
            result["tomorrow_date"] = tomorrow.isoformat()
            result["tomorrow_prayers"] = dict(zip(PRAYERS, tomorrow_times))
            _LOGGER.debug("Tomorrow's prayers fetched (same month): %s", result["tomorrow_prayers"])
        else:
            # End of month: fetch next month's data file
            _LOGGER.warning("End of month reached — fetching next month's data")
            try:
                next_month_data = await _fetch_month_data(session, tomorrow.year, tomorrow.month, city_id)
                tomorrow_times = _extract_city_prayers(next_month_data, city_id, city_name, tomorrow.day)
                result["tomorrow_date"] = tomorrow.isoformat()
                result["tomorrow_prayers"] = dict(zip(PRAYERS, tomorrow_times))
                _LOGGER.debug("Next month's first day prayers fetched: %s", result["tomorrow_prayers"])
            except Exception as next_err:
                _LOGGER.warning("Could not fetch next month (%s) — falling back to today: %s", tomorrow.strftime("%Y-%m"), next_err)
                result["tomorrow_date"] = today.isoformat()
                result["tomorrow_prayers"] = result["prayers"]

        return result

    except Exception as err:
        raise UpdateFailed(f"Erreur lors de la récupération des horaires pour {city_name}: {err}") from err


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Morocco Prayer Times data."""

    def __init__(self, hass: HomeAssistant, city: str, language: str = "english"):
        self.city = city
        self.city_id = CITIES_MAP.get(city, 58)
        self.language = language
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        session = client.async_get_clientsession(self.hass)
        return await fetch_prayer_times(session, self.city_id, self.city)
