"""Config flow for Energy Off-Peak Tracker."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_NAME,
    CONF_PEAK_END,
    CONF_PEAK_START,
    CONF_SOURCE_ENTITY,
    DEFAULT_NAME,
    DEFAULT_PEAK_END,
    DEFAULT_PEAK_START,
    DOMAIN,
)

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _validate_time(value: str) -> str:
    if not TIME_PATTERN.match(value):
        raise vol.Invalid("Invalid time format. Use HH:MM (e.g. 11:00)")
    return value


def _build_schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(
                CONF_SOURCE_ENTITY,
                default=defaults.get(CONF_SOURCE_ENTITY, "sensor.today_energy_import"),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_PEAK_START,
                default=defaults.get(CONF_PEAK_START, DEFAULT_PEAK_START),
            ): selector.TimeSelector(),
            vol.Required(
                CONF_PEAK_END,
                default=defaults.get(CONF_PEAK_END, DEFAULT_PEAK_END),
            ): selector.TimeSelector(),
        }
    )


class EnergyOffPeakConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Off-Peak Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            peak_start = user_input[CONF_PEAK_START]
            peak_end = user_input[CONF_PEAK_END]

            # Validate that peak_start < peak_end
            if peak_start >= peak_end:
                errors["base"] = "peak_start_after_end"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_SOURCE_ENTITY]}_{peak_start}_{peak_end}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EnergyOffPeakOptionsFlow:
        """Get the options flow."""
        return EnergyOffPeakOptionsFlow(config_entry)


class EnergyOffPeakOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            peak_start = user_input[CONF_PEAK_START]
            peak_end = user_input[CONF_PEAK_END]

            if peak_start >= peak_end:
                errors["base"] = "peak_start_after_end"
            else:
                return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
            errors=errors,
        )
