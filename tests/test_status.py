"""Calcolo degli stati (Completata/In ritardo/Da fare, Scaduto/...) —
dipende solo da date passate come argomenti, nessun I/O."""

from datetime import date

from utils.status import compute_activity_status, compute_deadline_status, completion_color

TODAY = date(2026, 6, 1)


def test_activity_completed_wins_over_date():
    assert compute_activity_status(True, date(2020, 1, 1), TODAY) == "Completata"


def test_activity_late_when_planned_end_in_past():
    assert compute_activity_status(False, date(2026, 1, 1), TODAY) == "In ritardo"


def test_activity_todo_when_planned_end_in_future():
    assert compute_activity_status(False, date(2026, 12, 1), TODAY) == "Da fare"


def test_activity_todo_when_no_planned_end():
    assert compute_activity_status(False, None, TODAY) == "Da fare"


def test_completion_color_thresholds_differ():
    assert completion_color(90) != completion_color(60)
    assert completion_color(60) != completion_color(10)


def test_deadline_expired():
    assert compute_deadline_status(date(2026, 1, 1), TODAY) == "Scaduto"


def test_deadline_within_30_days():
    assert compute_deadline_status(date(2026, 6, 15), TODAY) == "Entro 30 giorni"


def test_deadline_within_90_days():
    assert compute_deadline_status(date(2026, 8, 1), TODAY) == "Entro 90 giorni"


def test_deadline_valid_when_far_in_future():
    assert compute_deadline_status(date(2027, 1, 1), TODAY) == "Valido"


def test_deadline_none_means_no_expiry():
    assert compute_deadline_status(None, TODAY) == "Senza scadenza"
