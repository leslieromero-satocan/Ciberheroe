
from typing import TypedDict
from enum import Enum

# Phishing Campaigns

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

# User Info

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
    electedEnrollments: list[Enrollment]

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

# PasswordIQ

class DetectionType(TypedDict):
    name: str

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
    AD_PW_WEAK:int
    AD_USER_AES_ENCRYPTION_NOT_SET: int
    AD_USER_DES_ONLY_ENCRYPTION: int
    AD_USER_HAS_PREAUTHENTICATION: int
    AD_USER_USES_LM_HASH: int
    ALL: int

class PasswordIQDetectionCounts(TypedDict):
    counts: PasswordIQDetectionCount

class PasswordIQDetectionResponse(TypedDict):
    passwordIqDetectionCounts: PasswordIQDetectionCounts

# Assessment results

class AssessmentDomain(TypedDict):
    name: str
    score: int

class AssessmentResults(TypedDict):
    domains: list[AssessmentDomain]
    score: int

class AssessmentResultsResponse(TypedDict):
    assessmentResults: AssessmentResults

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

class Achievements(Enum):
    LESS_RISK = 'LESS_RISK'
    SAME_RISK = 'SAME_RISK'
    ONE_MONTHLY_ENROLLMENT = 'ONE_MONTHLY_ENROLLMENT'
    ALL_MONTHLY_ENROLLMENTS = 'ALL_MONTHLY_ENROLLMENTS'
    AVG_SCORE_80 = 'AVG_SCORE_80'
    AVG_SCORE_100 = 'AVG_SCORE_100'
    NO_PHISHING_MONTH = 'NO_PHISHING_MONTH'
    TOP_10_TEMPLATES = 'TOP_10_TEMPLATES'
    MONTHLY_PHISH_REPORTS = 'MONTHLY_PHISH_REPORTS'
    NO_PHISHING_YEAR = 'NO_PHISHING_YEAR'
    ALL_PHISH_REPORTS = 'ALL_PHISH_REPORTS'
    ALL_YEARLY_ENROLLMENTS = 'ALL_YEARLY_ENROLLMENTS'
    OPTIONAL_ENROLLMENTS = "OPTIONAL_ENROLLMENTS"

class UserScores(TypedDict):
    acc_score: float
    achievements: list[Achievements]

# Risk Score Histories

class RiskScoreHistoryNode(TypedDict):
    riskScore: float
    user: SimpleUser

class RiskScoreHistories(TypedDict):
    nodes: list[RiskScoreHistoryNode]

class RiskScoreHistoryResponse(TypedDict):
    riskScoreHistories: RiskScoreHistories

# DB

class DBMetrics(TypedDict):
    id: str
    date_registered: str
    phish_prone: float
    phish_reports: float
    monthly_educated: float
    monthly_reporting: float
    aw_educated: float
    aw_reporting: float
    yearly_educated: float
    yearly_reporting: float
    top_educated: list[int]
    low_risk: list[int]
    enrollments: float

class DBUser(TypedDict):
    id: int
    created: str
    updated_at: str
    status: str
    first_name: str
    last_name: str
    email: str
    job_title: str
    role: str
    current_risk: float
    enrollments: int
    optional_enrollments: int
    phish_reports: float
    phish_reports_abs: int
    phish_clicks: float
    phish_clicks_abs: int
    phish_opened: int

class DBUserScore(TypedDict):
    id: str
    updated_at: str
    score: float
    achievements: list[str]
    user_id: int

class DBUserScoreHistory(TypedDict):
    id: str
    updated_at: str
    score: float
    acc_score: int
    achievements: list[str]
    risk_score: float
    user_id: int

class DBTemplate(TypedDict):
    id: int
    template_name: str
    clicked_count_perc: float
    position: int
    topics: list[str]

class DBMonthlyRisk(TypedDict):
    id: str
    user_id: int
    risk_score: float
    created_at: str

class DBVulnerableUsers(TypedDict):
    id: str
    phishing_clicks: int
    last_click: str
    completed_enrollments: int | None
    user_id: int

class DBPasswords(TypedDict):
    id: str
    created_at: str
    pw_all: int
    pw_clear_text: int
    pw_empty: int
    pw_found_in_breach: int
    pw_never_expires: int
    pw_not_reqd: int
    pw_shared: int
    pw_weak: int
    pw_aes_not_set: int
    pw_des_only: int
    pw_preauth: int
    pw_lm_hash: int

class DBPasswordDetections(TypedDict):
    id: str
    user_id: int
    emails: list[str]
    detection_type: str
    ocurred_at: str
    status: str

class DBAssessmentResults(TypedDict):
    id: str
    actitudes: int
    conducta: int
    cognicion: int
    comunicacion: int
    cumplimiento: int
    normas: int
    responsabilidad: int
    security_score: int
    updated_at: str
