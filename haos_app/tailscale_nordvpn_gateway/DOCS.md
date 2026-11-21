# Configuration and safety notes

## Configuration

- `nordvpn_token`: NordVPN access token. Used to fetch the NordLynx private
  key if `/data/wireguard/private.key` does not already exist.
- `nordvpn_target`: NordVPN country or city name. Defaults to
  `San_Francisco`; `auto` selects NordVPN's recommended server.
- `tailscale_auth_key`: optional Tailscale auth key. If omitted, complete
  authentication using the URL shown in the app log.
- `tailscale_hostname`: node name in the tailnet.
- `reconnect_after_hours`: rotate to a fresh recommended server after this
  many hours (1–720).

## Routing model

The app runs with its own network namespace. It does not set HAOS host routes.
The WireGuard config uses `Table = off`; a dedicated routing table is populated
with a default route through `wg0`, and a policy rule matches only packets
whose input interface is `tailscale0`. The main routing table remains on the
Supervisor app network, so the Tailscale coordination connection and the
outer WireGuard UDP packets do not recurse into the VPN tunnel.

A forwarding firewall rule permits Tailscale client traffic only out `wg0`.
A kill-switch drop rule blocks any other forwarded IPv4 path. IPv6 forwarded
traffic is dropped because this version does not tunnel IPv6 through NordVPN.

## Before using it

- Confirm a current full Home Assistant backup exists and can be restored.
- Confirm the app's WireGuard module can be loaded in HAOS.
- Confirm app removal leaves Home Assistant connectivity unchanged.
- Confirm no Tailscale client traffic exits via the ISP when wg0 is down.
- Confirm the app can reconnect without losing persistent Tailscale identity.
- Confirm DNS requests from remote clients use a resolver reachable over the
  VPN path and do not leak via the ISP.
