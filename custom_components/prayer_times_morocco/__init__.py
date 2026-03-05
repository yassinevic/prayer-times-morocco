import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import PrayerTimesCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Morocco Prayer Times from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = PrayerTimesCoordinator(
        hass, 
        entry.data["city"], 
        entry.data.get("language", "english")
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Allow forced refresh via a custom service
    async def handle_refresh(call):
        """Handle the refresh service call."""
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "refresh", handle_refresh)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
