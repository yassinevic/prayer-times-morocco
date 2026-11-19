import json
import os
import sys
import types
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Provide lightweight mock for homeassistant when running outside HA environment
class _MockModule(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []

    def __getattr__(self, item):
        return MagicMock()

for _mod in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.aiohttp_client",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _MockModule(_mod)

try:
    from homeassistant.helpers.update_coordinator import UpdateFailed
except Exception:
    class UpdateFailed(Exception):
        pass
    if "homeassistant.helpers.update_coordinator" in sys.modules:
        sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = UpdateFailed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.prayer_times_morocco.coordinator import (
    _extract_city_prayers,
    _fetch_month_data,
    fetch_prayer_times,
)

SAMPLE_MONTH_DATA = {
    "annee": 2026,
    "mois": 11,
    "fuseau": "GMT",
    "cols": ["Fajr", "Chorouq", "Dhuhr", "Asr", "Maghrib", "Ishae"],
    "villes": [
        {
            "c": 58,
            "n": "الدار البيضاء",
            "h": [
                ["05:20", "06:46", "12:19", "15:16", "17:43", "18:58"],
                ["05:21", "06:47", "12:19", "15:15", "17:42", "18:57"],
                ["05:22", "06:48", "12:19", "15:14", "17:41", "18:56"],
            ],
        },
        {
            "c": 1,
            "n": "الرباط",
            "h": [
                ["05:17", "06:44", "12:16", "15:12", "17:39", "18:54"],
                ["05:18", "06:45", "12:16", "15:11", "17:38", "18:54"],
            ],
        },
    ],
}

SAMPLE_JS_CONTENT = (
    "(window.HORAIRES_MOIS=window.HORAIRES_MOIS||[]).push("
    + json.dumps(SAMPLE_MONTH_DATA)
    + ");"
)


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    def test_extract_city_prayers_success(self):
        prayers = _extract_city_prayers(SAMPLE_MONTH_DATA, 58, "Casablanca", 1)
        self.assertEqual(
            prayers, ["05:20", "06:46", "12:19", "15:16", "17:43", "18:58"]
        )

        prayers_day2 = _extract_city_prayers(SAMPLE_MONTH_DATA, 58, "Casablanca", 2)
        self.assertEqual(
            prayers_day2, ["05:21", "06:47", "12:19", "15:15", "17:42", "18:57"]
        )

    def test_extract_city_prayers_city_not_found(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_city_prayers(SAMPLE_MONTH_DATA, 999, "Unknown", 1)
        self.assertIn("999", str(ctx.exception))

    def test_extract_city_prayers_day_out_of_range(self):
        with self.assertRaises(ValueError) as ctx:
            _extract_city_prayers(SAMPLE_MONTH_DATA, 58, "Casablanca", 10)
        self.assertIn("jour 10", str(ctx.exception))

    async def test_fetch_month_data_success(self):
        session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.text.return_value = SAMPLE_JS_CONTENT
        mock_resp.raise_for_status = MagicMock()

        session.get.return_value.__aenter__.return_value = mock_resp

        data = await _fetch_month_data(session, 2026, 11, 58)
        self.assertEqual(data["annee"], 2026)
        self.assertEqual(data["mois"], 11)
        self.assertEqual(len(data["villes"]), 2)

    async def test_fetch_prayer_times_same_month(self):
        session = MagicMock()
        mock_resp = AsyncMock()
        mock_resp.text.return_value = SAMPLE_JS_CONTENT
        mock_resp.raise_for_status = MagicMock()

        session.get.return_value.__aenter__.return_value = mock_resp

        with patch("custom_components.prayer_times_morocco.coordinator.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 1)

            result = await fetch_prayer_times(session, 58, "Casablanca")

            self.assertEqual(result["city"], "Casablanca")
            self.assertEqual(result["date"], "2026-11-01")
            self.assertEqual(
                result["prayers"],
                {
                    "fajr": "05:20",
                    "chourouk": "06:46",
                    "dohr": "12:19",
                    "asr": "15:16",
                    "maghrib": "17:43",
                    "ichaa": "18:58",
                },
            )
            self.assertEqual(result["tomorrow_date"], "2026-11-02")
            self.assertEqual(
                result["tomorrow_prayers"],
                {
                    "fajr": "05:21",
                    "chourouk": "06:47",
                    "dohr": "12:19",
                    "asr": "15:15",
                    "maghrib": "17:42",
                    "ichaa": "18:57",
                },
            )
            # Only 1 HTTP call should be made since tomorrow is in the same month
            self.assertEqual(session.get.call_count, 1)

    async def test_fetch_prayer_times_end_of_month_with_next_month(self):
        session = MagicMock()

        next_month_data = {
            "annee": 2026,
            "mois": 12,
            "cols": ["Fajr", "Chorouq", "Dhuhr", "Asr", "Maghrib", "Ishae"],
            "villes": [
                {
                    "c": 58,
                    "n": "الدار البيضاء",
                    "h": [
                        ["05:40", "07:05", "12:22", "15:08", "17:35", "18:50"]
                    ],
                }
            ],
        }

        resp1 = AsyncMock()
        resp1.text.return_value = SAMPLE_JS_CONTENT
        resp1.raise_for_status = MagicMock()

        resp2 = AsyncMock()
        resp2.text.return_value = (
            "(window.HORAIRES_MOIS=window.HORAIRES_MOIS||[]).push("
            + json.dumps(next_month_data)
            + ");"
        )
        resp2.raise_for_status = MagicMock()

        session.get.return_value.__aenter__.side_effect = [resp1, resp2]

        with patch("custom_components.prayer_times_morocco.coordinator.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 30)

            with patch(
                "custom_components.prayer_times_morocco.coordinator._extract_city_prayers"
            ) as mock_extract:
                mock_extract.side_effect = [
                    ["05:22", "06:48", "12:19", "15:14", "17:41", "18:56"],
                    ["05:40", "07:05", "12:22", "15:08", "17:35", "18:50"],
                ]
                result = await fetch_prayer_times(session, 58, "Casablanca")
                self.assertEqual(result["tomorrow_date"], "2026-12-01")
                self.assertEqual(
                    result["tomorrow_prayers"]["fajr"], "05:40"
                )
                self.assertEqual(session.get.call_count, 2)

    async def test_fetch_prayer_times_end_of_month_fallback(self):
        session = MagicMock()

        resp1 = AsyncMock()
        resp1.text.return_value = SAMPLE_JS_CONTENT
        resp1.raise_for_status = MagicMock()

        # Next month returns 404
        resp2 = MagicMock()
        resp2.raise_for_status.side_effect = Exception("404 Not Found")

        session.get.return_value.__aenter__.side_effect = [resp1, resp2]

        with patch("custom_components.prayer_times_morocco.coordinator.date") as mock_date:
            mock_date.today.return_value = date(2026, 11, 30)

            with patch(
                "custom_components.prayer_times_morocco.coordinator._extract_city_prayers"
            ) as mock_extract:
                mock_extract.return_value = ["05:22", "06:48", "12:19", "15:14", "17:41", "18:56"]
                result = await fetch_prayer_times(session, 58, "Casablanca")
                # Fallback to today
                self.assertEqual(result["tomorrow_date"], "2026-11-30")
                self.assertEqual(
                    result["tomorrow_prayers"]["fajr"], "05:22"
                )

    async def test_fetch_prayer_times_error_raises_update_failed(self):
        session = MagicMock()
        session.get.side_effect = Exception("Connection error")

        with patch("custom_components.prayer_times_morocco.coordinator._load_cache", return_value=None):
            with self.assertRaises(UpdateFailed):
                await fetch_prayer_times(session, 58, "Casablanca")

    async def test_fetch_prayer_times_offline_fallback_to_cache(self):
        session = MagicMock()
        session.get.side_effect = Exception("Habous offline")

        with patch("custom_components.prayer_times_morocco.coordinator._load_cache", return_value=SAMPLE_MONTH_DATA):
            with patch("custom_components.prayer_times_morocco.coordinator.date") as mock_date:
                mock_date.today.return_value = date(2026, 11, 1)
                result = await fetch_prayer_times(session, 58, "Casablanca")
                self.assertEqual(result["city"], "Casablanca")
                self.assertEqual(result["date"], "2026-11-01")
                self.assertEqual(result["prayers"]["fajr"], "05:20")

    def test_save_and_load_cache(self):
        from custom_components.prayer_times_morocco.coordinator import _save_cache, _load_cache, CACHE_DIR
        _save_cache(99, SAMPLE_MONTH_DATA)
        loaded = _load_cache(99)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["annee"], 2026)
        test_path = os.path.join(CACHE_DIR, "horaires-99.json")
        if os.path.exists(test_path):
            os.remove(test_path)


if __name__ == "__main__":
    unittest.main()
