"""HTTP/HTTPS proxy handler with blocklist enforcement."""

from __future__ import annotations

import contextlib
import socket
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import config
from .log import log
from .platform.windows import set_socket_keepalive

# ===================================================================
# Relay helpers (high-performance pass-through)
# ===================================================================


def _set_socket_opts_for_perf(sock: socket.socket) -> None:
    """Apply TCP_NODELAY, SO_KEEPALIVE, and platform-specific tuning."""
    with contextlib.suppress(Exception):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        set_socket_keepalive(sock)
        sock.settimeout(config.SOCKET_IDLE_TIMEOUT)


def _relay_worker(
    src: socket.socket,
    dst: socket.socket,
    buffer_size: int = config.RELAY_BUFFER_SIZE_BYTES,
) -> None:
    """Unidirectional relay: *src* -> *dst*.

    Tolerates errors and shuts down sockets cleanly.
    """
    try:
        while not config._SHUTDOWN_EVENT.is_set():
            try:
                data = src.recv(buffer_size)
            except Exception:
                break
            if not data:
                with contextlib.suppress(Exception):
                    dst.shutdown(socket.SHUT_WR)
                break
            try:
                dst.sendall(data)
            except Exception:
                break
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            dst.shutdown(socket.SHUT_WR)


def full_duplex_relay(a_sock: socket.socket, b_sock: socket.socket) -> None:
    """Launch two threads to relay a->b and b->a.

    Uses bounded waits so shutdown (Ctrl+C / quit) is responsive even when
    sockets are idle and relay workers are blocked in ``recv``.
    """
    t1 = threading.Thread(target=_relay_worker, args=(a_sock, b_sock), daemon=True)
    t2 = threading.Thread(target=_relay_worker, args=(b_sock, a_sock), daemon=True)
    t1.start()
    t2.start()

    # Poll joins in short intervals so we can react to global shutdown quickly.
    while t1.is_alive() or t2.is_alive():
        t1.join(timeout=0.2)
        t2.join(timeout=0.2)
        if config._SHUTDOWN_EVENT.is_set():
            # Force-unblock any blocking recv/send calls.
            with contextlib.suppress(Exception):
                a_sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(Exception):
                b_sock.shutdown(socket.SHUT_RDWR)

    # Best-effort close
    with contextlib.suppress(Exception):
        a_sock.close()
    with contextlib.suppress(Exception):
        b_sock.close()


# ===================================================================
# HTTP(S) Proxy Handler
# ===================================================================


class BlockProxyHandler(BaseHTTPRequestHandler):
    """Proxy request handler with blocklist / whitelist enforcement."""

    timeout: int = config.PROXY_HANDLER_TIMEOUT_SECS
    rbufsize: int = 0
    protocol_version: str = config.PROXY_PROTOCOL_VERSION

    # VoIP / STUN / SIP allowed ports
    VOIP_ALLOWED_PORTS: set[int] = config.VOIP_ALLOWED_PORTS

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_hostname_from_path(self, path: str) -> str | None:
        """Extract the hostname from a full URL path."""
        try:
            parsed = urllib.parse.urlparse(path)
            return parsed.hostname
        except Exception:
            return None

    def _establish_tunnel(
        self,
        target_host: str,
        target_port: int,
    ) -> None:
        """Create a TCP tunnel and relay traffic bidirectionally.

        Sends a ``200 Connection Established`` response, configures
        socket options, and starts a full-duplex relay.
        """
        remote = socket.create_connection(
            (target_host, target_port), timeout=config.SOCKET_CONNECT_TIMEOUT_SECS
        )
        self.send_response(200, "Connection Established")
        self.send_header("Connection", "close")
        self.end_headers()

        conn = self.connection
        _set_socket_opts_for_perf(conn)
        _set_socket_opts_for_perf(remote)
        with contextlib.suppress(Exception):
            conn.settimeout(config.SOCKET_IDLE_TIMEOUT)
            remote.settimeout(config.SOCKET_IDLE_TIMEOUT)
        conn.setblocking(True)
        remote.setblocking(True)
        full_duplex_relay(conn, remote)

    def do_CONNECT(self) -> None:
        """Handle HTTPS CONNECT tunnel requests."""
        host_port = self.path
        target_host, target_port_str = host_port.split(":", 1)
        target_port = int(target_port_str)
        hostname = target_host.lower() if target_host else None

        try:
            # Trigger background reload if interval elapsed
            if config.current_resolver:
                config.current_resolver.maybe_reload_background()

            # ----------------------------------------------------------
            # 1) Whitelist: if whitelisted, bypass ALL restrictions
            # ----------------------------------------------------------
            try:
                if config.current_resolver and config.current_resolver.is_whitelisted(hostname):
                    log(f"\u2705 [Liste blanche] {hostname}:{target_port}")
                    self._establish_tunnel(target_host, target_port)
                    return
            except Exception as e:
                # If whitelist check fails, continue to security checks
                # rather than letting everything through.
                log(f"[WARN] whitelist check error in CONNECT for {hostname}: {e}")

            # ----------------------------------------------------------
            # 2) Blocklist: if blocked, reject
            # ----------------------------------------------------------
            if (
                config.block_enabled
                and config.current_resolver
                and config.current_resolver._is_blocked(hostname)
            ):
                log(f"\u274C [Liste noir] {hostname}")
                self.send_error(403, "Blocked by security policy")
                return

            # ----------------------------------------------------------
            # 3) Port check: block non-standard ports when flag is on
            # ----------------------------------------------------------
            if config.block_http_other_ports and target_port not in self.VOIP_ALLOWED_PORTS:
                log(f"\u274C [Port alternatif]  {target_host}:{target_port}")
                self.send_error(403, "Blocked by security policy")
                return

            # ----------------------------------------------------------
            # 4) Allow: establish tunnel
            # ----------------------------------------------------------
            log(f"\u2705 [Autorisé] {hostname}")
            self._establish_tunnel(target_host, target_port)

        except Exception as e:
            log(f"[Proxy CONNECT error] {e}")
            with contextlib.suppress(Exception):
                self.send_error(502, "Bad Gateway")

    # ------------------------------------------------------------------
    # HTTP method handler -- extracted helpers
    # ------------------------------------------------------------------

    def _resolve_target(
        self,
    ) -> tuple[str | None, str | None, int, str, str] | None:
        """Extract target_host, hostname, target_port, path_only, scheme.

        Returns ``None`` if the request is invalid (sends 400).
        The *hostname* value is always lowercased for security checks;
        *target_host* is used as-is for the actual connection.
        """
        # Extract normalized hostname for security checks
        hostname = self._extract_hostname_from_path(self.path)
        if not hostname:
            host_header = self.headers.get("Host", "")
            hostname = host_header.split(":", 1)[0] if host_header else None
        if hostname:
            hostname = hostname.lower().strip()

        # Extract connection parameters
        if isinstance(self.path, str) and self.path.startswith(("http://", "https://")):
            parsed = urllib.parse.urlparse(self.path)
            scheme = parsed.scheme
            target_host = parsed.hostname
            target_port = parsed.port or (443 if scheme == "https" else 80)
            path_only = parsed.path or "/"
            if parsed.query:
                path_only += "?" + parsed.query
        else:
            host_hdr = self.headers.get("Host", "")
            if ":" in host_hdr:
                target_host, port_str = host_hdr.split(":", 1)
                try:
                    target_port = int(port_str)
                except Exception:
                    target_port = 80
            else:
                target_host = host_hdr
                target_port = 80
            path_only = self.path
            scheme = "http"

        if not target_host:
            self.send_error(400, "Bad Request - target host unknown")
            return None

        return target_host, hostname, target_port, path_only, scheme

    def _build_forwarded_request(
        self,
        target_host: str,
        target_port: int,
        path_only: str,
        scheme: str,
    ) -> bytes:
        """Construct the HTTP request bytes to send to the remote server.

        Handles hop-by-hop header stripping and Host header rewriting.
        """
        hop_by_hop = {
            "proxy-connection",
            "connection",
            "keep-alive",
            "transfer-encoding",
            "te",
            "trailers",
            "upgrade",
            "proxy-authorization",
        }
        header_lines: list[str] = []
        host_header_value = target_host
        if (scheme == "http" and target_port != 80) or (scheme == "https" and target_port != 443):
            host_header_value = f"{target_host}:{target_port}"

        for k, v in self.headers.items():
            try:
                if k.lower() in hop_by_hop:
                    continue
                if k.lower() == "host":
                    header_lines.append(f"Host: {host_header_value}")
                else:
                    header_lines.append(f"{k}: {v}")
            except Exception:
                continue

        header_lines = [line for line in header_lines if not line.lower().startswith("connection:")]
        header_lines.append("Connection: close")

        request_line = f"{self.command} {path_only} {self.request_version}\r\n"
        request_headers_raw = "\r\n".join(header_lines) + "\r\n\r\n"
        return request_line.encode("utf-8") + request_headers_raw.encode("utf-8")

    def _forward_to_remote(
        self,
        target_host: str,
        target_port: int,
        request_bytes: bytes,
    ) -> None:
        """Create the remote connection, send the request, and start relay."""
        remote = socket.create_connection(
            (target_host, target_port), timeout=config.SOCKET_CONNECT_TIMEOUT_SECS
        )

        _set_socket_opts_for_perf(self.connection)
        _set_socket_opts_for_perf(remote)

        # Apply idle timeout after connection
        with contextlib.suppress(Exception):
            self.connection.settimeout(config.SOCKET_IDLE_TIMEOUT)
            remote.settimeout(config.SOCKET_IDLE_TIMEOUT)
        self.connection.setblocking(True)
        remote.setblocking(True)

        try:
            remote.sendall(request_bytes)
        except Exception as e:
            log(f"[Proxy send headers error] {e}")
            with contextlib.suppress(Exception):
                remote.close()
            self.send_error(502, "Bad Gateway")
            return

        full_duplex_relay(self.connection, remote)
        with contextlib.suppress(Exception):
            remote.close()

    # ------------------------------------------------------------------
    # HTTP method handler (orchestration)
    # ------------------------------------------------------------------

    def _handle_http_method(self) -> None:
        """Handle plain HTTP requests (GET, POST, PUT, DELETE, HEAD).

        Flow:
          1. Resolve target (host, port, path).
          2. Check whitelist -- bypass if whitelisted.
          3. Check blocklist -- 403 if blocked.
          4. Check port restrictions -- 403 if non-standard port.
          5. Check HTTP traffic restrictions -- 403 if plain HTTP.
          6. Build forwarded request.
          7. Forward to remote.
        """
        if config.current_resolver:
            config.current_resolver.maybe_reload_background()

        # 1. Resolve target
        result = self._resolve_target()
        if result is None:
            return
        target_host, hostname, target_port, path_only, scheme = result

        # 2. Check whitelist -- bypass if whitelisted
        is_whitelisted = False
        try:
            if config.current_resolver and config.current_resolver.is_whitelisted(hostname):
                is_whitelisted = True
        except Exception as e:
            log(f"_handle_http_method whitelist check error for {hostname}: {e}")

        if is_whitelisted:
            log(f"\u2705 [Liste blanche] {hostname} ({self.command} {self.path})")
        else:
            # 3. Check blocklist -- 403 if blocked
            if (
                config.block_enabled
                and config.current_resolver
                and config.current_resolver._is_blocked(hostname)
            ):
                log(f"\u274C [Liste noir] {hostname} ({self.command} {self.path})")
                self.send_error(403, "Blocked by security policy")
                return

            # 4. Check port restrictions -- 403 if non-standard port
            if config.block_http_other_ports and target_port not in self.VOIP_ALLOWED_PORTS:
                log(f"\u274C [Port non-standard] {target_host}:{target_port}")
                self.send_error(403, "Blocked by security policy")
                return

            # 5. Check HTTP traffic restrictions -- 403 if plain HTTP
            if (
                config.block_enabled
                and config.block_http_traffic
                and isinstance(self.path, str)
                and self.path.startswith("http://")
            ):
                log(f"\u274C [Traffic non sécurisé] {hostname}")
                self.send_error(403, "Blocked by security policy")
                return

        # 6. Build forwarded request & 7. Forward to remote
        try:
            request_bytes = self._build_forwarded_request(
                target_host, target_port, path_only, scheme
            )
            self._forward_to_remote(target_host, target_port, request_bytes)
            log(f"\u2705 [Autorisé] {target_host}:{target_port} -> {self.command} {path_only}")
        except Exception as e:
            log(f"[Proxy forward error] {e}\n{traceback.format_exc()}")
            with contextlib.suppress(Exception):
                self.send_error(502, "Bad Gateway")

    # ------------------------------------------------------------------
    # HTTP method shortcuts
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        self._handle_http_method()

    def do_POST(self) -> None:
        self._handle_http_method()

    def do_PUT(self) -> None:
        self._handle_http_method()

    def do_DELETE(self) -> None:
        self._handle_http_method()

    def do_HEAD(self) -> None:
        self._handle_http_method()

    def log_message(self, format: str, *args: Any) -> None:
        """Silence default HTTP server logging."""
        return


# ===================================================================
# Server with connection limit
# ===================================================================


class LimitedThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer with a connection semaphore.

    Prevents unbounded thread growth when clients keep connections open.
    """

    daemon_threads: bool = True

    def process_request(  # type: ignore[override]
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        acquired = config._CONNECTION_SEMAPHORE.acquire(blocking=False)
        if not acquired:
            with contextlib.suppress(Exception):
                request.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(Exception):
                request.close()
            log("\u274c Trop de connexions actives")
            return
        return super().process_request(request, client_address)

    def process_request_thread(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            config._CONNECTION_SEMAPHORE.release()


# ===================================================================
# Server entry point
# ===================================================================


def start_proxy_server(
    bind_ip: str = config.PROXY_BIND_IP,
    port: int = config.PROXY_PORT,
) -> LimitedThreadingHTTPServer | None:
    """Start the threading HTTP proxy server.

    Returns the server object, or ``None`` on error.
    """
    try:
        server = LimitedThreadingHTTPServer((bind_ip, port), BlockProxyHandler)
        config.proxy_server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        config.proxy_server_thread = thread
        thread.start()
        log(f"HTTP(S) proxy Démarré sur {bind_ip}:{port}")
        return server
    except Exception as e:
        log(f"Erreur lors du démarrage du proxy: {e}")
        return None
