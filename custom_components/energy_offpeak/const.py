"""Constants for the Energy Off-Peak Tracker integration."""

DOMAIN = "energy_offpeak"

CONF_SOURCE_ENTITY = "source_entity"
CONF_PEAK_START = "peak_start"
CONF_PEAK_END = "peak_end"
CONF_NAME = "name"

DEFAULT_NAME = "Energy Import Off-Peak"
DEFAULT_PEAK_START = "11:00"
DEFAULT_PEAK_END = "14:00"

STORAGE_VERSION = 1
STORAGE_KEY = "energy_offpeak_snapshots"

ATTR_PEAK_START = "peak_start"
ATTR_PEAK_END = "peak_end"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_SNAPSHOT_START = "snapshot_at_peak_start"
ATTR_SNAPSHOT_END = "snapshot_at_peak_end"
ATTR_PEAK_USAGE = "peak_window_usage_kwh"
ATTR_STATUS = "status"
