# Tailscale NordVPN Exit Gateway (Home Assistant OS)

This is an **experimental** Home Assistant app for an aarch64 Home Assistant OS
host. It runs Tailscale and NordVPN NordLynx in one isolated app network
namespace. It does not use host networking, Docker socket access, or host route
changes.

## Current scope

- Tailscale exit-node advertisement.
- NordVPN WireGuard/NordLynx tunnel, with a NordVPN access token used only to
  obtain the WireGuard private key on first start.
- Policy routing applies only to packets arriving from `tailscale0`.
- IPv4 forwarded traffic is NATed out `wg0`.
- IPv6 forwarded traffic is blocked (NordVPN IPv6 egress is not configured).
- Forwarded traffic fails closed if the VPN interface is unavailable.
- Tailscale state and the NordLynx private key persist under the app's
  Supervisor-managed `/data` directory.

The upstream control panel is deliberately not included in this first
dataplane milestone.

## Install for development

1. Back up Home Assistant and verify that you can restore it.
2. In Home Assistant, open **Settings → Apps → App store → ⋮ → Repositories**.
3. Add this repository URL:
   `https://github.com/dutchtexan25/ha-tailscale-vpn-gateway`
4. Find **Tailscale NordVPN Exit Gateway** under this repository in the app store.
5. Configure `nordvpn_token` with a NordVPN access token, and optionally set
   `nordvpn_target` (country or city, default `San_Francisco`).
6. Configure a Tailscale auth key in `tailscale_auth_key` (recommended for
   unattended setup). Use a one-off/preauthorized key with the minimum tags
   and expiry appropriate for your tailnet.
7. Install and start the app. The log should show a successful NordVPN egress
   check and then an exit-node advertisement.
8. Approve the new `ha-nordvpn-gateway` node as an exit node in the Tailscale
   admin console.
9. From a remote tailnet client, select this exit node and verify the public
   IP is NordVPN's, not your ISP's.

## Persistent private key

On first boot, `nordvpn_token` is used to fetch the NordLynx private key. The
key is stored as `/data/wireguard/private.key` with mode 0600. After that,
the token can be cleared from the app configuration; the key remains in the
app's persistent data. Never commit or share this file.

## Important limitations

This is an early implementation, not yet a validated release. The Raspberry Pi
4 / HAOS kernel combination must be tested for WireGuard module availability
and Supervisor device/capability behavior. The app must also be tested for
direct Tailscale UDP reachability, route selection, IPv6 leak prevention,
kill-switch behavior during tunnel failure, and clean removal.

Do not install on the production Home Assistant instance until the test plan
passes on a spare or disposable HAOS system. No test has yet been run on the
user's Raspberry Pi.

## Troubleshooting

- **WireGuard kernel support unavailable:** the app exits before advertising
  an exit node. Check that the HAOS kernel exposes the WireGuard module.
- **NordVPN target not found:** use a country or city name from NordVPN's
  server catalogue; spaces may be entered as underscores.
- **Tailscale login required:** inspect app logs for the authentication URL,
  or configure a valid auth key and restart.
- **No exit-node option appears:** approve the advertised node in the Tailscale
  admin console.
