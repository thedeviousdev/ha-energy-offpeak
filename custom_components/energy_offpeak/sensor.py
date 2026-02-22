"""Sensor platform for Energy Off-Peak Tracker."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_PEAK_END,
    ATTR_PEAK_START,
    ATTR_PEAK_USAGE,
    ATTR_SNAPSHOT_END,
    ATTR_SNAPSHOT_START,
    ATTR_SOURCE_ENTITY,
    ATTR_STATUS,
    CONF_NAME,
    CONF_PEAK_END,
    CONF_PEAK_START,
    CONF_SOURCE_ENTITY,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    config = {**entry.data, **entry.options}

    store = Store(
        hass,
        STORAGE_VERSION,
        f"{STORAGE_KEY}_{entry.entry_id}",
    )

    sensor = EnergyOffPeakSensor(
        hass=hass,
        entry_id=entry.entry_id,
        name=config[CONF_NAME],
        source_entity=config[CONF_SOURCE_ENTITY],
        peak_start=config[CONF_PEAK_START],  # "HH:MM:SS" or "HH:MM"
        peak_end=config[CONF_PEAK_END],
        store=store,
    )

    async_add_entities([sensor], update_before_add=True)


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' or 'HH:MM:SS' into (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


class EnergyOffPeakSensor(RestoreSensor):
    """Sensor that accumulates energy imported outside a defined peak window."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:transmission-tower-off"
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        source_entity: str,
        peak_start: str,
        peak_end: str,
        store: Store,
    ) -> None:
        """Initialise the sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_offpeak"
        self._source_entity = source_entity
        self._peak_start = peak_start
        self._peak_end = peak_end
        self._store = store

        self._peak_start_h, self._peak_start_m = _parse_hhmm(peak_start)
        self._peak_end_h, self._peak_end_m = _parse_hhmm(peak_end)

        # Snapshots — loaded from storage on setup
        self._snapshot_start: float | None = None
        self._snapshot_end: float | None = None
        self._snapshot_date: str | None = None  # "YYYY-MM-DD"

        self._attr_native_value: float | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore state and register listeners."""
        await super().async_added_to_hass()

        # Restore snapshots from persistent storage
        stored = await self._store.async_load()
        if stored:
            self._snapshot_start = stored.get("snapshot_start")
            self._snapshot_end = stored.get("snapshot_end")
            self._snapshot_date = stored.get("snapshot_date")
            _LOGGER.debug(
                "Restored snapshots: start=%s end=%s date=%s",
                self._snapshot_start,
                self._snapshot_end,
                self._snapshot_date,
            )

        # Restore previous sensor state
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_sensor_data.native_value

        # Listen for source entity state changes
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity],
                self._handle_source_state_change,
            )
        )

        # Register time triggers for peak start and end
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_peak_start,
                hour=self._peak_start_h,
                minute=self._peak_start_m,
                second=0,
            )
        )
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_peak_end,
                hour=self._peak_end_h,
                minute=self._peak_end_m,
                second=0,
            )
        )

        # Midnight reset
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_midnight_reset,
                hour=0,
                minute=0,
                second=2,
            )
        )

        # Force an immediate update
        self._update_value()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Time callbacks
    # ------------------------------------------------------------------

    @callback
    def _handle_peak_start(self, now: datetime) -> None:
        """Snapshot the source value at peak window start."""
        today = dt_util.now().date().isoformat()
        self._snapshot_date = today
        value = self._get_source_value()
        if value is not None:
            self._snapshot_start = value
            self._snapshot_end = None  # Reset end snapshot for today
            _LOGGER.debug("Peak start snapshot: %.3f kWh at %s", value, now)
            self.hass.async_create_task(self._async_save_snapshots())
        self._update_value()
        self.async_write_ha_state()

    @callback
    def _handle_peak_end(self, now: datetime) -> None:
        """Snapshot the source value at peak window end."""
        value = self._get_source_value()
        if value is not None:
            self._snapshot_end = value
            _LOGGER.debug("Peak end snapshot: %.3f kWh at %s", value, now)
            self.hass.async_create_task(self._async_save_snapshots())
        self._update_value()
        self.async_write_ha_state()

    @callback
    def _handle_midnight_reset(self, now: datetime) -> None:
        """Reset snapshots at midnight for a new day."""
        _LOGGER.debug("Midnight reset — clearing snapshots")
        self._snapshot_start = None
        self._snapshot_end = None
        self._snapshot_date = dt_util.now().date().isoformat()
        self.hass.async_create_task(self._async_save_snapshots())
        self._update_value()
        self.async_write_ha_state()

    @callback
    def _handle_source_state_change(self, event: Any) -> None:
        """Update our value whenever the source sensor changes."""
        self._update_value()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Core calculation
    # ------------------------------------------------------------------

    def _get_source_value(self) -> float | None:
        """Safely get the current source entity value as float."""
        state = self.hass.states.get(self._source_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _is_peak_window(self) -> bool:
        """Return True if we are currently inside the peak window."""
        now = dt_util.now()
        peak_start_minutes = self._peak_start_h * 60 + self._peak_start_m
        peak_end_minutes = self._peak_end_h * 60 + self._peak_end_m
        current_minutes = now.hour * 60 + now.minute
        return peak_start_minutes <= current_minutes < peak_end_minutes

    def _update_value(self) -> None:
        """Recalculate the off-peak energy value."""
        total = self._get_source_value()
        now = dt_util.now()
        peak_start_minutes = self._peak_start_h * 60 + self._peak_start_m
        peak_end_minutes = self._peak_end_h * 60 + self._peak_end_m
        current_minutes = now.hour * 60 + now.minute

        if total is None:
            status = "unavailable"
            value = self._attr_native_value  # Keep last known
        elif current_minutes < peak_start_minutes:
            # Before peak — all import is off-peak
            value = total
            status = "off_peak (before window)"
        elif current_minutes < peak_end_minutes:
            # Inside peak window — freeze at start snapshot
            value = self._snapshot_start if self._snapshot_start is not None else total
            status = "peak window (frozen)"
        else:
            # After peak window
            if self._snapshot_start is not None and self._snapshot_end is not None:
                peak_usage = max(0.0, self._snapshot_end - self._snapshot_start)
                value = max(0.0, total - peak_usage)
                status = "off_peak (after window)"
            elif self._snapshot_start is not None:
                # End snapshot missing (HA restarted during peak?)
                peak_usage = 0.0
                value = total
                status = "off_peak (missing end snapshot)"
            else:
                value = total
                status = "off_peak (no snapshots)"

        if value is not None:
            self._attr_native_value = round(value, 3)

        peak_usage_kwh = None
        if self._snapshot_start is not None and self._snapshot_end is not None:
            peak_usage_kwh = round(
                max(0.0, self._snapshot_end - self._snapshot_start), 3
            )

        self._attr_extra_state_attributes = {
            ATTR_SOURCE_ENTITY: self._source_entity,
            ATTR_PEAK_START: f"{self._peak_start_h:02d}:{self._peak_start_m:02d}",
            ATTR_PEAK_END: f"{self._peak_end_h:02d}:{self._peak_end_m:02d}",
            ATTR_SNAPSHOT_START: self._snapshot_start,
            ATTR_SNAPSHOT_END: self._snapshot_end,
            ATTR_PEAK_USAGE: peak_usage_kwh,
            ATTR_STATUS: status,
        }

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _async_save_snapshots(self) -> None:
        """Persist snapshots to HA storage."""
        await self._store.async_save(
            {
                "snapshot_start": self._snapshot_start,
                "snapshot_end": self._snapshot_end,
                "snapshot_date": self._snapshot_date,
            }
        )
