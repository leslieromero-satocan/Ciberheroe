from google_module import (
    AdminDirectoryExtractor,
    AdminReportsExtractor,
    CloudIdentityExtractor,
    GoogleDriveExtractor,
    GmailExtractor,
    GoogleDBClient,
    GoogleScoreCalculator,
)
from knowbe4_module.helper_functions import save_json
import logging
from custom_types import (
    GoogleUserMetrics,
    DBUserGoogleMetrics,
    DBGoogleUserScores,
)
import socket
from concurrent.futures import ThreadPoolExecutor

socket.setdefaulttimeout(60.0)

logger = logging.getLogger(f"ciberheroe.{__name__}")


def get_point_system(db_client):
    """Obtiene el sistema de puntuaciones de Google la BD"""
    google_db = GoogleDBClient(db_client, logger)
    point_system = google_db.fetch_points()
    save_json({"point_system": point_system}, "google_points")
    logger.info("Obtenido el sistema de puntuación de la BD")

    return google_db, point_system


def get_admin_metrics():
    """Obtenemos las métricas administrativas para todos los usuarios

    Las métricas administrativas son aquellas que se pueden extraer de todos
    los usuarios al mismo tiempo, en vez de uno a uno.
    """
    admin_directory = AdminDirectoryExtractor(logger)
    users = admin_directory.extract_user_list()
    save_json({"users": users}, "google_user_list")
    logger.info("Obtenida la lista de todos los usuarios")

    admin_directory.close_service()

    cloud_identity = CloudIdentityExtractor(logger)
    corporate_devices = cloud_identity.check_corporate_devices()
    save_json(corporate_devices, "corporate_devices")
    logger.info("Obtenida la lista de dispositivos utilizados")

    cloud_identity.close_service()

    admin_reports = AdminReportsExtractor(logger)
    unsafe_sites = admin_reports.check_ignore_certificate_warning()
    save_json(unsafe_sites, "unsafe_sites")

    reuse_passwords = admin_reports.check_reuse_password()
    save_json(reuse_passwords, "reuse_passwords")

    file_downloads = admin_reports.check_file_downloads()
    save_json(file_downloads, "file_downloads")

    malware_download = admin_reports.check_malware_download()
    save_json(malware_download, "malware_download")

    vulnerable_passwords = admin_reports.check_vulnerable_password()
    save_json(vulnerable_passwords, "vulnerable_passwords")

    admin_directory.close_service()

    return (
        users,
        corporate_devices,
        unsafe_sites,
        reuse_passwords,
        file_downloads,
        malware_download,
        vulnerable_passwords,
    )


def get_individual_metrics(
    user_info,
    db_metrics,
    corporate_devices,
    unsafe_sites,
    reuse_passwords,
    file_downloads,
    malware_download,
    vulnerable_passwords,
    current_month,
    point_system,
):
    """Obtiene las métricas individuales de cada usuario

    Se considera métrica individual aquella que hay que obtener asumiendo la
    identidad de cada usuario con la cuenta de servicio
    """
    email = user_info["primaryEmail"]

    current_db_metrics = db_metrics.get(email, {})

    user_devices = corporate_devices.get(email, {"devices": []}).get("devices")
    user_unsafe_sites = len(
        unsafe_sites.get(email, [])
    ) + current_db_metrics.get("unsafe_sites", 0)
    user_reused_pwds = len(
        reuse_passwords.get(email, [])
    ) + current_db_metrics.get("reused_pwds", 0)
    user_file_downloads = len(
        file_downloads.get(email, [])
    ) + current_db_metrics.get("risky_downloads", 0)
    user_malware_downloads = len(
        malware_download.get(email, [])
    ) + current_db_metrics.get("malware_downloads", 0)
    user_vulnerable_pwds = len(
        vulnerable_passwords.get(email, [])
    ) + current_db_metrics.get("vulnerable_pwds", 0)

    drive = GoogleDriveExtractor(logger, email)
    gmail = GmailExtractor(logger, email)

    full_access = drive.extract_files_with_full_access()
    exp_date = drive.extract_files_with_expiration_date()

    drive.close_service()

    conf_messages, error = gmail.extract_messages_sent_in_confidential_mode()

    gmail.close_service()

    score_calculator = GoogleScoreCalculator()
    non_corp_devices, platform = score_calculator.process_devices(user_devices)

    user_metrics: GoogleUserMetrics = {
        "enabled_2sv": user_info["isEnrolledIn2Sv"],
        "unsafe_sites": user_unsafe_sites,
        "reused_pwds": user_reused_pwds,
        "device_platform": platform
        + current_db_metrics.get("device_platform", 0),
        "risky_downloads": user_file_downloads,
        "malware_downloads": user_malware_downloads,
        "vulnerable_pwds": user_vulnerable_pwds,
        "non_corp_devices": non_corp_devices
        + current_db_metrics.get("non_corp_devices", 0),
        "files_public_link": len(full_access)
        + current_db_metrics.get("files_public_link", 0),
        "files_exp_date": len(exp_date)
        + current_db_metrics.get("files_exp_date", 0),
        "messages_conf": len(conf_messages)
        + current_db_metrics.get("messages_conf", 0),
    }

    user_score = score_calculator.calculate_scores(user_metrics, point_system)

    db_user_metrics: DBUserGoogleMetrics = {
        **user_metrics,
        "user_email": email,
        "month": current_month,
    }

    db_score: DBGoogleUserScores = {
        "user_email": email,
        "month": current_month,
        "score": user_score,
    }
    return db_user_metrics, db_score, error


def google_etl(db_client):
    # Obtenemos el sistema de puntuación
    google_db, point_system = get_point_system(db_client)

    # Obtenemos las métricas de la BD
    current_month_metrics = google_db.get_current_month_metrics()

    db_metrics = {row["user_email"]: row for row in current_month_metrics}

    # Obtenemos las métricas de todos los usuarios
    (
        users,
        corporate_devices,
        unsafe_sites,
        reuse_passwords,
        file_downloads,
        malware_download,
        vulnerable_passwords,
    ) = get_admin_metrics()

    # Insertamos la lista de usuarios
    google_db.insert_users(users)

    all_metrics: list[DBUserGoogleMetrics] = list()
    all_scores: list[DBGoogleUserScores] = list()

    def process_user_wrapper(user_info):
        try:
            return get_individual_metrics(
                user_info,
                db_metrics,
                corporate_devices,
                unsafe_sites,
                reuse_passwords,
                file_downloads,
                malware_download,
                vulnerable_passwords,
                google_db.current_month,
                point_system,
            )
        except Exception as e:
            logger.error(
                f"Error processing {user_info.get('primaryEmail')}: {e}"
            )
            return None, None, False

    logger.info(
        f"Empezando la extracción de la información de los {len(users)} usuarios..."
    )
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_user_wrapper, users)

        mails_not_registered = 0
        for metrics, scores, error in results:
            if error:
                mails_not_registered += 1
            if metrics is not None and scores is not None:
                all_metrics.append(metrics)
                all_scores.append(scores)
    logger.error(
        f"Se han registrado {mails_not_registered} usuarios cuyo email no se puede acceder"
    )
    logger.info("Completada la extracción, empezando la inserción en la BD...")

    # Insertamos las métricas y las puntuaciones en la base de datos
    google_db.insert_metrics(all_metrics)
    google_db.insert_scores(all_scores)

    return


# TODO: Find books about prompt engineering, clean code, interfaces, etc.
# TODO: Define data models for all of these functions (create TypedDicts for them)
# TODO: Reflect this model somehow in the memory
