import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import date, timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.helpers.aiohttp_client as client
from .const import DOMAIN, PRAYERS, CITIES_MAP, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def fetch_prayer_times(session: aiohttp.ClientSession, city_id: int, city_name: str) -> dict:
    url = f"https://www.habous.gov.ma/prieres/horaire_hijri_fr.php?ville={city_id}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
            resp.raise_for_status()
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Find today's row
        current_tr = soup.find("tr", class_="cournt")
        if not current_tr:
            raise ValueError("Données introuvables pour aujourd'hui")

        cells = current_tr.find_all("td")
        if len(cells) < 9:
            raise ValueError("Format de table invalide")

        today_times = [c.get_text(strip=True)[:5] for c in cells[3:9]]
        result = {
            "city": city_name,
            "date": today.isoformat(),
            "prayers": dict(zip(PRAYERS, today_times)),
        }

        # Tomorrow's row is the next sibling <tr> after today's
        tomorrow_tr = current_tr.find_next_sibling("tr")
        if tomorrow_tr:
            tomorrow_cells = tomorrow_tr.find_all("td")
            if len(tomorrow_cells) >= 9:
                tomorrow_times = [c.get_text(strip=True)[:5] for c in tomorrow_cells[3:9]]
                result["tomorrow_date"] = tomorrow.isoformat()
                result["tomorrow_prayers"] = dict(zip(PRAYERS, tomorrow_times))
                _LOGGER.debug("Tomorrow's prayers fetched: %s", result["tomorrow_prayers"])
            else:
                _LOGGER.warning("Tomorrow's row found but has unexpected format — falling back to today's prayers")
                result["tomorrow_date"] = today.isoformat()
                result["tomorrow_prayers"] = result["prayers"]
        else:
            # Last day of the month — try fetching next month's page for the first row
            _LOGGER.warning("No tomorrow row found (end of month) — fetching next month's table")
            try:
                next_month = today.replace(day=1) + timedelta(days=32)
                next_month_url = f"https://www.habous.gov.ma/prieres/horaire_hijri_fr.php?ville={city_id}&mois={next_month.month}&annee={next_month.year}"
                async with session.get(next_month_url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
                    resp.raise_for_status()
                    next_html = await resp.text()
                next_soup = BeautifulSoup(next_html, "html.parser")
                # First data row of next month
                first_tr = next_soup.find("tr", class_="cournt") or next_soup.find("table").find_all("tr")[1]
                if first_tr:
                    first_cells = first_tr.find_all("td")
                    if len(first_cells) >= 9:
                        tomorrow_times = [c.get_text(strip=True)[:5] for c in first_cells[3:9]]
                        result["tomorrow_date"] = tomorrow.isoformat()
                        result["tomorrow_prayers"] = dict(zip(PRAYERS, tomorrow_times))
                        _LOGGER.debug("Next month's first day prayers fetched: %s", result["tomorrow_prayers"])
                    else:
                        raise ValueError("Format de table invalide pour le mois suivant")
            except Exception as next_err:
                # Safe fallback — use today's prayers rather than leaving tomorrow empty
                _LOGGER.warning("Could not fetch next month's prayers (%s) — falling back to today's prayers", next_err)
                result["tomorrow_date"] = today.isoformat()
                result["tomorrow_prayers"] = result["prayers"]

        return result

    except Exception as err:
        raise UpdateFailed(f"Erreur lors du scraping pour {city_name}: {err}") from err


class PrayerTimesCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Morocco Prayer Times data."""

    def __init__(self, hass: HomeAssistant, city: str, language: str = "english"):
        """Initialize."""
        self.city = city
        self.city_id = CITIES_MAP.get(city, 58)  # Default Casablanca
        self.language = language

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Habous site."""
        session = client.async_get_clientsession(self.hass)
        return await fetch_prayer_times(session, self.city_id, self.city)