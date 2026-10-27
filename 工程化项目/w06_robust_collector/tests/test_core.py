# -*- coding: utf-8 -*-
import pytest

from robust_collector import core


def test_parse_good_line():
    assert core.parse_line("56.2,0.45") == (56.2, 0.45)


def test_parse_handles_spaces():
    assert core.parse_line(" 56.2 , 0.45 ") == (56.2, 0.45)


@pytest.mark.parametrize("raw", ["err,0.46", "56.2", "56.2,0.4,5", "abc"])
def test_parse_bad_lines_raise(raw):
    with pytest.raises(core.ParseError):
        core.parse_line(raw)


@pytest.mark.parametrize("t,p,reason", [
    (-1.0, 0.4, "负值"), (250.0, 0.4, "温度越界"), (50.0, 9.0, "压力越界")])
def test_validate_rejects(t, p, reason):
    ok, r = core.validate(t, p)
    assert ok is False and r == reason


def test_validate_accepts_normal():
    assert core.validate(56.2, 0.45) == (True, "")


def test_quarantine_entry_structure():
    e = core.quarantine_line(3, "err,1", "非数值")
    assert e == {"line": 3, "raw": "err,1", "reason": "非数值"}
