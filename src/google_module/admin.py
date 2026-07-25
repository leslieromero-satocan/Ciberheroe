from google_module.base import GoogleAPIBase
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import env_config as config
from datetime import datetime, timezone, timedelta
import os
from collections import defaultdict

SCOPES = [
    "https://www.googleapis.com/auth/admin.reports.audit.readonly",
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.device.mobile.readonly",
    "https://www.googleapis.com/auth/cloud-identity.devices.readonly",
]

admin_creds = service_account.Credentials.from_service_account_file(
    config.SERVICE_ACCOUNT_FILE, scopes=SCOPES, subject=config.SUBJECT_EMAIL
)


class AdminDirectoryExtractor(GoogleAPIBase):
    def __init__(self, logger):
        self.service = build(
            "admin",
            "directory_v1",
            credentials=admin_creds,
            cache_discovery=False,
        )
        super().__init__(logger, self.service)
        self.users_collection = self.service.users()
        self.mobiledevices_collecion = self.service.mobiledevices()

    def extract_user_list(self):
        # Extracts both the user list and the 2SV
        request = self.users_collection.list(
            customer="my_customer",
            fields="nextPageToken, users(primaryEmail, isEnrolledIn2Sv)",
            maxResults=500,
        )

        users = []
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            users += response.get("users", [])
            request = self.users_collection.list_next(request, response)

        return users

    def check_device_platform(self):
        request = self.mobiledevices_collecion.list(
            customerId="my_customer",
            maxResults=100,
            projection="BASIC",
            fields="nextPageToken,mobiledevices(model, os, type, status, firstSync, lastSync)",
        )
        devices = defaultdict(lambda: {"devices": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            for device in response.get("mobiledevices", []):
                owner = device.get("email", ["no_email_found"])[0]
                devices[owner]["devices"].append(device)
            request = self.mobiledevices_collecion.list_next(request, response)
        self.logger.info(
            "Se han extraído las plataformas de dispositivo de los usuarios"
        )
        return devices


class CloudIdentityExtractor(GoogleAPIBase):
    def __init__(self, logger, days_start=1):
        self.service = build(
            "cloudidentity",
            "v1",
            credentials=admin_creds,
            cache_discovery=False,
        )
        super().__init__(logger, self.service)
        self.devices_collection = self.service.devices()
        self.deviceUsers_collection = self.service.devices().deviceUsers()
        start_time = datetime.now(timezone.utc) - timedelta(days=days_start)
        self.start_time_string = start_time.strftime("%Y-%m-%dT%H:%M:%S")

    def check_corporate_devices(self):
        request_devices = self.devices_collection.list(
            customer="customers/my_customer",
            filter=f"sync:{self.start_time_string}..",
            pageSize=100,
        )
        physical_devices = defaultdict(
            lambda: {"ownerType": "", "devicePlatform": ""}
        )
        while request_devices is not None:
            response = self.exec_request(request_devices)
            if response is None:
                break
            for device in response.get("devices", []):
                device_id = device.get("name", "NA")
                physical_devices[device_id]["ownerType"] = device.get(
                    "ownerType", "NA"
                )
                physical_devices[device_id]["devicePlatform"] = device.get(
                    "deviceType", "Unknown"
                )
            request_devices = self.devices_collection.list_next(
                request_devices, response
            )
        self.logger.info(
            "Dispositivos corporativos: obtenidos los dispositivos fisicos"
        )
        request_deviceUsers = self.deviceUsers_collection.list(
            parent="devices/-",
            customer="customers/my_customer",
            filter=f"sync:{self.start_time_string}..",
            pageSize=20,
        )
        devices = defaultdict(lambda: {"devices": []})
        while request_deviceUsers is not None:
            response = self.exec_request(request_deviceUsers)
            if response is None:
                break
            for user in response.get("deviceUsers", []):
                user_email = user.get("userEmail", "email_not_found")
                full_device_name = user.get("name", "")
                device_id = full_device_name.split("/deviceUsers/")[0]
                ownership = physical_devices[device_id]["ownerType"]
                platform = physical_devices[device_id]["devicePlatform"]
                devices[user_email]["devices"].append(
                    {
                        "device_id": device_id,
                        "ownership": ownership,
                        "platform": platform,
                    }
                )
            request_deviceUsers = self.deviceUsers_collection.list_next(
                request_deviceUsers, response
            )
        self.logger.info(
            "Dispositivos corporativos: obtenidos los dispositivos junto con los usuarios"
        )
        return devices


class AdminReportsExtractor(GoogleAPIBase):
    def __init__(self, logger, days_start: float = 1):
        self.service = build(
            "admin",
            "reports_v1",
            credentials=admin_creds,
            cache_discovery=False,
        )
        super().__init__(logger, self.service)
        self.activities_collection = self.service.activities()
        start_time = datetime.now(timezone.utc) - timedelta(days=days_start)
        self.start_time_string = start_time.isoformat().replace("+00:00", "Z")

    def check_ignore_certificate_warning(self):
        """Revisa si se han visitado páginas no seguras en los últimos días"""
        request = self.activities_collection.list(
            userKey="all",
            applicationName="chrome",
            eventName="UNSAFE_SITE_VISIT",
            startTime=self.start_time_string,
            fields="nextPageToken,items(actor, events(parameters))",
        )
        events = defaultdict(lambda: {"unsafe_site_events": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            items = response.get("items", [])
            for item in items:
                actor = item["actor"].get("email", "missing-email")
                for event in item.get("events", []):
                    unsafe_site_event = next(
                        (
                            s.get("value")
                            for s in event.get("parameters")
                            if s.get("name") == "URL"
                        ),
                        "No valid URL",
                    )
                    events[actor]["unsafe_site_events"].append(
                        unsafe_site_event
                    )
            request = self.activities_collection.list_next(request, response)

        return events

    def check_reuse_password(self):
        """Revisa si el usuario tiene contraseñas reutilizadas"""
        request = self.activities_collection.list(
            userKey="all",
            applicationName="chrome",
            eventName="PASSWORD_REUSE",
            startTime=self.start_time_string,
            fields="nextPageToken,items(actor, events(parameters))",
        )
        events = defaultdict(lambda: {"reused_pwd_events": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            items = response.get("items", [])
            for item in items:
                actor = item["actor"].get("email", "missing-email")
                for event in item.get("events", []):
                    unsafe_site_event = next(
                        (
                            s.get("value")
                            for s in event.get("parameters")
                            if s.get("name") == "URL"
                        ),
                        "No valid URL",
                    )
                    events[actor]["reused_pwd_events"].append(
                        unsafe_site_event
                    )
            request = self.activities_collection.list_next(request, response)

        return events

    def check_file_downloads(
        self,
        dangerous_file_types={
            ".exe",
            ".bat",
            ".cmd",
            ".ps1",
            ".vbs",
            ".scr",
            ".msi",
            ".jar",
        },
    ):
        request = self.activities_collection.list(
            userKey="all",
            applicationName="chrome",
            eventName="CONTENT_TRANSFER",
            startTime=self.start_time_string,
            fields="nextPageToken,items(actor, events(parameters))",
        )
        events = defaultdict(lambda: {"download_events": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            items = response.get("items", [])
            for item in items:
                actor = item["actor"].get("email", "missing-email")
                for event in item.get("events", []):
                    download_event = next(
                        (
                            d.get("value")
                            for d in event.get("parameters")
                            if d.get("name") == "CONTENT_NAME"
                            and os.path.splitext(d.get("value"))[1]
                            in dangerous_file_types
                        ),
                        "No events",
                    )
                    if download_event == "No events":
                        continue
                    events[actor]["download_events"].append(download_event)
            request = self.activities_collection.list_next(request, response)

        return events

    def check_malware_download(self):
        request = self.activities_collection.list(
            userKey="all",
            applicationName="chrome",
            eventName="MALWARE_TRANSFER",
            startTime=self.start_time_string,
            fields="nextPageToken,items(actor, events(parameters))",
        )
        events = defaultdict(lambda: {"malware_events": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            items = response.get("items", [])
            for item in items:
                actor = item["actor"].get("email", "missing-email")
                for event in item.get("events", []):
                    malware_event = next(
                        (
                            d.get("value")
                            for d in event.get("parameters")
                            if d.get("name") == "URL"
                        ),
                        "No events",
                    )
                    if malware_event == "No events":
                        continue
                    events[actor]["malware_events"].append(malware_event)
            request = self.activities_collection.list_next(request, response)
        return events

    def check_vulnerable_password(self):
        """Revisa si el usuario tiene alguna contraseña vulnerada"""
        request = self.activities_collection.list(
            userKey="all",
            applicationName="chrome",
            eventName="PASSWORD_BREACH",
            startTime=self.start_time_string,
            fields="nextPageToken,items(actor, events(parameters))",
        )
        events = defaultdict(lambda: {"vulnerable_pwd_events": []})
        while request is not None:
            response = self.exec_request(request)
            if response is None:
                break
            items = response.get("items", [])
            for item in items:
                actor = item["actor"].get("email", "missing-email")
                for event in item.get("events", []):
                    vulnerable_pwd_event = next(
                        (
                            d.get("value")
                            for d in event.get("parameters")
                            if d.get("name") == "URL"
                        ),
                        "No events",
                    )
                    if vulnerable_pwd_event == "No events":
                        continue
                    events[actor]["vulnerable_pwd_events"].append(
                        vulnerable_pwd_event
                    )
            request = self.activities_collection.list_next(request, response)

        return events
