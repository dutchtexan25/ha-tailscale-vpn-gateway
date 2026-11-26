"""Data coordinator."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GatewayApi, GatewayApiError
from .const import DOMAIN, UPDATE_INTERVAL


class GatewayCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, api: GatewayApi) -> None:
        super().__init__(
            hass, hass.helpers if hasattr(hass, "helpers") else None,
            name=DOMAIN, update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            info, options, logs = await __import__("asyncio").gather(
                self.api.get_info(), self.api.get_options(), self.api.get_logs()
            )
        except GatewayApiError as err:
            raise UpdateFailed(str(err)) from err

        state = str(info.get("state", info.get("status", "unknown"))).lower()
        ip_match = re.findall(r"NordVPN egress check passed \(public IP ([0-9a-fA-F:.]+)\)", logs)
        return {
            "state": state,
            "target": options.get("nordvpn_target", "unknown"),
            "advertise_exit_node": bool(options.get("advertise_exit_node", False)),
            "public_ip": ip_match[-1] if ip_match else None,
            "last_log": logs[-500:] if logs else "",
            "updated_at": datetime.now(timezone.utc),
            "version": info.get("version"),
            "name": info.get("name"),
        }
