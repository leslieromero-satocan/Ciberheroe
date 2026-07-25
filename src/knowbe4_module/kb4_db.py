from database.base import DBClientBase
from dateutil.relativedelta import relativedelta
from datetime import datetime
import pytz
from typing import Any, cast, TYPE_CHECKING
import uuid
from knowbe4_module.scores import filter_by_date

if TYPE_CHECKING:
    from knowbe4_module.etl import Knowbe4Context, Knowbe4Metrics

from custom_types import (
    PasswordIQDetectionCount,
)
from custom_types.knowbe4.metrics_info import (
    User,
    VulnerableMetrics,
    UserScores,
    TemplateMetrics,
)
from custom_types.knowbe4.db import (
    DBUser,
    DBUserScore,
    DBUserScoreHistory,
    DBTemplate,
    DBMetrics,
    DBMonthlyRisk,
    DBVulnerableUsers,
    DBPasswords,
    DBPasswordDetections,
    DBAssessmentResults,
)


class Knowbe4DBClient(DBClientBase):
    def __init__(self, db_client, logger):
        super().__init__(db_client, logger)
        self.update_timestamp = self.current_time.isoformat()

    def get_achievement_info(self):
        db_achievement_info = self.read_db_data(
            "kb4_achievement_info", "tag, points"
        )

        achievement_info = {
            row["tag"]: row["points"] for row in db_achievement_info
        }
        return achievement_info, achievement_info["ACTIVE_WINDOW"]

    def clean_db_templates(self):
        try:
            delete_response = (
                self.db_client.table("kb4_best_templates")
                .delete()
                .gt("position", 0)
                .execute()
            )
            self.logger.info(
                "Se ha limpiado la tabla kb4_best_templates correctamente"
            )
            return delete_response
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar elimintar las plantillas (tabla: kb4_best_templates): {e}"
            )
            raise e

    def clean_db_vulnerable_users(self):
        try:
            delete_response = (
                self.db_client.table("kb4_vulnerable_users")
                .delete()
                .gt("user_id", 0)
                .execute()
            )
            self.logger.info(
                "Se ha limpiado la tabla kb4_vulnerable_users correctamente"
            )
            return delete_response
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar eliminar los usuarios (tabla: kb4_vulnerable_users): {e}"
            )

    def read_last_semester_scores(
        self, active_window: int, date_column: str, table_name: str
    ):
        "Lee datos de la base de datos filtrados por los últimos meses acorde a la ventana activa"
        try:
            start = self.first_day_month - relativedelta(months=active_window)
            response = self.db_client.rpc(
                "sum_scores_by_user",
                {
                    "start_date": start.isoformat(),
                    "end_date": self.first_day_month.isoformat(),
                },
            ).execute()
            return cast(list[dict[str, Any]], response.data)
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar leer los datos en la BD (tabla: kb4_user_scores): {e}"
            )
            raise e

    def build_user_record(
        self,
        user: User,
        active_window: int,
        sorted_enrollments: dict[int, int],
        report_percentages: dict[int, float],
        clicks_percentages: dict[int, float],
        raw_metrics: dict[int, tuple[int, int, int]],
    ) -> DBUser:
        completed_optional_enrollments = filter_by_date(
            user["optionalEnrollments"],
            "completedAt",
            active_window,
            self.current_time,
        )
        user_raw_metrics = raw_metrics.get(user["id"], (-1, -1, -1))
        user_record: DBUser = {
            "id": user["id"],
            "created": user["createdAt"],
            "updated_at": self.update_timestamp,
            "status": "active",
            "first_name": user["firstName"],
            "last_name": user["lastName"],
            "email": user["email"],
            "job_title": user["jobTitle"],
            "role": user["role"],
            "current_risk": user["riskScore"],
            "enrollments": sorted_enrollments[user["id"]],
            "optional_enrollments": len(completed_optional_enrollments),
            # Si son nuevas incorporaciones, no habrán abierto
            # ningún correo de phishing
            "phish_reports": report_percentages.get(user["id"], -1),
            "phish_reports_abs": user_raw_metrics[1],
            "phish_clicks": clicks_percentages.get(user["id"], -1),
            "phish_clicks_abs": user_raw_metrics[0],
            "phish_opened": user_raw_metrics[2],
        }
        return user_record

    def build_score_record(
        self,
        user: User,
        scores: dict[int, UserScores],
    ):
        user_achievements = [
            a.value for a in scores[user["id"]]["achievements"]
        ]
        score_record: DBUserScore = {
            "id": str(uuid.uuid4()),
            "updated_at": self.current_month,
            "score": scores[user["id"]]["acc_score"],
            "achievements": user_achievements,
            "user_id": user["id"],
        }
        return score_record

    def build_score_history_record(
        self, user: User, score_history: dict[int, dict[str, Any]]
    ) -> DBUserScoreHistory:
        user_achievements_history = [
            a.value for a in score_history[user["id"]]["achievements"]
        ]
        score_history_record: DBUserScoreHistory = {
            "id": str(uuid.uuid4()),
            "updated_at": self.current_month,
            "score": score_history[user["id"]]["score"],
            "acc_score": score_history[user["id"]]["acc_score"],
            "achievements": user_achievements_history,
            "risk_score": score_history[user["id"]]["risk_score"],
            "user_id": user["id"],
        }
        return score_history_record

    def build_monthly_risk_record(self, user: User):
        montly_risk_record: DBMonthlyRisk = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "risk_score": user["riskScore"],
            "created_at": self.current_month,
        }
        return montly_risk_record

    def insert_user_info(
        self,
        db_users: list[DBUser],
        db_scores: list[DBUserScore],
        db_score_history: list[DBUserScoreHistory],
        db_monthly_risk: list[DBMonthlyRisk],
    ):
        self.insert_db_data("kb4_users", db_users)

        # Actualizamos el status de los usuarios que no se han actualizado (no están en Knowbe4)
        try:
            data, count = (
                self.db_client.table("kb4_users")
                .update({"status": "archived"})
                .lt("updated_at", self.update_timestamp)
                .eq("status", "active")
                .execute()
            )
            n_archived = count[1] if count[1] is not None else 0
            self.logger.info(f"Archivados {n_archived} usuarios.")
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar archivar los usuarios: {e}"
            )

        self.insert_db_data("kb4_user_scores", db_scores, "user_id")
        self.insert_db_data(
            "kb4_user_score_history",
            db_score_history,
            "user_id, updated_at",
        )
        self.insert_db_data(
            "kb4_monthly_risk", db_monthly_risk, "user_id, created_at"
        )

    def get_last_month_risk(self):
        ref_date = self.first_day_month - relativedelta(months=1)
        if ref_date < pytz.utc.localize(datetime(2025, 11, 1)):
            ref_date = pytz.utc.localize(datetime(2024, 12, 1))

        db_last_risk = self.read_db_data(
            "kb4_monthly_risk",
            "user_id, risk_score",
            "created_at",
            ref_date.isoformat(),
        )

        return db_last_risk

    def get_last_months_scores(self, context: "Knowbe4Context"):
        db_last_semester_scores = self.read_last_semester_scores(
            context.active_window, "updated_at", "kb4_user_score_history"
        )

        db_score_data = {user["id"]: 0 for user in context.users}
        if db_last_semester_scores != list():
            db_score_data = {
                score["user_id"]: score["total_score"]
                for score in db_last_semester_scores
            }
        return db_score_data

    def fill_db_user_info(
        self,
        context: "Knowbe4Context",
        metrics: "Knowbe4Metrics",
        scores: dict[int, UserScores],
        score_history: dict[int, dict[str, Any]],
    ):
        db_users: list[DBUser] = list()
        db_scores: list[DBUserScore] = list()
        db_score_history: list[DBUserScoreHistory] = list()
        db_monthly_risk: list[DBMonthlyRisk] = list()

        for user in context.users:
            db_users.append(
                self.build_user_record(
                    user,
                    context.active_window,
                    metrics.sorted_enrollments,
                    metrics.report_percentages,
                    metrics.clicks_percentages,
                    metrics.raw_metrics,
                )
            )
            db_scores.append(self.build_score_record(user, scores))

            db_score_history.append(
                self.build_score_history_record(user, score_history)
            )
            db_monthly_risk.append(self.build_monthly_risk_record(user))

        self.insert_user_info(
            db_users, db_scores, db_score_history, db_monthly_risk
        )

    def build_template_record(self, template_id, template, index):
        template_topics = [i["name"] for i in template["topics"]]
        template_record: DBTemplate = {
            "id": template_id,
            "template_name": template["name"],
            "clicked_count_perc": template["clicked_count_perc"],
            "position": index + 1,
            "topics": template_topics,
        }
        return template_record

    def fill_best_templates(self, best_templates: dict[int, TemplateMetrics]):
        db_templates: list[DBTemplate] = list()
        for index, (template_id, template) in enumerate(
            best_templates.items()
        ):
            db_templates.append(
                self.build_template_record(template_id, template, index)
            )
        # TODO: Test that I can avoid cleaning up the templates
        self.insert_db_data("kb4_best_templates", db_templates, "position")

    def fill_db_basic_metrics(
        self,
        metrics: "Knowbe4Metrics",
    ):
        db_metrics: DBMetrics = {
            "id": str(uuid.uuid4()),
            "date_registered": self.current_month,
            "phish_prone": metrics.phish_prone_percentage,
            "phish_reports": metrics.phishing,
            "monthly_educated": metrics.user_education[0],
            "monthly_reporting": metrics.user_reports[0],
            "aw_educated": metrics.user_education[1],
            "aw_reporting": metrics.user_reports[1],
            "yearly_educated": metrics.user_education[2],
            "yearly_reporting": metrics.user_reports[2],
            "top_educated": list(metrics.top_educated.keys()),
            "low_risk": list(metrics.low_risk.keys()),
            "enrollments": metrics.enrollments,
        }

        self.insert_db_data("kb4_metrics", db_metrics, "date_registered")
        return

    def build_vulnerable_user_record(self, v_user_id, v_metrics):
        vulnerable_user_record: DBVulnerableUsers = {
            "id": str(uuid.uuid4()),
            "phishing_clicks": v_metrics["phishing_clicks"],
            "last_click": v_metrics["last_click"],
            "completed_enrollments": v_metrics["completed_enrollments"],
            "user_id": v_user_id,
        }
        return vulnerable_user_record

    def fill_db_vulnerable_users(
        self, vulnerable_users: dict[int, VulnerableMetrics]
    ):
        db_vulnerable_users: list[DBVulnerableUsers] = list()
        for v_user_id, v_metrics in vulnerable_users.items():
            db_vulnerable_users.append(
                self.build_vulnerable_user_record(v_user_id, v_metrics)
            )
        self.clean_db_vulnerable_users()
        self.insert_db_data(
            "kb4_vulnerable_users", db_vulnerable_users, "user_id"
        )

    def fill_db_passwords(self, pwd_detections: PasswordIQDetectionCount):
        db_pwd_metrics: DBPasswords = {
            "id": str(uuid.uuid4()),
            "created_at": self.current_month,
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

        self.insert_db_data("kb4_pwd", db_pwd_metrics, "created_at")

    def build_pwd_user_metrics(self, detection):
        user_metrics_record: DBPasswordDetections = {
            "id": str(uuid.uuid4()),
            "user_id": detection["user_id"],
            "emails": detection["emails"],
            "detection_type": detection["detection_type"],
            "ocurred_at": detection["ocurred_at"],
            "status": detection["status"],
        }
        return user_metrics_record

    def fill_db_passwords_detections(
        self, pwd_detections_per_user: list[dict[str, Any]]
    ):
        db_pwd_user_metrics: list[DBPasswordDetections] = list()
        for detection in pwd_detections_per_user:
            db_pwd_user_metrics.append(self.build_pwd_user_metrics(detection))

        self.insert_db_data(
            "kb4_pwd_detections",
            db_pwd_user_metrics,
            "user_id, detection_type, ocurred_at",
        )

    def fill_db_assessment_results(self, assessment_results: dict[str, int]):
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
            "updated_at": self.update_timestamp,
        }

        self.insert_db_data(
            "kb4_assessment_results", db_assessment_results, "updated_at"
        )
