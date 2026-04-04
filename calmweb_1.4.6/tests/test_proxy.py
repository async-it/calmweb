"""Tests for calmweb.proxy -- critical proxy handler paths.
"""

from __future__ import annotations

import io
import socket
from unittest.mock import MagicMock

import pytest

from calmweb import config
from calmweb.proxy import BlockProxyHandler


def _make_handler(path: str = "example.com:443") -> BlockProxyHandler:
    """Construct a BlockProxyHandler with mocked I/O so we can call
    its methods without a real server/socket pair.
    """
    handler = BlockProxyHandler.__new__(BlockProxyHandler)
    handler.path = path
    handler.command = "CONNECT"
    handler.request_version = "HTTP/1.1"

    # Provide a fake wfile so send_error / send_response can write
    handler.wfile = io.BytesIO()
    handler.rfile = io.BytesIO()

    # Fake connection socket
    handler.connection = MagicMock(spec=socket.socket)

    # Stub header-writing helpers that BaseHTTPRequestHandler normally sets up
    handler.headers = {}
    handler._headers_buffer = []
    handler.responses = {
        200: ("OK", ""),
        403: ("Forbidden", ""),
        502: ("Bad Gateway", ""),
    }
    handler.request = MagicMock()
    handler.client_address = ("127.0.0.1", 12345)
    handler.server = MagicMock()
    handler.close_connection = True
    return handler

class TestExtractHostname:
    def test_http_url(self):
        h = _make_handler()
        assert h._extract_hostname_from_path("http://example.com/path") == "example.com"

    def test_https_url(self):
        h = _make_handler()
        assert h._extract_hostname_from_path("https://foo.bar.com:8443/x") == "foo.bar.com"

    def test_plain_path_returns_none(self):
        h = _make_handler()
        # A bare path with no scheme -- urlparse puts it in path, not hostname
        result = h._extract_hostname_from_path("/just/a/path")
        assert result is None

    def test_empty_string(self):
        h = _make_handler()
        result = h._extract_hostname_from_path("")
        assert result is None

    def test_malformed_url_no_crash(self):
        h = _make_handler()
        # Should not raise, even with garbage
        result = h._extract_hostname_from_path("://broken")
        # Result may vary, but no exception
        assert isinstance(result, (str, type(None)))

class TestVoipAllowedPorts:
    def test_expected_ports_present(self):
        expected = {80, 443, 3478, 5060, 5061}
        assert expected == BlockProxyHandler.VOIP_ALLOWED_PORTS

    def test_arbitrary_port_not_in_set(self):
        assert 8443 not in BlockProxyHandler.VOIP_ALLOWED_PORTS

class TestDoConnect:
    """Verify the three-step decision flow in do_CONNECT:
       1) Whitelist check -- bypass everything if whitelisted
       2) Blocklist check -- 403 if blocked
       3) Port check -- 403 if non-standard port + flag on

    We mock the resolver and _establish_tunnel to avoid real sockets.
    """

    @pytest.fixture(autouse=True)
    def _reset_config(self):
        """Clean config globals before each test."""
        self._orig_resolver = config.current_resolver
        self._orig_block_enabled = config.block_enabled
        self._orig_block_other_ports = config.block_http_other_ports
        config.block_enabled = True
        config.block_http_other_ports = True
        yield
        config.current_resolver = self._orig_resolver
        config.block_enabled = self._orig_block_enabled
        config.block_http_other_ports = self._orig_block_other_ports

    def _run_connect(self, host_port: str, *, whitelisted: bool, blocked: bool):
        """Set up a handler with mocked resolver and call do_CONNECT.

        Returns (handler, tunnel_called, send_error_code).
        """
        handler = _make_handler(host_port)

        tunnel_called = []
        error_codes = []

        handler._establish_tunnel = lambda h, p: tunnel_called.append((h, p))

        def fake_send_error(code, message=None, explain=None):
            error_codes.append(code)

        handler.send_error = fake_send_error
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        resolver = MagicMock()
        resolver.is_whitelisted.return_value = whitelisted
        resolver._is_blocked.return_value = blocked
        resolver.maybe_reload_background = MagicMock()
        config.current_resolver = resolver

        handler.do_CONNECT()
        return handler, tunnel_called, error_codes

    def test_whitelisted_domain_non_standard_port_allowed(self):
        """Whitelisted domain on port 8443 must be ALLOWED."""
        _, tunnel_called, error_codes = self._run_connect(
            "example.com:8443", whitelisted=True, blocked=False
        )
        assert len(tunnel_called) == 1, "Tunnel should have been established"
        assert tunnel_called[0] == ("example.com", 8443)
        assert error_codes == []

    def test_non_whitelisted_non_standard_port_blocked(self):
        """Non-whitelisted domain on port 8443 with
        block_http_other_ports=True must get 403."""
        config.block_http_other_ports = True
        _, tunnel_called, error_codes = self._run_connect(
            "unknown.com:8443", whitelisted=False, blocked=False
        )
        assert tunnel_called == [], "Tunnel should NOT be established"
        assert 403 in error_codes

    def test_non_whitelisted_port_443_allowed(self):
        """Standard port 443 should be allowed for non-whitelisted, non-blocked domains."""
        _, tunnel_called, error_codes = self._run_connect(
            "safe.com:443", whitelisted=False, blocked=False
        )
        assert len(tunnel_called) == 1
        assert error_codes == []

    def test_blocked_domain_gets_403(self):
        """A blocked, non-whitelisted domain must receive a 403."""
        _, tunnel_called, error_codes = self._run_connect(
            "evil.com:443", whitelisted=False, blocked=True
        )
        assert tunnel_called == []
        assert 403 in error_codes

    def test_whitelisted_blocked_domain_still_allowed(self):
        """Whitelist has absolute priority, even if the domain is also blocked."""
        _, tunnel_called, error_codes = self._run_connect(
            "overlap.com:443", whitelisted=True, blocked=True
        )
        assert len(tunnel_called) == 1, "Whitelist should override blocklist"
        assert error_codes == []

    def test_port_check_skipped_when_flag_off(self):
        """When block_http_other_ports is False, non-standard ports are allowed."""
        config.block_http_other_ports = False
        _, tunnel_called, error_codes = self._run_connect(
            "somesite.com:9999", whitelisted=False, blocked=False
        )
        assert len(tunnel_called) == 1
        assert error_codes == []
