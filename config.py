import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MAX_CELLS = int(os.getenv("MAX_CELLS_PER_SHEET", 10000))
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# Locale formula: indonesia → pemisah argumen titik koma (;)
FORMULA_LOCALE = os.getenv("FORMULA_LOCALE", "indonesia").lower()

# Vercel serverless: cache di /tmp (ephemeral, per-instance)
CACHE_DIR = os.getenv(
    "CACHE_DIR",
    "/tmp/spreadsheet-cache" if os.getenv("VERCEL") else "./cache",
)
