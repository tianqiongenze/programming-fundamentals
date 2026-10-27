# -*- coding: utf-8 -*-
import pytest

from packet_parser import core


J = '{"id":"D1","t":78.5,"p":0.42}'


def test_parse_json():
    d = core.parse(J)
    assert d == {"id": "D1", "temp": 78.5, "press": 0.42, "format": "json"}


def test_parse_csv():
    assert core.parse("D2,81.0,0.50")["format"] == "csv"
    assert core.parse("D2,81.0,0.50")["temp"] == 81.0


def test_parse_kv():
    d = core.parse("id=D3;t=95.5;p=0.66")
    assert d == {"id": "D3", "temp": 95.5, "press": 0.66, "format": "kv"}


def test_parse_broken_packet_returns_none():
    assert core.parse("损坏报文@@@") is None


def test_malformed_json_falls_through_and_isolated():
    assert core.parse('{"id":"D1","t":78.5}') is None


@pytest.mark.parametrize("bad", ["D2,81.0", "D2,81.0,0.5,x", "id=D3;t=xx"])
def test_malformed_non_json_isolated(bad):
    assert core.parse(bad) is None


def test_router_is_extensible():
    """验证新增解析器只需注册，不改调用方。"""
    before = len(core.PARSERS)
    core.PARSERS.append(("test", lambda s: s.startswith("X"),
                         lambda s: {"id": "T", "temp": 1.0, "press": 0.1}))
    try:
        assert core.parse("X1")["format"] == "test"
    finally:
        core.PARSERS.pop()
    assert len(core.PARSERS) == before
