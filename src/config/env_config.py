import os
from dotenv import load_dotenv

load_dotenv("../.env")

# === Knoowbe4 ====

REPORT_API_URL = os.environ.get(
    "REPORT_API_URL", "https://eu.api.knowbe4.com/v1"
)
REPORT_API_TOKEN = os.environ.get("REPORT_API_TOKEN", "token_not_found_in_env")
REPORT_API_HEADERS = {
    "Authorization": f"Bearer {REPORT_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "My-KnowBe4-Integration-Script",
}
GRAPH_API_URL = os.environ.get(
    "GRAPH_API_URL", "https://eu.knowbe4.com/graphql"
)
GRAPH_API_PASS = os.environ.get("PASS_API_TOKEN", "token_not_found_in_env")
GRAPH_API_KSAT = os.environ.get("KSAT_API_TOKEN", "token_not_found_in_env")
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

SUPABASE_URL = os.environ.get(
    "SUPABASE_PROJECT_URL", "https://example-url.supabase.co"
)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "key_not_found_in_env")

HISTORICAL_DATA = False

# === GOOGLE WORKSPACE ===

SERVICE_ACCOUNT_FILE = os.environ.get(
    "SERVICE_ACCOUNT_FILE_PATH", "path/to/credentials.json"
)

SUBJECT_EMAIL = os.environ.get("SUBJECT_EMAIL", "admin@example.com")

# == EVENTS ==

LOGS_FILE_PATH = os.environ.get("LOGS_FILE_PATH", "path_not_in_env")
