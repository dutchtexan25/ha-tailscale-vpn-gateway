"""Config flow."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi, GatewayApiError
from .const import DOMAIN


class GatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                api, app = await GatewayApi.discover(session)
                await api.get_info()
            except GatewayApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(api.app_slug)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=app.get("name", "Tailscale NordVPN Gateway"),
                    data={"app_slug": api.app_slug},
                )
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({}), errors=errors
        )
