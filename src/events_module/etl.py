from knowbe4_module import save_json
from events_module import read_event_logs, EventScoreCalculator, EventsDBClient
from custom_types import (
    DBEventsUser,
    EventMetrics,
    DBEventMetrics,
    DBEventUserScores,
)

from pathlib import Path
from collections import defaultdict
import logging
import json

logger = logging.getLogger(f"ciberheroe.{__name__}")

map_device = [
    {"equipo": "LAPTOP-DEV-01", "email": "user1@test-events.com"},
    {"equipo": "LAPTOP-MKT-02", "email": "user2@test-events.com"},
    {"equipo": "DESKTOP-HR-05", "email": "user3@test-events.com"},
]


def get_point_system(db_client):
    """Obtiene el sistema de puntuaciones de la BD"""
    events_db = EventsDBClient(db_client, logger)
    point_system = events_db.fetch_points()
    save_json({"point_system": point_system}, "events_points")
    logger.info("Obtenido el sistema de puntuación de la BD")

    return events_db, point_system


def get_event_codes(
    file="event_codes.json",
):
    src_dir = Path(__file__).parent
    json_file_path = src_dir / file
    with open(json_file_path, "r", encoding="utf-8") as f:
        event_codes_json = json.loads(f.read())
    event_codes = {row["code"]: row["label"] for row in event_codes_json}
    return event_codes


def process_events_by_user(events):
    # TODO: Para el procesado real de los eventos, habría que ver si se realiza
    # el filtrado por fecha (para el día de hoy) desde el XML y el Powershell o
    # si habría que filtrar desde aquí, por lo que habría que añadirlo en esta
    # función. Ahora mismo la función supone que solo hay datos del día de hoy
    # en el JSON

    event_codes = get_event_codes()
    events_by_user = defaultdict(lambda: defaultdict(lambda: 0))
    users = {}
    for row in events:
        equipo = row.get("Equipo", "NA")
        usuario = row.get("Usuario", "usuario_desconocido")
        if usuario != "SISTEMA":
            users[equipo] = usuario
        label = event_codes[row["ID"]]
        if label == "login_success" and row["WindowsHello"]:
            label = "biometric_auth"
        events_by_user[equipo][label] += 1
    return users, events_by_user


def accumulate_event_metrics(current_month_metrics, events_by_user, month):
    current_metrics = (
        {
            row["user_email"]: row
            for row in current_month_metrics
            if row["user_email"] is not None
        }
        if current_month_metrics is not None
        else {}
    )
    save_json(current_metrics, "test_current_metrics")

    event_metrics = {}
    for device, metrics in events_by_user.items():
        user_email = next(
            (row["email"] for row in map_device if row["equipo"] == device),
            "No email found for this device",
        )
        user_month_metrics = current_metrics.get(user_email, {})
        user_metrics: EventMetrics = {
            "login_success": metrics.get("login_success", 0)
            + user_month_metrics.get("login_success", 0),
            "lock_screen": metrics.get("lock_screen", 0)
            + user_month_metrics.get("lock_screen", 0),
            "restart": metrics.get("restart", 0)
            + user_month_metrics.get("restart", 0),
            "updates": metrics.get("updates", 0)
            + user_month_metrics.get("updates", 0),
            "usb_devices": metrics.get("usb_devices", 0)
            + user_month_metrics.get("usb_devices", 0),
            "login_failed": metrics.get("login_failed", 0)
            + user_month_metrics.get("login_failed", 0),
            "biometric_auth": metrics.get("biometric_auth", 0)
            + user_month_metrics.get("biometric_auth", 0),
        }

        event_metrics[user_email] = user_metrics

    return event_metrics


def events_etl(db_client):
    # Extraer el sistema de puntuaciones
    events_db, point_system = get_point_system(db_client)
    # Llamar al extractor
    events = read_event_logs()
    # Procesar loe eventos
    users, events_by_user = process_events_by_user(events)
    save_json({"users": users}, "event_users")
    # Insertar los usuarios
    db_users: list[DBEventsUser] = [
        {
            "user": users[row["equipo"]],
            "user_email": row["email"],
            "device": row["equipo"],
            "updated_at": events_db.current_time.isoformat(),
        }
        for row in map_device
    ]
    events_db.insert_users(db_users)

    current_month_metrics = events_db.get_current_month_metrics()
    event_metrics: dict[str, EventMetrics] = accumulate_event_metrics(
        current_month_metrics, events_by_user, events_db.current_month
    )

    # Pasar datos a la calculadora de puntuaciones
    score_calculator = EventScoreCalculator()
    scores = score_calculator.calculate_scores(event_metrics, point_system)

    db_metrics: list[DBEventMetrics] = [
        {**metrics, "user_email": user_email, "month": events_db.current_month}
        for user_email, metrics in event_metrics.items()
    ]

    db_scores: list[DBEventUserScores] = [
        {
            "user_email": user_email,
            "month": events_db.current_month,
            "score": score,
        }
        for user_email, score in scores.items()
    ]

    # Pasar información a la base de datos
    events_db.insert_metrics(db_metrics)
    events_db.insert_scores(db_scores)
    return
