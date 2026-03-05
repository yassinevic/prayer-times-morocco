from unittest.mock import patch
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from custom_components.prayer_times_morocco.const import DOMAIN

async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.prayer_times_morocco.config_flow.fetch_prayer_times",
        return_value={"city": "Casablanca", "prayers": {}},
    ), patch(
        "custom_components.prayer_times_morocco.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"city": "Casablanca", "language": "english"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert "Morocco Prayer Times" in result2["title"]
    assert result2["data"] == {
        "city": "Casablanca",
        "language": "english"
    }
    assert len(mock_setup_entry.mock_calls) == 1

async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.prayer_times_morocco.config_flow.fetch_prayer_times",
        side_effect=Exception("Failed to load"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"city": "Casablanca", "language": "english"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
