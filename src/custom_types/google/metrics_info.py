from typing import TypedDict


class User(TypedDict):
    displayName: str
    kind: str
    me: bool
    permissionId: str
    emailAddress: str
    photoLink: str


class File(TypedDict):
    id: str
    name: str
    mimeType: str


class FileListResponse(TypedDict):
    files: list[File]


class GoogleUserMetrics(TypedDict):
    unsafe_sites: int
    reused_pwds: int
    device_platform: float
    risky_downloads: int
    malware_downloads: int
    vulnerable_pwds: int
    enabled_2sv: bool
    non_corp_devices: int
    files_public_link: int
    files_exp_date: int
    messages_conf: int
