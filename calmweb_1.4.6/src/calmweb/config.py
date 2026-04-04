"""CalmWeb configuration: constants, paths, and global runtime state."""

from __future__ import annotations

import os
import platform
import threading

# --- GitHub / Update ------------------------------------------------
GITHUB_REPO: str = "async-it/calmweb"
GITHUB_RELEASES_URL: str = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_REPO_URL: str = f"https://github.com/{GITHUB_REPO}"

# ---------------------------------------------------------------------------
# Red Flag Domains
# ---------------------------------------------------------------------------

RED_FLAG_DOMAINS_URL: str = "https://dl.red.flag.domains/pihole/red.flag.domains.txt"
RED_FLAG_UPDATE_INTERVAL_SECS: int = 86400  # 24 hours

# ---------------------------------------------------------------------------
# Blocklist / whitelist source URLs
# ---------------------------------------------------------------------------

BLOCKLIST_SOURCE_URLS: list[str] = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/refs/heads/master/hosts",
    "https://raw.githubusercontent.com/easylist/listefr/refs/heads/master/hosts.txt",
    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/ultimate.txt",
    "https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/blocklist.txt",
    "https://urlhaus.abuse.ch/downloads/csv/",
]

WHITELIST_URLS: list[str] = [
    "https://raw.githubusercontent.com/async-it/calmweb/refs/heads/main/filters/whitelist.txt"
]

# Default user-editable sets (overwritten by custom.cfg at runtime)
manual_blocked_domains: set[str] = {"add.blocked.domain"}
whitelisted_domains: set[str] = {"add.allowed.domain"}

# ---------------------------------------------------------------------------
# Timers and network
# ---------------------------------------------------------------------------

RELOAD_INTERVAL: int = 3600
PROXY_BIND_IP: str = "127.0.0.1"
PROXY_PORT: int = 8080

# ---------------------------------------------------------------------------
# Network timeouts (all values in seconds)
# ---------------------------------------------------------------------------

DOWNLOAD_TIMEOUT_CONNECT_SECS: float = 10.0
DOWNLOAD_TIMEOUT_READ_SECS: float = 30.0
BLOCKLIST_TIMEOUT_CONNECT_SECS: float = 5.0
BLOCKLIST_TIMEOUT_READ_SECS: float = 15.0
WHITELIST_TIMEOUT_CONNECT_SECS: float = 5.0
WHITELIST_TIMEOUT_READ_SECS: float = 10.0

# ---------------------------------------------------------------------------
# Proxy handler settings
# ---------------------------------------------------------------------------

PROXY_HANDLER_TIMEOUT_SECS: int = 10
PROXY_PROTOCOL_VERSION: str = "HTTP/1.1"
VOIP_ALLOWED_PORTS: set[int] = {80, 443, 3478, 5060, 5061}

# ---------------------------------------------------------------------------
# Relay buffer size (bytes)
# ---------------------------------------------------------------------------

RELAY_BUFFER_SIZE_BYTES: int = 65536

# ---------------------------------------------------------------------------
# Retry settings
# ---------------------------------------------------------------------------

DOWNLOAD_MAX_RETRIES: int = 3
DOWNLOAD_RETRY_BASE_DELAY_SECS: int = 1

# ---------------------------------------------------------------------------
# Socket connection timeout
# ---------------------------------------------------------------------------

SOCKET_CONNECT_TIMEOUT_SECS: int = 10

# ---------------------------------------------------------------------------
# Resource / connection safety limits
# ---------------------------------------------------------------------------

MAX_BLOCKLIST_BYTES: int = 25 * 1024 * 1024  # skip downloads larger than this
MAX_PROXY_CONNECTIONS: int = 200  # cap concurrent proxy threads
SOCKET_IDLE_TIMEOUT: int = 90  # seconds before dropping idle relays
MAX_BLOCKED_DOMAINS: int = 1_500_000  # guardrail to avoid unbounded memory

# ---------------------------------------------------------------------------
# Installation paths (Windows-specific paths are no-ops on other platforms)
# ---------------------------------------------------------------------------

INSTALL_DIR: str = r"C:\Program Files\CalmWeb" if platform.system() == "Windows" else ""
EXE_NAME: str = "calmweb.exe"
STARTUP_FOLDER: str = (
    os.getenv("APPDATA", "") + r"\Microsoft\Windows\Start Menu\Programs\Startup"
    if platform.system() == "Windows"
    else ""
)
CUSTOM_CFG_NAME: str = "custom.cfg"

# ---------------------------------------------------------------------------
# User config directory and derived paths
# ---------------------------------------------------------------------------

USER_CFG_DIR: str = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "CalmWeb")
USER_CFG_PATH: str = os.path.join(USER_CFG_DIR, CUSTOM_CFG_NAME)
RED_FLAG_CACHE_PATH: str = os.path.join(USER_CFG_DIR, "red_flag_domains.txt")
RED_FLAG_TIMESTAMP_PATH: str = os.path.join(USER_CFG_DIR, "red_flag_last_update.txt")

# ---------------------------------------------------------------------------
# Global runtime state
# ---------------------------------------------------------------------------

block_enabled: bool = True
block_ip_direct: bool = True  # Block direct IP access
block_http_traffic: bool = True  # Block HTTP (non-HTTPS) traffic
block_http_other_ports: bool = True

current_resolver: object | None = None
proxy_server: object | None = None
proxy_server_thread: threading.Thread | None = None

# Threading primitives
_RESOLVER_LOADING = threading.Event()
_SHUTDOWN_EVENT = threading.Event()
_CONFIG_LOCK = threading.RLock()
_CONNECTION_SEMAPHORE = threading.BoundedSemaphore(MAX_PROXY_CONNECTIONS)
