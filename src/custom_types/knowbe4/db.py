from typing import TypedDict

# DB (Supabase DB tables)


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
