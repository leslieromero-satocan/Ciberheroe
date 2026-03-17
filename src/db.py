import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, cast
from dateutil.relativedelta import relativedelta

from dotenv import load_dotenv
from supabase import Client, create_client
import pytz

from scores import filter_by_date
from custom_types import (
    PasswordIQDetectionCount,
    User,
    UserScores,
    TemplateMetrics,
    DBUser,
    DBUserScore,
    DBUserScoreHistory,
    DBTemplate,
    DBMetrics,
    DBMonthlyRisk,
    DBVulnerableUsers,
    VulnerableMetrics,
    DBPasswords,
    DBPasswordDetections,
    DBAssessmentResults,
)

# ===================== VARIABLES GLOBALES =====================

load_dotenv()

REPORT_API_URL = "https://eu.api.knowbe4.com/v1"
REPORT_API_TOKEN = os.environ.get("REPORT_API_TOKEN")
REPORT_API_HEADERS = {
    "Authorization": f"Bearer {REPORT_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}
GRAPH_API_URL = "https://eu.knowbe4.com/graphql"
GRAPH_API_PASS = os.environ.get("PASS_API_TOKEN")
GRAPH_API_KSAT = os.environ.get("KSAT_API_TOKEN")
PASSWORDIQ_HEADERS = {
    "Authorization": f"Bearer {GRAPH_API_PASS}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}
KSAT_HEADERS = {
    "Authorization": f"Bearer {GRAPH_API_KSAT}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}

SUPABASE_URL = os.environ.get("SUPABASE_PROJECT_URL", "SUPABASE_PROJECT_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_KEY")

# ========================== LOGGING ==========================

logger = logging.getLogger(f"kb4_integration.{__name__}")

# ======================= BASE DE DATOS =======================


def initialize_supabase_client() -> Client:
    if SUPABASE_URL == "SUPABASE_PROJECT_URL" or SUPABASE_KEY == "SUPABASE_SERVICE_KEY":
        logger.error(
            "Las credenciales de Supabase no se han establecido correctamente."
        )
        exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def read_db_data(
    client: Client,
    table_name: str,
    select: str,
    date_column: str | None = None,
    date: str | None = None,
) -> list[dict[str, Any]]:
    """Lee datos de la base de datos"""
    try:
        query = client.table(table_name).select(select)
        if date_column and date:
            query.eq(date_column, date)

        response = query.execute()
        return cast(list[dict[str, Any]], response.data)
    except Exception as e:
        logger.error(
            f"Ha ocurrido un error al intentar leer los datos en la BD (tabla: kb4_user_scores): {e}"
        )
        raise e


def insert_db_data(client: Client, table_name: str, data: Any, conflict: str = "id"):
    """Inserta datos en la base de datos"""
    try:
        response = (
            client.table(table_name)
            .upsert(cast(list[dict], data), on_conflict=conflict)
            .execute()
        )
        return response
    except Exception as e:
        logger.error(
            f"Ha ocurrido un error al intentar insertar los datos en la BD (tabla: {table_name}): {e}"
        )
        raise e


def clean_db_templates(client: Client):
    try:
        delete_response = (
            client.table("kb4_best_templates").delete().gt("position", 0).execute()
        )
        return delete_response
    except Exception as e:
        logger.error(
            f"Ha ocurrido un error al intentar elimintar las plantillas (tabla: kb4_best_templates): {e}"
        )
        raise e


def clean_db_vulnerable_users(client: Client):
    try:
        delete_response = (
            client.table("kb4_vulnerable_users").delete().gt("user_id", 0).execute()
        )
        return delete_response
    except Exception as e:
        logger.error(
            f"Ha ocurrido un error al intentar eliminar los usuarios (tabla: kb4_vulnerable_users): {e}"
        )


current_time = datetime.now(pytz.utc).replace(
    day=1, hour=0, minute=0, second=0, microsecond=0
)
current_month = current_time.strftime("%Y-%m-%d")
update_timestamp = datetime.now(pytz.utc).isoformat()

def read_last_semester_scores(client: Client, date_column: str, table_name: str):
    "Lee datos de la base de datos filtrados por los últimos 6 meses"
    try:
        six_months_start = current_time - relativedelta(months=6)
        response = client.rpc(
            "sum_scores_by_user",
            {
                "start_date": six_months_start.isoformat(),
                "end_date": current_time.isoformat(),
            },
        ).execute()
        return cast(list[dict[str, Any]], response.data)
    except Exception as e:
        logger.error(
            f"Ha ocurrido un error al intentar leer los datos en la BD (tabla: kb4_user_scores): {e}"
        )
        raise e


def fill_db_user_info(
    client: Client,
    active_window: int,
    users: list[User],
    sorted_enrollments: dict[int, int],
    report_percentages: dict[int, float],
    clicks_percentages: dict[int, float],
    raw_metrics: dict[int, tuple[int, int, int]],
    scores: dict[int, UserScores],
    score_history: dict[int, dict[str, Any]],
):
    # Tabla users
    db_users: list[DBUser] = list()
    # Tabla user_scores
    db_scores: list[DBUserScore] = list()
    # Tabla user_score_history
    db_score_history: list[DBUserScoreHistory] = list()
    # Tabla monthly_risk_score
    db_monthly_risk: list[DBMonthlyRisk] = list()

    
    for user in users:
        completed_optional_enrollments = filter_by_date(
            user["electedEnrollments"],
            "completedAt",
            active_window,
            datetime.now(pytz.utc),
        )
        db_users.append(
            {
                "id": user["id"],
                "created": user["createdAt"],
                "updated_at": update_timestamp,
                "status": "active",
                "first_name": user["firstName"],
                "last_name": user["lastName"],
                "email": user["email"],
                "job_title": user["jobTitle"],
                "role": user["role"],
                "current_risk": user["riskScore"],
                "enrollments": sorted_enrollments[user["id"]],
                "optional_enrollments": len(completed_optional_enrollments),
                # Si son nuevas incorporaciones, no habrán abierto ningún correo de phishing
                "phish_reports": report_percentages.get(user["id"], -1),
                "phish_reports_abs": raw_metrics.get(user["id"], (-1, -1, -1))[1],
                "phish_clicks": clicks_percentages.get(user["id"], -1),
                "phish_clicks_abs": raw_metrics.get(user["id"], (-1, -1, -1))[0],
                "phish_opened": raw_metrics.get(user["id"], (-1, -1, -1))[2],
            }
        )
        user_achievements = [a.value for a in scores[user["id"]]["achievements"]]
        db_scores.append(
            {
                "id": str(uuid.uuid4()),
                "updated_at": current_month,
                "score": scores[user["id"]]["acc_score"],
                "achievements": user_achievements,
                "user_id": user["id"],
            }
        )
        user_achievements_history = [
            a.value for a in score_history[user["id"]]["achievements"]
        ]
        db_score_history.append(
            {
                "id": str(uuid.uuid4()),
                "updated_at": current_month,
                "score": score_history[user["id"]]["score"],
                "acc_score": score_history[user["id"]]["acc_score"],
                "achievements": user_achievements_history,
                "risk_score": score_history[user["id"]]["risk_score"],
                "user_id": user["id"],
            }
        )
        db_monthly_risk.append(
            {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "risk_score": user["riskScore"],
                "created_at": current_month,
            }
        )
    insert_db_data(client, "kb4_users", db_users)
    logger.info("Insertados los usuarios a la tabla kb4_users correctamente")
    # Actualizamos el status de los usuarios que no se han actualizado (no están en Knowbe4)
    try:
        data, count = (
            client.table("kb4_users")
            .update({"status": "archived"})
            .lt("updated_at", update_timestamp)
            .eq("status", "active")
            .execute()
        )
        n_archived = count[1] if count[1] is not None else 0
        logger.info(f"Archivados {n_archived} usuarios.")
    except Exception as e:
        logger.error(f"Ha ocurrido un error al intentar archivar los usuarios: {e}")

    insert_db_data(client, "kb4_user_scores", db_scores, "user_id")
    logger.info(
        "Insertadas las puntuaciones de los usuarios a la tabla kb4_user_scores correctamente"
    )
    insert_db_data(
        client, "kb4_user_score_history", db_score_history, "user_id, updated_at"
    )
    logger.info(
        "Insertado el historial de puntuaciones de los usuarios de este mes en la tabla kb4_score_history correctamente"
    )
    insert_db_data(client, "kb4_monthly_risk", db_monthly_risk, "user_id, created_at")
    logger.info(
        "Insertadas las puntuaciones de riesgo de este mes a la tabla kb4_monthly_risk correctamente"
    )


def fill_db_basic_metrics(
    client: Client,
    best_templates: dict[int, TemplateMetrics],
    phish_prone: float,
    phish_reports: float,
    monthly_educated: float,
    monthly_reporting: float,
    aw_educated: float,
    aw_reporting: float,
    yearly_educated: float,
    yearly_reporting: float,
    top_educated: dict[int, int],
    low_risk: dict[int, float],
    enrollments: float,
):
    # Tabla best_templates
    db_templates: list[DBTemplate] = list()
    for index, (template_id, template) in enumerate(best_templates.items()):
        template_topics = [i["name"] for i in template["topics"]]
        db_templates.append(
            {
                "id": template_id,
                "template_name": template["name"],
                "clicked_count_perc": template["clicked_count_perc"],
                "position": index + 1,
                "topics": template_topics,
            }
        )
    clean_db_templates(client)
    logger.info("Se ha limpiado la tabla de plantillas correctamente")
    insert_db_data(client, "kb4_best_templates", db_templates)
    logger.info(
        "Insertadas las mejores plantillas a la tabla kb4_best_templates correctamente"
    )

    # Tabla metrics
    db_metrics: DBMetrics = {
        "id": str(uuid.uuid4()),
        "date_registered": current_month,
        "phish_prone": phish_prone,
        "phish_reports": phish_reports,
        "monthly_educated": monthly_educated,
        "monthly_reporting": monthly_reporting,
        "aw_educated": aw_educated,
        "aw_reporting": aw_reporting,
        "yearly_educated": yearly_educated,
        "yearly_reporting": yearly_reporting,
        "top_educated": list(top_educated.keys()),
        "low_risk": list(low_risk.keys()),
        "enrollments": enrollments,
    }

    insert_db_data(client, "kb4_metrics", db_metrics, "date_registered")
    logger.info(
        "Insertadas las metricas generales de este mes en la tabla kb4_metrics correctamente"
    )


def fill_db_vulnerable_data(
    client: Client,
    vulnerable_users: dict[int, VulnerableMetrics],
    pwd_detections: PasswordIQDetectionCount,
    pwd_detections_per_user: list[dict[str, Any]],
    assessment_results: dict[str, int],
):
    # Tabla kb4_vulnerable_users
    db_vulnerable_users: list[DBVulnerableUsers] = list()
    for v_user_id, v_metrics in vulnerable_users.items():
        db_vulnerable_users.append(
            {
                "id": str(uuid.uuid4()),
                "phishing_clicks": v_metrics["phishing_clicks"],
                "last_click": v_metrics["last_click"],
                "completed_enrollments": v_metrics["completed_enrollments"],
                "user_id": v_user_id,
            }
        )
    clean_db_vulnerable_users(client)
    logger.info("Se han limpiado los usuarios vulnerables correctamente")
    insert_db_data(client, "kb4_vulnerable_users", db_vulnerable_users, "user_id")
    logger.info("Insertados los usuarios vulnerables")

    # Tabla kb4_pwd
    db_pwd_metrics: DBPasswords = {
        "id": str(uuid.uuid4()),
        "created_at": current_month,
        "pw_all": pwd_detections["ALL"],
        "pw_clear_text": pwd_detections["AD_PW_CLEAR_TEXT"],
        "pw_empty": pwd_detections["AD_PW_EMPTY"],
        "pw_found_in_breach": pwd_detections["AD_PW_FOUND_IN_BREACH"],
        "pw_never_expires": pwd_detections["AD_PW_NEVER_EXPIRES"],
        "pw_not_reqd": pwd_detections["AD_PW_NOT_REQD"],
        "pw_shared": pwd_detections["AD_PW_SHARED"],
        "pw_weak": pwd_detections["AD_PW_WEAK"],
        "pw_aes_not_set": pwd_detections["AD_USER_AES_ENCRYPTION_NOT_SET"],
        "pw_des_only": pwd_detections["AD_USER_DES_ONLY_ENCRYPTION"],
        "pw_preauth": pwd_detections["AD_USER_HAS_PREAUTHENTICATION"],
        "pw_lm_hash": pwd_detections["AD_USER_USES_LM_HASH"],
    }
    insert_db_data(client, "kb4_pwd", db_pwd_metrics, "created_at")
    logger.info("Insertadas las métricas de contraseñas vulnerables")

    # Tabla kb4_pwd_detections
    db_pwd_user_metrics: list[DBPasswordDetections] = list()
    for detection in pwd_detections_per_user:
        db_pwd_user_metrics.append(
            {
                "id": str(uuid.uuid4()),
                "user_id": detection["user_id"],
                "emails": detection["emails"],
                "detection_type": detection["detection_type"],
                "ocurred_at": detection["ocurred_at"],
                "status": detection["status"],
            }
        )

    insert_db_data(
        client,
        "kb4_pwd_detections",
        db_pwd_user_metrics,
        "user_id, detection_type, ocurred_at",
    )
    logger.info("Insertadas las detecciones de contraseñas vulnerables por usuario")

    # Tabla kb4_assessment_results
    db_assessment_results: DBAssessmentResults = {
        "id": str(uuid.uuid4()),
        "actitudes": assessment_results["ATTITUDES"],
        "conducta": assessment_results["BEHAVIOR"],
        "cognicion": assessment_results["COGNITION"],
        "comunicacion": assessment_results["COMMUNICATION"],
        "cumplimiento": assessment_results["COMPLIANCE"],
        "normas": assessment_results["NORMS"],
        "responsabilidad": assessment_results["RESPONSIBILITY"],
        "security_score": assessment_results["security_score"],
        "updated_at": update_timestamp,
    }
    insert_db_data(
        client, "kb4_assessment_results", db_assessment_results, "updated_at"
    )


def save_score_history(
    client: Client, users: list[User], score_history: dict[int, dict[str, Any]]
):
    db_score_history: list[DBUserScoreHistory] = list()
    last_month = (current_time - relativedelta(months=1)).strftime("%Y-%m-%d")
    for user in users:
        user_achievements_history = [
            a.value for a in score_history[user["id"]]["achievements"]
        ]
        db_score_history.append(
            {
                "id": str(uuid.uuid4()),
                "updated_at": last_month,
                "score": score_history[user["id"]]["score"],
                "acc_score": score_history[user["id"]]["acc_score"],
                "achievements": user_achievements_history,
                "risk_score": score_history[user["id"]]["risk_score"],
                "user_id": user["id"],
            }
        )
    insert_db_data(
        client, "kb4_user_score_history", db_score_history, "user_id, updated_at"
    )
