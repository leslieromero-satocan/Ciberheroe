import pytest
from unittest.mock import patch, MagicMock
from src.google_module.gmail import GmailExtractor


# We patch `build` so the constructor doesn't try to connect to Google
@patch("src.google_module.gmail.build")
def test_extract_messages_confidential(mock_build):
    extractor = GmailExtractor(logger=MagicMock(), user_email="test@test.com")
    extractor.exec_request = MagicMock(
        return_value={"messages": [{"id": "msg_123"}, {"id": "msg_456"}]}
    )
    extractor.messages_collection.list_next = MagicMock(return_value=None)

    messages, errors = extractor.extract_messages_sent_in_confidential_mode()

    assert len(messages) == 2
    assert messages[0]["id"] == "msg_123"
    assert errors is False
