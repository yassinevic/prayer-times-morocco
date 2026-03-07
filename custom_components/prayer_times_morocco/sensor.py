import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PRAYERS, PRAYERS_NAMES, CITY_TRANSLATIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [PrayerTimeSensor(coordinator, prayer) for prayer in PRAYERS]
    entities += [
        PrayerNextSensor(coordinator),
        PrayerNextTimeSensor(coordinator),
        PrayerCitySensor(coordinator),
        PrayerDateSensor(coordinator),
    ]
    
    async_add_entities(entities, True)


def get_active_prayers(coordinator):
    """
    Return the active prayer schedule based on current time.
    After 3ichaa has passed, flip to tomorrow's prayers.
    Falls back to today's prayers if tomorrow's data is not available.
    """
    if not coordinator.data or "prayers" not in coordinator.data:
        return None

    today_prayers = coordinator.data["prayers"]
    tomorrow_prayers = coordinator.data.get("tomorrow_prayers")

    # Check if 3ichaa has passed
    ichaa_time_str = today_prayers.get("ichaa") or today_prayers.get("isha")
    if ichaa_time_str:
        try:
            h, m = map(int, ichaa_time_str.split(':'))
            if datetime.datetime.now().time() >= datetime.time(h, m):
                # 3ichaa passed — use tomorrow's prayers if available
                if tomorrow_prayers:
                    return tomorrow_prayers
        except ValueError:
            pass

    return today_prayers


class PrayerBaseEntity(CoordinatorEntity):
    """Base class for all prayer sensors."""
    
    def __init__(self, coordinator, sensor_type):
        """Initialize."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._sensor_type = sensor_type
        self.city = coordinator.city
        
        display_city = self.city
        if coordinator.language == "arabic":
            display_city = CITY_TRANSLATIONS.get(self.city, self.city)

        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.city)},
            name=f"Morocco Prayer Times - {display_city}",
            manufacturer="Habous",
            model="Habous Scraping",
            entry_type=DeviceEntryType.SERVICE,
        )


class PrayerTimeSensor(PrayerBaseEntity, SensorEntity):
    def __init__(self, coordinator, prayer_key):
        super().__init__(coordinator, prayer_key)
        self._prayer = prayer_key
        
        lang = coordinator.language
        lang_name = PRAYERS_NAMES[lang][prayer_key]

        self.entity_id = f"sensor.prayer_{prayer_key}"
        self._attr_unique_id = f"{DOMAIN}_{self.city}_prayer_{prayer_key}".lower()
        self._attr_name = f"{lang_name}"
        self._attr_icon = "mdi:mosque"

    @property
    def native_value(self):
        prayers = get_active_prayers(self._coordinator)
        if prayers:
            return prayers.get(self._prayer)
        return None


class PrayerNextSensor(PrayerBaseEntity, SensorEntity):
    """Sensor that returns the NAME of the next upcoming prayer."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "next")
        
        self.entity_id = "sensor.prayer_next"
        self._attr_unique_id = f"{DOMAIN}_{self.city}_prayer_next".lower()
        self._attr_name = PRAYERS_NAMES[coordinator.language]["next"]
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self):
        """Return the next prayer name based on current time."""
        prayers = get_active_prayers(self._coordinator)
        if not prayers:
            return None

        now = datetime.datetime.now().time()

        for p_name in PRAYERS:
            time_str = prayers.get(p_name)
            if time_str:
                try:
                    h, m = map(int, time_str.split(':'))
                    if now < datetime.time(h, m):
                        return PRAYERS_NAMES[self._coordinator.language][p_name]
                except ValueError:
                    continue

        # All prayers passed — Fajr is next (tomorrow's schedule already active at this point)
        return PRAYERS_NAMES[self._coordinator.language]["fajr"]


class PrayerNextTimeSensor(PrayerBaseEntity, SensorEntity):
    """Sensor that returns the TIME of the next upcoming prayer."""

    def __init__(self, coordinator):
        super().__init__(coordinator, "next_time")

        self.entity_id = "sensor.prayer_next_time"
        self._attr_unique_id = f"{DOMAIN}_{self.city}_prayer_next_time".lower()
        self._attr_name = PRAYERS_NAMES[coordinator.language]["next_time"]
        self._attr_icon = "mdi:clock-fast"

    @property
    def native_value(self):
        """Return the time (HH:MM) of the next prayer."""
        prayers = get_active_prayers(self._coordinator)
        if not prayers:
            return None

        now = datetime.datetime.now().time()

        for p_name in PRAYERS:
            time_str = prayers.get(p_name)
            if time_str:
                try:
                    h, m = map(int, time_str.split(':'))
                    if now < datetime.time(h, m):
                        return time_str
                except ValueError:
                    continue

        # All prayers passed — return Fajr (tomorrow's schedule already active at this point)
        return prayers.get("fajr")


class PrayerCitySensor(PrayerBaseEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "city")
        
        self.entity_id = "sensor.prayer_city"
        self._attr_unique_id = f"{DOMAIN}_{self.city}_prayer_city".lower()
        self._attr_name = PRAYERS_NAMES[coordinator.language]["city"]
        self._attr_icon = "mdi:city"

    @property
    def native_value(self):
        city_name = self.city
        if self._coordinator.data:
            city_name = self._coordinator.data.get("city", self.city)
            
        if self._coordinator.language == "arabic":
            return CITY_TRANSLATIONS.get(city_name, city_name)
        return city_name


class PrayerDateSensor(PrayerBaseEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator, "date")
        
        self.entity_id = "sensor.prayer_date"
        self._attr_unique_id = f"{DOMAIN}_{self.city}_prayer_date".lower()
        self._attr_name = PRAYERS_NAMES[coordinator.language]["date"]
        self._attr_icon = "mdi:calendar"

    @property
    def native_value(self):
        """Return the active date — tomorrow's if 3ichaa has passed."""
        if not self._coordinator.data:
            return None

        today_prayers = self._coordinator.data.get("prayers", {})
        ichaa_time_str = today_prayers.get("ichaa") or today_prayers.get("isha")
        if ichaa_time_str:
            try:
                h, m = map(int, ichaa_time_str.split(':'))
                if datetime.datetime.now().time() >= datetime.time(h, m):
                    tomorrow_date = self._coordinator.data.get("tomorrow_date")
                    if tomorrow_date:
                        return tomorrow_date
            except ValueError:
                pass

        return self._coordinator.data.get("date")