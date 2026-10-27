"""Common entity metadata and one-second UI updates."""

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import update_signal
from .const import CONF_WEB_PORT, DEFAULT_WEB_PORT, DOMAIN, NAME, VERSION


class BridgeEntity(Entity):
    """One device per mapping, independent from the target light's device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, key: str) -> None:
        self.entry = entry
        self.engine = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=NAME,
            model="DDP to Home Assistant light",
            sw_version=VERSION,
        )
        if host := entry.data.get(CONF_HOST):
            port = entry.data.get(CONF_WEB_PORT, DEFAULT_WEB_PORT)
            self._attr_device_info["configuration_url"] = f"http://{host}:{port}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                update_signal(self.entry.entry_id),
                self._refresh,
            )
        )

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()
