import logging
import requests
import time
import math
from typing import cast

import knowbe4_module.queries as queries
import config.exceptions as exceptions

# Temporarily everything is hardcoded in config
import config.env_config as config
from custom_types import (
    PasswordIQUserResponse,
    PhishingCampaignResponse,
    UserResponse,
    PasswordIQDetectionResponse,
    EnrollmentResponse,
    AssessmentResultsResponse,
)

logger = logging.getLogger(f"ciberheroe.{__name__}")

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
            url=f"{config.REPORT_API_URL}{endpoint}{params}",
            headers=config.REPORT_API_HEADERS,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as errh:
        logger.error(f"HTTP Error: {errh.args[0]}")
        return list()


def request_graphql_api(query: str, is_ksat: bool = True) -> GraphAPIResponse:
    """Realiza la solicitud a la Graph API de Knowbe4"""
    try:
        headers = config.KSAT_HEADERS if is_ksat else config.PASSWORDIQ_HEADERS
        response = requests.post(
            config.GRAPH_API_URL, json={"query": query}, headers=headers
        )
        response.raise_for_status()
        result = response.json()
        if "data" in result:
            return result["data"]
        else:
            logger.error(
                f"Hubo un error con la query, no se pudo obtener la informacion {response.content!r}"
            )
            raise exceptions.QueryError(
                f"Data not found, incorrect query: {query}"
            )
    except requests.exceptions.HTTPError as errh:
        logger.error(f"HTTP Error: {errh.args[0]}")
        raise exceptions.APIRequestError(
            f"HTTP Error: {errh.args[0]}"
        ) from errh
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection Error: {e}")
        raise exceptions.APIRequestError(f"Connection Error: {e}") from e


def fetch_rest_api_data() -> tuple[int, int]:
    """Obtiene la información de la API REST de Knowbe4"""
    rest_users = request_rest_api(
        "/users", "?status=active&page=1&per_page=500"
    )
    logger.info(f"Extraidos {len(rest_users)} usuarios de la REST API")
    rest_psts = request_rest_api(
        "/phishing/security_tests", "?page=1&per_page=500"
    )
    logger.info(f"Extraidos {len(rest_psts)} PSTs de la REST API")
    return len(rest_users), len(rest_psts)


def fetch_assessment_results():
    assessment_results = cast(
        AssessmentResultsResponse,
        request_graphql_api(queries.get_query_assessment(2157482, 864417)),
    )
    # save_json(dict(assessment_results), "assessment_results")
    logger.info(
        "Extraida la informacion de los resultados de la prueba de seguridad"
    )
    return assessment_results


def fetch_passwords():
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

    n_detections = password_detections["passwordIqDetectionCounts"]["counts"][
        "ALL"
    ]
    password_user_events = cast(
        PasswordIQUserResponse,
        request_graphql_api(
            queries.get_query_password_users(1, 75), is_ksat=False
        ),
    )
    for i in range(1, math.ceil(n_detections / 75)):
        new_response = cast(
            PasswordIQUserResponse,
            request_graphql_api(
                queries.get_query_password_users(i + 1, 75), is_ksat=False
            ),
        )
        password_user_events["passwordIqUserStates"]["users"] += new_response[
            "passwordIqUserStates"
        ]["users"]

    logger.info("Extraida la informacion de las contraseñas por usuario")

    return password_user_events


def fetch_campaign_runs(n_psts):
    campaign_runs = cast(
        PhishingCampaignResponse,
        request_graphql_api(queries.get_query_pst(1, 50)),
    )
    for i in range(1, math.ceil(n_psts / 50)):
        new_response = cast(
            PhishingCampaignResponse,
            request_graphql_api(queries.get_query_pst(i + 1, 50)),
        )
        campaign_runs["phishingCampaignRuns"]["nodes"] += new_response[
            "phishingCampaignRuns"
        ]["nodes"]

    logger.info(
        "Extraida la informacion de los tests de phishing (PST) de la GraphAPI"
    )

    return campaign_runs


def fetch_user_info(n_users):
    user_info = cast(
        UserResponse, request_graphql_api(queries.get_query_user(1, 75))
    )
    for i in range(1, math.ceil(n_users / 75)):
        new_response = cast(
            UserResponse,
            request_graphql_api(queries.get_query_user(i + 1, 75)),
        )
        user_info["users"]["nodes"] += new_response["users"]["nodes"]

    logger.info(
        """Extraida la informacion relativa a los usuarios (puntuaciones,
         formaciones) de la GraphAPI"""
    )

    return user_info


def fetch_enrollment_info():
    enrollment_info = cast(
        EnrollmentResponse,
        request_graphql_api(queries.get_query_enrollments(1, 500)),
    )
    n_enrollments = enrollment_info["enrollments"]["pagination"]["totalCount"]
    for i in range(1, math.ceil(n_enrollments / 500)):
        new_response = cast(
            EnrollmentResponse,
            request_graphql_api(queries.get_query_enrollments(i + 1, 500)),
        )
        enrollment_info["enrollments"]["nodes"] += new_response["enrollments"][
            "nodes"
        ]

    logger.info(
        """Extraida la informacion relativa a las formaciones realizadas
          en los ultimos 12 meses"""
    )

    return enrollment_info


def fetch_graph_api_data(n_users: int, n_psts: int) -> tuple[
    PhishingCampaignResponse,
    UserResponse,
    PasswordIQUserResponse,
    EnrollmentResponse,
    AssessmentResultsResponse,
]:
    """Obtiene todos los datos de la Graph API de Knowbe4"""

    assessment_results = fetch_assessment_results()

    password_user_events = fetch_passwords()

    # Necesita un delay para evitar un timeout entre solicitudes
    time.sleep(30)

    campaign_runs = fetch_campaign_runs(n_psts)
    # save_json(dict(campaign_runs), "campaigns")

    user_info = fetch_user_info(n_users)
    # save_json(dict(user_info), "user_info")

    enrollment_info = fetch_enrollment_info()
    # save_json(dict(enrollment_info), "enrollments")

    return (
        campaign_runs,
        user_info,
        password_user_events,
        enrollment_info,
        assessment_results,
    )
