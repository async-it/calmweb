"""Windows-specific functionality for CalmWeb.

Each function has its own platform guard and returns early / is a no-op
when not running on Windows.
"""

from __future__ import annotations

import atexit
import contextlib
import ctypes
import socket
import subprocess
from typing import Any

from ..log import log
from . import is_windows

# Optional Windows-only imports
try:
    import win32com.client  # type: ignore[import-untyped]  # noqa: F401
    import win32con  # type: ignore[import-untyped]
    import win32gui  # type: ignore[import-untyped]
    import win32ui  # type: ignore[import-untyped]

    WIN32_AVAILABLE: bool = True
except Exception:
    WIN32_AVAILABLE = False


# ===================================================================
# Exe icon extraction
# ===================================================================


def get_exe_icon(path: str, size: tuple[int, int] = (64, 64)) -> Any:
    """Extract the icon from a Windows executable and return it as a PIL Image.

    Returns None if not on Windows or if extraction fails.
    """
    if not is_windows():
        return None
    if not WIN32_AVAILABLE:
        return None

    try:
        large, small = win32gui.ExtractIconEx(path, 0)
    except Exception as e:
        log(f"get_exe_icon: ExtractIconEx error: {e}")
        return None

    if (not small) and (not large):
        return None

    try:
        hicon = large[0] if large else small[0]
    except Exception:
        return None

    # Create compatible DC
    img = None
    try:
        from PIL import Image

        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hdc_mem = hdc.CreateCompatibleDC()
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size[0], size[1])
        hdc_mem.SelectObject(hbmp)
        win32gui.DrawIconEx(
            hdc_mem.GetSafeHdc(), 0, 0, hicon, size[0], size[1], 0, 0, win32con.DI_NORMAL
        )
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGB",
            (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
            bmpstr,
            "raw",
            "BGRX",
            0,
            1,
        )
    except Exception as e:
        log(f"get_exe_icon: conversion error: {e}")
        img = None
    finally:
        with contextlib.suppress(Exception):
            win32gui.DestroyIcon(hicon)
        with contextlib.suppress(Exception):
            hdc_mem.DeleteDC()
            hdc.DeleteDC()
            win32gui.ReleaseDC(0, 0)
    return img


# ===================================================================
# Firewall rule
# ===================================================================


def add_firewall_rule(target_file: str) -> None:
    """Add a Windows Firewall rule to allow CalmWeb."""
    if not is_windows():
        log("add_firewall_rule: not on Windows, skipping.")
        return
    try:
        subprocess.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                "name=CalmWeb",
                "dir=in",
                "action=allow",
                "program=" + target_file,
                "profile=any",
            ],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log("Règles pare-feu ajoutée")
    except Exception as e:
        log(f"Firewall error: {e}")


# ===================================================================
# System proxy
# ===================================================================


def _set_registry_proxy(proxy_enable: int, proxy_server: str) -> None:
    """Write ProxyEnable / ProxyServer to the Windows Internet Settings registry key."""
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, proxy_enable)
    winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
    winreg.CloseKey(key)


def enable_proxy(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Configure the Windows system proxy to route through CalmWeb. Tolerates errors."""
    if not is_windows():
        log("enable_proxy: not on Windows, skipping.")
        return

    proxy_str = f"{host}:{port}"

    try:
        try:
            _set_registry_proxy(1, proxy_str)
        except Exception as e:
            log(f"enable_proxy: registry write failed: {e}")

        log(f"Proxy système configuré sur {proxy_str}")

    except Exception as e:
        log(f"Error in enable_proxy: {e}")


def disable_proxy() -> None:
    """Remove the Windows system proxy settings. Tolerates errors."""
    if not is_windows():
        log("disable_proxy: not on Windows, skipping.")
        return
    try:
        with contextlib.suppress(Exception):
            subprocess.run(
                ["netsh", "winhttp", "reset", "proxy"],
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        # setx with an empty string sets the variable to "" rather than
        # removing it. This is a known Windows limitation; skipping setx
        # entirely when disabling so environment variables from the enable
        # phase persist until the user or a future run clears them.
        try:
            _set_registry_proxy(0, "")
        except Exception as e:
            log(f"disable_proxy: registry clear failed: {e}")
        log("Proxy réinitialisé")
    except Exception as e:
        log(f"Error in disable_proxy: {e}")


# ===================================================================
# Socket keepalive
# ===================================================================


def set_socket_keepalive(sock: socket.socket) -> None:
    """Apply Windows-specific TCP keepalive tuning to a socket.

    Uses SIO_KEEPALIVE_VALS ioctl: (on/off, keepalive_time_ms, keepalive_interval_ms).
    No-op on non-Windows platforms.
    """
    if not is_windows():
        return
    with contextlib.suppress(Exception):
        sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 60000, 10000))  # type: ignore[attr-defined]


# ===================================================================
# Shutdown / logoff proxy cleanup
# ===================================================================


def _console_ctrl_handler(event: int) -> bool:
    """Handle Windows console control events to clean up proxy on shutdown/logoff."""
    # CTRL_CLOSE_EVENT=2, CTRL_LOGOFF_EVENT=5, CTRL_SHUTDOWN_EVENT=6
    if event in (2, 5, 6):
        log("System shutdown/logoff detected, disabling proxy...")
        disable_proxy()
        return True
    return False


def register_shutdown_handler() -> None:
    """Register handlers to disable the proxy on Windows shutdown, logoff, or close.

    Two layers of protection:
    - ``atexit`` handler as the primary safety net (works in --noconsole mode).
    - ``SetConsoleCtrlHandler`` for CTRL_CLOSE, CTRL_LOGOFF, and CTRL_SHUTDOWN
      events (may not fire in --noconsole PyInstaller builds, but covers
      console-mode runs).

    No-op on non-Windows platforms.
    """
    if not is_windows():
        return

    # atexit handler -- primary safety net
    def _cleanup_proxy() -> None:
        disable_proxy()

    atexit.register(_cleanup_proxy)

    # Console ctrl handler for shutdown/logoff events
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
        handler = handler_type(_console_ctrl_handler)
        # Keep a reference to prevent garbage collection
        register_shutdown_handler._handler_ref = handler  # type: ignore[attr-defined]
        kernel32.SetConsoleCtrlHandler(handler, True)
    except Exception as e:
        log(f"Console ctrl handler registration failed (expected in --noconsole mode): {e}")

    log("Shutdown handlers registered.")
