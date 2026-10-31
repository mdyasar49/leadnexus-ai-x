import socket
import ipaddress
import logging
from urllib.parse import urlparse
from typing import Tuple, Optional

logger = logging.getLogger("leadnexus.browser.ssrf")

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),          # RFC 1918 private
    ipaddress.ip_network("100.64.0.0/10"),       # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),         # Loopback
    ipaddress.ip_network("169.254.0.0/16"),      # Link-local / AWS / GCP / Azure metadata
    ipaddress.ip_network("172.16.0.0/12"),       # RFC 1918 private
    ipaddress.ip_network("192.0.0.0/24"),        # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),        # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),      # RFC 1918 private
    ipaddress.ip_network("198.18.0.0/15"),       # Network benchmark tests
    ipaddress.ip_network("198.51.100.0/24"),     # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),      # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),         # Multicast
    ipaddress.ip_network("240.0.0.0/4"),         # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),             # IPv6 Loopback
    ipaddress.ip_network("::/128"),              # IPv6 Unspecified
    ipaddress.ip_network("fc00::/7"),            # Unique local
    ipaddress.ip_network("fe80::/10"),           # Link-local unicast
    ipaddress.ip_network("ff00::/8"),            # Multicast
]


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks whether an IP falls into private, loopback, or metadata ranges."""
    for network in BLOCKED_IP_NETWORKS:
        if ip in network:
            return True
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved


def validate_safe_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Strict SSRF validation:
    1. Enforces HTTP or HTTPS.
    2. Checks hostname blocklist.
    3. Resolves DNS to IP and checks against all private/internal network ranges.
    Returns (is_safe, error_reason).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

        hostname = (parsed.hostname or "").lower().strip()
        if not hostname:
            return False, "Missing hostname in URL."

        if hostname in BLOCKED_HOSTNAMES:
            return False, f"Hostname '{hostname}' is explicitly blocked (internal/metadata)."

        # Reject direct private IP notation in hostname
        try:
            direct_ip = ipaddress.ip_address(hostname)
            if is_ip_blocked(direct_ip):
                return False, f"Destination IP {direct_ip} is in a private, loopback, or restricted network."
            return True, None
        except ValueError:
            pass  # It is a domain name, proceed to DNS resolution

        # Resolve DNS to verify destination IP
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if is_ip_blocked(ip_obj):
                    logger.warning(f"[SSRF Protection] Blocked unsafe target {hostname} resolved to {ip_str}")
                    return False, f"Hostname '{hostname}' resolves to restricted IP {ip_str}."
        except socket.gaierror as e:
            return False, f"DNS resolution failed for hostname '{hostname}': {e}"

        return True, None
    except Exception as e:
        logger.error(f"[SSRF Protection] Error during URL validation for {url}: {e}")
        return False, f"URL validation error: {str(e)}"

