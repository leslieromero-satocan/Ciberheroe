from typing import TypedDict, Literal

# PasswordIQ (GraphQL)

DetectionTypeName = Literal[
    "AD_PW_CLEAR_TEXT",
    "AD_PW_EMPTY",
    "AD_PW_FOUND_IN_BREACH",
    "AD_PW_NEVER_EXPIRES",
    "AD_PW_NOT_REQD",
    "AD_PW_SHARED",
    "AD_PW_WEAK",
    "AD_USER_AES_ENCRYPTION_NOT_SET",
    "AD_USER_DES_ONLY_ENCRYPTION",
    "AD_USER_HAS_PREAUTHENTICATION",
    "AD_USER_USES_LM_HASH",
    "ALL",
]


class DetectionType(TypedDict):
    name: DetectionTypeName


class Event(TypedDict):
    detectionType: DetectionType
    occurredAt: str
    status: str


class Email(TypedDict):
    address: str


class PasswordIQUser(TypedDict):
    id: int
    emails: list[Email]
    events: list[Event]


class PasswordIQUserNode(TypedDict):
    users: list[PasswordIQUser]


class PasswordIQUserResponse(TypedDict):
    passwordIqUserStates: PasswordIQUserNode


class PasswordIQDetectionCount(TypedDict):
    AD_PW_CLEAR_TEXT: int
    AD_PW_EMPTY: int
    AD_PW_FOUND_IN_BREACH: int
    AD_PW_NEVER_EXPIRES: int
    AD_PW_NOT_REQD: int
    AD_PW_SHARED: int
    AD_PW_WEAK: int
    AD_USER_AES_ENCRYPTION_NOT_SET: int
    AD_USER_DES_ONLY_ENCRYPTION: int
    AD_USER_HAS_PREAUTHENTICATION: int
    AD_USER_USES_LM_HASH: int
    ALL: int


class PasswordIQDetectionCounts(TypedDict):
    counts: PasswordIQDetectionCount


class PasswordIQDetectionResponse(TypedDict):
    passwordIqDetectionCounts: PasswordIQDetectionCounts
