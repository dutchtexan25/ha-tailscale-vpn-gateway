#!/bin/bash
set -Eeuo pipefail

OPTIONS=/data/options.json
DATA=/data
STATE_DIR=/data/tailscale
WG_DIR=/data/wireguard
mkdir -p "$STATE_DIR" "$WG_DIR" /run/tailscale

option() {
  python3 - "$1" "$OPTIONS" <<'PY'
import json, sys
with open(sys.argv[2], encoding="utf-8") as f:
    data = json.load(f)
value = data.get(sys.argv[1], "")
if value is None:
    value = ""
print(value)
PY
}

export NORDVPN_TOKEN="$(option nordvpn_token)"
export NORDVPN_TARGET="$(option nordvpn_target)"
export TAILSCALE_AUTH_KEY="$(option tailscale_auth_key)"
export TAILSCALE_HOSTNAME="$(option tailscale_hostname)"
export RECONNECT_AFTER_HOURS="$(option reconnect_after_hours)"

log() { printf '[gateway] %s\n' "$*"; }

if [ ! -c /dev/net/tun ]; then
  log "ERROR: /dev/net/tun is unavailable. Check the app device mapping."
  exit 1
fi

if ! command -v wg >/dev/null || ! ip link add wg-test type wireguard 2>/dev/null; then
  ip link del wg-test 2>/dev/null || true
  log "ERROR: WireGuard kernel support is unavailable on this Home Assistant OS kernel."
  log "The app needs the host WireGuard module; no host networking changes were made."
  exit 1
fi
ip link del wg-test 2>/dev/null || true

sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv6.conf.all.forwarding=0

python3 /gateway.py
