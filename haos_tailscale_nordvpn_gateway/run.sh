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
export ADVERTISE_EXIT_NODE="$(option advertise_exit_node)"

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

# Home Assistant OS app containers cannot write host-wide sysctls. Read the
# current host values instead; never try to change them from inside this app.
IPV4_FORWARDING="$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo unknown)"
IPV6_FORWARDING="$(cat /proc/sys/net/ipv6/conf/all/forwarding 2>/dev/null || echo unknown)"
log "Host IPv4 forwarding: $IPV4_FORWARDING"
log "Host IPv6 forwarding: $IPV6_FORWARDING"

# Forwarding is only required when this app is configured to advertise an
# exit node. Fail closed if the host is not already in the expected state.
if [ "$ADVERTISE_EXIT_NODE" = "true" ]; then
  if [ "$IPV4_FORWARDING" != "1" ]; then
    log "ERROR: Exit-node mode requires host IPv4 forwarding to be enabled."
    exit 1
  fi
  if [ "$IPV6_FORWARDING" != "0" ]; then
    log "ERROR: Exit-node mode requires host IPv6 forwarding to be disabled."
    log "No host sysctl values were changed."
    exit 1
  fi
fi

python3 /gateway.py
