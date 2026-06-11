"""
Phase 40b — SSRF guard (adapted from OpenJarvis).

Blocks fetches to internal/private/reserved networks so a user request can't
make JARVIS reach into the local network (e.g. http://192.168.1.1/admin,
http://169.254.169.254/ cloud metadata, http://localhost:5000 self-loop).

Use for NON-security fetches (news, research, document URLs). Do NOT apply to
the Ultron security agent — scanning your own internal hosts is its purpose.
"""
import ipaddress
import socket
from urllib.parse import urlparse

# Schemes we allow to be fetched at all
_ALLOWED_SCHEMES = {"http", "https"}

# Cloud metadata + obvious internal hostnames blocked outright
_BLOCKED_HOSTNAMES = {
    "localhost", "metadata", "metadata.google.internal",
}


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def is_safe_url(url: str) -> tuple[bool, str]:
    """Return (safe, reason). safe=True only for public http(s) hosts."""
    if not url or not isinstance(url, str):
        return False, "empty url"

    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"scheme '{parsed.scheme}' not allowed (http/https only)"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "no host"

    if host in _BLOCKED_HOSTNAMES:
        return False, f"blocked hostname '{host}'"

    # Direct IP literal in URL
    if _is_private_ip(host):
        return False, f"private/reserved IP '{host}'"

    # Resolve hostname → reject if ANY resolved address is internal
    # (defends against DNS rebinding to internal ranges)
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as e:
        return False, f"DNS resolution failed: {e}"

    for info in infos:
        ip_str = info[4][0]
        if _is_private_ip(ip_str):
            return False, f"host '{host}' resolves to internal IP {ip_str}"

    return True, "ok"


def assert_safe_url(url: str) -> None:
    """Raise ValueError if url is not safe to fetch."""
    safe, reason = is_safe_url(url)
    if not safe:
        raise ValueError(f"Blocked unsafe URL: {reason}")
