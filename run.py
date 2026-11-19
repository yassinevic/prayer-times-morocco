"""Standalone runner and verification script for Morocco Prayer Times."""

import argparse
import asyncio
import datetime
import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Shim Home Assistant dependencies for standalone execution
import types
from unittest.mock import MagicMock

for _mod in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.aiohttp_client",
]:
    if _mod not in sys.modules:
        class _MockModule(types.ModuleType):
            def __getattr__(self, name):
                return MagicMock()
        m = _MockModule(_mod)
        m.__path__ = []
        sys.modules[_mod] = m

class _UpdateFailed(Exception):
    pass

sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = _UpdateFailed

import aiohttp
from custom_components.prayer_times_morocco.const import (
    CITIES_MAP,
    CITY_TRANSLATIONS,
    PRAYERS,
    PRAYERS_NAMES,
)
from custom_components.prayer_times_morocco.coordinator import fetch_prayer_times


def compute_next_prayer(prayers: dict, language: str = "english"):
    """Compute the upcoming prayer name and time."""
    now = datetime.datetime.now().time()
    for prayer_key in PRAYERS:
        time_str = prayers.get(prayer_key)
        if time_str:
            try:
                h, m = map(int, time_str.split(":"))
                if now < datetime.time(h, m):
                    name = PRAYERS_NAMES[language][prayer_key]
                    return name, time_str
            except ValueError:
                continue

    # All prayers passed -> next is Fajr
    return PRAYERS_NAMES[language]["fajr"], prayers.get("fajr")


async def run_live(city: str = "Casablanca", language: str = "english"):
    """Fetch and display prayer times live from Habous."""
    if city not in CITIES_MAP:
        print(f"Error: Unknown city '{city}'.")
        print(f"Available cities: {', '.join(sorted(CITIES_MAP.keys()))}")
        return

    city_id = CITIES_MAP[city]
    display_name = CITY_TRANSLATIONS.get(city, city) if language == "arabic" else city

    print("=" * 60)
    print(f"🕌 Morocco Prayer Times — {city} (ID: {city_id})")
    print("=" * 60)
    print(f"Connecting to https://www.habous.gov.ma/data/horaires-...js?v={city_id} ...")

    async with aiohttp.ClientSession() as session:
        try:
            data = await fetch_prayer_times(session, city_id, city)
        except Exception as err:
            print(f"❌ Failed to fetch prayer times: {err}")
            return

    today_prayers = data["prayers"]
    tomorrow_prayers = data.get("tomorrow_prayers", today_prayers)
    next_name, next_time = compute_next_prayer(today_prayers, language)

    print("\n📅 Schedule:")
    print(f"  • Date: {data.get('date')}")
    print(f"  • City: {display_name}")
    print(f"  • Next Prayer: {next_name} at {next_time}")

    print("\n⏰ Today's Prayer Times:")
    for p in PRAYERS:
        label = PRAYERS_NAMES[language][p]
        time_val = today_prayers.get(p, "--:--")
        print(f"  • {label:12}: {time_val}")

    print("\n🌅 Tomorrow's Prayer Times:")
    for p in PRAYERS:
        label = PRAYERS_NAMES[language][p]
        time_val = tomorrow_prayers.get(p, "--:--")
        print(f"  • {label:12}: {time_val}")

    print("=" * 60)


def run_tests():
    """Run the test suite."""
    print("\n🧪 Running Unit Tests...")
    sys.stdout.flush()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("tests.test_coordinator")
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    result = runner.run(suite)
    sys.stdout.flush()
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="Morocco Prayer Times integration runner")
    parser.add_argument("--city", default="Casablanca", help="City name (e.g. Casablanca, Rabat, Marrakech)")
    parser.add_argument("--lang", default="english", choices=["english", "arabic"], help="Display language")
    parser.add_argument("--test-only", action="store_true", help="Only run tests")
    args = parser.parse_args()

    if not args.test_only:
        asyncio.run(run_live(args.city, args.lang))

    run_tests()


if __name__ == "__main__":
    main()
