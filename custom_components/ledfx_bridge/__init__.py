"""Receive LedFx DDP colors and forward them to existing HA lights."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    COLOR_MODES,
    CONF_MAX_FPS,
    CONF_MAX_INFLIGHT,
    CONF_START_ENABLED,
    CONF_THRESHOLD,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .engine import RGB, BridgeEngine, Settings, light_command

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


def update_signal(entry_id: str) -> str:
    """Separate UI refreshes for each configured bulb."""
    return f"{DOMAIN}_{entry_id}_updated"


def target_supports_color(hass: HomeAssistant, entity_id: str) -> bool:
    """Missing entities can recover later without deleting the mapping."""
    state = hass.states.get(entity_id)
    return bool(
        state
        and state.state not in ("unavailable", "unknown")
        and COLOR_MODES.intersection(state.attributes.get("supported_color_modes", []))
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one light mapping. HA persists all settings; no token is needed."""
    options = DEFAULT_OPTIONS | dict(entry.options)
    entity_id = entry.data[CONF_ENTITY_ID]

    async def send(rgb: RGB) -> None:
        if not target_supports_color(hass, entity_id):
            raise HomeAssistantError("Target light is unavailable")
        action, payload = light_command(rgb)
        state = hass.states.get(entity_id)
        if state and int(state.attributes.get("supported_features", 0)) & 32:
            payload["transition"] = 0
        # Each of these calls waits for its own result. The engine runs up to
        # four calls concurrently, so one 160 ms call does not stall the stream.
        await hass.services.async_call(
            "light",
            action,
            payload,
            target={CONF_ENTITY_ID: entity_id},
            blocking=True,
        )

    engine = BridgeEngine(
        Settings(
            port=entry.data[CONF_PORT],
            source_ip=entry.data.get(CONF_HOST, ""),
            max_fps=options[CONF_MAX_FPS],
            max_inflight=options[CONF_MAX_INFLIGHT],
            threshold=options[CONF_THRESHOLD],
        ),
        send,
        ready=lambda: target_supports_color(hass, entity_id),
        create_task=lambda coro, name: entry.async_create_background_task(
            hass,
            coro,
            name,
            eager_start=False,
        ),
        enabled=options[CONF_START_ENABLED],
    )
    try:
        await engine.start()
    except OSError as exc:
        raise ConfigEntryNotReady(
            f"Cannot bind UDP port {entry.data[CONF_PORT]}; check for another DDP receiver"
        ) from exc
    entry.runtime_data = engine
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await engine.stop()
        raise

    @callback
    def refresh(_now=None) -> None:
        async_dispatcher_send(hass, update_signal(entry.entry_id))

    entry.async_on_unload(async_track_time_interval(hass, refresh, timedelta(seconds=1)))
    entry.async_on_unload(entry.add_update_listener(_options_updated))

    async def stop_on_shutdown(_event) -> None:
        await engine.stop()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_on_shutdown))
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply options by reloading; keep this separate from reconfiguration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Disable or reload without leaving sockets or scheduler tasks behind."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.stop()
    return True
