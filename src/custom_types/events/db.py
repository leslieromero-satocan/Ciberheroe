from typing import TypedDict, Literal
from custom_types import EventMetrics


class DBEventsUser(TypedDict):
    updated_at: str
    device: str
    user: str
    user_email: str


class DBEventMetrics(EventMetrics):
    month: str
    user_email: str


class DBEventUserScores(TypedDict):
    month: str
    score: float
    user_email: str
