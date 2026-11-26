FROM tailscale/tailscale:v1.104.7

RUN apk add --no-cache \
    bash \
    ca-certificates \
    curl \
    iproute2 \
    iptables \
    ip6tables \
    nftables \
    python3 \
    py3-requests \
    wireguard-tools

COPY run.sh /run.sh
COPY gateway.py /gateway.py
RUN chmod 0755 /run.sh /gateway.py

ENTRYPOINT ["/run.sh"]
