import pytest
from unittest.mock import patch

from src.events_module.etl import (
    process_events_by_user,
    accumulate_event_metrics,
)


@patch("src.events_module.etl.get_event_codes")
def test_process_events_by_user_translates_correctly(mock_get_event_codes):
    mock_get_event_codes.return_value = {
        4624: "login_success",
        4800: "lock_screen",
    }

    fake_raw_events = [
        # Normal login
        {
            "Equipo": "LAPTOP-DEV-01",
            "Usuario": "user1",
            "ID": 4624,
            "WindowsHello": False,
        },
        # Biometric login (Should override to biometric_auth)
        {
            "Equipo": "LAPTOP-DEV-01",
            "Usuario": "user1",
            "ID": 4624,
            "WindowsHello": True,
        },
        # System event (Should NOT be added to the users dict)
        {
            "Equipo": "LAPTOP-MKT-02",
            "Usuario": "SISTEMA",
            "ID": 4800,
            "WindowsHello": False,
        },
    ]

    users, events_by_user = process_events_by_user(fake_raw_events)

    assert users["LAPTOP-DEV-01"] == "user1"
    assert "LAPTOP-MKT-02" not in users

    assert events_by_user["LAPTOP-DEV-01"]["login_success"] == 1
    assert events_by_user["LAPTOP-DEV-01"]["biometric_auth"] == 1
    assert events_by_user["LAPTOP-MKT-02"]["lock_screen"] == 1


def test_accumulate_event_metrics_calculates_delta_correctly():
    fake_db_metrics = [
        {
            "user_email": "user1@test-events.com",  # LAPTOP-DEV-01
            "login_success": 10,
            "lock_screen": 5,
            "restart": 2,
        }
    ]

    fake_new_events = {
        "LAPTOP-DEV-01": {"login_success": 2, "restart": 1},
        "LAPTOP-MKT-02": {  # user2@test-events.com
            "lock_screen": 3,
            "biometric_auth": 1,
        },
    }

    result = accumulate_event_metrics(
        current_month_metrics=fake_db_metrics,
        events_by_user=fake_new_events,
        month="2026-06",
    )

    user1_metrics = result["user1@test-events.com"]
    assert user1_metrics["login_success"] == 12  # 10 (DB) + 2 (New)
    assert user1_metrics["lock_screen"] == 5  # 5 (DB) + 0 (New)
    assert user1_metrics["restart"] == 3  # 2 (DB) + 1 (New)

    user2_metrics = result["user2@test-events.com"]
    assert user2_metrics["lock_screen"] == 3
    assert user2_metrics["biometric_auth"] == 1
    assert user2_metrics["login_success"] == 0  # Default dictionary key check
