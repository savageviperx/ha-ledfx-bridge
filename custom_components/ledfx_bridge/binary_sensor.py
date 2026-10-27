"""Whether valid DDP frames arrived during the last five seconds."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import BridgeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ReceivingSensor(entry, "receiving")])


class ReceivingSensor(BridgeEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return self.engine.receiving
