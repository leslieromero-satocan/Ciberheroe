import logging
import uuid
from dateutil.relativedelta import relativedelta

from knowbe4_module.kb4_db import Knowbe4DBClient

import config.env_config as config
from knowbe4_module import (
    admin_metrics,
    basic_metrics,
    fetch_graph_api_data,
    fetch_rest_api_data,
    calculate_scores,
    get_historical_data,
    save_json,
)
from custom_types import (
    PasswordIQUser,
    User,
    CampaignRecipient,
    PhishingCampaignRun,
    DBMonthlyRisk,
    YearlyEnrollment,
    PasswordIQUserResponse,
    PhishingCampaignResponse,
    UserResponse,
    EnrollmentResponse,
    AssessmentResultsResponse,
    VulnerableMetrics,
    TemplateMetrics,
    PasswordIQDetectionCount,
)

from dataclasses import dataclass, field
from typing import Any, cast, List, Set, Dict

logger = logging.getLogger(f"ciberheroe.{__name__}")


def fill_in_with_historical_data(users, knowbe4_db: Knowbe4DBClient):
    """Obtenemos datos históricos para suplir el historial si no existen datos del mes anterior

    Se activa con la variable HISTORICAL_DATA en el archivo .env
    """
    historical_data = get_historical_data(users)
    db_monthly_risk_hist: list[DBMonthlyRisk] = list()
    for record in historical_data:
        db_monthly_risk_hist.append(
            {
                "id": str(uuid.uuid4()),
                "user_id": int(record["user_id"]),
                "risk_score": float(record["risk_score"]),
                "created_at": "2024-12-01",
            }
        )
    save_json({"data": db_monthly_risk_hist}, "historical_data")
    knowbe4_db.insert_db_data(
        "kb4_monthly_risk",
        db_monthly_risk_hist,
        "user_id, created_at",
    )
    logger.info("Insertamos los historicos para diciembre de 2024")


@dataclass
class Knowbe4Context:
    achievement_info: Dict[Any, Any] = field(default_factory=dict)
    active_window: int = 0

    n_users: int = 0
    n_psts: int = 0

    raw_psts: PhishingCampaignResponse | None = None
    raw_user_info: UserResponse | None = None
    raw_pwd_user_events: PasswordIQUserResponse | None = None
    raw_yearly_enrollments: EnrollmentResponse | None = None
    raw_assessment_results: AssessmentResultsResponse | None = None

    users: List[User] = field(default_factory=list)
    active_users: Set[int] = field(default_factory=set)
    recipients: List[CampaignRecipient] = field(default_factory=list)
    psts: List[PhishingCampaignRun] = field(default_factory=list)
    user_pwds: List[PasswordIQUser] = field(default_factory=list)
    yearly_completed_enrollments: List[YearlyEnrollment] = field(
        default_factory=list
    )


@dataclass
class Knowbe4Metrics:
    phish_prone_percentage: float = 0
    phishing: float = 0
    top_educated: Dict[int, int] = field(default_factory=dict)
    sorted_enrollments: Dict[int, int] = field(default_factory=dict)
    clicks_percentages: Dict[int, float] = field(default_factory=dict)
    report_percentages: Dict[int, float] = field(default_factory=dict)
    raw_metrics: Dict[int, tuple[int, int, int]] = field(default_factory=dict)
    best_templates: Dict[int, TemplateMetrics] = field(default_factory=dict)
    monthly_clicks: int = 0
    low_risk: Dict[int, float] = field(default_factory=dict)

    top10_month_templates: Dict[int, TemplateMetrics] = field(
        default_factory=dict
    )
    user_reports: tuple[float, float, float] = (0, 0, 0)
    user_education: tuple[float, float, float] = (0, 0, 0)
    enrollments: float = 0
    vulnerable_users: Dict[int, VulnerableMetrics] = field(
        default_factory=dict
    )
    pwds_detections_per_user: List[dict[str, Any]] = field(
        default_factory=list
    )
    pwds: PasswordIQDetectionCount | None = None
    assessment_results: Dict[str, int] = field(default_factory=dict)


class Knowbe4APIProcessor:

    def extract_raw_data(self, context: Knowbe4Context):
        (
            context.raw_psts,
            context.raw_user_info,
            context.raw_pwd_user_events,
            context.raw_yearly_enrollments,
            context.raw_assessment_results,
        ) = fetch_graph_api_data(context.n_users, context.n_psts)

    def process_raw_data(self, context: Knowbe4Context):
        raw_user_info = cast(UserResponse, context.raw_user_info)
        raw_psts = cast(PhishingCampaignResponse, context.raw_psts)
        raw_pwd_user_events = cast(
            PasswordIQUserResponse, context.raw_pwd_user_events
        )
        raw_yearly_enrollments = cast(
            EnrollmentResponse, context.raw_yearly_enrollments
        )

        context.users = raw_user_info["users"]["nodes"]
        context.active_users = {user["id"] for user in context.users}
        for pst in raw_psts["phishingCampaignRuns"]["nodes"]:
            context.psts.append(pst)
            context.recipients += [
                recipient
                for recipient in pst["campaignRecipients"]
                if recipient["user"]["id"] in context.active_users
            ]
        context.user_pwds = raw_pwd_user_events["passwordIqUserStates"][
            "users"
        ]
        context.yearly_completed_enrollments = raw_yearly_enrollments[
            "enrollments"
        ]["nodes"]

        save_json({"users": context.users}, "kb4_users")


class Knowbe4MetricsCalculator:
    def calculate_general_metrics(
        self, context: Knowbe4Context, metrics: Knowbe4Metrics
    ):
        metrics.phish_prone_percentage = basic_metrics.phish_prone_percentage(
            context.psts
        )
        metrics.phishing = basic_metrics.phishing_reports(context.psts)
        metrics.top_educated, metrics.sorted_enrollments = (
            basic_metrics.most_educated(
                context.users, context.yearly_completed_enrollments, 5
            )
        )
        (
            metrics.clicks_percentages,
            metrics.report_percentages,
            metrics.raw_metrics,
        ) = basic_metrics.click_percentage(
            context.recipients, context.users, context.active_window
        )
        metrics.best_templates, metrics.monthly_clicks = (
            basic_metrics.best_phishing_templates(
                context.recipients, 10, context.active_window
            )
        )
        metrics.low_risk = basic_metrics.lowest_risk_users(10, context.users)

    def calculate_additional_metrics(
        self,
        context: Knowbe4Context,
        metrics: Knowbe4Metrics,
        this_month,
        last_month,
    ):

        metrics.top10_month_templates, m = (
            basic_metrics.best_phishing_templates(
                context.recipients,
                10,
                context.active_window,
                (this_month, (last_month.month, last_month.year)),
            )
        )
        metrics.user_reports = basic_metrics.get_reporting_users(
            context.recipients,
            context.active_users,
            context.n_users,
            context.active_window,
        )
        metrics.user_education = basic_metrics.get_educated_users(
            context.yearly_completed_enrollments,
            context.active_window,
            context.n_users,
        )
        metrics.enrollments = basic_metrics.get_year_enrollments(context.users)

        # Vulnerabilidades
        metrics.vulnerable_users = admin_metrics.get_vulnerable_users(
            context.users,
            context.yearly_completed_enrollments,
            metrics.raw_metrics,
            context.recipients,
        )

        metrics.pwds_detections_per_user, metrics.pwds = (
            admin_metrics.get_vulnerable_pwd(context.user_pwds, context.users)
        )

        raw_assessment_results = cast(
            AssessmentResultsResponse, context.raw_assessment_results
        )
        metrics.assessment_results = admin_metrics.get_assessment_results(
            raw_assessment_results
        )


def knowbe4_etl(db_client):

    knowbe4_db = Knowbe4DBClient(db_client, logger)

    context = Knowbe4Context()

    context.achievement_info, context.active_window = (
        knowbe4_db.get_achievement_info()
    )
    context.n_users, context.n_psts = fetch_rest_api_data()

    processor = Knowbe4APIProcessor()
    processor.extract_raw_data(context)
    processor.process_raw_data(context)

    metrics = Knowbe4Metrics()
    metrics_calculator = Knowbe4MetricsCalculator()
    metrics_calculator.calculate_general_metrics(context, metrics)

    # Inserción de datos históricos a falta de datos del último mes
    if config.HISTORICAL_DATA:
        fill_in_with_historical_data(context.users, knowbe4_db)

    # Obtenemos el riesgo del mes anterior
    db_last_risk = knowbe4_db.get_last_month_risk()

    # Leemos las puntuaciones de los últimos meses
    # para sumar a las de este mes
    db_score_data = knowbe4_db.get_last_months_scores(context)

    # Métricas adicionales
    last_month = knowbe4_db.first_day_month - relativedelta(months=1)
    metrics_calculator.calculate_additional_metrics(
        context, metrics, knowbe4_db.first_day_month, last_month
    )

    # Cálculo de puntuaciones
    user_scores, user_score_history = calculate_scores(
        context.users,
        context.yearly_completed_enrollments,
        context.recipients,
        metrics.top10_month_templates,
        db_score_data,
        context.achievement_info,
        db_last_risk,
        context.active_window,
    )

    # Rellenamos la base de datos
    knowbe4_db.fill_db_user_info(
        context, metrics, user_scores, user_score_history
    )
    knowbe4_db.fill_db_basic_metrics(metrics)
    knowbe4_db.fill_db_vulnerable_users(metrics.vulnerable_users)
    knowbe4_db.fill_db_passwords(cast(PasswordIQDetectionCount, metrics.pwds))
    knowbe4_db.fill_db_passwords_detections(metrics.pwds_detections_per_user)
    knowbe4_db.fill_db_assessment_results(metrics.assessment_results)
