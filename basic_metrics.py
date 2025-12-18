import logging
from datetime import datetime
import pytz
from typing import cast
from collections import defaultdict
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta

from scores import filter_by_date
from custom_types import (
    PhishingCampaignRun,
    CampaignRecipient,
    ClickMetrics,
    TemplateMetrics,
    User,
    UserScores,
    Enrollment,
    YearlyEnrollment,
)
from main import save_json

# ========================== LOGGING ==========================

logger = logging.getLogger(f"kb4_integration.{__name__}")

# ==================== FUNCIONES PARA MÉTRICAS INICIALES ====================

CURRENT_DATE = datetime.now(pytz.utc)

filterByDateInput = (
    list[Enrollment]
    | list[CampaignRecipient]
    | list[PhishingCampaignRun]
    | list[YearlyEnrollment]
)


def filter_by_year(items: filterByDateInput, property_name: str, by_year: datetime):
    """Filtra las formaciones asignadas por año (copia de filter_by_date, exclusiva por 12 meses)

    Parameters:
        items: la lista de elementos que queramos filtrar por fecha
        property_name: la propiedad de tipo fecha formateada en ISO8601
        by_year: la fecha desde la que se quieren calcular los 12 meses anteriores

    Return:
        La lista de elementos pasada por parámetro filtrada por los últimos 12 meses

    """
    if by_year.tzinfo is None or by_year.tzinfo.utcoffset(by_year) is None:
        end_date = by_year.replace(tzinfo=pytz.utc)
    else:
        end_date = by_year.astimezone(pytz.utc)

    def check_match(e):
        if e[property_name] is not None:
            date = isoparse(e[property_name])
        else:
            return False
        if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
            date = date.replace(tzinfo=pytz.utc)
        start_date = end_date - relativedelta(months=12)
        return start_date <= date <= end_date

    return list(filter(check_match, items))


def phish_prone_percentage(psts: list[PhishingCampaignRun]) -> float:
    """Obtiene el porcentaje de usuarios phish prone en todas las campañas de phishing"""
    year_psts = filter_by_year(psts, "createdAt", CURRENT_DATE)
    year_psts = cast(list[PhishingCampaignRun], year_psts)
    
    avg_phish_prone = 0

    for test in year_psts:
        avg_phish_prone += test["phishPronePercentage"]
    phish_prone = (avg_phish_prone / len(year_psts)) * 100
    logger.info("Calculado el porcentaje phish-prone")

    return round(phish_prone, 2)


def phishing_reports(psts: list[PhishingCampaignRun]) -> float:
    """Obtiene el porcentaje de denuncias de phishing con respecto a todos los correos leidos"""
    reported = 0
    opened = 0

    year_psts = filter_by_year(psts, "createdAt", CURRENT_DATE)
    year_psts = cast(list[PhishingCampaignRun], year_psts)

    for test in year_psts:
        reported += test["totalReported"]
        opened += test["totalOpened"]

    if opened > 0:
        logger.info("Calculado el porcentaje de emails de phishing denunciados")
        reported_perc = (reported / opened) * 100
        return round(reported_perc, 2)
    else:
        logger.warning(
            "No se han encontrado emails abiertos, el porcentaje no se pudo calcular"
        )
        return 0


def most_educated(
    users: list[User], enrollments: list[YearlyEnrollment], n_users: int
) -> tuple[dict[int, int], dict[int, int]]:
    """Obtiene a los usuarios con mayor cantidad de formaciones realizadas"""
    completed_enrollments = {user["id"]: 0 for user in users}
    for enrollment in enrollments:
        completed_enrollments[enrollment["user"]["id"]] += 1

    sorted_enrollments = sorted(
        completed_enrollments.items(), key=lambda item: item[1], reverse=True
    )
    top_enrollments = dict(sorted_enrollments[:n_users])

    if len(sorted_enrollments) > 0:
        logger.info("Obtenidos los usuarios con mayor numero de formaciones")
        return top_enrollments, dict(sorted_enrollments)
    else:
        logger.warning(
            "La lista de formaciones estaba vacia, no se pudieron obtener a los usuarios mas formados"
        )
        return dict(), dict()


def click_percentage(
    recipients: list[CampaignRecipient], users: list[User], active_window
) -> tuple[dict[int, float], dict[int, float], dict[int, tuple[int, int, int]]]:
    """Otbiene el porcentaje de clicks con respecto a los correos abiertos por usuario"""
    total_recipients: defaultdict[int, ClickMetrics] = defaultdict(
        lambda: {"clicks": 0, "reports": 0, "opened": 0}
    )

    year_opened = cast(
        list[CampaignRecipient],
        filter_by_date(recipients, "opened", active_window, CURRENT_DATE),
    )
    year_clicked = cast(
        list[CampaignRecipient],
        filter_by_date(recipients, "clicked", active_window, CURRENT_DATE),
    )
    year_reported = cast(
        list[CampaignRecipient],
        filter_by_date(recipients, "reported", active_window, CURRENT_DATE),
    )
    active_users = {i["user"]["id"] for i in year_opened}

    for user in users:
        user_id = user["id"]
        if user_id not in active_users:
            continue
        total_recipients[user_id]["opened"] = sum(
            1 for i in year_opened if i["user"]["id"] == user_id
        )
        total_recipients[user_id]["clicks"] = sum(
            1 for i in year_clicked if i["user"]["id"] == user_id
        )
        total_recipients[user_id]["reports"] = sum(
            1 for i in year_reported if i["user"]["id"] == user_id
        )

    if len(total_recipients) > 0:
        clicks_reports_opened = {
            user_id: (values["clicks"], values["reports"], values["opened"])
            for user_id, values in total_recipients.items()
        }
        click_percentage = {
            user_id: (
                round((values["clicks"] / values["opened"]) * 100, 2)
                if values["opened"] != 0
                else -1
            )
            for user_id, values in total_recipients.items()
        }
        sorted_clicks = sorted(click_percentage.items(), key=lambda item: item[1])
        report_percentage = {
            user_id: (
                round((values["reports"] / values["opened"]) * 100, 2)
                if values["opened"] != 0
                else -1
            )
            for user_id, values in total_recipients.items()
        }
        sorted_reports = sorted(report_percentage.items(), key=lambda item: item[1])
        logger.info(
            "Calculado el porcentaje de clicks en links de phishing para cada usuario"
        )
        return dict(sorted_clicks), dict(sorted_reports), clicks_reports_opened
    else:
        logger.warning(
            "El numero de destinatarios es cero, no se pudieron obtener los porcentajes"
        )
        return dict(), dict(), dict()


def best_phishing_templates(
    recipients: list[CampaignRecipient],
    n_templates: int,
    active_window: int,
    filter: tuple[datetime, tuple[int, int] | None] | None = None,
) -> tuple[dict[int, TemplateMetrics], int]:
    """Obtiene las plantillas de phishing con mayor tasa de éxito (general, anual, mensual)"""
    templates: defaultdict[int, TemplateMetrics] = defaultdict(
        lambda: {
            "name": "template_name",
            "clicked_count": 0,
            "topics": list(),
            "clicked_count_perc": 0,
        }
    )
    selected_recipients = recipients
    if filter is not None:
        selected_recipients = filter_by_date(
            recipients, "clicked", active_window, filter[0], filter[1]
        )
        selected_recipients = cast(list[CampaignRecipient], selected_recipients)

    total_clicks = sum(1 for i in selected_recipients if i["clicked"] is not None)

    for r in selected_recipients:
        template = r["emailTemplate"]
        if template["id"] not in templates:
            templates[template["id"]]["name"] = template["name"]
            templates[template["id"]]["topics"] = template["topics"]
        if r["clicked"] is not None:
            templates[template["id"]]["clicked_count"] += r["clickedCount"]

    for template_id in templates.keys():
        template = templates[template_id]
        templates[template_id]["clicked_count_perc"] = (
            template["clicked_count"] / total_clicks
        ) * 100

    sorted_templates = sorted(
        templates.items(), key=lambda item: item[1]["clicked_count"], reverse=True
    )
    monthly_clicks = sum(i["clicked_count"] for i in templates.values())
    best_templates = dict(sorted_templates[:n_templates])
    if len(sorted_templates) > 0:
        logger.info("Se han obtenido las mejores plantillas de phishing")
        return best_templates, monthly_clicks
    else:
        logger.warning("No se pudieron encontrar plantillas")
        return dict(), 0


def lowest_risk_users(n_users: int, users: list[User]) -> dict[int, float]:
    """Obtiene a los usuarios con menor riesgo acorde a su puntuación de riesgo"""
    user_risk_scores = {i["id"]: i["riskScore"] for i in users}

    sorted_grades = sorted(user_risk_scores.items(), key=lambda item: item[1])

    best_users = dict(sorted_grades[:n_users])

    logger.info("Se han obtenido a los usuarios con menor riesgo")
    return best_users


# Métricas generales de usuario (añadidos)
def get_reporting_users(
    recipients: list[CampaignRecipient], active_users: set[int], n_users: int, active_window: int
) -> tuple[float, float, float]:
    """Devuelve el porcentaje de usuarios que han denunciado phishinig"""

    monthly_reports = filter_by_date(
        recipients,
        "reported",
        active_window,
        CURRENT_DATE,
        (CURRENT_DATE.month, CURRENT_DATE.year),
    )
    monthly_reports = cast(list[CampaignRecipient], monthly_reports)

    # AW = Active Window
    aw_reports = filter_by_date(
        recipients,
        "reported",
        active_window,
        CURRENT_DATE
    )

    aw_reports = cast(list[CampaignRecipient], aw_reports)

    yearly_reports = filter_by_year(recipients, "reported", CURRENT_DATE)
    yearly_reports = cast(list[CampaignRecipient], yearly_reports)

    month_reporting_users = {
        i["user"]["id"] for i in monthly_reports if i["user"]["id"] in active_users
    }
    month_perc_reporting_users = (len(month_reporting_users) / n_users) * 100

    aw_reporting_users = {
        i["user"]["id"] for i in aw_reports if i["user"]["id"] in active_users
    }
    aw_perc_reporting_users = (len(aw_reporting_users) / n_users) * 100

    year_reporting_users = {
        i["user"]["id"] for i in yearly_reports if i["user"]["id"] in active_users
    }
    logger.info(
        f"Se han registrado {len(year_reporting_users)} usuarios que han reportado phishing"
    )
    year_perc_reporting_users = (len(year_reporting_users) / n_users) * 100

    return (
        month_perc_reporting_users,
        aw_perc_reporting_users,
        year_perc_reporting_users,
    )


def get_educated_users(
    completed_enrollments: list[YearlyEnrollment],
    active_window: int,
    n_users,
) -> tuple[float, float, float]:
    """Devuelve el procentaje de usuarios que han realizado al menos una formación"""

    monthly_enrollments = filter_by_date(
        completed_enrollments,
        "completedAt",
        active_window,
        CURRENT_DATE,
        (CURRENT_DATE.month, CURRENT_DATE.year),
    )
    monthly_enrollments = cast(list[YearlyEnrollment], monthly_enrollments)
    monthly_educated = {e["user"]["id"] for e in monthly_enrollments}
    
    perc_monthly_educated = (len(monthly_educated) / n_users) * 100

    # AW = Active Window
    aw_enrollments = filter_by_date(
        completed_enrollments,
        "completedAt",
        active_window,
        CURRENT_DATE,
    )
    aw_enrollments = cast(list[YearlyEnrollment], aw_enrollments)
    aw_educated = {e["user"]["id"] for e in aw_enrollments}
    perc_aw_educated = (len(aw_educated) / n_users) * 100

    yearly_educated = {e["user"]["id"] for e in completed_enrollments}
    perc_yearly_educated = (len(yearly_educated) / n_users) * 100

    logger.info(
        f"Se han registrado {len(yearly_educated)} usuarios que han realizado al menos una formación"
    )
    return (
        perc_monthly_educated,
        perc_aw_educated,
        perc_yearly_educated
    )


def get_year_enrollments(users: list[User]) -> float:
    """Obtiene el porcentaje de formaciones completadas de todas las que se han asignado en los últimos 12 meses (campañas activas)"""
    count = 0
    all = 0
    for user in users:
        yearly_mandatory = filter_by_year(
            user["mandatoryEnrollments"], "createdAt", CURRENT_DATE
        )
        all += len(yearly_mandatory)
        yearly_enrollments = filter_by_year(
            user["mandatoryEnrollments"], "completedAt", CURRENT_DATE
        )
        yearly_enrollments = cast(list[Enrollment], yearly_enrollments)
        count += sum(1 for e in yearly_enrollments)

    enrollments_completed = (count / all) * 100
    return enrollments_completed
