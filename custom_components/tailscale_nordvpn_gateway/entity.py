"""Base entity."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class GatewayEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data["app_slug"])},
            "name": "Tailscale NordVPN Gateway",
            "manufacturer": "Home Assistant community",
            "model": "Tailscale + NordLynx add-on",
        }
