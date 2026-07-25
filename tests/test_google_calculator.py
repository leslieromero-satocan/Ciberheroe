import pytest
from src.google_module import GoogleScoreCalculator

from src.custom_types import DBGooglePointSystem, GoogleUserMetrics

FAKE_POINT_SYSTEM: list[DBGooglePointSystem] = [
    {"label": "unsafe_sites", "points": 10},
    {"label": "reused_pwds", "points": 15},
    {"label": "risky_downloads", "points": 5},
    {"label": "non_corp_devices", "points": 10},
    {"label": "files_public_link", "points": 5},
    {"label": "vulnerable_pwds", "points": 20},
    {"label": "malware_downloads", "points": 25},
    # Good Practices (Multiplied by value)
    {"label": "messages_conf", "points": 2},
    {"label": "enabled_2sv", "points": 50},
    {"label": "files_exp_date", "points": 5},
    {"label": "device_platform", "points": 10},
]


def test_perfect_user_gets_all_points():
    calc = GoogleScoreCalculator()

    metrics: GoogleUserMetrics = {
        # Bad Practices: All 0 (Award full 90 points)
        "unsafe_sites": 0,
        "reused_pwds": 0,
        "risky_downloads": 0,
        "non_corp_devices": 0,
        "files_public_link": 0,
        "vulnerable_pwds": 0,
        "malware_downloads": 0,
        # Good Practices: Normal amounts
        "messages_conf": 5,  # 5 * 2 = +10
        "enabled_2sv": True,  # 1 * 50 = +50
        "files_exp_date": 2,  # 2 * 5 = +10
        "device_platform": 1,  # 1 * 10 = +10
    }

    score = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    # Expected: 90 (bad) + 80 (good) = 170.0
    assert score == 170.0


def test_risky_user_misses_bad_practice_points():
    calc = GoogleScoreCalculator()

    metrics: GoogleUserMetrics = {
        # Bad Practices: All > 0 (Award 0 points)
        "unsafe_sites": 1,
        "reused_pwds": 2,
        "risky_downloads": 1,
        "non_corp_devices": 3,
        "files_public_link": 5,
        "vulnerable_pwds": 1,
        "malware_downloads": 1,
        # Good Practices: All 0 (Award 0 points)
        "messages_conf": 0,
        "enabled_2sv": False,
        "files_exp_date": 0,
        "device_platform": 0,
    }

    score = calc.calculate_scores(metrics, FAKE_POINT_SYSTEM)

    # Expected: 0
    assert score == 0.0


def test_max_accumulation_cap():
    calc = GoogleScoreCalculator()

    metrics: GoogleUserMetrics = {
        # Bad Practices: All 0 (Award full 90 points)
        "unsafe_sites": 0,
        "reused_pwds": 0,
        "risky_downloads": 0,
        "non_corp_devices": 0,
        "files_public_link": 0,
        "vulnerable_pwds": 0,
        "malware_downloads": 0,
        # Good Practices: Way over the limit of 10!
        "messages_conf": 50,  # Cap triggers: 10 * 2 = +20
        "enabled_2sv": True,  # 1 * 50 = +50
        "files_exp_date": 20,  # Cap triggers: 10 * 5 = +50
        "device_platform": 1,  # 1 * 10 = +10
    }

    # We explicitly pass max_accumulation=10 just to be safe
    score = calc.calculate_scores(
        metrics, FAKE_POINT_SYSTEM, max_accumulation=10
    )

    # Expected: 90 (bad) + 130 (good capped) = 220.0
    assert score == 220.0
