"""CalmWeb configuration file I/O and red-flag domain helpers.

Functions that read/write custom.cfg and manage the red-flag-domains cache.
Delegates low-level cfg parsing/writing to parser.py.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import urllib3

from . import config
from .log import log
from .parser import parse_cfg_file, write_cfg_file

# ===================================================================
# Custom config file handling
# ===================================================================


def get_custom_cfg_path(install_dir: str | None = None) -> str:
    """Return the path to custom.cfg.

    Priority: APPDATA dir > install_dir > directory of the running executable.
    """
    if config.USER_CFG_DIR:
        return config.USER_CFG_PATH
    if install_dir and os.path.isdir(install_dir):
        return os.path.join(install_dir, config.CUSTOM_CFG_NAME)
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), config.CUSTOM_CFG_NAME)


# Default options written into a fresh custom.cfg
_DEFAULT_OPTIONS: dict[str, bool] = {
    "block_ip_direct": True,
    "block_http_traffic": True,
    "block_http_other_ports": True,
}


def write_default_custom_cfg(
    path: str,
    blocked_set: set[str],
    whitelist_set: set[str],
) -> None:
    """Write a default custom.cfg file. Never raises."""
    write_cfg_file(path, blocked_set, whitelist_set, _DEFAULT_OPTIONS)


def parse_custom_cfg(path: str) -> tuple[set[str], set[str]]:
    """Parse a custom.cfg file. Returns (blocked_set, whitelist_set).

    Tolerant to errors; also sets global option flags in config module.
    """
    # Default values
    config.block_ip_direct = True
    config.block_http_traffic = True
    config.block_http_other_ports = True

    blocked, whitelist, options = parse_cfg_file(path)

    # Apply parsed options to global config
    for key in ("block_ip_direct", "block_http_traffic", "block_http_other_ports"):
        if key in options:
            setattr(config, key, options[key])

    if blocked or whitelist:
        log(
            f"custom.cfg chargé: {len(blocked)} blocked, {len(whitelist)} whitelisted, "
            f"Blocage IP={config.block_ip_direct}, Blocage HTTP={config.block_http_traffic}, "
            f"Ports alternatifs={config.block_http_other_ports}"
        )

    return blocked, whitelist


def ensure_custom_cfg_exists(
    install_dir: str,
    default_blocked: set[str],
    default_whitelist: set[str],
) -> str:
    """Ensure a custom.cfg exists (APPDATA preferred, then install_dir). Return its path."""
    try:
        if not os.path.isdir(config.USER_CFG_DIR):
            os.makedirs(config.USER_CFG_DIR, exist_ok=True)
        if not os.path.exists(config.USER_CFG_PATH):
            write_default_custom_cfg(config.USER_CFG_PATH, default_blocked, default_whitelist)
        return config.USER_CFG_PATH
    except Exception as e:
        log(f"Error in ensure_custom_cfg_exists (APPDATA): {e}")

    cfg_path = get_custom_cfg_path(install_dir)
    if not os.path.exists(cfg_path):
        try:
            write_default_custom_cfg(cfg_path, default_blocked, default_whitelist)
        except Exception as e:
            log(f"Error writing fallback custom.cfg {cfg_path}: {e}")
    return cfg_path


def load_custom_cfg_to_globals(path: str) -> tuple[set[str], set[str]]:
    """Load user config into global variables in config module."""
    blocked, whitelist = parse_custom_cfg(path)
    with config._CONFIG_LOCK:
        if blocked:
            config.manual_blocked_domains = blocked
        if whitelist:
            config.whitelisted_domains = whitelist
    return config.manual_blocked_domains, config.whitelisted_domains


# ===================================================================
# Red Flag Domains auto-update
# ===================================================================


def should_update_red_flag_domains() -> bool:
    """Check whether red.flag.domains needs updating (daily)."""
    try:
        if not os.path.exists(config.RED_FLAG_TIMESTAMP_PATH):
            return True

        with open(config.RED_FLAG_TIMESTAMP_PATH) as f:
            last_update_str = f.read().strip()

        last_update = datetime.fromisoformat(last_update_str)
        now = datetime.now()

        # Update if more than 24h elapsed or a new calendar day
        return (
            now - last_update
        ).total_seconds() > config.RED_FLAG_UPDATE_INTERVAL_SECS or now.date() > last_update.date()

    except Exception as e:
        log(f"Error checking red.flag.domains timestamp: {e}")
        return True


def download_red_flag_domains() -> bool:
    """Download and cache red.flag.domains locally."""
    try:
        log("📥 Téléchargement red.flag.domains...")

        # Create directory if needed
        os.makedirs(config.USER_CFG_DIR, exist_ok=True)

        # Download with urllib3
        http = urllib3.PoolManager()
        response = http.request(
            "GET",
            config.RED_FLAG_DOMAINS_URL,
            timeout=urllib3.Timeout(
                connect=config.DOWNLOAD_TIMEOUT_CONNECT_SECS,
                read=config.DOWNLOAD_TIMEOUT_READ_SECS,
            ),
        )

        if response.status != 200:
            log(f"❌ Erreur de téléchargement red.flag.domains: HTTP {response.status}")
            return False

        # Save file
        with open(config.RED_FLAG_CACHE_PATH, "wb") as f:
            f.write(response.data)

        # Mark update timestamp
        with open(config.RED_FLAG_TIMESTAMP_PATH, "w") as f:
            f.write(datetime.now().isoformat())

        log(f"✅ red.flag.domains mis à jour ({len(response.data)} bytes)")
        return True

    except Exception as e:
        log(f"❌ Error downloading red.flag.domains: {e}")
        return False


def get_red_flag_domains_path() -> str:
    """Return the path to the red.flag.domains file (local cache or URL fallback)."""
    if should_update_red_flag_domains():
        download_red_flag_domains()

    # Use local cache if it exists
    if os.path.exists(config.RED_FLAG_CACHE_PATH):
        return f"file://{config.RED_FLAG_CACHE_PATH}"

    # Fallback to direct URL
    return config.RED_FLAG_DOMAINS_URL


def get_blocklist_urls() -> list[str]:
    """Return the list of blocklist URLs including auto-updated red.flag.domains."""
    return [
        *config.BLOCKLIST_SOURCE_URLS,
        # Red Flag Domains - with automatic daily update
        get_red_flag_domains_path(),
    ]
