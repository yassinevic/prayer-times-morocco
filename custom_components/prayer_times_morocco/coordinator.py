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
    # NEW URL: horaire_hijri_2.php instead of horaire_hijri_fr.php
    url = f"https://www.habous.gov.ma/prieres/horaire_hijri_2.php?ville={city_id}"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
            resp.raise_for_status()
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # NEW: table has id="horaire", no more class="cournt"
        table = soup.find("table", id="horaire")
        if not table:
            raise ValueError("Table #horaire introuvable")

        rows = table.find_all("tr")[1:]  # skip header row

        today_str = str(today.day)
        tomorrow_str = str(tomorrow.day)

        today_times = None
        tomorrow_times = None

        for row in rows:
            cells = row.find_all("td")
            texts = [c.get_text(strip=True) for c in cells]

            # Skip rows with fewer than 9 cells or special annotation rows
            if len(texts) < 9:
                continue
            if any("حسب" in t or "المراقبة" in t for t in texts):
                continue

            # Column 2 is the Gregorian day number
            day_num = texts[2]
            if not day_num.isdigit():
                continue

            times = [texts[i][:5] for i in range(3, 9)]

            if day_num == today_str and today_times is None:
                today_times = times
            elif day_num == tomorrow_str and tomorrow_times is None:
                tomorrow_times = times

        if today_times is None:
            raise ValueError(f"Données introuvables pour aujourd'hui (jour {today_str})")

        result = {
            "city": city_name,
            "date": today.isoformat(),
            "prayers": dict(zip(PRAYERS, today_times)),
        }

        if tomorrow_times:
            result["tomorrow_date"] = tomorrow.isoformat()
            result["tomorrow_prayers"] = dict(zip(PRAYERS, tomorrow_times))
            _LOGGER.debug("Tomorrow's prayers fetched: %s", result["tomorrow_prayers"])
        else:
            # End of month: fetch next month's page
            _LOGGER.warning("No tomorrow row found (end of month) — fetching next month's table")
            try:
                next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
                next_url = (
                    f"https://www.habous.gov.ma/prieres/horaire_hijri_2.php"
                    f"?ville={city_id}&mois={next_month.month}&annee={next_month.year}"
                )
                async with session.get(next_url, timeout=aiohttp.ClientTimeout(total=15), ssl=False) as resp:
                    resp.raise_for_status()
                    next_html = await resp.text()

                next_soup = BeautifulSoup(next_html, "html.parser")
                next_table = next_soup.find("table", id="horaire")
                if next_table:
                    next_rows = next_table.find_all("tr")[1:]
                    for row in next_rows:
                        cells = row.find_all("td")
                        texts = [c.get_text(strip=True) for c in cells]
                        if len(texts) < 9 or not texts[2].isdigit():
                            continue
                        times = [texts[i][:5] for i in range(3, 9)]
                        result["tomorrow_date"] = tomorrow.isoformat()
                        result["tomorrow_prayers"] = dict(zip(PRAYERS, times))
                        _LOGGER.debug("Next month's first day prayers: %s", result["tomorrow_prayers"])
                        break

            except Exception as next_err:
                _LOGGER.warning("Could not fetch next month (%s) — falling back to today", next_err)

            if "tomorrow_prayers" not in result:
                result["tomorrow_date"] = today.isoformat()
                result["tomorrow_prayers"] = result["prayers"]

        return result

    except Exception as err:
        raise UpdateFailed(f"Erreur lors du scraping pour {city_name}: {err}") from err


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
