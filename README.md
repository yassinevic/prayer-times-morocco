# Morocco Prayer Times 🕌

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/yassinevic/prayer-times-morocco.svg)](https://github.com/yassinevic/prayer-times-morocco/releases)

A Home Assistant custom integration that fetches official Moroccan prayer times from [habous.gov.ma](https://www.habous.gov.ma) and exposes them as native sensors.

---

## Features

- 🕐 **9 sensors** per configured city:
  - Fajr, Sunrise (Chourouk), Dhuhr, Asr, Maghrib, Isha
  - Next Prayer (dynamically updated)
  - City name
  - Date
- 🌍 **Supports all Moroccan cities** (75+ cities)
- 🔤 **Bilingual**: English or Arabic sensor names
- 🔄 **Auto-refresh** every hour
- 🛠️ **UI config flow** — no YAML required
- 💪 **Manual refresh** via service call

---

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant.
2. Go to **Integrations** → Click the **⋮** menu → **Custom repositories**.
3. Add `https://github.com/yassinevic/prayer-times-morocco` as category **Integration**.
4. Search for **Morocco Prayer Times** and click **Download**.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/prayer_times_morocco` folder into your HA `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Morocco Prayer Times**.
3. Select your **city** and **language** (English or Arabic).
4. Done! Your sensors will appear immediately.

---

## Dashboard Card

Add this to your Lovelace dashboard:

```yaml
type: entities
title: Prayer Times
icon: mdi:mosque
entities:
  - entity: sensor.prayer_date
    icon: mdi:calendar
  - entity: sensor.prayer_city
    icon: mdi:city
  - type: divider
  - entity: sensor.prayer_fajr
    icon: mdi:weather-sunset-up
  - entity: sensor.prayer_chourouk
    icon: mdi:weather-sunny-alert
  - entity: sensor.prayer_dohr
    icon: mdi:weather-sunny
  - entity: sensor.prayer_asr
    icon: mdi:sun-angle-outline
  - entity: sensor.prayer_maghrib
    icon: mdi:weather-sunset-down
  - entity: sensor.prayer_ichaa
    icon: mdi:weather-night
  - type: divider
  - entity: sensor.prayer_next
    icon: mdi:clock-outline
```

---

## Manual Refresh

Force an immediate data refresh via the Developer Tools service call:

```yaml
service: prayer_times_morocco.refresh
```

---

## Sensors

| Entity ID                | Description                      |
| ------------------------ | -------------------------------- |
| `sensor.prayer_fajr`     | Fajr prayer time                 |
| `sensor.prayer_chourouk` | Sunrise time                     |
| `sensor.prayer_dohr`     | Dhuhr prayer time                |
| `sensor.prayer_asr`      | Asr prayer time                  |
| `sensor.prayer_maghrib`  | Maghrib prayer time              |
| `sensor.prayer_ichaa`    | Isha prayer time                 |
| `sensor.prayer_next`     | Name of the next upcoming prayer |
| `sensor.prayer_city`     | Configured city                  |
| `sensor.prayer_date`     | Date of the fetched prayer times |

---

## Data Source

All prayer times are fetched from the official Moroccan Ministry of Islamic Affairs website:  
🔗 [habous.gov.ma](https://www.habous.gov.ma)

---

## License

MIT License — free to use, modify and distribute.
