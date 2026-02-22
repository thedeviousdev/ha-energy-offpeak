"""Config flow for Energy Window Tracker."""

from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_NAME,
    CONF_WINDOWS,
    CONF_WINDOW_END,
    CONF_WINDOW_NAME,
    CONF_WINDOW_START,
    CONF_SOURCE_ENTITY,
    DEFAULT_NAME,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
)

MAX_WINDOWS = 8


def _time_to_str(t: Any) -> str:
    """Convert time object or string to HH:MM format."""
    if t is None:
        return "00:00"
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")
    if hasattr(t, "hour") and hasattr(t, "minute"):
        return f"{t.hour:02d}:{t.minute:02d}"
    if isinstance(t, str):
        return t[:5] if len(t) >= 5 else t
    return str(t)


def _get_entity_friendly_name(hass, entity_id: str) -> str:
    """Get friendly name for an entity, fallback to entity id or default."""
    state = hass.states.get(entity_id)
    if state:
        name = state.attributes.get("friendly_name")
        if name:
            return str(name)
    return entity_id.split(".")[-1].replace("_", " ").title() if entity_id else DEFAULT_NAME


def _build_windows_schema(
    hass,
    source_entity: str,
    existing_windows: list[dict] | None = None,
    default_source_name: str | None = None,
) -> vol.Schema:
    """Build step 2 schema: source name + window rows (name, start, end per row)."""
    if default_source_name is not None:
        default_name = default_source_name
    else:
        default_name = _get_entity_friendly_name(hass, source_entity) if source_entity else DEFAULT_NAME
    existing = existing_windows or []

    schema_dict: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=default_name): str,
    }

    for i in range(MAX_WINDOWS):
        if i < len(existing):
            ex = existing[i]
            schema_dict[vol.Optional(f"w{i}_name", default=ex.get(CONF_WINDOW_NAME) or ex.get("name") or "")] = str
            schema_dict[vol.Optional(f"w{i}_start", default=_time_to_str(ex.get(CONF_WINDOW_START) or ex.get("start") or DEFAULT_WINDOW_START))] = selector.TimeSelector()
            schema_dict[vol.Optional(f"w{i}_end", default=_time_to_str(ex.get(CONF_WINDOW_END) or ex.get("end") or DEFAULT_WINDOW_END))] = selector.TimeSelector()
        else:
            schema_dict[vol.Optional(f"w{i}_name", default="")] = str
            schema_dict[vol.Optional(f"w{i}_start", default=DEFAULT_WINDOW_START)] = selector.TimeSelector()
            schema_dict[vol.Optional(f"w{i}_end", default=DEFAULT_WINDOW_END)] = selector.TimeSelector()

    return vol.Schema(schema_dict)


def _collect_windows_from_input(data: dict) -> list[dict[str, Any]]:
    """Collect non-empty windows from the row fields. A row is used if start < end."""
    windows = []
    for i in range(MAX_WINDOWS):
        start = _time_to_str(data.get(f"w{i}_start", "00:00"))
        end = _time_to_str(data.get(f"w{i}_end", "00:00"))
        if start >= end:
            continue
        name = (data.get(f"w{i}_name") or "").strip()
        windows.append({
            CONF_WINDOW_START: start,
            CONF_WINDOW_END: end,
            CONF_WINDOW_NAME: name or None,
        })
    return windows


def _get_all_window_rows_from_input(data: dict) -> list[dict[str, Any]]:
    """Get all row data from input (for re-showing form after validation error)."""
    rows = []
    for i in range(MAX_WINDOWS):
        rows.append({
            CONF_WINDOW_NAME: data.get(f"w{i}_name") or "",
            CONF_WINDOW_START: _time_to_str(data.get(f"w{i}_start", "00:00")),
            CONF_WINDOW_END: _time_to_str(data.get(f"w{i}_end", "00:00")),
        })
    return rows


class EnergyWindowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Window Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._source_entity: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 1: Select energy sensor only."""
        if user_input is not None:
            self._source_entity = user_input[CONF_SOURCE_ENTITY]
            return await self.async_step_windows()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SOURCE_ENTITY,
                    default="sensor.today_energy_import",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }),
        )

    async def async_step_windows(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step 2: Source name (default from entity) + window rows, then Create."""
        errors: dict[str, str] = {}

        if user_input is not None:
            windows = _collect_windows_from_input(user_input)
            if not windows:
                errors["base"] = "at_least_one_window"
                return self.async_show_form(
                    step_id="windows",
                    data_schema=_build_windows_schema(
                        self.hass,
                        self._source_entity or "",
                        _get_all_window_rows_from_input(user_input),
                        default_source_name=user_input.get(CONF_NAME) or "",
                    ),
                    errors=errors,
                )
            else:
                # Validate each window
                for w in windows:
                    if w[CONF_WINDOW_START] >= w[CONF_WINDOW_END]:
                        errors["base"] = "window_start_after_end"
                        break
                if errors:
                    return self.async_show_form(
                        step_id="windows",
                        data_schema=_build_windows_schema(
                            self.hass,
                            self._source_entity or "",
                            _get_all_window_rows_from_input(user_input),
                            default_source_name=user_input.get(CONF_NAME) or "",
                        ),
                        errors=errors,
                    )
                source_name = (user_input.get(CONF_NAME) or "").strip() or _get_entity_friendly_name(
                    self.hass, self._source_entity or ""
                )
                windows_hash = hashlib.sha256(
                    str(sorted(w.items()) for w in windows).encode()
                ).hexdigest()[:8]
                unique_id = f"{self._source_entity}_{windows_hash}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=source_name,
                    data={
                        CONF_NAME: source_name,
                        CONF_SOURCE_ENTITY: self._source_entity,
                        CONF_WINDOWS: windows,
                    },
                )

        return self.async_show_form(
            step_id="windows",
            data_schema=_build_windows_schema(self.hass, self._source_entity or ""),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EnergyWindowOptionsFlow:
        """Get the options flow."""
        return EnergyWindowOptionsFlow(config_entry)


class EnergyWindowOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Single step: source name + window rows (same as initial step 2)."""
        current = {**self.config_entry.data, **self.config_entry.options}
        source_entity = current.get(CONF_SOURCE_ENTITY) or "sensor.today_energy_import"
        existing = current.get(CONF_WINDOWS) or current.get("periods", [])

        if user_input is not None:
            windows = _collect_windows_from_input(user_input)
            if not windows:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_build_windows_schema(self.hass, source_entity, existing),
                    errors={"base": "at_least_one_window"},
                )
            for w in windows:
                if w[CONF_WINDOW_START] >= w[CONF_WINDOW_END]:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=_build_windows_schema(self.hass, source_entity, existing),
                        errors={"base": "window_start_after_end"},
                    )
            source_name = (user_input.get(CONF_NAME) or "").strip() or current.get(CONF_NAME) or DEFAULT_NAME
            return self.async_create_entry(
                title="",
                data={
                    CONF_NAME: source_name,
                    CONF_SOURCE_ENTITY: source_entity,
                    CONF_WINDOWS: windows,
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_windows_schema(
                self.hass,
                source_entity,
                list(existing),
                default_source_name=current.get(CONF_NAME) or DEFAULT_NAME,
            ),
        )
