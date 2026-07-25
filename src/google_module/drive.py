from google_module.base import GoogleAPIBase
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import env_config as config
from logging import Logger
from datetime import datetime, timezone, timedelta

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

base_creds = service_account.Credentials.from_service_account_file(
    config.SERVICE_ACCOUNT_FILE, scopes=SCOPES
)


class GoogleDriveExtractor(GoogleAPIBase):
    def __init__(self, logger: Logger, user_email: str, days_start: float = 1):

        user_credentials = base_creds.with_subject(user_email)

        self.service = build(
            "drive", "v3", credentials=user_credentials, cache_discovery=False
        )
        super().__init__(logger, self.service)
        self.files_collection = self.service.files()
        start_time = datetime.now(timezone.utc) - timedelta(days=days_start)
        self.start_time_string = start_time.isoformat().replace("+00:00", "Z")

    def extract_files_with_full_access(self):
        """Extrae los archivos cuya visibilidad sea para todas las personas con el link"""
        query = f"visibility='anyoneWithLink' and modifiedTime >= '{self.start_time_string}'"
        request = self.files_collection.list(
            q=query,
            spaces="drive",
            pageSize=10,
            fields="nextPageToken,files(id, name, mimeType)",
        )

        files = []
        page_count = 0
        max_pages = 2

        while request is not None and page_count < max_pages:
            response = self.exec_request(request)
            if response is None:
                break
            page_count += 1
            files += response.get("files", [])
            request = self.files_collection.list_next(request, response)
        return files

    def extract_files_with_expiration_date(self):
        """Extrae los archivos que se hayan compartido durante un tiempo limitado"""
        request = self.files_collection.list(
            spaces="drive",
            pageSize=10,
            fields="nextPageToken,files(id, name, permissions(expirationTime))",
        )

        files = []
        page_count = 0
        max_pages = 2
        while request is not None and page_count < max_pages:
            response = self.exec_request(request)
            if response is None:
                break
            page_count += 1
            files += response.get("files", [])
            request = self.files_collection.list_next(request, response)
        return files
