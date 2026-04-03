"""Logging utilities for CalmWeb.

Provides a thread-safe log() function with file rotation, console output,
and an in-memory ring buffer for the log viewer.
"""

from __future__ import annotations

import contextlib
import sys
import threading
import time
from collections import deque
from typing import Any

# In-memory ring buffer accessible by the log viewer
log_buffer: deque[str] = deque(maxlen=1000)

_LOG_LOCK = threading.Lock()


def log(msg: Any) -> None:
    """Thread-safe log to console, file, and in-memory buffer."""
    try:
        timestamp = time.strftime("[%H:%M:%S]")
        try:
            # Force str conversion + replace unicode errors
            safe_msg = str(msg).encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        except Exception:
            safe_msg = "Log message conversion error"

        line = f"{timestamp} {safe_msg}"

        with _LOG_LOCK:
            # Append to ring buffer (deque handles max size automatically)
            log_buffer.append(line)

            # Protected console output
            with contextlib.suppress(Exception):
                print(line, flush=True)

    except Exception:
        # Last line of defense: never propagate exceptions
        with contextlib.suppress(Exception):
            sys.stderr.write("Logging internal error\n")
