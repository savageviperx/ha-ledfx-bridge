"""Low-frequency diagnostics; light frames never write HA states directly."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_ENTITY_ID, CONF_PORT, EntityCategory, UnitOfTime

from .entity import BridgeEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([StatusSensor(entry), SendRateSensor(entry), LatencySensor(entry)])


class StatusSensor(BridgeEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["disabled", "waiting", "streaming", "backoff", "target_unavailable"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:traffic-light"

    def __init__(self, entry):
        super().__init__(entry, "status")

    @property
    def native_value(self):
        return self.engine.status

    @property
    def extra_state_attributes(self):
        # Deliberately omit changing counters/RGB to keep Recorder writes low.
        return {
            "target_entity": self.entry.data[CONF_ENTITY_ID],
            "ddp_port": self.entry.data[CONF_PORT],
        }


class SendRateSensor(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = "updates/s"
    _attr_icon = "mdi:speedometer"

    def __init__(self, entry):
        super().__init__(entry, "send_rate")

    @property
    def native_value(self):
        return self.engine.snapshot()["send_rate"]


class LatencySensor(BridgeEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry):
        super().__init__(entry, "latency")

    @property
    def native_value(self):
        return self.engine.snapshot()["latency_ms"]
