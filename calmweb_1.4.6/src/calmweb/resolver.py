"""Blocklist downloading, parsing, and domain resolution.

Handles hosts-file format, plain domain lists, CSV, ZIP archive
blocklists and whitelists (exact, wildcard, CIDR).  Provides
background reload on a configurable timer.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import ssl
import requests
import certifi
import threading
import time
import traceback
import zipfile
from urllib.parse import urlparse

import urllib3

from . import config
from .log import log

# ------------------------------------------------------------------
# Module-level helpers (used by both blocklist and whitelist loaders)
# ------------------------------------------------------------------

def _looks_like_ip(s: str) -> bool:
    """Return True if *s* parses as a valid IP address."""
    try:
        ipaddress.ip_address(s)
        return True
    except Exception:
        return False


def _download_content(url: str, http: urllib3.PoolManager) -> bytes | None:
    """Download from *url* (or read from ``file://``) with retries.

    Returns raw bytes or ``None`` on failure.  Handles the retry loop
    that currently exists inline in the loader methods.
    """
    for attempt in range(config.DOWNLOAD_MAX_RETRIES):
        try:
            log(f"\u2b07\ufe0f Loading blocklist {url} (attempt {attempt + 1})")

            if url.startswith("file://"):
                file_path = url[7:]  # Strip "file://"
                with open(file_path, "rb") as f:
                    raw_data = f.read()
            else:
                response = http.request(
                    "GET",
                    url,
                    timeout=urllib3.Timeout(
                        connect=config.BLOCKLIST_TIMEOUT_CONNECT_SECS,
                        read=config.BLOCKLIST_TIMEOUT_READ_SECS,
                    ),
                )
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                raw_data = response.data

            if len(raw_data) > config.MAX_BLOCKLIST_BYTES:
                raise Exception(
                    f"Payload too large ({len(raw_data)} bytes > {config.MAX_BLOCKLIST_BYTES})"
                )

            return raw_data

        except Exception as e:
            log(f"[Error] Loading {url} attempt {attempt + 1}: {e}")
            time.sleep(config.DOWNLOAD_RETRY_BASE_DELAY_SECS + attempt * 2)

    log(f"[\u26a0\ufe0f] Failed to download blocklist from {url}")
    return None


# ------------------------------------------------------------------
# Blocklist line parsers
# ------------------------------------------------------------------

def _parse_csv_line(line: str) -> str | None:
    """Parse a CSV line (URLHaus format) and return the hostname, or ``None``."""
    try:
        reader = csv.reader(io.StringIO(line))
        row = next(reader)
        if len(row) >= 3:
            url_candidate = row[2].strip('"').strip()
            host = urlparse(url_candidate).hostname
            if host:
                host = host.lower()
                try:
                    ipaddress.ip_address(host)
                    return host
                except ValueError:
                    if len(host) <= 253:
                        return host
    except Exception:
        pass
    return None


def _parse_hosts_line(line: str) -> str | None:
    """Parse a hosts-file or plain domain line and return the domain, or ``None``.

    Handles lines like ``0.0.0.0 ads.example.com``, ``127.0.0.1 ads.example.com``,
    plain ``ads.example.com``, and strips inline ``#`` comments.
    """
    line = line.split("#", 1)[0].strip()
    if not line:
        return None

    parts = line.split()
    domain: str | None = None
    if len(parts) == 1:
        domain = parts[0]
    elif len(parts) >= 2:
        domain = parts[0] if not _looks_like_ip(parts[0]) else parts[1]

    if not domain:
        return None

    domain = domain.lower().lstrip(".")
    if not domain or len(domain) > 253:
        return None
    if _looks_like_ip(domain):
        return None
    return domain


# ------------------------------------------------------------------
# Blocklist content parsers
# ------------------------------------------------------------------

def _parse_text_blocklist(content: str, domains: set[str], cap_reached: bool) -> bool:
    """Parse plain text blocklist content (hosts-file format, plain domain list).

    Returns updated *cap_reached* flag.
    """
    for line in content.splitlines():
        if cap_reached:
            break
        domain = _parse_hosts_line(line)
        if domain:
            domains.add(domain)
            if len(domains) >= config.MAX_BLOCKED_DOMAINS:
                cap_reached = True
                log(
                    f"\u26a0\ufe0f Domain limit reached ({config.MAX_BLOCKED_DOMAINS}), truncating."
                )
                break
    return cap_reached


def _parse_zip_blocklist(
    raw_data: bytes,
    url: str,
    domains: set[str],
    cap_reached: bool,
) -> bool:
    """Extract and parse ZIP archive contents.  Returns updated *cap_reached*."""
    log(f"\u2B1C ZIP archive detected: {url}")
    with zipfile.ZipFile(io.BytesIO(raw_data)) as zf:
        for name in zf.namelist():
            if cap_reached:
                break
            if not name.lower().endswith((".txt", ".csv", ".log")):
                continue
            log(f"   -> Reading {name} from ZIP archive")
            content = zf.read(name).decode("utf-8", errors="ignore")

            for line in content.splitlines():
                if cap_reached:
                    break
                if not line or line.startswith("#"):
                    continue
                # CSV format (e.g. URLHaus)
                if line.startswith('"') and "," in line:
                    host = _parse_csv_line(line)
                    if host:
                        domains.add(host)
                else:
                    # Plain text / hosts-file format
                    domain = _parse_hosts_line(line)
                    if domain:
                        domains.add(domain)

                if len(domains) >= config.MAX_BLOCKED_DOMAINS:
                    cap_reached = True
                    log(
                        f"\u26a0\ufe0f Domain limit reached "
                        f"({config.MAX_BLOCKED_DOMAINS}), truncating."
                    )
    return cap_reached


def _parse_blocklist_content(
    raw_data: bytes,
    url: str,
    domains: set[str],
    cap_reached: bool,
) -> bool:
    """Parse raw content and add domains to the set.

    Handles both ZIP and plain text formats.
    Returns updated *cap_reached* flag.
    """
    if zipfile.is_zipfile(io.BytesIO(raw_data)):
        return _parse_zip_blocklist(raw_data, url, domains, cap_reached)
    content = raw_data.decode("utf-8", errors="ignore")
    return _parse_text_blocklist(content, domains, cap_reached)


# ------------------------------------------------------------------
# Whitelist entry parser
# ------------------------------------------------------------------

def _parse_whitelist_entry(
    entry: str,
) -> tuple[str | None, ipaddress.IPv4Network | ipaddress.IPv6Network | None]:
    """Parse a single whitelist entry.

    Returns ``(domain, None)`` for domain/IP strings,
    ``(None, network)`` for CIDR ranges, or ``(None, None)`` if invalid.
    """
    # Wildcard *.example.com -> store example.com
    if entry.startswith("*."):
        domain = entry[2:].lstrip(".")
        if domain and not _looks_like_ip(domain):
            return domain, None
        return None, None

    # CIDR or IP network
    if "/" in entry:
        try:
            net = ipaddress.ip_network(entry, strict=False)
            return None, net
        except Exception:
            return None, None

    # Plain IP
    if _looks_like_ip(entry):
        return entry, None

    # Plain domain
    entry = entry.lstrip(".")
    if entry and not _looks_like_ip(entry) and len(entry) <= 253:
        return entry, None

    return None, None


# ===================================================================
# BlocklistResolver
# ===================================================================

class BlocklistResolver:
    """Download, parse, and query blocklists / whitelists."""

    def __init__(
        self,
        blocklist_urls: list[str],
        reload_interval: int = 3600,
    ) -> None:
        self.blocklist_urls: list[str] = list(blocklist_urls)
        self.reload_interval: int = max(60, int(reload_interval or 3600))
        self.blocked_domains: set[str] = set()
        self.last_reload: float = 0
        self._lock = threading.Lock()
        self._loading_lock = threading.Lock()

        # Dedicated whitelist structures
        self.whitelisted_domains_local: set[str] = set()
        self.whitelisted_networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
        self.whitelist_download_successful: bool = False

        # Initial load (tolerant of errors)
        try:
            self._load_blocklist()
            self._load_whitelist()
        except Exception as e:
            log(f"BlocklistResolver init error: {e}")

    # ------------------------------------------------------------------
    # Blocklist loading
    # ------------------------------------------------------------------

    def _load_blocklist(self) -> None:
        """Download all configured blocklists and rebuild the blocked-domains set."""
        if self._loading_lock.locked():
            log("Blocklist load already in progress, skipping.")
            return
        with self._loading_lock:
            config._RESOLVER_LOADING.set()
            try:
                domains: set[str] = set()
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                http = urllib3.PoolManager(
                    cert_reqs="CERT_REQUIRED",
                    ssl_context=ssl_context,
                )
                cap_reached = False

                for url in self.blocklist_urls:
                    if cap_reached:
                        break
                    raw_data = _download_content(url, http)
                    if raw_data is None:
                        continue
                    cap_reached = _parse_blocklist_content(raw_data, url, domains, cap_reached)

                # Atomic blocklist update
                with self._lock:
                    self.blocked_domains = domains
                    self.last_reload = time.time()

                log(f"\u2705 {len(domains)} blocked domains/IPs loaded.")

            except Exception as e:
                log(f"Error in _load_blocklist: {e}\n{traceback.format_exc()}")

            finally:
                config._RESOLVER_LOADING.clear()

    # ------------------------------------------------------------------
    # Whitelist loading
    # ------------------------------------------------------------------

    def _load_whitelist(self) -> None:
        """Download and parse whitelists, updating local and global sets."""
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            http = urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED",
                ssl_context=ssl_context,
            )
            new_domains: set[str] = set()
            new_networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()
            any_download_succeeded = False

            # Seed with global whitelisted_domains from config
            try:
                for d in config.whitelisted_domains:
                    if isinstance(d, str) and d:
                        new_domains.add(d.lower().lstrip("."))
            except Exception:
                pass

            for url in config.WHITELIST_URLS:
                for attempt in range(config.DOWNLOAD_MAX_RETRIES):
                    try:
                        log(f"\u2b07\ufe0f Downloading whitelist {url} (attempt {attempt + 1})")
                        response = http.request(
                            "GET",
                            url,
                            timeout=urllib3.Timeout(
                                connect=config.WHITELIST_TIMEOUT_CONNECT_SECS,
                                read=config.WHITELIST_TIMEOUT_READ_SECS,
                            ),
                        )
                        if response.status != 200:
                            raise Exception(f"HTTP {response.status}")
                        content = response.data.decode("utf-8", errors="ignore")
                        for line in content.splitlines():
                            try:
                                line = line.split("#", 1)[0].strip()
                                if not line:
                                    continue
                                entry = line.lower().strip()
                                domain, network = _parse_whitelist_entry(entry)
                                if domain is not None:
                                    new_domains.add(domain)
                                elif network is not None:
                                    new_networks.add(network)
                            except Exception:
                                continue
                        any_download_succeeded = True
                        break
                    except Exception as e:
                        log(
                            f"[\u26a0\ufe0f] Loading whitelist failed {url} "
                            f"attempt {attempt + 1}: {e}"
                        )
                        time.sleep(config.DOWNLOAD_RETRY_BASE_DELAY_SECS + attempt * 2)

            # Atomic update
            with self._lock:
                self.whitelisted_domains_local = new_domains
                self.whitelisted_networks = new_networks
                self.whitelist_download_successful = any_download_succeeded
                try:
                    config.whitelisted_domains.clear()
                    config.whitelisted_domains.update(new_domains)
                except Exception:
                    pass

            log(
                f"\u2705 {len(self.whitelisted_domains_local)} whitelisted domains "
                f"loaded, {len(self.whitelisted_networks)} CIDR networks."
            )
        except Exception as e:
            self.whitelist_download_successful = False
            log(f"[Error] _load_whitelist: {e}\n{traceback.format_exc()}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_ip(s: str) -> bool:
        return _looks_like_ip(s)

    def is_whitelisted(self, hostname: str | None) -> bool:
        """Check whether *hostname* is explicitly whitelisted."""
        try:
            if not hostname:
                return False
            host = hostname.strip().lower().rstrip(".")
            if not host:
                return False

            # Direct IP -- check networks and exact IP whitelist
            try:
                if _looks_like_ip(host):
                    ip_obj = ipaddress.ip_address(host)
                    with self._lock:
                        if host in self.whitelisted_domains_local:
                            return True
                        for net in self.whitelisted_networks:
                            if ip_obj in net:
                                return True
                    return False
            except Exception:
                pass

            parts = host.split(".")
            with self._lock:
                for i in range(len(parts)):
                    candidate = ".".join(parts[i:])
                    if candidate in self.whitelisted_domains_local:
                        return True

            return False
        except Exception as e:
            log(f"is_whitelisted error for {hostname}: {e}")
            return False

    def _is_blocked(self, hostname: str | None) -> bool:
        """Return True if *hostname* should be blocked."""
        try:
            if not hostname:
                return False

            host = hostname.strip().lower().rstrip(".")
            if not host:
                return False

            # 1) Whitelist has absolute priority
            try:
                if self.is_whitelisted(host):
                    log(f"\u2705 [WHITELIST ALLOW] {host} matched whitelist")
                    return False
            except Exception as e:
                log(f"_is_blocked: whitelist check failed for {hostname}: {e}")
                return False

            # 2) Direct IP handling
            try:
                if _looks_like_ip(host):
                    if host in config.whitelisted_domains:
                        log(f"\u2705 [WHITELIST ALLOW IP] {hostname}")
                        return False
                    return bool(config.block_ip_direct)
            except Exception:
                pass

            parts = host.split(".")
            # 3) Blocklist check
            try:
                with self._lock:
                    if host in self.blocked_domains or host in config.manual_blocked_domains:
                        return True
                    for i in range(1, len(parts)):
                        parent = ".".join(parts[i:])
                        if (
                            parent in self.blocked_domains
                            or parent in config.manual_blocked_domains
                        ):
                            return True
            except Exception as e:
                log(f"_is_blocked blocklist check error for {hostname}: {e}")
                return False

            return False
        except Exception as e:
            log(f"_is_blocked error for {hostname}: {e}")
            return False

    def maybe_reload_background(self) -> None:
        """Reload blocklist and whitelist in background threads if interval elapsed."""
        try:
            if time.time() - self.last_reload > self.reload_interval:
                if self._loading_lock.locked():
                    return
                t1 = threading.Thread(target=self._load_blocklist, daemon=True)
                t2 = threading.Thread(target=self._load_whitelist, daemon=True)
                t1.start()
                t2.start()
        except Exception as e:
            log(f"maybe_reload_background error: {e}")