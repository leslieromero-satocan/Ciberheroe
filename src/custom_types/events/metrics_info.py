from typing import TypedDict


class EventMetrics(TypedDict):
    login_success: int
    biometric_auth: int
    lock_screen: int
    restart: int
    updates: int
    usb_devices: int
    login_failed: int
