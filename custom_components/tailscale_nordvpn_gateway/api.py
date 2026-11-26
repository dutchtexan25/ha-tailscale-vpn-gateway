"""Supervisor API client for the gateway add-on."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from aiohttp import ClientError, ClientSession

SUPERVISOR_URL = "http://supervisor"


class GatewayApiError(Exception):
    """Raised when the Supervisor API request fails."""


class GatewayApi:
    def __init__(self, session: ClientSession, app_slug: str) -> None:
        self._session = session
        self.app_slug = app_slug
        self._token = os.environ.get("SUPERVISOR_TOKEN", "")

    @classmethod
    async def discover(cls, session: ClientSession) -> tuple["GatewayApi", dict[str, Any]]:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not token:
            raise GatewayApiError("Home Assistant Supervisor token is unavailable")
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with asyncio.timeout(15):
                async with session.get(f"{SUPERVISOR_URL}/addons", headers=headers) as response:
                    response.raise_for_status()
                    payload = await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise GatewayApiError(f"Cannot contact Home Assistant Supervisor: {err}") from err

        data = payload.get("data", payload)
        apps = data.get("addons", []) if isinstance(data, dict) else []
        matches = [
            app for app in apps
            if str(app.get("slug", "")).endswith("tailscale_nordvpn_gateway")
            or app.get("name") == "Tailscale NordVPN Exit Gateway"
        ]
        if len(matches) != 1:
            raise GatewayApiError(
                "Expected exactly one installed Tailscale NordVPN Gateway add-on; "
                f"found {len(matches)}"
            )
        api = cls(session, matches[0]["slug"])
        return api, matches[0]

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> dict:
        if not self._token:
            raise GatewayApiError("Supervisor token is unavailable")
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(20):
                async with self._session.request(
                    method, f"{SUPERVISOR_URL}{path}", headers=headers, json=json
                ) as response:
                    body = await response.json(content_type=None)
                    if response.status >= 400:
                        message = body.get("message") or body.get("error") or str(body)
                        raise GatewayApiError(f"Supervisor API returned {response.status}: {message}")
                    return body.get("data", body)
        except GatewayApiError:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            raise GatewayApiError(f"Supervisor API request failed: {err}") from err

    async def get_info(self) -> dict:
        return await self._request("GET", f"/addons/{self.app_slug}/info")

    async def get_options(self) -> dict:
        data = await self._request("GET", f"/addons/{self.app_slug}/options/config")
        return data.get("options", data)

    async def set_options(self, values: dict[str, Any]) -> None:
        await self._request(
            "POST", f"/addons/{self.app_slug}/options", json={"options": values}
        )

    async def restart(self) -> None:
        await self._request("POST", f"/addons/{self.app_slug}/restart", json={})

    async def get_logs(self) -> str:
        if not self._token:
            raise GatewayApiError("Supervisor token is unavailable")
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(20):
                async with self._session.get(
                    f"{SUPERVISOR_URL}/addons/{self.app_slug}/logs/latest",
                    headers=headers,
                ) as response:
                    text = await response.text()
                    if response.status >= 400:
                        raise GatewayApiError(
                            f"Supervisor logs API returned {response.status}: {text[:300]}"
                        )
                    return text
        except GatewayApiError:
            raise
        except (ClientError, TimeoutError) as err:
            raise GatewayApiError(f"Cannot read gateway logs: {err}") from err
