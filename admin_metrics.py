import logging
from collections import defaultdict
from dateutil.parser import isoparse
from datetime import datetime
import pytz
from typing import Any

from custom_types import (
    CampaignRecipient,
    VulnerableMetrics,
    VulnerableMetrics,
    User,
    PasswordIQUser,
    PasswordIQDetectionCount,
    YearlyEnrollment,
    AssessmentResultsResponse,
)

# ========================== LOGGING ==========================

logger = logging.getLogger(f"kb4_integration.{__name__}")

# ==================== FUNCIONES PARA MÉTRICAS DE ADMIN ====================

CURRENT_DATE = datetime.now(pytz.utc)

def get_vulnerable_users(
    users: list[User],
    yearly_completed_enrollments: list[YearlyEnrollment],
    raw_metrics: dict[int, tuple[int, int, int]],
    recipients: list[CampaignRecipient],
) -> dict[int, VulnerableMetrics]:
    """Obtiene a los usuarios que no han realizado ninguna formación y han caído en más de un phishing en los últimos 12 meses"""
    vulnerable_users: defaultdict[int, VulnerableMetrics] = defaultdict(
        lambda: {"phishing_clicks": 0, "last_click": "", "completed_enrollments": None}
    )
    for user in users:
        count_completed = sum(
            1 for e in yearly_completed_enrollments if e["user"]["id"] == user["id"]
        )
        phishing_clicks = raw_metrics.get(user["id"], (0, 0, 0))[
            0
        ]  # (clicks, reports, opened)
        user_recipients = [
            i
            for i in recipients
            if i["user"]["id"] == user["id"] and i["clicked"] is not None
        ]
        last_click = sorted(user_recipients, key=lambda item: isoparse(item["clicked"]))
        if phishing_clicks > 1:
            vulnerable_users[user["id"]]["phishing_clicks"] = phishing_clicks
            vulnerable_users[user["id"]]["last_click"] = last_click[-1]["clicked"]
            if count_completed > 0:
                vulnerable_users[user["id"]]["completed_enrollments"] = count_completed

    logger.info("Se han obtenido los usuarios vulnerables")
    return vulnerable_users


def get_vulnerable_pwd(
    user_pwds: list[PasswordIQUser], users: list[User]
) -> tuple[list[dict[str, Any]], PasswordIQDetectionCount]:
    """Obtiene las detecciones de contraseñas vulnerables y los usuarios correspondientes"""
    detections_per_user = list()
    pwds: PasswordIQDetectionCount = {
        "AD_PW_CLEAR_TEXT": 0,
        "AD_PW_EMPTY": 0,
        "AD_PW_FOUND_IN_BREACH": 0,
        "AD_PW_NEVER_EXPIRES": 0,
        "AD_PW_NOT_REQD": 0,
        "AD_PW_SHARED": 0,
        "AD_PW_WEAK": 0,
        "AD_USER_AES_ENCRYPTION_NOT_SET": 0,
        "AD_USER_DES_ONLY_ENCRYPTION": 0,
        "AD_USER_HAS_PREAUTHENTICATION": 0,
        "AD_USER_USES_LM_HASH": 0,
        "ALL": 0,
    }
    users_emails = {user["email"]: user["id"] for user in users}
    for user in user_pwds:
        emails = [i["address"] for i in user["emails"]]
        check_email = [i for i in emails if i in users_emails.keys()]
        if len(check_email) < 1:
            continue
        for detection in user["events"]:
            detection_type = detection["detectionType"]["name"]
            pwds[detection_type] += 1
            detections_per_user.append(
                {
                    "user_id": users_emails[check_email[0]],
                    "emails": emails,
                    "detection_type": detection_type,
                    "ocurred_at": detection["occurredAt"],
                    "status": detection["status"],
                }
            )
    logger.info("Se han obtenido a los usuarios con contraseñas vulnerables")
    return detections_per_user, pwds

def get_assessment_results(assessments: AssessmentResultsResponse) -> dict[str, int]:
    assessment_domains = assessments["assessmentResults"]["domains"]
    assessment_results = {domain["name"]: int(domain["score"]) for domain in assessment_domains}
    assessment_results["security_score"] = int(assessments["assessmentResults"]["score"])
    return assessment_results