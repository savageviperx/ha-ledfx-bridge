"""Native Home Assistant setup and options forms."""

from __future__ import annotations

from ipaddress import IPv4Address
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    COLOR_MODES,
    CONF_MAX_FPS,
    CONF_MAX_INFLIGHT,
    CONF_START_ENABLED,
    CONF_THRESHOLD,
    CONF_WEB_PORT,
    DEFAULT_OPTIONS,
    DEFAULT_PORT,
    DEFAULT_WEB_PORT,
    DOMAIN,
)


def _number(minimum: int, maximum: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "Music light")): str,
            vol.Required(
                CONF_ENTITY_ID,
                **({"default": defaults[CONF_ENTITY_ID]} if CONF_ENTITY_ID in defaults else {}),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="light")),
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): _number(
                1, 65535
            ),
            vol.Optional(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_WEB_PORT, default=defaults.get(CONF_WEB_PORT, DEFAULT_WEB_PORT)
            ): _number(1, 65535),
        }
    )


class BridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Add one mapping; add more integration entries for additional bulbs."""

    VERSION = 1

    def _validate(self, data: dict[str, Any], skip_entry: str | None = None) -> dict[str, str]:
        errors: dict[str, str] = {}
        data[CONF_NAME] = data[CONF_NAME].strip()
        data[CONF_HOST] = data.get(CONF_HOST, "").strip()
        data[CONF_PORT] = int(data[CONF_PORT])
        data[CONF_WEB_PORT] = int(data[CONF_WEB_PORT])
        if not data[CONF_NAME]:
            errors[CONF_NAME] = "empty_name"
        if data[CONF_HOST]:
            try:
                ip = IPv4Address(data[CONF_HOST])
                if ip.is_unspecified or ip.is_multicast or str(ip) == "255.255.255.255":
                    raise ValueError
            except ValueError:
                errors[CONF_HOST] = "invalid_ip"
        state = self.hass.states.get(data[CONF_ENTITY_ID])
        if not data[CONF_ENTITY_ID].startswith("light.") or state is None:
            errors[CONF_ENTITY_ID] = "light_missing"
        elif state.state in ("unavailable", "unknown"):
            errors[CONF_ENTITY_ID] = "light_unavailable"
        elif not COLOR_MODES.intersection(state.attributes.get("supported_color_modes", [])):
            errors[CONF_ENTITY_ID] = "color_unsupported"
        for entry in self._async_current_entries():
            if entry.entry_id == skip_entry:
                continue
            if entry.data[CONF_PORT] == data[CONF_PORT]:
                errors[CONF_PORT] = "port_in_use"
            if entry.data[CONF_ENTITY_ID] == data[CONF_ENTITY_ID]:
                errors[CONF_ENTITY_ID] = "light_in_use"
        return errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure a light, a UDP port and an optional LedFx source filter."""
        errors = {}
        if user_input is not None:
            errors = self._validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_ENTITY_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        used_ports = {e.data[CONF_PORT] for e in self._async_current_entries()}
        port = next((p for p in range(DEFAULT_PORT, 65536) if p not in used_ports), DEFAULT_PORT)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {CONF_PORT: port}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Change connections; the update listener performs the reload."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            errors = self._validate(user_input, entry.entry_id)
            if not errors:
                # Updating data notifies the listener. Do not also schedule a
                # reload here, which would compete for the same UDP port.
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                    title=user_input[CONF_NAME],
                    unique_id=user_input[CONF_ENTITY_ID],
                )
                return self.async_abort(reason="reconfigure_successful")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BridgeOptionsFlow()


class BridgeOptionsFlow(config_entries.OptionsFlow):
    """Tune outgoing starts per second, concurrency and color threshold."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            for key in (CONF_MAX_FPS, CONF_MAX_INFLIGHT, CONF_THRESHOLD):
                user_input[key] = int(user_input[key])
            return self.async_create_entry(title="", data=user_input)
        values = DEFAULT_OPTIONS | dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAX_FPS, default=values[CONF_MAX_FPS]): _number(1, 60),
                    vol.Required(CONF_MAX_INFLIGHT, default=values[CONF_MAX_INFLIGHT]): _number(
                        1, 8
                    ),
                    vol.Required(CONF_THRESHOLD, default=values[CONF_THRESHOLD]): _number(1, 255),
                    vol.Required(CONF_START_ENABLED, default=values[CONF_START_ENABLED]): bool,
                }
            ),
        )
