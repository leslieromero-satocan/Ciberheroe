import logging
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import cast, Any

from dateutil.parser import isoparse
import pytz

from custom_types.knowbe4.metrics_info import (
    Enrollment,
    CampaignRecipient,
    User,
    UserScores,
    TemplateMetrics,
    Achievements,
    PhishingCampaignRun,
    YearlyEnrollment,
    ContextData,
    UserData,
)

# ========================== LOGGING ==========================

logger = logging.getLogger(f"ciberheroe.{__name__}")

# ==================== FUNCIONES PARA LAS PUNTUACIONES ====================

filterByDateInput = (
    list[Enrollment]
    | list[CampaignRecipient]
    | list[PhishingCampaignRun]
    | list[YearlyEnrollment]
)


def filter_by_date(
    items: filterByDateInput,
    property_name: str,
    active_window: int,
    by_active_window: datetime,
    by_month: tuple[int, int] | None = None,
):
    """Filtra las formaciones asignadas por fecha

    Parameters:
        items: la lista de elementos que queramos filtrar por fecha
        property_name: la propiedad de tipo fecha formateada en ISO8601
        by_active_window: la fecha desde la que se quieren calcular los meses
        anteriores de la ventana activa
        by_month: tupla con el número del mes y el año para filtrar por mes

    Return:
        La lista de elementos pasada por parámetro filtrada por fecha

    """
    if (
        by_active_window.tzinfo is None
        or by_active_window.tzinfo.utcoffset(by_active_window) is None
    ):
        end_date = by_active_window.replace(tzinfo=pytz.utc)
    else:
        end_date = by_active_window.astimezone(pytz.utc)

    def check_match(e):
        if e[property_name] is not None:
            date = isoparse(e[property_name])
        else:
            return False
        if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
            date = date.replace(tzinfo=pytz.utc)
        if by_month is not None:
            return date.month == by_month[0] and date.year == by_month[1]
        else:
            start_date = end_date - relativedelta(months=active_window)
            return start_date <= date <= end_date

    return list(filter(check_match, items))


def str_to_enum(achievement_list: list[str]) -> list[Achievements]:
    new_achievements: list[Achievements] = list()
    for achievement in achievement_list:
        new_achievements.append(Achievements[achievement])
    return new_achievements


def check_risk_score(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba la puntuación de riesgo"""
    risk_score_history = context["risk_score_history"]
    user = user_data["user"]
    achievement_info = context["achievement_info"]

    if risk_score_history != dict():
        # Si no encuentra historial, que en ningún caso se pueda dar puntos
        last_score = risk_score_history.get(user["id"], -1)
        new_score = user["riskScore"]
        if new_score < last_score:
            return (
                achievement_info[Achievements.LESS_RISK],
                Achievements.LESS_RISK,
            )
        elif new_score <= last_score + 0.2:
            return (
                achievement_info[Achievements.SAME_RISK],
                Achievements.SAME_RISK,
            )
    return 0, None


def check_avg_enrollments_score(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba la puntuación media de formaciones"""
    completed_enrollments = user_data["completed_enrollments"]
    achievement_info = context["achievement_info"]

    eval_enrollments = [
        e["totalScore"]
        for e in completed_enrollments
        if e["totalScore"] is not None
    ]
    avg_score = (
        sum(eval_enrollments) / len(eval_enrollments)
        if eval_enrollments != list()
        else 0
    )
    if avg_score >= 0.8 and avg_score < 1:
        return (
            achievement_info[Achievements.AVG_SCORE_80],
            Achievements.AVG_SCORE_80,
        )
    elif avg_score == 1:
        return (
            achievement_info[Achievements.AVG_SCORE_100],
            Achievements.AVG_SCORE_100,
        )
    return 0, None


def check_monthly_phishings(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha caído en algún phishing en el mes"""
    user_recipients = user_data["user_recipients"]
    active_window = context["active_window"]
    current_date = context["current_date"]
    month_min = context["month_min"]
    achievement_info = context["achievement_info"]

    month_clicks = filter_by_date(
        user_recipients,
        "clicked",
        active_window,
        current_date,
        (current_date.month, current_date.year),
    )
    month_opened = filter_by_date(
        user_recipients,
        "opened",
        active_window,
        current_date,
        (current_date.month, current_date.year),
    )
    if len(month_clicks) == 0 and len(month_opened) >= month_min:
        return (
            achievement_info[Achievements.NO_PHISHING_MONTH],
            Achievements.NO_PHISHING_MONTH,
        )
    return 0, None


def check_top10_templates(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha caído en las plantillas top del mes"""
    best_templates = context["best_templates"]
    user_templates = user_data["user_templates"]
    achievement_info = context["achievement_info"]

    skipped_template = 0
    received_templates = 0
    for template_id in best_templates.keys():
        if template_id in user_templates:
            received_templates += 1
            if user_templates[template_id] is None:
                skipped_template += 1
    if skipped_template == received_templates and received_templates >= 1:
        return (
            achievement_info[Achievements.TOP_10_TEMPLATES],
            Achievements.TOP_10_TEMPLATES,
        )
    return 0, None


def check_monthly_phishing_reports(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba las denuncias de phishing del mes"""
    user_recipients = user_data["user_recipients"]
    active_window = context["active_window"]
    current_date = context["current_date"]
    month_min = context["month_min"]
    achievement_info = context["achievement_info"]

    month_reported = filter_by_date(
        user_recipients,
        "reported",
        active_window,
        current_date,
        (current_date.month, current_date.year),
    )
    if len(month_reported) >= month_min:
        return (
            achievement_info[Achievements.MONTHLY_PHISH_REPORTS],
            Achievements.MONTHLY_PHISH_REPORTS,
        )
    return 0, None


def check_no_phishing_in_year(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha caído en phishings en el año"""
    year_clicks = user_data["year_clicks"]
    year_opened = user_data["year_opened"]
    year_min = context["year_min"]
    achievement_info = context["achievement_info"]

    if len(year_clicks) == 0 and len(year_opened) >= year_min:
        return (
            achievement_info[Achievements.NO_PHISHING_YEAR],
            Achievements.NO_PHISHING_YEAR,
        )
    return 0, None


def check_all_phishing_reports(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha denunciado todos los phishings"""
    user_recipients = user_data["user_recipients"]
    active_window = context["active_window"]
    current_date = context["current_date"]
    year_opened = user_data["year_opened"]
    year_min = context["year_min"]
    achievement_info = context["achievement_info"]

    year_reported = filter_by_date(
        user_recipients, "reported", active_window, current_date
    )
    if (
        len(year_reported) == len(year_opened)
        and len(year_reported) >= year_min
    ):
        return (
            achievement_info[Achievements.ALL_PHISH_REPORTS],
            Achievements.ALL_PHISH_REPORTS,
        )
    return 0, None


def check_yearly_enrollments(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha completado todas las formaciones del año"""
    mandatory_enrollments = user_data["mandatory_enrollments"]
    active_window = context["active_window"]
    current_date = context["current_date"]
    achievement_info = context["achievement_info"]

    yearly_enrollments = filter_by_date(
        mandatory_enrollments, "createdAt", active_window, current_date
    )
    yearly_enrollments = cast(list[Enrollment], yearly_enrollments)
    count_enrollments = sum(
        1 for e in yearly_enrollments if e["status"] == "COMPLETED"
    )
    if (
        count_enrollments == len(yearly_enrollments)
        and len(yearly_enrollments) != 0
    ):
        return (
            achievement_info[Achievements.ALL_YEARLY_ENROLLMENTS],
            Achievements.ALL_YEARLY_ENROLLMENTS,
        )
    return 0, None


def check_optional_enrollments(
    user_data: UserData, context: ContextData
) -> tuple[int, Achievements | None]:
    """Comprueba si ha realizado alguna formación opcional"""
    user = user_data["user"]
    active_window = context["active_window"]
    current_date = context["current_date"]
    achievement_info = context["achievement_info"]

    if user["optionalEnrollments"] != []:
        completed_optional_enrollments = filter_by_date(
            user["optionalEnrollments"],
            "completedAt",
            active_window,
            current_date,
        )
        return (
            achievement_info[Achievements.OPTIONAL_ENROLLMENTS]
            * len(completed_optional_enrollments),
            Achievements.OPTIONAL_ENROLLMENTS,
        )
    return 0, None


SCORING_RULES = [
    check_risk_score,
    check_avg_enrollments_score,
    check_monthly_phishings,
    check_top10_templates,
    check_monthly_phishing_reports,
    check_no_phishing_in_year,
    check_all_phishing_reports,
    check_yearly_enrollments,
    check_optional_enrollments,
]


def calculate_total_user_score(
    user_data: UserData, context: ContextData
) -> tuple[list[Achievements] | list, int]:
    """Calcula la puntuación total a partir de las reglas establecidas"""
    achievements = []
    total_score = 0
    for rule in SCORING_RULES:
        score, achievement = rule(user_data, context)
        if achievement:
            achievements.append(achievement)
        total_score += score
    return achievements, total_score


def calculate_scores(
    users: list[User],
    completed_yearly_enrollments: list[YearlyEnrollment],
    recipients: list[CampaignRecipient],
    best_templates: dict[int, TemplateMetrics],
    score_list: dict[int, int],
    achievement_info: dict[str, int],
    last_risk: list[dict[str, Any]],
    active_window: int,
) -> tuple[dict[int, UserScores], dict[int, dict[str, Any]]]:
    """Calcula la puntuación acumulada de cada usuario"""
    user_scores: defaultdict[int, UserScores] = defaultdict(
        lambda: {"acc_score": 0, "achievements": []}
    )

    risk_score_history = {
        item["user_id"]: item["risk_score"] for item in last_risk
    }

    month_min = achievement_info["MIN_MONTHLY_OPENED"]
    year_min = achievement_info["MIN_ACTIVE_WINDOW"]

    current_date = datetime.now(pytz.utc)

    context: ContextData = {
        "active_window": active_window,
        "risk_score_history": risk_score_history,
        "month_min": month_min,
        "year_min": year_min,
        "current_date": current_date,
        "achievement_info": achievement_info,
        "best_templates": best_templates,
    }

    save_history = {
        user["id"]: {
            "score": 0,
            "acc_score": 0,
            "achievements": [],
            "risk_score": 0,
        }
        for user in users
    }

    for user in users:
        user_id = user["id"]
        user_scores[user_id]["acc_score"] = 0

        user_recipients: list[CampaignRecipient] = [
            i for i in recipients if i["user"]["id"] == user_id
        ]
        user_templates = {
            i["emailTemplate"]["id"]: i["clickedCount"]
            for i in user_recipients
            if i["opened"] is not None
        }
        completed_enrollments = [
            e
            for e in completed_yearly_enrollments
            if e["user"]["id"] == user_id
        ]

        year_clicks = filter_by_date(
            user_recipients, "clicked", active_window, current_date
        )
        year_opened = filter_by_date(
            user_recipients, "opened", active_window, current_date
        )

        user_data: UserData = {
            "user": user,
            "user_recipients": user_recipients,
            "user_templates": user_templates,
            "mandatory_enrollments": user["mandatoryEnrollments"],
            "completed_enrollments": completed_enrollments,
            "year_clicks": cast(list[CampaignRecipient], year_clicks),
            "year_opened": cast(list[CampaignRecipient], year_opened),
        }

        achievements, total_score = calculate_total_user_score(
            user_data, context
        )
        user_scores[user_id]["achievements"] = achievements

        risk_bonus = 100 - user["riskScore"]
        final_score = total_score + risk_bonus

        save_history[user_id]["score"] = final_score
        save_history[user_id]["achievements"] = user_scores[user_id][
            "achievements"
        ]
        save_history[user_id]["risk_score"] = user["riskScore"]

        user_scores[user_id]["acc_score"] = round(
            score_list.get(user_id, 0) + final_score
        )
        save_history[user_id]["acc_score"] = round(
            score_list.get(user_id, 0) + final_score
        )

    sorted_scores = sorted(
        user_scores.items(),
        key=lambda item: item[1]["acc_score"],
        reverse=True,
    )
    logger.info("""Se han calculado las puntuaciones de cada usuario
         acorde a los criterios establecidos""")
    return dict(sorted_scores), save_history


def get_historical_data(users: list[User]):
    """Obtiene los datos de puntuaciones de diciembre de 2024 (cuando aún no se han guardado las puntuaciones mensuales)"""
    historical_risk: list[dict[str, int | float]] = list()
    nov2025 = pytz.utc.localize(datetime(2025, 11, 1))
    historical_users = [
        user for user in users if isoparse(user["createdAt"]) < nov2025
    ]
    for user in historical_users:
        risk_history = user["riskScoreHistories"]
        historical_risk.append(
            {
                "user_id": user["id"],
                "risk_score": (
                    risk_history[len(risk_history) - 1]["riskScore"]
                    if risk_history != list()
                    else -1
                ),
            }
        )
    return historical_risk
