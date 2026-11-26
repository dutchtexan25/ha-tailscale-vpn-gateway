"""Gateway actions."""
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GatewayRestartButton(coordinator, entry)])


class GatewayRestartButton(GatewayEntity, ButtonEntity):
    _attr_name = "Reconnect gateway"
    _attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        await self.coordinator.api.restart()
        await self.coordinator.async_request_refresh()
