from typing import TypedDict, Literal
from custom_types import GoogleUserMetrics


class DBUserGoogleMetrics(GoogleUserMetrics):
    user_email: str
    month: str


class DBGoogleUser(TypedDict):
    created: str
    email: str


class DBGoogleUserScores(TypedDict):
    month: str
    user_email: str
    score: float


GoogleMetricsLabel = Literal[
    "unsafe_sites",
    "reused_pwds",
    "device_platform",
    "risky_downloads",
    "malware_downloads",
    "vulnerable_pwds",
    "enabled_2sv",
    "non_corp_devices",
    "files_public_link",
    "files_exp_date",
    "messages_conf",
]


class DBGooglePointSystem(TypedDict):
    label: GoogleMetricsLabel
    points: int
