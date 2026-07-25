from logging import Logger
from supabase import Client
from database.base import DBClientBase


class EventsDBClient(DBClientBase):
    def __init__(self, db_client: Client, logger: Logger):
        super().__init__(db_client, logger)

    def fetch_points(self, table_name="events_metrics_info"):
        points = self.read_db_data(table_name, "label, points, minimum")
        self.logger.info(
            "Extraídas las puntuaciones para las métricas de los Eventos de Windows"
        )
        return points

    def insert_scores(self, scores):
        self.insert_db_data("events_user_scores", scores, "user_email, month")
        self.logger.info(
            "Insertadas las puntuaciones de Eventos de Windows para cada usuario"
        )

    def insert_metrics(self, metrics):
        self.insert_db_data("events_metrics", metrics, "user_email, month")
        self.logger.info(
            "Insertadas las métricas de Eventos de Windows para cada usuario"
        )

    def get_current_month_metrics(self):
        current_month_metrics = self.read_db_data(
            "events_metrics", "*", "month", self.current_month
        )
        self.logger.info(
            "Leídas las métricas existentes de Eventos de Windows del mes actual"
        )
        return current_month_metrics

    def insert_users(self, users):
        self.insert_db_data(
            "events_users",
            users,
            "device",
        )
        self.logger.info("Insertados los usuarios de Eventos de Windows")
