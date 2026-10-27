# -*- coding: utf-8 -*-

from telemetry_upload import core


def test_batches_even_split():
    items = list(range(7))
    assert core.batches(items, 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_batches_single_size():
    assert core.batches([1, 2, 3], 1) == [[1], [2], [3]]


def test_batches_invalid_size_falls_back():
    assert core.batches([1, 2], 0) == [[1, 2]]


def test_read_all_deterministic():
    d = [{"code": "D1", "temp": 50.0, "press": 0.4}]
    assert core.read_all(d, 7) == core.read_all(d, 7)


def test_send_succeeds_first_try():
    calls = []

    def tr(b):
        calls.append(1)
        return True

    assert core.send_with_retry(tr, ["x"]) is True and len(calls) == 1


def test_send_succeeds_on_third_try():
    n = {"i": 0}

    def tr(b):
        n["i"] += 1
        return n["i"] >= 3

    assert core.send_with_retry(tr, ["x"], max_retry=2) is True
    assert n["i"] == 3


def test_send_fails_all_attempts():
    calls = []

    def tr(b):
        calls.append(1)
        raise RuntimeError("network down")

    assert core.send_with_retry(tr, ["x"], max_retry=2) is False
    assert len(calls) == 3


def test_flush_pending_writes_json(tmp_path):
    p = str(tmp_path / "sub" / "pending.json")
    core.flush_pending(p, [{"code": "D1"}])
    import json
    assert json.load(open(p, encoding="utf-8")) == [{"code": "D1"}]
