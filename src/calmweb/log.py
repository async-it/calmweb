"""Logging utilities for CalmWeb."""
from __future__ import annotations
import contextlib
import sys
import threading
import time
from collections import deque
from typing import Any

# Buffer partagé
log_buffer: deque[str] = deque(maxlen=1000)
# Lock partagé pour éviter les crashs de lecture/écriture simultanée
_LOG_LOCK = threading.Lock()

def log(msg: Any) -> None:
    """Thread-safe log to console and in-memory buffer."""
    try:
        timestamp = time.strftime("[%H:%M:%S]")
        try:
            safe_msg = str(msg).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        except Exception:
            safe_msg = "Log message conversion error"

        line = f"{timestamp} {safe_msg}"

        with _LOG_LOCK:
            log_buffer.append(line)
            # On print à l'extérieur ou à l'intérieur, mais avec suppression d'erreur
            with contextlib.suppress(Exception):
                print(line, flush=True)

    except Exception:
        with contextlib.suppress(Exception):
            sys.stderr.write("Logging internal error\n")