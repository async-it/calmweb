"""CalmWeb entry point (``python -m calmweb``)."""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import threading
import time
import traceback
from tkinter import Tk, messagebox

from pystray import Icon

from . import config
from .config_io import ensure_custom_cfg_exists, get_blocklist_urls, load_custom_cfg_to_globals
from .log import log
from .platform.windows import disable_proxy, enable_proxy, register_shutdown_handler
from .proxy import start_proxy_server
from .resolver import BlocklistResolver
from .single_instance import acquire_single_instance_lock, release_single_instance_lock
from .tray import (
    apply_state_icon,
    check_for_updates_startup,
    create_image,
    quit_app,
    run_log_viewer,
    update_menu,
)

# ===================================================================
# Application startup
# ===================================================================


def run_calmweb() -> None:
    """Main application startup sequence.

    1. Load configuration
    2. Create a :class:`BlocklistResolver`
    3. Start the proxy server
    4. Set the system proxy
    5. Start the system tray icon
    6. Handle signals for graceful termination
    """
    def _initialize_backend(icon: Icon) -> None:
        """Initialize all heavy services after tray icon becomes visible."""
        try:
            cfg_path = ensure_custom_cfg_exists(
                config.INSTALL_DIR, config.manual_blocked_domains, config.whitelisted_domains
            )
            load_custom_cfg_to_globals(cfg_path)
        except Exception as e:
            log(f"Error loading initial config: {e}")

        try:
            resolver = BlocklistResolver(get_blocklist_urls(), config.RELOAD_INTERVAL)
            config.current_resolver = resolver
            if not resolver.whitelist_download_successful:
                config.block_enabled = False
                log("[⚠️] Whitelist download failed at startup; blocking kept disabled.")
        except Exception as e:
            config.block_enabled = False
            log(f"Error creating resolver: {e}")

        try:
            start_proxy_server(config.PROXY_BIND_IP, config.PROXY_PORT)
        except Exception as e:
            log(f"Error starting proxy server: {e}")

        try:
            if config.block_enabled:
                enable_proxy()
            else:
                disable_proxy()
        except Exception as e:
            log(f"Error setting system proxy: {e}")

        # Register shutdown/logoff handlers to ensure proxy is disabled on exit
        try:
            register_shutdown_handler()
        except Exception as e:
            log(f"Error registering shutdown handler: {e}")

        with contextlib.suppress(Exception):
            icon.title = "Calm Web"
            update_menu(icon)

        log(
            f"Calm Web started. Proxy on {config.PROXY_BIND_IP}:{config.PROXY_PORT}, "
            f"blocking {'enabled' if config.block_enabled else 'disabled'}."
        )

    # Start systray icon first; heavy initialization is deferred to setup callback.
    try:
        icon = Icon("calmweb")
        icon.icon = create_image()  # placeholder until apply_state_icon runs
        icon.title = "Calm Web (Starting...)"
        apply_state_icon(icon)
        update_menu(icon)

        # Hook signals for graceful termination
        def _signal_handler(signum: int, frame: object) -> None:
            log(f"Signal {signum} received, shutting down.")
            quit_app(icon)

        with contextlib.suppress(Exception):
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)

        tray_thread = threading.Thread(target=icon.run, daemon=True)
        tray_thread.start()

        # Give the tray backend a brief moment to publish the icon first.
        started_at = time.time()
        while tray_thread.is_alive() and (time.time() - started_at) < 1.0:
            if getattr(icon, "visible", False):
                break
            time.sleep(0.05)

        # Run update check as the very first startup action (blocking).
        # This finishes before the backend starts so the user can install
        # the update before blocklists and other heavy downloads begin.
        check_for_updates_startup()

        threading.Thread(target=_initialize_backend, args=(icon,), daemon=True).start()

        while tray_thread.is_alive() and not config._SHUTDOWN_EVENT.is_set():
            tray_thread.join(timeout=0.2)

        # Ensure clean stop if shutdown was requested outside tray callbacks.
        with contextlib.suppress(Exception):
            if config._SHUTDOWN_EVENT.is_set():
                icon.stop()
    except Exception as e:
        log(f"Error in systray / run: {e}")
        # If systray fails (e.g. headless environment), keep server running in background
        try:
            while not config._SHUTDOWN_EVENT.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            quit_app(None)


# ===================================================================
# Entry point with auto-restart and installer detection
# ===================================================================


def _show_already_running_alert() -> None:
    """Show a user-facing dialog when another CalmWeb instance is active."""
    try:
        root = Tk()
        root.withdraw()
        messagebox.showwarning(
            "CalmWeb",
            "CalmWeb is already running. Please close the existing instance before launching again.",
            parent=root,
        )
        root.destroy()
    except Exception as exc:
        log(f"Failed to show already-running alert: {exc}")


def main() -> None:
    """Entry point with auto-restart loop for maximum reliability.

    - ``--log-viewer`` argument launches only the Tk log viewer.
    - If the executable basename is ``calmweb_installer.exe``, runs the
      installer instead of the normal application.
    - Otherwise starts the proxy application with up to 5 restart attempts
      on critical failure.
    """
    if "--log-viewer" in sys.argv:
        run_log_viewer()
        return

    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        log("Another CalmWeb instance is already running. Exiting this launch.")
        _show_already_running_alert()
        return

    restart_count = 0
    max_restarts = 5

    while restart_count < max_restarts:
        try:
            log(f"Starting CalmWeb (attempt {restart_count + 1})")

            # Filename-based installer detection
            exe_name = os.path.basename(sys.argv[0]).lower()
            if exe_name == "calmweb_installer.exe":
                from .installer import install  # noqa: PLC0415

                install()
            else:
                run_calmweb()

            # If we reach here, everything is fine
            break

        except KeyboardInterrupt:
            log("Shutdown requested by Ctrl+C.")
            break
        except Exception as e:
            restart_count += 1
            log(f"❌ Critical error (attempt {restart_count}): {e}")
            log(traceback.format_exc())

            if restart_count < max_restarts:
                log("🔄 Automatic restart in 5 seconds...")
                time.sleep(5)
            else:
                log(f"❌ Failed after {max_restarts} attempts. Final shutdown.")
                break

    # Final clean shutdown
    release_single_instance_lock(instance_lock)
    with contextlib.suppress(Exception):
        quit_app(None, None)
    try:
        sys.exit(1)
    except Exception:
        os._exit(1)


if __name__ == "__main__":
    main()
