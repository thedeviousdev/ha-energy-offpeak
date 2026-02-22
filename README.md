# Energy Off-Peak Tracker

A Home Assistant custom integration that tracks energy imported **outside** a defined peak window (e.g. 11am–2pm). It creates a sensor whose value accumulates only during off-peak hours.

---

## How It Works

| Time period | Sensor behaviour |
|---|---|
| Before peak window | Tracks total import (all off-peak) |
| During peak window | Freezes — not accumulating |
| After peak window | Resumes, with peak usage subtracted |

Snapshots are taken at the **start** and **end** of the peak window and persisted to HA storage, so the sensor survives restarts.

---

## Installation

### HACS (recommended)
1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add this repo URL, category **Integration**
3. Install **Energy Off-Peak Tracker**
4. Restart Home Assistant

### Manual
1. Copy the `custom_components/energy_offpeak/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → + Add Integration**
2. Search for **Energy Off-Peak Tracker**
3. Fill in the form:
   - **Source energy sensor** — your daily cumulative kWh sensor (e.g. `sensor.today_energy_import`)
   - **Peak window start** — e.g. `11:00`
   - **Peak window end** — e.g. `14:00`
4. Click **Submit**

The sensor will appear as **Energy Import Off-Peak** (or whatever name you chose).

---

## Sensor Attributes

| Attribute | Description |
|---|---|
| `source_entity` | The tracked source sensor |
| `peak_start` / `peak_end` | Configured window times |
| `snapshot_at_peak_start` | kWh value captured at window start |
| `snapshot_at_peak_end` | kWh value captured at window end |
| `peak_window_usage_kwh` | Energy used *during* the peak window |
| `status` | Current calculation mode |

---

## Notes

- The source sensor **must** be a daily cumulative total that resets at midnight (e.g. from a Shelly, Fronius, SolarEdge, or similar device)
- If HA restarts during the peak window, the start snapshot is restored from storage and the end snapshot will be captured at 2pm as normal
- You can configure multiple instances for different sensors or peak windows
