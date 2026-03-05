import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.aiohttp_client as client

from .const import DOMAIN, CITIES_MAP
from .coordinator import fetch_prayer_times

_LOGGER = logging.getLogger(__name__)

class PrayerTimesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Morocco Prayer Times."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            city = user_input["city"]
            city_id = CITIES_MAP.get(city)

            try:
                # Test scraping before accepting
                session = client.async_get_clientsession(self.hass)
                await fetch_prayer_times(session, city_id, city)
                
                await self.async_set_unique_id(city)
                self._abort_if_unique_id_configured()
                
                from .const import CITY_TRANSLATIONS
                display_city = city
                if user_input.get("language") == "arabic":
                    display_city = CITY_TRANSLATIONS.get(city, city)
                    
                return self.async_create_entry(title=f"Morocco Prayer Times - {display_city}", data=user_input)
            except Exception as e:
                _LOGGER.error("Erreur de test de connexion : %s", e)
                errors["base"] = "cannot_connect"

        # Generate SelectSelector options alphabetically
        options = [city for city in sorted(CITIES_MAP.keys())]

        data_schema = vol.Schema({
            vol.Required("city", default="Casablanca"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("language", default="english"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["english", "arabic"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
