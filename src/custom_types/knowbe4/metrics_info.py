from typing import TypedDict
from enum import StrEnum
from datetime import datetime

# User Info (GraphQL)


class RiskScoreRecord(TypedDict):
    createdAt: str
    riskScore: float


class TrainingCampaign(TypedDict):
    id: int
    name: str


class Enrollment(TypedDict):
    id: int
    completedAt: str
    createdAt: str
    status: str
    totalScore: float
    type: str
    trainingCampaign: TrainingCampaign


class User(TypedDict):
    id: int
    email: str
    firstName: str
    lastName: str
    createdAt: str
    jobTitle: str
    role: str
    riskScore: float
    riskScoreHistories: list[RiskScoreRecord]
    mandatoryEnrollments: list[Enrollment]
    optionalEnrollments: list[Enrollment]


class UserNodes(TypedDict):
    nodes: list[User]


class UserResponse(TypedDict):
    users: UserNodes


class YearlyEnrollmentUser(TypedDict):
    id: int


class YearlyEnrollment(TypedDict):
    id: int
    completedAt: str
    createdAt: str
    status: str
    totalScore: float
    type: str
    trainingCampaign: TrainingCampaign
    user: YearlyEnrollmentUser


class Pagination(TypedDict):
    totalCount: int


class EnrollmentNodes(TypedDict):
    nodes: list[YearlyEnrollment]
    pagination: Pagination


class EnrollmentResponse(TypedDict):
    enrollments: EnrollmentNodes


# Phishing Campaigns (GraphQL)


class SimpleUser(TypedDict):
    id: int
    email: int


class Topic(TypedDict):
    name: str


class EmailTemplate(TypedDict):
    id: int
    name: str
    rating: str
    isAida: bool
    topics: list[Topic]


class FailureDetails(TypedDict):
    date: str
    type: str


class CampaignRecipient(TypedDict):
    createdAt: str
    clicked: str
    clickedCount: int
    opened: str
    # failureDetails: list[FailureDetails]
    emailTemplate: EmailTemplate
    reported: str
    user: SimpleUser


class PhishingCampaignRun(TypedDict):
    id: int
    createdAt: str
    phishPronePercentage: float
    totalOpened: int
    totalReported: int
    campaignRecipients: list[CampaignRecipient]


class PhishingNodes(TypedDict):
    nodes: list[PhishingCampaignRun]


class PhishingCampaignResponse(TypedDict):
    phishingCampaignRuns: PhishingNodes


# Metrics


class TemplateMetrics(TypedDict):
    name: str
    clicked_count: int
    topics: list[Topic]
    clicked_count_perc: float


class ClickMetrics(TypedDict):
    clicks: int
    reports: int
    opened: int


class VulnerableMetrics(TypedDict):
    phishing_clicks: int
    last_click: str
    completed_enrollments: int | None


class Achievements(StrEnum):
    LESS_RISK = "LESS_RISK"
    SAME_RISK = "SAME_RISK"
    ONE_MONTHLY_ENROLLMENT = "ONE_MONTHLY_ENROLLMENT"
    ALL_MONTHLY_ENROLLMENTS = "ALL_MONTHLY_ENROLLMENTS"
    AVG_SCORE_80 = "AVG_SCORE_80"
    AVG_SCORE_100 = "AVG_SCORE_100"
    NO_PHISHING_MONTH = "NO_PHISHING_MONTH"
    TOP_10_TEMPLATES = "TOP_10_TEMPLATES"
    MONTHLY_PHISH_REPORTS = "MONTHLY_PHISH_REPORTS"
    NO_PHISHING_YEAR = "NO_PHISHING_YEAR"
    ALL_PHISH_REPORTS = "ALL_PHISH_REPORTS"
    ALL_YEARLY_ENROLLMENTS = "ALL_YEARLY_ENROLLMENTS"
    OPTIONAL_ENROLLMENTS = "OPTIONAL_ENROLLMENTS"


class UserScores(TypedDict):
    acc_score: float
    achievements: list[Achievements]


class ContextData(TypedDict):
    active_window: int
    risk_score_history: dict[int, float]
    month_min: int
    year_min: int
    current_date: datetime
    achievement_info: dict[str, int]
    best_templates: dict[int, TemplateMetrics]


class UserData(TypedDict):
    user: User
    user_recipients: list[CampaignRecipient]
    user_templates: dict[int, int]
    mandatory_enrollments: list[Enrollment]
    completed_enrollments: list[YearlyEnrollment]
    year_clicks: list[CampaignRecipient]
    year_opened: list[CampaignRecipient]


# Risk Score Histories


class RiskScoreHistoryNode(TypedDict):
    riskScore: float
    user: SimpleUser


class RiskScoreHistories(TypedDict):
    nodes: list[RiskScoreHistoryNode]


class RiskScoreHistoryResponse(TypedDict):
    riskScoreHistories: RiskScoreHistories
