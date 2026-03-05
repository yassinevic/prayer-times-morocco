import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import date
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
        
        current_tr = soup.find("tr", class_="cournt")
        if not current_tr:
            raise ValueError(f"Données introuvables pour aujourd'hui")
            
        cells = current_tr.find_all("td")
        if len(cells) >= 9:
            times = [c.get_text(strip=True)[:5] for c in cells[3:9]]
            return {
                "city": city_name,
                "date": today.isoformat(),
                "prayers": dict(zip(PRAYERS, times))
            }

        raise ValueError("Format de table invalide")
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
