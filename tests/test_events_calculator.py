import pytest
from src.events_module import EventScoreCalculator
from src.custom_types import EventMetrics

FAKE_POINT_SYSTEM = [
    {"label": "restart", "points": 10, "minimum": 2},
    {"label": "lock_screen", "points": 15, "minimum": 10},
    {"label": "biometric_auth", "points": 5, "minimum": 0},
    {"label": "updates", "points": 10, "minimum": 1},
    {"label": "login_failed", "points": 5, "minimum": 0},
    {"label": "usb_devices", "points": 20, "minimum": 0},
]


def test_perfect_user_gets_all_points():
    calc = EventScoreCalculator()

    metrics: dict[str, EventMetrics] = {
        "perfect@email.com": {
            # Good Practices: ALL > minimum (All 40 points)
            "restart": 5,
            "lock_screen": 15,
            "updates": 2,
            # Biometrics: biometric login > other login
            "biometric_auth": 5,
            "login_success": 0,
            # Bad practices: ALL < minimum (ALL 25 points)
            "login_failed": 0,
            "usb_devices": 0,
        }
    }

    scores = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    assert scores["perfect@email.com"] == 65.0


def test_risky_user_gets_zero_points():
    calc = EventScoreCalculator()

    metrics: dict[str, EventMetrics] = {
        "risky@email.com": {
            # Good Practices: ALL < minimum (0 points)
            "restart": 1,  # Min is 2
            "lock_screen": 9,  # Min is 10
            "updates": 0,  # Min is 1
            # Biometrics: biometric <= other login (0 points)
            "biometric_auth": 2,
            "login_success": 5,
            # Bad practices: ALL > minimum (0 points awarded)
            "login_failed": 2,  # Min is 0
            "usb_devices": 1,  # Min is 0
        }
    }

    scores = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    assert scores["risky@email.com"] == 0.0


def test_boundary_conditions():
    calc = EventScoreCalculator()

    metrics: dict[str, EventMetrics] = {
        "boundary@email.com": {
            # Good Practices: Exactly AT the minimum.
            "restart": 2,
            "lock_screen": 10,
            "updates": 1,
            # Biometrics: Exactly equal to standard logins.
            "biometric_auth": 5,
            "login_success": 5,
            # Bad practices: Exactly AT the minimum (0).
            "login_failed": 0,
            "usb_devices": 0,
        }
    }

    scores = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    # Expected: restart(10) + lock_screen(15) + updates(10)
    # + login_failed(5) + usb_devices(20) = 60.0
    assert scores["boundary@email.com"] == 60.0


def test_partial_user_mixed_results():
    calc = EventScoreCalculator()

    metrics: dict[str, EventMetrics] = {
        "partial@email.com": {
            # Good Practices: Mix of pass and fail
            "restart": 5,  # Pass (+10)
            "lock_screen": 2,  # Fail (+0)
            "updates": 1,  # Pass (+10)
            # Biometrics: Pass (+5)
            "biometric_auth": 10,
            "login_success": 2,
            # Bad practices: One pass, one fail
            "login_failed": 3,  # Fail (+0)
            "usb_devices": 0,  # Pass (+20)
        }
    }

    scores = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    # Expected: 10 + 0 + 10 + 5 + 0 + 20 = 45.0
    assert scores["partial@email.com"] == 45.0
