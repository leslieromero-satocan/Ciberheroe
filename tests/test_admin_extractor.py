import pytest
from unittest.mock import patch, MagicMock
from src.google_module.admin import AdminReportsExtractor


@patch("src.google_module.admin.build")
def test_check_ignore_certificate_warning_parses_nested_json(mock_build):
    extractor = AdminReportsExtractor(logger=MagicMock())

    fake_google_response = {
        "items": [
            {
                "actor": {"email": "hacker@ulpgc.es"},
                "events": [
                    {
                        "parameters": [
                            {"name": "OTHER_PARAM", "value": "ignore_me"},
                            {
                                "name": "URL",
                                "value": "http://malicious-site.com",
                            },
                        ]
                    }
                ],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_google_response)
    extractor.activities_collection.list_next = MagicMock(return_value=None)

    events_dict = extractor.check_ignore_certificate_warning()

    assert "hacker@ulpgc.es" in events_dict
    assert len(events_dict["hacker@ulpgc.es"]["unsafe_site_events"]) == 1
    assert (
        events_dict["hacker@ulpgc.es"]["unsafe_site_events"][0]
        == "http://malicious-site.com"
    )


@patch("src.google_module.admin.build")
def test_check_file_downloads_filters_dangerous_files(mock_build):
    extractor = AdminReportsExtractor(logger=MagicMock())

    fake_google_response = {
        "items": [
            {
                "actor": {"email": "user@ulpgc.es"},
                "events": [
                    {
                        "parameters": [
                            {"name": "CONTENT_NAME", "value": "syllabus.pdf"}
                        ]
                    },
                    {
                        "parameters": [
                            {
                                "name": "CONTENT_NAME",
                                "value": "sketchy_script.bat",
                            }
                        ]
                    },
                ],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_google_response)
    extractor.activities_collection.list_next = MagicMock(return_value=None)

    events_dict = extractor.check_file_downloads()

    assert "user@ulpgc.es" in events_dict
    download_events = events_dict["user@ulpgc.es"]["download_events"]

    assert len(download_events) == 1
    assert download_events[0] == "sketchy_script.bat"


@patch("src.google_module.admin.build")
def test_check_reuse_password_finds_events(mock_build):
    extractor = AdminReportsExtractor(logger=MagicMock())

    fake_google_response = {
        "items": [
            {
                "actor": {"email": "user@ulpgc.es"},
                "events": [
                    {
                        "parameters": [
                            {"name": "OTHER_PARAM", "value": "ignore_me"},
                            {
                                "name": "URL",
                                "value": "http://reused-pwd-site.com",
                            },
                        ]
                    },
                ],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_google_response)
    extractor.activities_collection.list_next = MagicMock(return_value=None)

    events_dict = extractor.check_reuse_password()

    assert "user@ulpgc.es" in events_dict
    download_events = events_dict["user@ulpgc.es"]["reused_pwd_events"]

    assert len(download_events) == 1
    assert download_events[0] == "http://reused-pwd-site.com"


@patch("src.google_module.admin.build")
def test_check_malware_download_finds_events(mock_build):
    extractor = AdminReportsExtractor(logger=MagicMock())

    fake_google_response = {
        "items": [
            {
                "actor": {"email": "user@ulpgc.es"},
                "events": [
                    {
                        "parameters": [
                            {"name": "OTHER_PARAM", "value": "ignore_me"},
                            {
                                "name": "URL",
                                "value": "http://malware-download-site.com",
                            },
                        ]
                    },
                ],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_google_response)
    extractor.activities_collection.list_next = MagicMock(return_value=None)

    events_dict = extractor.check_malware_download()

    assert "user@ulpgc.es" in events_dict
    download_events = events_dict["user@ulpgc.es"]["malware_events"]

    assert len(download_events) == 1
    assert download_events[0] == "http://malware-download-site.com"


@patch("src.google_module.admin.build")
def test_check_vulnerable_password_finds_events(mock_build):
    extractor = AdminReportsExtractor(logger=MagicMock())

    fake_google_response = {
        "items": [
            {
                "actor": {"email": "user@ulpgc.es"},
                "events": [
                    {
                        "parameters": [
                            {"name": "OTHER_PARAM", "value": "ignore_me"},
                            {
                                "name": "URL",
                                "value": "http://vulnerable-pwd-site.com",
                            },
                        ]
                    },
                ],
            }
        ]
    }

    extractor.exec_request = MagicMock(return_value=fake_google_response)
    extractor.activities_collection.list_next = MagicMock(return_value=None)

    events_dict = extractor.check_vulnerable_password()

    assert "user@ulpgc.es" in events_dict
    download_events = events_dict["user@ulpgc.es"]["vulnerable_pwd_events"]

    assert len(download_events) == 1
    assert download_events[0] == "http://vulnerable-pwd-site.com"
