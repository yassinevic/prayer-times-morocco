from unittest.mock import patch, MagicMock
from homeassistant.core import HomeAssistant
from custom_components.prayer_times_morocco.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Morocco Prayer Times - Casablanca",
        data={"city": "Casablanca", "language": "english"},
        entry_id="test_id",
    )
    entry.add_to_hass(hass)

    mock_data = {
        "city": "Casablanca",
        "date": "2026-03-04",
        "prayers": {
            "fajr": "05:15",
            "chourouk": "06:42",
            "dohr": "13:10",
            "asr": "16:35",
            "maghrib": "19:38",
            "ichaa": "21:00"
        }
    }

    with patch(
        "custom_components.prayer_times_morocco.coordinator.fetch_prayer_times",
        return_value=mock_data,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Check sensors are created properly
    state = hass.states.get("sensor.prayer_fajr")
    assert state
    assert state.state == "05:15"

    state = hass.states.get("sensor.prayer_city")
    assert state
    assert state.state == "Casablanca"

    # Testing next prayer might be flaky since it depends on current time via datetime.datetime.now(),
    # but asserting it exists and returns a valid English prayer name.
    state = hass.states.get("sensor.prayer_next")
    assert state
    assert state.state in ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
