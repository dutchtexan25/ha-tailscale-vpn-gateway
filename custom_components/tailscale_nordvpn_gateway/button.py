"""Gateway actions."""
from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GatewayRestartButton(coordinator, entry)])


class GatewayRestartButton(GatewayEntity, ButtonEntity):
    _attr_name = "Restart gateway"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['app_slug']}_restart"

    async def async_press(self) -> None:
        await self.coordinator.api.restart()
