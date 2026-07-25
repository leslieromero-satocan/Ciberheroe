from typing import Any, cast
from supabase import Client
from logging import Logger
from datetime import datetime
import pytz


class DBClientBase:
    """Base class for all clients interacting with the Database"""

    def __init__(self, db_client: Client, logger: Logger):
        self.db_client = db_client
        self.logger = logger
        self.current_time = datetime.now(pytz.utc)
        self.first_day_month = self.current_time.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        self.current_month = self.first_day_month.strftime("%Y-%m-%d")

    def insert_db_data(self, table_name: str, data: Any, conflict: str = "id"):
        """Inserta datos en la base de datos"""
        try:
            response = (
                self.db_client.table(table_name)
                .upsert(cast(list[dict], data), on_conflict=conflict)
                .execute()
            )
            self.logger.info(f"Insertados los datos en la tabla {table_name}")
            return response
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar insertar los datos en la BD (tabla: {table_name}): {e}"
            )
            raise e

    def read_db_data(
        self,
        table_name: str,
        select: str,
        date_column: str | None = None,
        date: str | None = None,
    ):
        """Lee datos de la base de datos"""
        try:
            query = self.db_client.table(table_name).select(select)
            if date_column and date:
                query.eq(date_column, date)

            response = query.execute()
            return cast(list[dict[str, Any]], response.data)
        except Exception as e:
            self.logger.error(
                f"Ha ocurrido un error al intentar leer los datos en la BD (tabla: {table_name}): {e}"
            )
            raise e
