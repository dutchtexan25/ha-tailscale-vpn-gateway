"""Tailscale NordVPN Gateway integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi
from .const import DOMAIN, PLATFORMS
from .coordinator import GatewayCoordinator

type GatewayConfigEntry = ConfigEntry[GatewayCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GatewayConfigEntry) -> bool:
    api = GatewayApi(async_get_clientsession(hass), entry.data["app_slug"])
    coordinator = GatewayCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GatewayConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
