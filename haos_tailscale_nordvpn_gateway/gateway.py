#!/usr/bin/env python3
"""Single-namespace Tailscale + NordVPN NordLynx gateway for Home Assistant OS.

Only packets forwarded from tailscale0 are policy-routed into wg0. The
container's own control-plane traffic keeps the Supervisor app-network route.
"""
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOG = logging.getLogger("ha-nordvpn-gateway")

DATA = Path("/data")
WG_DIR = DATA / "wireguard"
KEY_FILE = WG_DIR / "private.key"
WG_CONF = WG_DIR / "wg0.conf"
TS_STATE = DATA / "tailscale" / "tailscaled.state"
WG_TABLE = "100"
WG_RULE_PRIORITY = "100"
API = "https://api.nordvpn.com/v1"
WG_TECH = "wireguard_udp"
WG_PORT = 51820
CLIENT_ADDR = "10.5.0.2/32"

TOKEN = os.environ.get("NORDVPN_TOKEN", "").strip()
TARGET = os.environ.get("NORDVPN_TARGET", "auto").strip()
AUTH_KEY = os.environ.get("TAILSCALE_AUTH_KEY", "").strip()
ADVERTISE_EXIT_NODE = os.environ.get("ADVERTISE_EXIT_NODE", "false").strip().lower() == "true"
HOSTNAME = os.environ.get("TAILSCALE_HOSTNAME", "ha-nordvpn-gateway").strip()
ROTATE_HOURS = max(1, int(os.environ.get("RECONNECT_AFTER_HOURS", "168")))
STOP = False


def run(args, check=True, capture=False):
    LOG.debug("exec: %s", " ".join(str(x) for x in args))
    return subprocess.run(
        args, check=check, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def nordvpn_get(path, params=None, auth=None):
    response = requests.get(
        f"{API}/{path}", params=params, auth=auth, timeout=25
    )
    response.raise_for_status()
    return response.json()


def ensure_private_key():
    if KEY_FILE.is_file() and KEY_FILE.stat().st_size > 30:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    if not TOKEN:
        raise RuntimeError(
            "NordVPN private key is not present in /data/wireguard/private.key. "
            "Set nordvpn_token once, or securely place the NordLynx private key "
            "in that file (permissions 0600)."
        )
    LOG.info("Requesting NordLynx key from NordVPN (token is never logged).")
    data = nordvpn_get(
        "users/services/credentials", auth=("token", TOKEN)
    )
    key = str(data.get("nordlynx_private_key", "")).strip()
    if len(key) < 40:
        raise RuntimeError("NordVPN returned an invalid or empty WireGuard key.")
    temp = KEY_FILE.with_suffix(".tmp")
    temp.write_text(key + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(KEY_FILE)
    return key


def resolve_target():
    if not TARGET or TARGET.lower() in ("auto", "any"):
        return []
    wanted = TARGET.replace("_", " ").strip().casefold()
    countries = nordvpn_get("servers/countries")
    for country in countries:
        if str(country.get("name", "")).casefold() == wanted:
            return [("filters[country_id]", str(country["id"]))]
    for country in countries:
        for city in country.get("cities", []):
            if str(city.get("name", "")).casefold() == wanted:
                return [("filters[country_city_id]", str(city["id"]))]
    raise RuntimeError(
        f"NordVPN target '{TARGET}' was not found as a country or city. "
        "Use the spelling returned by NordVPN (spaces may be underscores)."
    )


def select_server():
    params = [
        ("limit", "5"),
        ("filters[servers_technologies][identifier]", WG_TECH),
    ] + resolve_target()
    servers = nordvpn_get("servers/recommendations", params=params)
    for server in servers:
        public_key = None
        for tech in server.get("technologies", []):
            if tech.get("identifier") != WG_TECH:
                continue
            if tech.get("pivot", {}).get("status") != "online":
                continue
            for item in tech.get("metadata", []):
                if item.get("name") == "public_key":
                    public_key = item.get("value")
                    break
        endpoint_ip = server.get("station")
        if not endpoint_ip:
            for item in server.get("ips", []):
                ip_data = item.get("ip", {})
                if item.get("type") == "entry" or item.get("is_default"):
                    endpoint_ip = ip_data.get("ip")
                    if endpoint_ip:
                        break
        if public_key and endpoint_ip:
            location = server.get("locations", [{}])[0].get("country", {})
            return {
                "host": server.get("hostname", "NordVPN"),
                "ip": endpoint_ip,
                "public_key": public_key,
                "city": location.get("city", {}).get("name", "unknown"),
                "country": location.get("name", "unknown"),
            }
    raise RuntimeError(f"No online NordLynx server found for target '{TARGET or 'auto'}'.")


def configure_wireguard(key, server):
    WG_DIR.mkdir(parents=True, exist_ok=True)
    conf = (
        "[Interface]\n"
        f"PrivateKey = {key}\n"
        f"Address = {CLIENT_ADDR}\n"
        "Table = off\n"
        "\n[Peer]\n"
        f"PublicKey = {server['public_key']}\n"
        "AllowedIPs = 0.0.0.0/0\n"
        f"Endpoint = {server['ip']}:{WG_PORT}\n"
        "PersistentKeepalive = 25\n"
    )
    WG_CONF.write_text(conf, encoding="utf-8")
    WG_CONF.chmod(0o600)


def ensure_iptables_rule(table, chain, rule, position=None):
    """Install a firewall rule once; reconnects must not grow duplicate rules."""
    base = ["iptables", "-t", table]
    check = subprocess.run(
        base + ["-C", chain] + rule,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        return
    if position is None:
        run(base + ["-A", chain] + rule)
    else:
        run(base + ["-I", chain, str(position)] + rule)


def ensure_ip6tables_rule(chain, rule, position=None):
    """Install and require the IPv6 firewall rule; never silently skip the block."""
    base = ["ip6tables"]
    check = subprocess.run(
        base + ["-C", chain] + rule,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        return
    if position is None:
        run(base + ["-A", chain] + rule)
    else:
        run(base + ["-I", chain, str(position)] + rule)


def install_gateway_rules():
    # Route only forwarded tailnet client packets to the VPN. Local app
    # traffic (including tailscaled and the WireGuard outer UDP socket)
    # continues to use the Supervisor-provided eth0 default route.
    run(["ip", "route", "replace", "default", "dev", "wg0", "table", WG_TABLE])
    rules = run(["ip", "rule", "show"], capture=True).stdout
    if f"iif tailscale0 lookup {WG_TABLE}" not in rules:
        run([
            "ip", "rule", "add", "priority", WG_RULE_PRIORITY,
            "iif", "tailscale0", "lookup", WG_TABLE,
        ])
    # Fail closed: Tailscale-forwarded IPv4 packets can only leave via wg0.
    ensure_iptables_rule(
        "filter", "FORWARD", ["-i", "tailscale0", "-o", "wg0", "-j", "ACCEPT"], 1
    )
    ensure_iptables_rule(
        "filter", "FORWARD", ["-i", "tailscale0", "-j", "DROP"], 2
    )
    ensure_iptables_rule(
        "filter", "FORWARD",
        ["-i", "wg0", "-o", "tailscale0", "-m", "conntrack",
         "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"], 1
    )
    ensure_iptables_rule(
        "nat", "POSTROUTING", ["-o", "wg0", "-j", "MASQUERADE"]
    )
    # NordVPN does not provide IPv6 egress here. Explicitly block forwarded
    # IPv6 from tailnet peers instead of allowing an ISP-route leak.
    ensure_ip6tables_rule("FORWARD", ["-i", "tailscale0", "-j", "DROP"], 1)


def tunnel_egress_ok():
    result = subprocess.run(
        ["curl", "--interface", "wg0", "--fail", "--silent", "--show-error",
         "--max-time", "10", "https://api.ipify.org"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        LOG.info("NordVPN egress check passed (public IP %s).", result.stdout.strip())
        return True
    LOG.warning("NordVPN egress check failed.")
    return False


def connect_vpn():
    key = ensure_private_key()
    server = select_server()
    LOG.info("Selected NordVPN server %s (%s, %s).", server["host"], server["city"], server["country"])
    configure_wireguard(key, server)
    run(["wg-quick", "down", str(WG_CONF)], check=False)
    run(["wg-quick", "up", str(WG_CONF)])
    # Wait briefly for the handshake and real egress before advertising exit-node.
    for _ in range(12):
        if tunnel_egress_ok():
            return
        time.sleep(5)
    raise RuntimeError("NordVPN tunnel came up but did not pass the egress test.")


def start_tailscale():
    args = [
        "tailscaled",
        "--state", str(TS_STATE),
        "--socket", "/run/tailscale/tailscaled.sock",
        "--tun", "tailscale0",
    ]
    daemon = subprocess.Popen(args)
    sock = "/run/tailscale/tailscaled.sock"
    for _ in range(60):
        if Path(sock).exists():
            break
        if daemon.poll() is not None:
            raise RuntimeError("tailscaled exited during startup.")
        time.sleep(1)
    up = ["tailscale", "--socket", sock, "up", "--hostname", HOSTNAME, "--accept-dns=false"]
    if AUTH_KEY:
        up += ["--auth-key", AUTH_KEY]
    run(up)
    for _ in range(60):
        if subprocess.run(["ip", "link", "show", "tailscale0"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("tailscale0 did not appear; refusing to advertise an exit node.")
    return daemon, sock


def diagnose_nftables():
    """Log a bounded, read-only snapshot of this container's nftables ruleset."""
    try:
        result = subprocess.run(
            ["nft", "-a", "list", "ruleset"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        LOG.warning("Read-only nftables inspection unavailable: nft command not found.")
        return

    if result.returncode != 0:
        detail = result.stderr.strip() or f"nft exited with status {result.returncode}"
        LOG.warning("Read-only nftables inspection failed: %s", detail)
        return

    lines = result.stdout.splitlines()
    if not lines:
        LOG.warning("Read-only nftables inspection returned an empty ruleset.")
        return

    LOG.info("Read-only nftables ruleset follows (%d lines; maximum 120 shown):", len(lines))
    for line in lines[:120]:
        LOG.info("nft: %s", line)
    if len(lines) > 120:
        LOG.info("nft: output truncated; %d additional lines omitted.", len(lines) - 120)


def advertise_exit_node(sock):
    install_gateway_rules()
    run(["tailscale", "--socket", sock, "set", "--advertise-exit-node"])
    LOG.info("Exit node advertised. Approve it in the Tailscale admin console.")


def handle_signal(signum, frame):
    global STOP
    STOP = True
    LOG.info("Shutdown requested.")


def main():
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    WG_DIR.mkdir(parents=True, exist_ok=True)
    # Do not attempt to change sysctls: HAOS may expose them read-only to apps.
    # IPv6 forwarding from tailnet clients is blocked explicitly by ip6tables
    # in install_gateway_rules(); failure to install that rule aborts advertising.
    connect_vpn()
    daemon, sock = start_tailscale()
    if ADVERTISE_EXIT_NODE:
        advertise_exit_node(sock)
    else:
        LOG.info("Exit-node advertising is disabled; VPN tunnel is up for initial validation.")
    LOG.info("Gateway ready; Home Assistant host routes are not modified.")
    rotate_at = time.monotonic() + ROTATE_HOURS * 3600
    failures = 0
    while not STOP:
        time.sleep(30)
        if daemon.poll() is not None:
            raise RuntimeError("tailscaled exited unexpectedly.")
        if time.monotonic() >= rotate_at or not tunnel_egress_ok():
            failures += 1
            if failures >= 3 or time.monotonic() >= rotate_at:
                LOG.warning("Rotating NordVPN tunnel.")
                if ADVERTISE_EXIT_NODE:
                    run(["tailscale", "--socket", sock, "set", "--advertise-exit-node=false"], check=False)
                run(["wg-quick", "down", str(WG_CONF)], check=False)
                connect_vpn()
                if ADVERTISE_EXIT_NODE:
                    install_gateway_rules()
                    run(["tailscale", "--socket", sock, "set", "--advertise-exit-node"])
                rotate_at = time.monotonic() + ROTATE_HOURS * 3600
                failures = 0
        else:
            failures = 0
    run(["tailscale", "--socket", sock, "set", "--advertise-exit-node=false"], check=False)
    run(["wg-quick", "down", str(WG_CONF)], check=False)
    daemon.terminate()
    daemon.wait(timeout=10)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        LOG.exception("Gateway startup/runtime failure: %s", exc)
        sys.exit(1)
