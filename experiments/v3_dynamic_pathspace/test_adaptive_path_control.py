"""Unit checks for request-level adaptive path admission."""

from experiments.v3_dynamic_pathspace.scheduler import (
    AdaptiveLinkPressurePathScheduler,
)


def test_adaptive_gate_uses_positive_10ms_deadband():
    scheduler = object.__new__(AdaptiveLinkPressurePathScheduler)
    scheduler.min_link_relief_s = 0.01

    assert not scheduler._admit_candidate(0.0, 0.0)
    assert not scheduler._admit_candidate(0.009, 0.0)
    assert not scheduler._admit_candidate(0.01, 0.0)
    assert scheduler._admit_candidate(0.010001, 0.0)


def test_batch_cost_remains_a_hard_veto_when_enabled():
    scheduler = object.__new__(AdaptiveLinkPressurePathScheduler)
    scheduler.min_link_relief_s = 0.01

    assert not scheduler._admit_candidate(0.015, 0.02)
    assert scheduler._admit_candidate(0.021, 0.02)
