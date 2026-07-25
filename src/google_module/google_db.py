from database.base import DBClientBase
from custom_types import (
    DBUserGoogleMetrics,
    DBGoogleUser,
    DBGoogleUserScores,
)


class GoogleDBClient(DBClientBase):
    def __init__(self, db_client, logger):
        super().__init__(db_client, logger)

    def insert_users(self, users: list[dict]):

        db_users: list[DBGoogleUser] = [
            {
                "email": user["primaryEmail"],
                "created": self.current_time.isoformat(),
            }
            for user in users
        ]
        self.insert_db_data("google_users", db_users, "email")
        self.logger.info("Insertados los usuarios en la base de datos")

    def get_current_month_metrics(self):
        current_metrics = self.read_db_data(
            "google_metrics", "*", "month", self.current_month
        )
        self.logger.info("Leídas las métricas existentes de este mes de la BD")
        return current_metrics

    def insert_scores(self, scores: list[DBGoogleUserScores]):
        self.insert_db_data("google_user_scores", scores, "user_email, month")
        self.logger.info(
            "Insertadas las puntuaciones de Google para cada usuario"
        )

    def fetch_points(self, table_name="google_metrics_info"):
        points = self.read_db_data(table_name, "label, points")
        self.logger.info(
            "Extraídas las puntuaciones para las métricas de Google"
        )
        return points

    def insert_metrics(self, metrics: list[DBUserGoogleMetrics]):
        self.insert_db_data("google_metrics", metrics, "user_email, month")
        self.logger.info("Insertadas las métricas de Google para cada usuario")
