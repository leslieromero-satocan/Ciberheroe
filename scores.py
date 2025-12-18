import logging
from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import cast, Any

from dateutil.parser import isoparse
import pytz

from custom_types import (
    Enrollment,
    CampaignRecipient,
    User,
    UserScores,
    TemplateMetrics,
    Achievements,
    PhishingCampaignRun,
    YearlyEnrollment
)

# ========================== LOGGING ==========================

logger = logging.getLogger(f"kb4_integration.{__name__}")

# ==================== FUNCIONES PARA LAS PUNTUACIONES ====================

filterByDateInput = (list[Enrollment] | list[CampaignRecipient] | list[PhishingCampaignRun] | list[YearlyEnrollment])

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
        by_active_window: la fecha desde la que se quieren calcular los meses anteriores de la ventana activa
        by_month: tupla con el número del mes y el año para filtrar por mes
    
    Return:
        La lista de elementos pasada por parámetro filtrada por fecha

    """
    if by_active_window.tzinfo is None or by_active_window.tzinfo.utcoffset(by_active_window) is None:
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

def calculate_scores(
    users: list[User],
    completed_yearly_enrollments: list[YearlyEnrollment],
    recipients: list[CampaignRecipient],
    best_templates: dict[int, TemplateMetrics],
    score_list: dict[int, int],
    achievement_info: dict[str, int],
    last_risk: list[dict[str, Any]],
    active_window: int
) -> tuple[dict[int, UserScores], dict[int, dict[str, Any]]]:
    """Calcula la puntuación acumulada de cada usuario acorde a unos objetivos establecidos"""
    user_scores: defaultdict[int, UserScores] = defaultdict(
        lambda: {"acc_score": 0, "achievements": []}
    )

    risk_score_history = {item["user_id"]: item["risk_score"] for item in last_risk}

    month_min = achievement_info["MIN_MONTHLY_OPENED"]
    year_min = achievement_info["MIN_ACTIVE_WINDOW"]

    save_history = {user["id"]: {"score": 0, "acc_score": 0, "achievements": [], "risk_score": 0} for user in users}

    for user in users:
        user_id = user["id"]
        user_scores[user_id]["acc_score"] = 0

        user_recipients = [i for i in recipients if i["user"]["id"] == user_id]
        user_templates = {
            i["emailTemplate"]["id"]: i["clickedCount"]
            for i in user_recipients
            if i["opened"] is not None
        }
        mandatory_enrollments = user["mandatoryEnrollments"]
        completed_enrollments = [e for e in completed_yearly_enrollments if e["user"]["id"] == user_id]

        current_date = datetime.now(pytz.utc)

        # Ha disminuido o se mantiene la puntuación de riesgo
        if risk_score_history != dict():
            # Si no encuentra historial, que en ningún caso se pueda dar puntos
            last_score = risk_score_history.get(user_id, -1)
            new_score = user["riskScore"]
            if new_score < last_score:
                user_scores[user_id]["acc_score"] += achievement_info[
                    Achievements.LESS_RISK.value
                ]
                user_scores[user_id]["achievements"].append(Achievements.LESS_RISK)
            elif new_score <= last_score + 0.2:
                user_scores[user_id]["acc_score"] += achievement_info[
                    Achievements.SAME_RISK.value
                ]
                user_scores[user_id]["achievements"].append(Achievements.SAME_RISK)

        # Puntuación media (>=80% o =100%)
        eval_enrollments = [
            e["totalScore"] for e in completed_enrollments if e["totalScore"] is not None
        ]
        avg_score = (
            sum(eval_enrollments) / len(eval_enrollments)
            if eval_enrollments != list()
            else 0
        )
        if avg_score >= 0.8 and avg_score < 1:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.AVG_SCORE_80.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.AVG_SCORE_80)
        elif avg_score == 1:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.AVG_SCORE_100.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.AVG_SCORE_100)


        # No ha caido en ningún phishing simulado en el mes
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
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.NO_PHISHING_MONTH.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.NO_PHISHING_MONTH)

        # No ha caído en ninguna de las 10 plantillas simuladas de Top Clics mensual
        skipped_template = 0
        received_templates = 0
        for template_id in best_templates.keys():
            if template_id in user_templates:
                received_templates += 1
                if user_templates[template_id] is None:
                    skipped_template += 1
        if skipped_template == received_templates and received_templates >= 1:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.TOP_10_TEMPLATES.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.TOP_10_TEMPLATES)

        # Ha denunciado suficientes phishings en el mes de manera que ha denunciado al
        # menos el 80% (en el año, de momento en total)
        month_reported = filter_by_date(
            user_recipients,
            "reported",
            active_window,
            current_date,
            (current_date.month, current_date.year),
        )
        if len(month_reported) >= month_min:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.MONTHLY_PHISH_REPORTS.value
            ]
            user_scores[user_id]["achievements"].append(
                Achievements.MONTHLY_PHISH_REPORTS
            )

        # No ha caído en ningún phishing simulado (clic) en todo el año
        year_clicks = filter_by_date(user_recipients, "clicked", active_window, current_date)
        year_opened = filter_by_date(user_recipients, "opened", active_window, current_date)
        if len(year_clicks) == 0 and len(year_opened) >= year_min:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.NO_PHISHING_YEAR.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.NO_PHISHING_YEAR)

        # Ha denunciado el 100% de los phishings
        year_reported = filter_by_date(user_recipients, "reported", active_window, current_date)
        if len(year_reported) == len(year_opened) and len(year_reported) >= year_min:
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.ALL_PHISH_REPORTS.value
            ]
            user_scores[user_id]["achievements"].append(Achievements.ALL_PHISH_REPORTS)

        # Ha completado todas las formaciones asignadas a lo largo del año
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
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.ALL_YEARLY_ENROLLMENTS.value
            ]
            user_scores[user_id]["achievements"].append(
                Achievements.ALL_YEARLY_ENROLLMENTS
            )

        # Ha realizado algún Optional Enrollment
        if user["electedEnrollments"] is not None:
            completed_elected_enrollments = filter_by_date(user["electedEnrollments"], "completedAt", active_window, current_date)
            user_scores[user_id]["acc_score"] += achievement_info[
                Achievements.OPTIONAL_ENROLLMENTS.value
            ] * len(completed_elected_enrollments)
            user_scores[user_id]["achievements"].append(
                Achievements.OPTIONAL_ENROLLMENTS
            )
        
        score = user_scores[user_id]["acc_score"]
        new_score = score + (100 - user["riskScore"])

        save_history[user_id]["score"] = new_score
        save_history[user_id]["achievements"] = user_scores[user_id]["achievements"]
        save_history[user_id]["risk_score"] = user["riskScore"]

        user_scores[user_id]["acc_score"] = round(score_list.get(user_id, 0) + new_score)
        save_history[user_id]["acc_score"] = round(score_list.get(user_id, 0) + new_score)

    sorted_scores = sorted(
        user_scores.items(), key=lambda item: item[1]["acc_score"], reverse=True
    )
    logger.info(
        "Se han calculado las puntuaciones de cada usuario acorde a los criterios establecidos"
    )
    return dict(sorted_scores), save_history


def get_historical_data(users: list[User]):
    """Obtiene los datos de puntuaciones de diciembre de 2024 (cuando aún no se han guardado las puntuaciones mensuales)"""
    historical_risk: list[dict[str, int | float]] = list()
    nov2025 = pytz.utc.localize(datetime(2025, 11, 1))
    historical_users = [user for user in users if isoparse(user["createdAt"]) < nov2025]
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
