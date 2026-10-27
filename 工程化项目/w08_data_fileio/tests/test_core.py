# -*- coding: utf-8 -*-
import os


from data_fileio import core, io_utils


def test_summarize_basic():
    rows = [{"code": "A", "temp": 10.0, "press": 0.1},
            {"code": "B", "temp": 96.0, "press": 0.7}]
    st = core.summarize(rows)
    assert st["count"] == 2
    assert st["temp"]["max"] == 96.0 and st["temp"]["min"] == 10.0
    assert st["over_limit"] == ["B"]


def test_summarize_empty():
    assert core.summarize([]) == {"count": 0}


def test_atomic_write_no_tmp_left(tmp_path):
    p = str(tmp_path / "a.txt")
    io_utils.write_text(p, "hello")
    assert open(p, encoding="utf-8").read() == "hello"
    assert [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")] == []


def test_atomic_write_overwrites(tmp_path):
    p = str(tmp_path / "a.txt")
    io_utils.write_text(p, "v1")
    io_utils.write_text(p, "v2")
    assert open(p, encoding="utf-8").read() == "v2"


def test_csv_roundtrip(tmp_path):
    rows = [{"code": "D1", "temp": 56.5, "press": 0.45}]
    p = str(tmp_path / "d.csv")
    io_utils.write_csv_rows(p, rows, ["code", "temp", "press"])
    back = io_utils.read_csv_rows(p)
    assert back[0]["code"] == "D1" and float(back[0]["temp"]) == 56.5


def test_json_roundtrip_utf8(tmp_path):
    p = str(tmp_path / "d.json")
    io_utils.write_json(p, [{"name": "注塑机"}])
    assert io_utils.read_json(p) == [{"name": "注塑机"}]


def test_write_csv_empty_rows(tmp_path):
    p = str(tmp_path / "e.csv")
    io_utils.write_csv_rows(p, [])
    assert open(p, encoding="utf-8").read() == ""
