# Energy Window Tracker

Tracks energy over custom time windows in Home Assistant. Snapshots at window start and end are stored so sensors survive restarts.

| When           | Sensor value                    |
| -------------- | ------------------------------- |
| Before window  | 0 kWh                           |
| During window  | Energy so far (live)            |
| After window   | Final energy for that window   |

## Installation

### HACS (recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add this repo URL, category **Integration**
3. Install **Energy Window Tracker**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/energy_window_tracker/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

After any update, restart HA. Some versions of the plugin have been [yanked](YANKED.md).

## Setup

One entry = one energy source + many windows. You can add multiple entries (e.g. same sensor, different window sets).

1. **Settings → Devices & Services → Add Integration** → Energy Window Tracker
2. **Step 1:** Pick a daily cumulative sensor that resets (e.g. at midnight)
3. **Step 2:** Friendly name (optional), window name, start/end time, optional cost per kWh. You can add more windows later via **⚙️ Configure**

**Configure menu (⚙️ on the entry):**

- **✚ Add new window** — Name, start, end, optional cost
- **✏️ Manage windows** — Pick a window → edit (or delete with confirmation)
- **⚡️ Update energy source** — New sensor + optional friendly name. Checkbox: remove old entities and data or keep them and clean up manually. Changing the source source will create new entity IDs 

## Sensors

Each window is one sensor. Friendly name = window name. Entity ID includes the source (e.g. `sensor.today_load_peak`). Find them under the entry’s **Entities** tab or **Settings → Entities** filtered by the integration.

| Attribute       | Meaning |
| --------------- | ------- |
| `source_entity` | Source sensor |
| `start` / `end` | Window times |
| `status`        | before_window, during_window, after_window, etc. |
| `cost`          | Energy × cost per kWh (if set), 2 decimals. Use e.g. `{{ state_attr('sensor.x', 'cost') }}` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for tests and CI.

## FAQ

**What kind of energy sensor do I need?**  
The source must be a **daily cumulative total** that resets (e.g. at midnight).

**What happens if Home Assistant restarts during a window?**  
The start snapshot is restored from storage, and the end snapshot is taken at the window end time. Your data is preserved.

**How many sources and windows can I have?**  
Each integration entry has **one energy source** and can have **any number of time windows**. You can create multiple entries but they cannot use the same sensor.

**How do I get more detail when something fails?**  
Enable debug logging: **Settings → System → Logging** → set **Logger** to `custom_components.energy_window_tracker` and **Level** to **Debug**, then reproduce the issue. In **Settings → System → Logs** (or your log file), look for entries from `custom_components.energy_window_tracker`; the config flow logs step transitions and entity selector values to help trace errors.
