"""
CZID-160: unit tests for benchmark_gate.py.

Pure-Python, no docker or miniwdl required, so this runs anywhere pytest does:
  pytest workflows/short-read-mngs/auto_benchmark/test_benchmark_gate.py

It locks down the gate's pass/fail contract: exact match passes, a >tolerance
deviation fails, a NaN/None metric fails, and the absolute AUPR floor fails the
low-AUPR viral samples (which is why the floor is full-index-only).
"""

import json
import math

import benchmark_gate as bg


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return str(p)


def _ref_lib(tmp_path):
    ref_dir = tmp_path / "ref_libs"
    ref_dir.mkdir()
    (ref_dir / "s1.json").write_text(json.dumps({"NT_aupr": 0.5, "NR_aupr": 0.4}))
    return str(ref_dir)


def test_exact_match_passes(tmp_path):
    ref = _ref_lib(tmp_path)
    h = _write(tmp_path, "s1.json", {"s1": {"NT_aupr": 0.5, "NR_aupr": 0.4}})
    rows, failures = bg.evaluate([h], ref, tolerance=0.01, min_aupr=None)
    assert failures == []
    assert all(r["status"] == "OK" for r in rows)


def test_over_tolerance_deviation_fails(tmp_path):
    ref = _ref_lib(tmp_path)
    # 2% high on NT_aupr, tolerance is 1%.
    h = _write(tmp_path, "s1.json", {"s1": {"NT_aupr": 0.51, "NR_aupr": 0.4}})
    rows, failures = bg.evaluate([h], ref, tolerance=0.01, min_aupr=None)
    assert len(failures) == 1
    assert any(r["status"].startswith("FAIL(deviation)") for r in rows)


def test_within_tolerance_passes(tmp_path):
    ref = _ref_lib(tmp_path)
    # 0.5% high, under the 1% tolerance.
    h = _write(tmp_path, "s1.json", {"s1": {"NT_aupr": 0.5025, "NR_aupr": 0.4}})
    _, failures = bg.evaluate([h], ref, tolerance=0.01, min_aupr=None)
    assert failures == []


def test_nan_or_missing_metric_fails(tmp_path):
    ref = _ref_lib(tmp_path)
    h = _write(tmp_path, "s1.json", {"s1": {"NT_aupr": None, "NR_aupr": 0.4}})
    _, failures = bg.evaluate([h], ref, tolerance=0.01, min_aupr=None)
    assert len(failures) >= 1


def test_absolute_floor_fails_low_aupr(tmp_path):
    ref = _ref_lib(tmp_path)
    h = _write(tmp_path, "s1.json", {"s1": {"NT_aupr": 0.5, "NR_aupr": 0.4}})
    # Exact match (0 deviation) but both below the 0.98 floor.
    _, failures = bg.evaluate([h], ref, tolerance=0.01, min_aupr=0.98)
    assert len(failures) == 2


def test_relative_deviation_helper():
    assert bg._relative_deviation(0.5, 0.5) == 0.0
    assert math.isclose(bg._relative_deviation(0.55, 0.5), 0.1)
    assert bg._relative_deviation(float("nan"), 0.5) == math.inf
    assert bg._relative_deviation(None, 0.5) == math.inf
