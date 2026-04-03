"""System tray icon, menu, log viewer, and UI actions for CalmWeb.

Provides the pystray menu, Tkinter log viewer, config editor launcher,
and application quit logic.
"""

from __future__ import annotations

import contextlib
import os
import platform
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageDraw
from pystray import Menu, MenuItem

from . import __version__, config
from .config_io import get_custom_cfg_path, load_custom_cfg_to_globals, write_default_custom_cfg
from .log import log
from .platform.windows import disable_proxy, enable_proxy

if TYPE_CHECKING:
    from pystray import Icon

    from .updater import UpdateInfo


_ICON_CACHE: dict[str, Image.Image] = {}


def _get_project_root() -> str:
    """Return project root directory (works in dev and frozen modes)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return str(Path(__file__).resolve().parent.parent.parent)


def _load_tray_icon_from_file(path: str, size: int = 64) -> Image.Image | None:
    """Load an image file and return a (*size* x *size*) RGBA PIL Image.

    Handles PNG, ICO, and other PIL-supported formats.  Results are cached
    by absolute path so repeated calls are free.
    """
    try:
        abs_path = os.path.abspath(path)
        if abs_path in _ICON_CACHE:
            return _ICON_CACHE[abs_path]
        if not os.path.exists(abs_path):
            return None

        img = Image.open(abs_path)
        rgba = img.convert("RGBA")
        if rgba.size != (size, size):
            rgba = rgba.resize((size, size), Image.LANCZOS)

        _ICON_CACHE[abs_path] = rgba
        return rgba
    except Exception:
        return None


def apply_state_icon(icon: Icon) -> None:
    """Set tray icon according to current blocking state.

    - Active blocking  -> calmweb_active.png / .ico
    - Inactive blocking -> calmweb.png / .ico (or fallback assets)
    """
    try:
        root = _get_project_root()
        meipass = getattr(sys, "_MEIPASS", None)

        # Common "normal" icon candidates (used as fallback for active too)
        # Prefer .ico (reliable RGBA transparency) over .png;
        normal_candidates = [
            os.path.join(root, "calmweb.ico"),
            os.path.join(root, "resources", "calmweb.ico"),
            os.path.join(root, "resources", "calmweb_icon.png"),
            os.path.join(root, "calmweb.png"),
            os.path.join(root, "resources", "calmweb.png"),
        ]
        if meipass:
            normal_candidates.insert(0, os.path.join(meipass, "calmweb.ico"))

        if config.block_enabled:
            active_candidates = [
                os.path.join(root, "calmweb_active.png"),
                os.path.join(root, "resources", "calmweb_active.png"),
                os.path.join(root, "calmweb_active.ico"),
                os.path.join(root, "resources", "calmweb_active.ico"),
            ]
            if meipass:
                active_candidates.insert(0, os.path.join(meipass, "calmweb_active.png"))
                active_candidates.insert(1, os.path.join(meipass, "calmweb_active.ico"))
            candidates = active_candidates + normal_candidates
        else:
            candidates = normal_candidates

        icon_image = None
        for candidate in candidates:
            icon_image = _load_tray_icon_from_file(candidate)
            if icon_image is not None:
                break

        if icon_image is None:
            exe_icon = get_exe_icon(sys.executable)
            if exe_icon is not None:
                icon_image = exe_icon.convert("RGBA")

        icon.icon = icon_image or create_image()
    except Exception as e:
        log(f"apply_state_icon error: {e}")


# ===================================================================
# Exe icon extraction (wrapper)
# ===================================================================


def get_exe_icon(path: str, size: tuple[int, int] = (64, 64)) -> Any:
    """Return a PIL Image of the executable icon, or None on failure.

    Delegates to :func:`calmweb.platform.windows.get_exe_icon`.
    Returns None gracefully on non-Windows platforms.
    """
    try:
        from .platform.windows import get_exe_icon as win_get_exe_icon

        return win_get_exe_icon(path, size)
    except Exception:
        return None


# ===================================================================
# Fallback icon
# ===================================================================


def create_image() -> Image.Image | None:
    """Create a generic fallback PIL Image icon when exe icon extraction fails."""
    try:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        d.rectangle([(8, 16), (56, 48)], outline=(0, 0, 0))
        d.text((18, 22), "CW", fill=(0, 0, 0))
        return image
    except Exception:
        return None


# ===================================================================
# Log viewer (runs in a separate process)
# ===================================================================


def run_log_viewer() -> None:
    """Standalone Tk window that auto-refreshes the log from memory every second.

    Designed to run in a separate process to avoid Tk threading issues.
    Note: Since this runs in a separate process, it won't see the main process's
    memory buffer. We should probably run it in-thread or use a different mechanism.
    For now, we'll update it to reflect that file logging is disabled.
    """
    win = tk.Tk()
    win.title("Calm Web - Log")
    win.geometry("780x440")
    text_area = ScrolledText(win, wrap=tk.WORD)
    text_area.pack(expand=True, fill="both")
    text_area.config(state="disabled")

    def refresh() -> None:
        from .log import log_buffer

        content = "\n".join(log_buffer)
        if not content:
            content = "No logs found."

        try:
            text_area.config(state="normal")
            text_area.delete(1.0, tk.END)
            text_area.insert(tk.END, content)
            text_area.see(tk.END)
            text_area.config(state="disabled")
        except Exception:
            pass
        win.after(1000, refresh)

    refresh()
    with contextlib.suppress(Exception):
        win.mainloop()


def show_log_window() -> None:
    """Launch the log viewer in a separate thread to share the in-memory buffer."""
    try:
        threading.Thread(target=run_log_viewer, daemon=True).start()
        log("Opening log window...")
    except Exception as e:
        log(f"Unable to open log window: {e}")


# ===================================================================
# Config editor
# ===================================================================


def open_config_in_editor(path: str) -> None:
    """Open custom.cfg in Notepad (Windows) or the OS default editor, and reload config after editor closes."""
    try:
        if not os.path.exists(path):
            log(f"custom.cfg missing, creating before opening: {path}")
            write_default_custom_cfg(
                path, config.manual_blocked_domains, config.whitelisted_domains
            )

        def _open_and_wait() -> None:
            try:
                proc = None
                system_name = platform.system().lower()

                if system_name == "windows":
                    # Launch Notepad and wait
                    proc = subprocess.Popen(["notepad.exe", path])
                else:
                    # Non-Windows fallback
                    if hasattr(os, "startfile"):
                        os.startfile(path)  # Note: startfile is non-blocking
                        log("Cannot wait for editor on this platform; reload may happen immediately.")
                    else:
                        proc = subprocess.Popen(
                            ["xdg-open", path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )

                if proc:
                    proc.wait()  # Wait until the editor is closed
                    log(f"Editor closed, reloading config: {path}")
                    reload_config_action()

            except Exception as e:
                log(f"Error opening editor for {path}: {e}")

        threading.Thread(target=_open_and_wait, daemon=True).start()
        log(f"Opening configuration file: {path}")

    except Exception as e:
        log(f"Error opening editor for {path}: {e}")


# ===================================================================
# Tray menu actions
# ===================================================================


def reload_config_action(icon: Icon | None = None, item: Any | None = None) -> None:
    """Reload custom.cfg and trigger a full blocklist/whitelist refresh."""
    try:
        cfg_path = get_custom_cfg_path(config.INSTALL_DIR)
        if not os.path.exists(cfg_path):
            log(f"No custom.cfg found to reload: {cfg_path}")
            return

        # Reload global variables from user config file
        load_custom_cfg_to_globals(cfg_path)
        log("Local configuration reloaded from user file.")

        if config.current_resolver:
            # Launch both reloads (blocklist + whitelist) in parallel
            threading.Thread(target=config.current_resolver._load_blocklist, daemon=True).start()
            threading.Thread(target=config.current_resolver._load_whitelist, daemon=True).start()
            log("Full reload of external blocklists and whitelists requested (thread).")
        else:
            log("[WARN] No active resolver for reload.")

    except Exception as e:
        log(f"Error reloading configuration: {e}")


def toggle_block(icon: Icon, item: Any) -> None:
    """Toggle blocking on/off and update the system proxy accordingly."""
    config.block_enabled = not config.block_enabled
    state = "enabled" if config.block_enabled else "disabled"
    log(f"Calm Web: blocking {state}")
    try:
        if config.block_enabled:
            enable_proxy()
        else:
            disable_proxy()
    except Exception as e:
        log(f"Error setting system proxy on toggle: {e}")
    update_menu(icon)


def check_for_updates(icon: Icon | None = None, item: Any | None = None) -> None:
    """Check GitHub Releases for a newer version and offer to install it."""

    def _check_in_background() -> None:
        from .updater import (
            UpdateCheckError,
            apply_update,
            check_for_update,
        )

        try:
            update_info = check_for_update()
        except UpdateCheckError as exc:
            _show_update_error(str(exc))
            return
        except Exception as exc:
            _show_update_error(f"Unexpected error: {exc}")
            return

        if update_info is None:
            _show_up_to_date()
            return

        # Show update dialog and ask user
        if _show_update_available(update_info):
            # User said yes — download and install
            try:
                installer_path = _download_with_progress(update_info)
                if installer_path:
                    apply_update(installer_path)
            except Exception as exc:
                _show_update_error(f"Update failed: {exc}")

    thread = threading.Thread(target=_check_in_background, daemon=True)
    thread.start()


def check_for_updates_silent() -> None:
    """Silently check for updates on startup — only prompt if an update is available."""

    def _check_in_background() -> None:
        from .updater import (
            UpdateCheckError,
            apply_update,
            check_for_update,
        )

        try:
            update_info = check_for_update()
        except (UpdateCheckError, Exception):
            # Silently ignore errors on startup check
            return

        if update_info is None:
            return

        # Show update dialog and ask user
        if _show_update_available(update_info):
            try:
                installer_path = _download_with_progress(update_info)
                if installer_path:
                    apply_update(installer_path)
            except Exception as exc:
                _show_update_error(f"Update failed: {exc}")

    thread = threading.Thread(target=_check_in_background, daemon=True)
    thread.start()


def check_for_updates_startup() -> None:
    """Run update check inline as an immediate startup step."""
    from .updater import (
        UpdateCheckError,
        apply_update,
        check_for_update,
    )

    try:
        update_info = check_for_update()
    except (UpdateCheckError, Exception):
        return

    if update_info is None:
        return

    if _show_update_available(update_info):
        try:
            installer_path = _download_with_progress(update_info)
            if installer_path:
                apply_update(installer_path)
        except Exception as exc:
            _show_update_error(f"Update failed: {exc}")


def _show_up_to_date() -> None:
    """Show a dialog telling the user they're up to date."""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "CalmWeb Update",
            f"Application à jour!\n\nCurrent version: {__version__}",
            parent=root,
        )
        root.destroy()
    except Exception as exc:
        log(f"Error showing up-to-date dialog: {exc}")


def _show_update_error(message: str) -> None:
    """Show an error dialog for update failures."""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("CalmWeb Update", message, parent=root)
        root.destroy()
    except Exception as exc:
        log(f"Error showing update error dialog: {exc}")


def _show_update_available(update_info: UpdateInfo) -> bool:
    """Show a dialog with update info and return True if user wants to update."""
    try:
        root = tk.Tk()
        root.withdraw()

        # Truncate release notes if very long
        notes = update_info.release_notes
        if len(notes) > 500:
            notes = notes[:500] + "..."

        size_mb = update_info.asset_size / (1024 * 1024)

        message = (
            f"Une nouvelle version est disponible!\n\n"
            f"Version actuelle: {__version__}\n"
            f"Nouvelle version: {update_info.version}\n"
            f"Taille du téléchargement: {size_mb:.1f} MB\n\n"
            f"Informations:\n{notes}\n\n"
            f"Souhaitez-vous mettre à jour?"
        )

        result = messagebox.askyesno("CalmWeb Update", message, parent=root)
        root.destroy()
        return result
    except Exception as exc:
        log(f"Error showing update dialog: {exc}")
        return False


def _download_with_progress(update_info: UpdateInfo) -> Path | None:
    """Download the installer with a progress bar dialog."""
    from .updater import UpdateCheckError, download_installer

    # Create a progress window
    root = tk.Tk()
    root.title("CalmWeb Update")
    root.geometry("400x120")
    root.resizable(False, False)

    # Center the window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - 200
    y = (root.winfo_screenheight() // 2) - 60
    root.geometry(f"+{x}+{y}")

    label = tk.Label(
        root,
        text=f"Downloading CalmWeb {update_info.version}...",
    )
    label.pack(pady=(15, 5))

    # Use ttk Progressbar
    from tkinter import ttk

    progress_var = tk.DoubleVar(value=0)
    progress_bar = ttk.Progressbar(
        root, variable=progress_var, maximum=100, length=350
    )
    progress_bar.pack(pady=5, padx=25)

    percent_label = tk.Label(root, text="0%")
    percent_label.pack(pady=(0, 10))

    result_path: list[Path | None] = [None]
    error_msg: list[str | None] = [None]

    def progress_callback(downloaded: int, total: int) -> None:
        """Update the progress bar from the download thread."""
        if total > 0:
            pct = (downloaded / total) * 100
            with contextlib.suppress(Exception):
                root.after(0, lambda p=pct: _update_progress(p))

    def _update_progress(pct: float) -> None:
        with contextlib.suppress(Exception):
            progress_var.set(pct)
            percent_label.config(text=f"{pct:.0f}%")
            root.update_idletasks()

    def _do_download() -> None:
        try:
            path = download_installer(
                update_info.download_url,
                progress_callback=progress_callback,
            )
            result_path[0] = path
        except (UpdateCheckError, Exception) as exc:
            error_msg[0] = str(exc)
        finally:
            with contextlib.suppress(Exception):
                root.after(0, root.destroy)

    dl_thread = threading.Thread(target=_do_download, daemon=True)
    dl_thread.start()

    root.mainloop()
    dl_thread.join(timeout=5)

    if error_msg[0]:
        _show_update_error(f"Download failed: {error_msg[0]}")
        return None

    return result_path[0]


def update_menu(icon: Icon) -> None:
    """Rebuild the systray menu. Wraps callbacks to prevent unhandled exceptions."""
    try:
        apply_state_icon(icon)
        icon.menu = Menu(
            MenuItem(
                f"Calm Web v{__version__}",
                lambda: None,
                enabled=False,
            ),
            MenuItem(
                f"Filtrage: {'✓ Activé' if config.block_enabled else '✕ Désactivé'}",
                lambda: None,
                enabled=False,
            ),
            MenuItem(
                "✕ Désactiver le filtre" if config.block_enabled else "✓ Activer le filtre",
                toggle_block,
            ),
            MenuItem(
                "Configuration",
                Menu(
                    MenuItem(
                        "Editer",
                        lambda icon, item: threading.Thread(
                            target=open_config_in_editor,
                            args=(get_custom_cfg_path(config.INSTALL_DIR),),
                            daemon=True,
                        ).start(),
                    ),
                    MenuItem("Recharger listes et configuration", reload_config_action),
                ),
            ),
            MenuItem(
                "Afficher l'activité",
                lambda: threading.Thread(target=show_log_window, daemon=True).start(),
            ),
            MenuItem("Rechercher une mise à jour", check_for_updates),
            MenuItem("Quitter", quit_app),
        )
        # pystray may raise if the icon has been stopped; ignore
        with contextlib.suppress(Exception):
            icon.update_menu()
    except Exception as e:
        log(f"update_menu error: {e}")


def quit_app(icon: Icon | None = None, item: Any | None = None) -> None:
    """Clean up resources and exit the application."""
    try:
        log("Shutdown requested.")
        config._SHUTDOWN_EVENT.set()

        # Remove system proxy if it was configured
        try:
            disable_proxy()
            log("System proxy reset.")
        except Exception as e:
            log(f"Error resetting system proxy: {e}")

        if config.proxy_server:
            try:
                config.proxy_server.shutdown()
                config.proxy_server.server_close()
                log("Proxy server stopped.")
            except Exception as e:
                log(f"Error stopping proxy: {e}")

        with contextlib.suppress(Exception):
            if icon:
                icon.stop()

        log("Shutting down Calm Web application.")
        # Brief delay to let threads finish cleanly
        time.sleep(0.2)
        # Force a clean exit
        release_single_instance_lock(instance_lock)
        try:
            os._exit(0)
        except Exception:
            with contextlib.suppress(Exception):
                sys.exit(0)
    except Exception as e:
        log(f"Error shutting down the application: {e}")

