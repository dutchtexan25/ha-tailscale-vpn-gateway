"""Constants for the Tailscale NordVPN Gateway integration."""
from datetime import timedelta

DOMAIN = "tailscale_nordvpn_gateway"
PLATFORMS = ["sensor", "select", "switch", "button"]
UPDATE_INTERVAL = timedelta(seconds=30)
APP_NAME = "Tailscale NordVPN Exit Gateway"
APP_SLUG_SUFFIX = "tailscale_nordvpn_gateway"
