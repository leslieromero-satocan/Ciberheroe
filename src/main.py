import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import traceback
import uuid
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, MutableMapping, cast
from dateutil.relativedelta import relativedelta
from supabase import Client

import requests
from dotenv import load_dotenv
import pytz

import csv
import basic_metrics
import admin_metrics
import exceptions
import scores
import db
from custom_types import (
    PhishingCampaignResponse,
    UserResponse,
    PasswordIQUserResponse,
    PasswordIQUser,
    PasswordIQDetectionResponse,
    User,
    CampaignRecipient,
    PhishingCampaignRun,
    DBMonthlyRisk,
    EnrollmentResponse,
    YearlyEnrollment,
    AssessmentResultsResponse,
    RiskScoreHistoryResponse,
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

HISTORICAL_DATA = False

# ========================== LOGGING ==========================

logger = logging.getLogger("kb4_integration")
logger.setLevel(logging.INFO)

MAX_BYTES = 285 * 1024
BACKUP_COUNT = 2

if not logger.handlers:
    file_handler = RotatingFileHandler(
        "./logs/knowbe4_integration.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s: line %(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# ==================== OBTENCIÓN DE DATOS ====================

GraphAPIResponse = (
    PhishingCampaignResponse
    | UserResponse
    | PasswordIQUserResponse
    | PasswordIQDetectionResponse
    | AssessmentResultsResponse
)


def request_rest_api(endpoint: str, params: str = "") -> list:
    """Realiza la solicitud a la REST API de Knowbe4"""
    try:
        response = requests.get(
            url=f"{REPORT_API_URL}{endpoint}{params}", headers=REPORT_API_HEADERS
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as errh:
        logger.error(f"HTTP Error: {errh.args[0]}")
        return list()


def request_graphql_api(query: str, is_ksat: bool = True) -> GraphAPIResponse:
    """Realiza la solicitud a la Graph API de Knowbe4"""
    try:
        headers = KSAT_HEADERS if is_ksat else PASSWORDIQ_HEADERS
        response = requests.post(GRAPH_API_URL, json={"query": query}, headers=headers)
        response.raise_for_status()
        result = response.json()
        if "data" in result:
            return result["data"]
        else:
            logger.error(
                f"Hubo un error con la query, no se pudo obtener la informacion {response.content}"
            )
            raise exceptions.QueryError(f"Data not found, incorrect query: {query}")
    except requests.exceptions.HTTPError as errh:
        logger.error(f"HTTP Error: {errh.args[0]}")
        raise exceptions.APIRequestError(f"HTTP Error: {errh.args[0]}") from errh
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection Error: {e}")
        raise exceptions.APIRequestError(f"Connection Error: {e}") from e


def enum_serializer(obj: Any) -> Any:
    """Devuelve el literal de cada elemento del Enum"""
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def save_json(info: MutableMapping | dict, file: str):
    """Vuelca los datos pasados por parámetro a un archivo JSON"""
    try:
        with open(f"./out/{file}.json", "w") as f:
            json.dump(info, f, default=enum_serializer)
    except TypeError as e:
        logger.error(
            f"ERROR DE SERIALIZACIÓN: No se puede guardar '{file}.json'. Los datos contienen tipos no compatibles con JSON: {e}"
        )
    except OSError as e:
        logger.error(
            f"ERROR I/O: Fallo al escribir el archivo '{file}.json'. Revise los permisos o la ruta del archivo: {e}"
        )
    except Exception as e:
        logger.error(
            f"Ocurrió un error inesperado intentando guardar el archivo {file}.json: {e}"
        )
        raise


def fetch_rest_api_data() -> tuple[int, int]:
    """Obtiene la información de la API REST de Knowbe4"""
    rest_users = request_rest_api("/users", "?status=active&page=1&per_page=500")
    logger.info(f"Extraidos {len(rest_users)} usuarios de la REST API")
    rest_psts = request_rest_api("/phishing/security_tests", "?page=1&per_page=500")
    logger.info(f"Extraidos {len(rest_psts)} PSTs de la REST API")
    return len(rest_users), len(rest_psts)


def get_query_enrollments(page: int = 1, per: int = 100) -> str:
    end_date = datetime.now(pytz.utc)
    start_date = end_date - relativedelta(years=1)
    query = f"""{{
        enrollments(
            dateRangeEndDate: "{end_date.strftime("%Y-%m-%dT%H:%M:%SZ")}", 
            dateRangeField: COMPLETED_AT, 
            dateRangeStartDate: "{start_date.strftime("%Y-%m-%dT%H:%M:%SZ")}",
            page: {page},
            per: {per}
        ) {{
            nodes {{
                id
                createdAt
                completedAt
                status
                totalScore
                type
                trainingCampaign {{
                    id
                    name
                }}
                user {{
                    id
                }}
            }}
            pagination {{
                totalCount
            }}
        }}
    
    }}"""

    return query


def get_query_pst(page: int, per: int) -> str:
    """Crea la query para solicitar información relativa a los PSTs de la Graph API"""
    query = f"""{{
        phishingCampaignRuns(page: {page}, per: {per}){{
            nodes {{
                id
                createdAt
                phishPronePercentage
                totalOpened
                totalReported
                campaignRecipients {{
                    createdAt
                    clicked
                    clickedCount
                    opened
                    emailTemplate {{
                        id
                        name
                        rating
                        isAida
                        topics {{
                            name
                        }}
                    }}
                    reported
                    user {{
                        id
                        email
                    }}
                }}
            }}
        }}
    }}
    """
    return query


def get_query_user(page: int, per: int) -> str:
    """Crea la query para solicitar información relativa a los usuarios de la Graph API"""
    query = f"""{{
        users(status: ACTIVE, page: {page}, per: {per}) {{
            nodes {{
                id
                email
                firstName
                lastName
                createdAt
                jobTitle
                role
                riskScore
                mandatoryEnrollments{{
                    id
                    completedAt
                    createdAt
                    status
                    totalScore
                    type
                    trainingCampaign {{
                        id
                        name
                    }}
                }}
                electedEnrollments {{
                    id
                    completedAt
                }}
            }}
        }}
    }}
    """
    return query


def get_query_password_users(page: int, per: int) -> str:
    query = f"""{{
        passwordIqUserStates(pagination: {{ page: {page}, per: {per} }}) {{
            users {{
                id
                emails {{
                    address
                }}
                events {{
                    detectionType {{
                        name
                    }}
                    occurredAt
                    status
                }}
            }}
        }}
    }}"""
    return query


def get_query_assessment(assessmentId: int, campaignId: int) -> str:
    query = f"""{{
        assessmentResults(assessmentId: {assessmentId}, campaignId: {campaignId}){{
            domains {{
                name
                score
            }}
            score
        }}
    }}"""

    return query


def fetch_graph_api_data(n_users: int, n_psts: int) -> tuple[
    PhishingCampaignResponse,
    UserResponse,
    PasswordIQUserResponse,
    EnrollmentResponse,
    AssessmentResultsResponse,
]:
    """Obtiene todos los datos de la Graph API de Knowbe4"""
    assessment_results = cast(
        AssessmentResultsResponse,
        request_graphql_api(get_query_assessment(2157482, 864417)),
    )
    # save_json(dict(assessment_results), "assessment_results")
    logger.info("Extraida la informacion de los resultados de la prueba de seguridad")
    query_password_detections = """{
        passwordIqDetectionCounts {
            counts {
                ALL
            }
        }
    } 
    """
    password_detections = cast(
        PasswordIQDetectionResponse,
        request_graphql_api(query_password_detections, is_ksat=False),
    )
    logger.info("Extraida la informacion de las detecciones de contraseñas")

    n_detections = password_detections["passwordIqDetectionCounts"]["counts"]["ALL"]
    password_user_events = cast(
        PasswordIQUserResponse,
        request_graphql_api(get_query_password_users(1, 75), is_ksat=False),
    )
    for i in range(1, math.ceil(n_detections / 75)):
        new_response = cast(
            PasswordIQUserResponse,
            request_graphql_api(get_query_password_users(i + 1, 75), is_ksat=False),
        )
        password_user_events["passwordIqUserStates"]["users"] += new_response[
            "passwordIqUserStates"
        ]["users"]
    logger.info("Extraida la informacion de las contraseñas por usuario")

    time.sleep(30)

    campaign_runs = cast(
        PhishingCampaignResponse, request_graphql_api(get_query_pst(1, 50))
    )
    for i in range(1, math.ceil(n_psts / 50)):
        new_response = cast(
            PhishingCampaignResponse, request_graphql_api(get_query_pst(i + 1, 50))
        )
        campaign_runs["phishingCampaignRuns"]["nodes"] += new_response[
            "phishingCampaignRuns"
        ]["nodes"]
    logger.info(
        f"Extraida la informacion de los tests de phishing (PST) de la GraphAPI"
    )
    # save_json(dict(campaign_runs), "campaigns")

    user_info = cast(UserResponse, request_graphql_api(get_query_user(1, 75)))
    for i in range(1, math.ceil(n_users / 75)):
        new_response = cast(
            UserResponse, request_graphql_api(get_query_user(i + 1, 75))
        )
        user_info["users"]["nodes"] += new_response["users"]["nodes"]
    logger.info(
        f"Extraida la informacion relativa a los usuarios (puntuaciones, formaciones) de la GraphAPI"
    )
    # save_json(dict(user_info), "user_info")

    enrollment_info = cast(
        EnrollmentResponse, request_graphql_api(get_query_enrollments(1, 500))
    )
    n_enrollments = enrollment_info["enrollments"]["pagination"]["totalCount"]
    for i in range(1, math.ceil(n_enrollments / 500)):
        new_response = cast(
            EnrollmentResponse, request_graphql_api(get_query_enrollments(i + 1, 500))
        )
        enrollment_info["enrollments"]["nodes"] += new_response["enrollments"]["nodes"]
    logger.info(
        f"Extraida la informacion relativa a las formaciones realizadas en los ultimos 12 meses"
    )
    # save_json(dict(enrollment_info), "enrollments")

    return (
        campaign_runs,
        user_info,
        password_user_events,
        enrollment_info,
        assessment_results,
    )


def main():
    db_client = db.initialize_supabase_client()

    # Test conexión con supabase y obtenemos la ventana activa
    # Obtneemos la información de los logros (puntos que asignar por cada logro)
    db_read_achievement_info = db.read_db_data(
        db_client, "kb4_achievement_info", "tag, points"
    )

    achievement_info = {row["tag"]: row["points"] for row in db_read_achievement_info}

    # Ventana activa para el filtrado por fecha
    active_window = achievement_info["ACTIVE_WINDOW"]

    n_users, n_psts = fetch_rest_api_data()

    api_psts, user_info, pwd_user_events, year_enrollments, assessment = (
        fetch_graph_api_data(n_users, n_psts)
    )

    users: list[User] = user_info["users"]["nodes"]
    active_users = {user["id"] for user in users}

    # check_histories(users)

    recipients: list[CampaignRecipient] = list()
    psts: list[PhishingCampaignRun] = list()
    for pst in api_psts["phishingCampaignRuns"]["nodes"]:
        psts.append(pst)
        recipients += [
            recipient
            for recipient in pst["campaignRecipients"]
            if recipient["user"]["id"] in active_users
        ]

    user_pwds: list[PasswordIQUser] = pwd_user_events["passwordIqUserStates"]["users"]

    yearly_completed_enrollments: list[YearlyEnrollment] = year_enrollments[
        "enrollments"
    ]["nodes"]

    # 1. Porcentaje promedio de usuarios phish-prone
    phish_prone = basic_metrics.phish_prone_percentage(psts)

    # 2. Porcentaje de denuncias de phishing (simuladas)
    phishing = basic_metrics.phishing_reports(psts)

    # 3. Usuarios con más formaciones realizadas (top 5)
    top_educated, sorted_enrollments = basic_metrics.most_educated(
        users, yearly_completed_enrollments, 5
    )

    # 4. Porcentaje de clicks y denuncias por usuario en simulaciones de phishing
    clicks_percentages, report_percentages, raw_metrics = (
        basic_metrics.click_percentage(recipients, users, active_window)
    )

    # 5. Plantillas de phishing con mayor tasa de éxitoç
    best_templates, monthly_clicks = basic_metrics.best_phishing_templates(
        recipients, 10, active_window
    )

    # 6. Usuarios con menor riesgo (KSAT)
    low_risk = basic_metrics.lowest_risk_users(10, users)

    # Inserción de datos históricos a falta de datos del último mes
    if HISTORICAL_DATA:
        historical_data = scores.get_historical_data(users)
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
        db.insert_db_data(
            db_client, "kb4_monthly_risk", db_monthly_risk_hist, "user_id, created_at"
        )
        logger.info("Insertamos los historicos para diciembre de 2024")

    # Obtenemos el riesgo del mes anterior
    now = datetime.now(pytz.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    ref_date = now - relativedelta(months=1)
    if ref_date < pytz.utc.localize(datetime(2025, 11, 1)):
        ref_date = pytz.utc.localize(datetime(2024, 12, 1))
    db_last_risk = db.read_db_data(
        db_client,
        "kb4_monthly_risk",
        "user_id, risk_score",
        "created_at",
        ref_date.isoformat(),
    )

    # Cálculo de puntuaciones

    current_time = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_month = current_time - relativedelta(months=1)

    # Leemos las puntuaciones de los últimos seis meses para sumar a las de este mes
    db_last_semester_scores = db.read_last_semester_scores(
        db_client, "updated_at", "kb4_user_score_history"
    )

    db_score_data = {user["id"]: 0 for user in users}
    if db_last_semester_scores != list():
        # save_json({"scores": db_last_semester_scores}, "last_semester_scores")
        db_score_data = {
            score["user_id"]: score["total_score"] for score in db_last_semester_scores
        }

    top10_month_templates, m = basic_metrics.best_phishing_templates(
        recipients,
        10,
        active_window,
        (current_time, (last_month.month, last_month.year)),
    )
    user_scores, user_score_history = scores.calculate_scores(
        users,
        yearly_completed_enrollments,
        recipients,
        top10_month_templates,
        db_score_data,
        achievement_info,
        db_last_risk,
        active_window,
    )

    # db.save_score_history(db_client, users, user_score_history)

    # Métricas adicionales (mensual y anual)
    user_reports = basic_metrics.get_reporting_users(
        recipients, active_users, n_users, active_window
    )
    user_education = basic_metrics.get_educated_users(
        yearly_completed_enrollments, active_window, n_users
    )
    enrollments = basic_metrics.get_year_enrollments(users)

    # Vulnerabilidades
    vulnerable_users = admin_metrics.get_vulnerable_users(
        users, yearly_completed_enrollments, raw_metrics, recipients
    )

    pwds_detections_per_user, pwds = admin_metrics.get_vulnerable_pwd(user_pwds, users)

    assessment_results = admin_metrics.get_assessment_results(assessment)

    # Rellenamos la base de datos
    db.fill_db_user_info(
        db_client,
        active_window,
        users,
        sorted_enrollments,
        report_percentages,
        clicks_percentages,
        raw_metrics,
        user_scores,
        user_score_history,
    )

    db.fill_db_basic_metrics(
        db_client,
        best_templates,
        phish_prone,
        phishing,
        user_education[0],
        user_reports[0],
        user_education[1],
        user_reports[1],
        user_education[2],
        user_reports[2],
        top_educated,
        low_risk,
        enrollments,
    )

    db.fill_db_vulnerable_data(
        db_client, vulnerable_users, pwds, pwds_detections_per_user, assessment_results
    )


if __name__ == "__main__":
    try:
        main()
        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")
        logger.critical(
            f"Ha ocurrido un error critico, se ha interrumpido la ejecucion: {e} \n {traceback.format_exc()}"
        )
        raise SystemExit(1)
    finally:
        logging.shutdown()
