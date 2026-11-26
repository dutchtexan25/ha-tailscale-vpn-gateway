"""NordVPN target selector."""
from __future__ import annotations

import asyncio

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .entity import GatewayEntity

NORDVPN_COUNTRIES_URL = "https://api.nordvpn.com/v1/servers/countries"


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NordVpnTargetSelect(hass, coordinator, entry)])


class NordVpnTargetSelect(GatewayEntity, SelectEntity):
    _attr_name = "NordVPN location"
    _attr_icon = "mdi:map-marker"

    def __init__(self, hass, coordinator, entry):
        super().__init__(coordinator, entry)
        self.hass = hass
        self._attr_unique_id = f"{entry.data['app_slug']}_nordvpn_target"
        self._attr_options = ["auto"]

    @property
    def current_option(self):
        current = str(self.coordinator.data.get("target", "auto"))
        return current if current in self.options else "auto"

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        try:
            session = async_get_clientsession(self.hass)
            async with asyncio.timeout(20):
                async with session.get(NORDVPN_COUNTRIES_URL) as response:
                    response.raise_for_status()
                    countries = await response.json()
            options = {"auto"}
            for country in countries:
                name = str(country.get("name", "")).strip()
                if name:
                    options.add(name.replace(" ", "_"))
                for city in country.get("cities", []):
                    city_name = str(city.get("name", "")).strip()
                    if city_name:
                        options.add(city_name.replace(" ", "_"))
            current = str(self.coordinator.data.get("target", "auto"))
            options.add(current)
            self._attr_options = sorted(options, key=str.casefold)
            self.async_write_ha_state()
        except (OSError, asyncio.TimeoutError, ValueError):
            current = str(self.coordinator.data.get("target", "auto"))
            self._attr_options = sorted(set(self._attr_options + [current]), key=str.casefold)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError("Unsupported NordVPN target")
        await self.coordinator.api.set_options({"nordvpn_target": option})
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "target": option}
        )
        await self.coordinator.api.restart()
