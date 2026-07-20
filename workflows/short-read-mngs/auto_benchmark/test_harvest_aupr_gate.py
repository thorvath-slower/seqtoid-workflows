"""Unit tests for the AUPR acceptance gate in harvest.py (aupr_regressions).

Kept dependency-light: exercises only the pure gate function, which decides whether a benchmark run's
per-sample NT/NR AUPR clears the floor used to BLOCK a regressing taxonomy/index refresh.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from harvest import aupr_regressions  # noqa: E402


def test_passes_when_all_metrics_clear_the_floor():
    results = {
        "atcc_even": {"NT_aupr": 0.995, "NR_aupr": 0.991, "outputs": {"junk": 1}},
        "atcc_staggered": {"NT_aupr": 0.982, "NR_aupr": 0.980},
    }
    assert aupr_regressions(results, 0.98) == []


def test_flags_every_metric_below_the_floor():
    results = {
        "atcc_even": {"NT_aupr": 0.995, "NR_aupr": 0.970},   # NR regresses
        "atcc_staggered": {"NT_aupr": 0.950, "NR_aupr": 0.999},  # NT regresses
    }
    regressions = aupr_regressions(results, 0.98)
    assert ("atcc_even", "NR_aupr", 0.970) in regressions
    assert ("atcc_staggered", "NT_aupr", 0.950) in regressions
    assert len(regressions) == 2


def test_ignores_non_metric_keys_and_non_numeric_values():
    results = {
        "s1": {"NT_aupr": 0.99, "NR_aupr": 0.99, "outputs": {"a": 0.0}, "NT_precision": [0.1, 0.2]},
    }
    # 'outputs' and the *_precision list must not be treated as AUPR metrics.
    assert aupr_regressions(results, 0.98) == []


def test_boundary_is_inclusive():
    # exactly at the floor passes (>= floor)
    assert aupr_regressions({"s1": {"NT_aupr": 0.98}}, 0.98) == []
    assert aupr_regressions({"s1": {"NT_aupr": 0.9799}}, 0.98) == [("s1", "NT_aupr", 0.9799)]


def test_tolerates_a_sample_without_metrics():
    assert aupr_regressions({"s1": "skipped"}, 0.98) == []
