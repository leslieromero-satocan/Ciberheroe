import pytest
from unittest.mock import patch, MagicMock

from src.google_module.etl import get_individual_metrics


@patch("src.google_module.etl.GoogleScoreCalculator")
@patch("src.google_module.etl.GmailExtractor")
@patch("src.google_module.etl.GoogleDriveExtractor")
def test_get_individual_metrics_calculates_delta_correctly(
    mock_drive_class, mock_gmail_class, mock_calc_class
):

    mock_drive_instance = mock_drive_class.return_value
    mock_drive_instance.extract_files_with_full_access.return_value = [
        "file1",
        "file2",
    ]
    mock_drive_instance.extract_files_with_expiration_date.return_value = [
        "file3"
    ]
    mock_gmail_instance = mock_gmail_class.return_value
    mock_gmail_instance.extract_messages_sent_in_confidential_mode.return_value = (
        ["msg1", "msg2", "msg3"],
        False,
    )

    mock_calc_instance = mock_calc_class.return_value
    mock_calc_instance.process_devices.return_value = (
        0,
        1,
    )  # non_corp_devices=0, platform=1
    mock_calc_instance.calculate_scores.return_value = 85.0  # Fake final score

    user_email = "test@ulpgc.es"
    user_info = {"primaryEmail": user_email, "isEnrolledIn2Sv": True}

    # The user already has SOME data in the DB
    db_metrics = {
        user_email: {
            "files_public_link": 10,  # DB has 10, API will find 2 -> Expected: 12
            "messages_conf": 5,  # DB has 5, API will find 3 -> Expected: 8
            "unsafe_sites": 2,  # DB has 2, API will find 0 -> Expected: 2
        }
    }

    db_user_metrics, db_score, error = get_individual_metrics(
        user_info=user_info,
        db_metrics=db_metrics,
        corporate_devices={},
        unsafe_sites={},
        reuse_passwords={},
        file_downloads={},
        malware_download={},
        vulnerable_passwords={},
        current_month="2026-06",
        point_system=[],
    )

    assert error is False

    assert db_user_metrics["files_public_link"] == 12  # 10 (DB) + 2 (Mock API)
    assert db_user_metrics["messages_conf"] == 8  # 5 (DB) + 3 (Mock API)
    assert db_user_metrics["unsafe_sites"] == 2  # 2 (DB) + 0 (Mock API)

    assert db_user_metrics["enabled_2sv"] is True

    assert db_score["score"] == 85.0
    assert db_score["user_email"] == user_email
    assert db_score["month"] == "2026-06"
