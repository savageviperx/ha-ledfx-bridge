"""Counters without names, tokens, IP addresses, entity IDs or raw frames."""

from .const import CONF_MAX_FPS, CONF_MAX_INFLIGHT, CONF_THRESHOLD, DEFAULT_OPTIONS, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    options = DEFAULT_OPTIONS | dict(entry.options)
    return {
        "version": VERSION,
        "settings": {
            key: options[key] for key in (CONF_MAX_FPS, CONF_MAX_INFLIGHT, CONF_THRESHOLD)
        },
        "statistics": entry.runtime_data.snapshot(),
    }
