"""Exit-node advertising switch."""
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ExitNodeSwitch(coordinator, entry)])


class ExitNodeSwitch(GatewayEntity, SwitchEntity):
    _attr_name = "Advertise exit node"
    _attr_icon = "mdi:transit-connection-variant"

    @property
    def is_on(self):
        return bool(self.coordinator.data.get("advertise_exit_node", False))

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.set_options({"advertise_exit_node": True})
        await self.coordinator.api.restart()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.set_options({"advertise_exit_node": False})
        await self.coordinator.api.restart()
        await self.coordinator.async_request_refresh()
