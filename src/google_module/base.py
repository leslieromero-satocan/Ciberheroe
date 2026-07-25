# google_base.py
from googleapiclient.errors import HttpError
from logging import Logger
from googleapiclient.discovery import Resource
import time
import random


class GoogleAPIBase:
    """Parent class that holds shared logic for all Google APIs."""

    def __init__(self, logger: Logger, service: Resource):
        self.logger = logger
        self.service = service

    def exec_request(self, request, max_retries=5):
        """Se encarga de ejecutar cualquier solicitud a las APIs de Google"""
        for n in range(max_retries):
            try:
                response = request.execute()
                return response

            except HttpError as e:
                if e.status_code in [403, 429, 500, 502, 503, 504]:
                    sleep_time = (2**n) + random.uniform(0, 1)

                    self.logger.error(
                        f"API Rate Limited (Code {e.status_code}). "
                        f"Retrying in {sleep_time:.2f}s... (Attempt {n + 1}/{max_retries})"
                    )

                    time.sleep(sleep_time)
                else:
                    self.logger.error(
                        f"Non-retriable error {e.status_code}: {e.error_details}"
                    )
                    return None

            except Exception as e:
                print(f"Unexpected network disconnect: {e}")
                sleep_time = (2**n) + random.uniform(0, 1)
                time.sleep(sleep_time)
        print("Max retries exceeded. Skipping this request.")
        return None

    def close_service(self):
        self.service.close()
