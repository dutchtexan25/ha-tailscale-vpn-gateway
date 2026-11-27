# Changelog

## 0.1.8

- Explicitly pass the exit-node advertising boolean on every Tailscale startup.
- Avoid resending a Tailscale auth key when persisted node state is available.
- Suppress command details on Tailscale startup errors to avoid exposing credentials.

## 0.1.0

- Initial experimental HAOS app implementation.
- Single isolated app network namespace for Tailscale and NordVPN NordLynx.
- Policy routing for packets arriving from tailscale0 only.
- IPv4 forwarding kill switch and IPv6 forwarded-traffic block.
