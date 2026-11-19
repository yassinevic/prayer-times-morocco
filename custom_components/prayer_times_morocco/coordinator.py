import json
import logging
import re
from datetime import date, timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.aiohttp_client as client
from .const import DOMAIN, PRAYERS, CITIES_MAP, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def _fetch_month_data(session: aiohttp.ClientSession, year: int, month: int, city_id: int) -> dict:
    url = f"https://www.habous.gov.ma/data/horaires-{year}-{month:02d}.js?v={city_id}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
        resp.raise_for_status()
        text = await resp.text()

    match = re.search(r"push\s*\(\s*(\{.*\})\s*\)", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])

    raise ValueError(f"Impossible d'extraire les données JSON de {url}")


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
