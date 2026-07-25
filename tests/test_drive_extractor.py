import pytest
from unittest.mock import patch, MagicMock
from src.google_module.drive import GoogleDriveExtractor


@patch("src.google_module.drive.build")
def test_extract_files_with_full_access(mock_build):
    extractor = GoogleDriveExtractor(
        logger=MagicMock(), user_email="test@test.com"
    )

    fake_response = {
        "files": [
            {
                "id": "file1",
                "name": "public_doc.txt",
                "mimeType": "text/plain",
            },
            {"id": "file2", "name": "open_sheet.csv", "mimeType": "text/csv"},
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_response)
    extractor.files_collection.list_next = MagicMock(return_value=None)

    files = extractor.extract_files_with_full_access()

    assert len(files) == 2
    assert files[0]["name"] == "public_doc.txt"


@patch("src.google_module.drive.build")
def test_extract_files_with_expiration_date(mock_build):
    extractor = GoogleDriveExtractor(
        logger=MagicMock(), user_email="test@test.com"
    )

    fake_response = {
        "files": [
            {
                "id": "file3",
                "name": "temp_access.pdf",
                "permissions": [{"expirationTime": "2026-12-31T23:59:59Z"}],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_response)
    extractor.files_collection.list_next = MagicMock(return_value=None)

    files = extractor.extract_files_with_expiration_date()

    assert len(files) == 1
    assert files[0]["id"] == "file3"
    assert "expirationTime" in files[0]["permissions"][0]
