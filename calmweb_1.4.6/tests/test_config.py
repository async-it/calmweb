"""Tests for calmweb.config_io -- custom.cfg parsing and writing.
"""

from __future__ import annotations

import os

import pytest

from calmweb import config
from calmweb.config_io import parse_custom_cfg, write_default_custom_cfg
from calmweb.parser import _normalize_domain, _parse_option_line, _parse_section_line


def _write_cfg(tmp_path, text: str) -> str:
    """Write *text* into a temporary custom.cfg and return its path."""
    path = str(tmp_path / "custom.cfg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path

def test_parse_valid_config_all_sections(tmp_path):
    """All three sections are parsed into the correct sets / flags."""
    cfg = _write_cfg(
        tmp_path,
        "[BLOCK]\n"
        "evil.com\n"
        "bad.org\n"
        "\n"
        "[WHITELIST]\n"
        "good.com\n"
        "\n"
        "[OPTIONS]\n"
        "block_ip_direct = 0\n"
        "block_http_traffic = 1\n"
        "block_http_other_ports = false\n",
    )
    blocked, whitelist = parse_custom_cfg(cfg)

    assert blocked == {"evil.com", "bad.org"}
    assert whitelist == {"good.com"}
    assert config.block_ip_direct is False
    assert config.block_http_traffic is True
    assert config.block_http_other_ports is False

def test_parse_missing_file_returns_empty(tmp_path):
    """A non-existent path returns empty sets without raising."""
    path = str(tmp_path / "does_not_exist.cfg")
    blocked, whitelist = parse_custom_cfg(path)

    assert blocked == set()
    assert whitelist == set()


def test_parse_empty_file_returns_empty(tmp_path):
    """An empty file returns empty sets."""
    cfg = _write_cfg(tmp_path, "")
    blocked, whitelist = parse_custom_cfg(cfg)

    assert blocked == set()
    assert whitelist == set()

def test_comments_and_blanks_are_ignored(tmp_path):
    """Lines starting with # and blank lines are skipped."""
    cfg = _write_cfg(
        tmp_path,
        "# This is a comment\n"
        "\n"
        "[BLOCK]\n"
        "# another comment\n"
        "evil.com\n"
        "\n"
        "[WHITELIST]\n"
        "good.com\n",
    )
    blocked, whitelist = parse_custom_cfg(cfg)

    assert blocked == {"evil.com"}
    assert whitelist == {"good.com"}

@pytest.mark.parametrize(
    "val,expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("True", True),
        ("YES", True),
        ("ON", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("anything_else", False),
    ],
)
def test_option_boolean_parsing(tmp_path, val, expected):
    """Various truthy/falsy values are interpreted correctly."""
    cfg = _write_cfg(tmp_path, f"[OPTIONS]\nblock_ip_direct = {val}\n")
    parse_custom_cfg(cfg)

    assert config.block_ip_direct is expected

def test_malformed_option_line_no_equals(tmp_path):
    """A line with no '=' in [OPTIONS] does not crash."""
    cfg = _write_cfg(
        tmp_path,
        "[OPTIONS]\n"
        "this_line_has_no_equals_sign\n"
        "block_ip_direct = 0\n",
    )
    parse_custom_cfg(cfg)
    # The valid line still takes effect
    assert config.block_ip_direct is False

def test_domains_before_section_go_to_blocked(tmp_path):
    """Domains appearing before any [SECTION] header go to blocked set."""
    cfg = _write_cfg(tmp_path, "stray.com\n[WHITELIST]\ngood.com\n")
    blocked, whitelist = parse_custom_cfg(cfg)

    assert "stray.com" in blocked
    assert whitelist == {"good.com"}

def test_leading_dots_are_stripped(tmp_path):
    """Domains like '.example.com' are stored as 'example.com'."""
    cfg = _write_cfg(
        tmp_path,
        "[BLOCK]\n"
        ".evil.com\n"
        "..double.dot.com\n"
        "[WHITELIST]\n"
        ".good.com\n",
    )
    blocked, whitelist = parse_custom_cfg(cfg)

    assert "evil.com" in blocked
    assert "double.dot.com" in blocked
    assert "good.com" in whitelist

def test_write_then_parse_roundtrip(tmp_path):
    """write_default_custom_cfg -> parse_custom_cfg reproduces the data."""
    path = str(tmp_path / "subdir" / "custom.cfg")
    blocked_in = {"block-a.com", "block-b.org"}
    whitelist_in = {"allow-x.com", "allow-y.net"}

    write_default_custom_cfg(path, blocked_in, whitelist_in)
    assert os.path.exists(path)

    blocked_out, whitelist_out = parse_custom_cfg(path)

    assert blocked_out == blocked_in
    assert whitelist_out == whitelist_in
    # Default options should all be truthy after a fresh write
    assert config.block_ip_direct is True
    assert config.block_http_traffic is True
    assert config.block_http_other_ports is True

class TestNormalizeDomain:
    def test_strips_leading_dots(self):
        assert _normalize_domain("..evil.com") == "evil.com"

    def test_lowercases(self):
        assert _normalize_domain("EVIL.COM") == "evil.com"

    def test_strips_whitespace(self):
        assert _normalize_domain("  evil.com  ") == "evil.com"


class TestParseSectionLine:
    def test_recognises_block_header(self):
        new_section, value = _parse_section_line("[BLOCK]")
        assert new_section == "BLOCK"
        assert value is None

    def test_case_insensitive_header(self):
        new_section, _ = _parse_section_line("[whitelist]")
        assert new_section == "WHITELIST"

    def test_regular_line_returns_value(self):
        new_section, value = _parse_section_line("evil.com")
        assert new_section is None
        assert value == "evil.com"


class TestParseOptionLine:
    def test_valid_truthy(self):
        assert _parse_option_line("block_ip_direct = 1") == ("block_ip_direct", True)

    def test_valid_falsy(self):
        assert _parse_option_line("block_ip_direct = 0") == ("block_ip_direct", False)

    def test_no_equals_returns_none(self):
        assert _parse_option_line("no_equals_here") is None
