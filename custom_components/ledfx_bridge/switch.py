"""Pause/resume music synchronization, restoring the last switch state."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import BridgeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SyncSwitch(entry, "sync")])


class SyncSwitch(BridgeEntity, SwitchEntity, RestoreEntity):
    """Already sent lamp commands may finish after this switch is turned off."""

    _attr_icon = "mdi:music-sync"

    @property
    def is_on(self):
        return self.engine.enabled

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last := await self.async_get_last_state():
            self.engine.set_enabled(last.state == "on")

    async def async_turn_on(self, **kwargs):
        self.engine.set_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self.engine.set_enabled(False)
        self.async_write_ha_state()
