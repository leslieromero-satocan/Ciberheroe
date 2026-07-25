from google_module.base import GoogleAPIBase
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import env_config as config
from logging import Logger
from datetime import datetime, timezone, timedelta

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

base_creds = service_account.Credentials.from_service_account_file(
    config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
)


class GmailExtractor(GoogleAPIBase):
    def __init__(self, logger: Logger, user_email: str, days_start: float = 1):
        user_credentials = base_creds.with_subject(user_email)

        self.service = build(
            "gmail", "v1", credentials=user_credentials, cache_discovery=False
        )
        super().__init__(logger, self.service)
        self.messages_collection = self.service.users().messages()
        start_time = datetime.now(timezone.utc) - timedelta(days=days_start)
        self.start_time_epoch = int(start_time.timestamp())

    def extract_messages_sent_in_confidential_mode(self):
        """Extrae los correos enviados en modo confidencial"""
        query = f"from:me AND label:confidentialmode AND after:{self.start_time_epoch}"
        request = self.messages_collection.list(
            userId="me",
            q=query,
            maxResults=10,
            fields="nextPageToken,messages(id)",
        )

        messages = []
        errors = False

        page_count = 0
        max_pages = 2

        while request is not None and page_count < max_pages:
            response = self.exec_request(request)
            if response is None:
                errors = True
                break
            page_count += 1
            messages += response.get("messages", [])
            request = self.messages_collection.list_next(request, response)
        return messages, errors
