"""Gateway status sensors."""
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [GatewayStatusSensor(coordinator, entry), GatewayIpSensor(coordinator, entry)]
    )


class GatewayStatusSensor(GatewayEntity, SensorEntity):
    _attr_name = "Add-on status"
    _attr_icon = "mdi:server-network"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['app_slug']}_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("state", "unknown")

    @property
    def extra_state_attributes(self):
        return {
            "nordvpn_target": self.coordinator.data.get("target"),
            "exit_node_advertising": self.coordinator.data.get("advertise_exit_node"),
            "add_on_version": self.coordinator.data.get("version"),
        }


class GatewayIpSensor(GatewayEntity, SensorEntity):
    _attr_name = "NordVPN public IP"
    _attr_icon = "mdi:ip-network"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['app_slug']}_public_ip"

    @property
    def native_value(self):
        return self.coordinator.data.get("public_ip")
