"""Tests for the scheduling system — cadence loading, cron parsing, health tracking."""

from __future__ import annotations

import pytest

from ai_benchmark.scheduling.cadence import (
    ScheduleEntry,
    load_schedules,
    parse_cron_fields,
)
from ai_benchmark.scheduling.scheduler import (
    MAX_CONSECUTIVE_FAILURES,
    SourceHealthTracker,
)

# ─── Cadence loading ───


def test_load_schedules():
    schedules = load_schedules()
    assert len(schedules) > 0
    assert all(isinstance(s, ScheduleEntry) for s in schedules)


def test_schedules_cover_all_sources():
    schedules = load_schedules()
    orgs = {s.organization for s in schedules}
    # Should have entries for all major source categories
    assert "OpenAI" in orgs
    assert "Reuters" in orgs
    assert "arXiv" in orgs
    assert "Hugging Face Forums" in orgs


def test_schedule_entry_fields():
    schedules = load_schedules()
    for s in schedules:
        assert s.organization
        assert s.cron
        assert s.max_concurrent >= 1


# ─── Cron parsing ───


def test_parse_cron_fields_standard():
    fields = parse_cron_fields("0 */6 * * *")
    assert fields["minute"] == "0"
    assert fields["hour"] == "*/6"
    assert fields["day"] == "*"
    assert fields["month"] == "*"
    assert fields["day_of_week"] == "*"


def test_parse_cron_fields_specific():
    fields = parse_cron_fields("30 6,18 * * *")
    assert fields["minute"] == "30"
    assert fields["hour"] == "6,18"


def test_parse_cron_invalid():
    with pytest.raises(ValueError, match="Invalid cron"):
        parse_cron_fields("* *")


# ─── Health tracking ───


def test_health_tracker_success():
    tracker = SourceHealthTracker()
    tracker.record_success("OpenAI")
    status = tracker.get_status("OpenAI")
    assert status["last_success_at"] is not None
    assert status["consecutive_failures"] == 0


def test_health_tracker_failure():
    tracker = SourceHealthTracker()
    tracker.record_failure("OpenAI", "Connection timeout")
    status = tracker.get_status("OpenAI")
    assert status["last_failure_at"] is not None
    assert status["consecutive_failures"] == 1
    assert status["last_error"] == "Connection timeout"


def test_health_tracker_circuit_breaker():
    tracker = SourceHealthTracker()
    for i in range(MAX_CONSECUTIVE_FAILURES):
        assert not tracker.is_circuit_open("OpenAI")
        tracker.record_failure("OpenAI", f"Error {i}")
    assert tracker.is_circuit_open("OpenAI")


def test_health_tracker_circuit_reset_on_success():
    tracker = SourceHealthTracker()
    for i in range(MAX_CONSECUTIVE_FAILURES):
        tracker.record_failure("OpenAI", f"Error {i}")
    assert tracker.is_circuit_open("OpenAI")

    tracker.record_success("OpenAI")
    assert not tracker.is_circuit_open("OpenAI")


def test_health_tracker_unknown_source():
    tracker = SourceHealthTracker()
    status = tracker.get_status("Unknown")
    assert status["consecutive_failures"] == 0


def test_get_all_statuses():
    tracker = SourceHealthTracker()
    tracker.record_success("OpenAI")
    tracker.record_failure("Google", "Error")
    statuses = tracker.get_all_statuses()
    assert "OpenAI" in statuses
    assert "Google" in statuses
