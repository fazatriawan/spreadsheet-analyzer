"""Google credentials helper — supports file path (local) or JSON env (Vercel)."""
import json
import os
import tempfile

from google.oauth2.service_account import Credentials

WRITE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

READ_SCOPES = WRITE_SCOPES


def get_service_account_path() -> str:
    """Return path to service account JSON (file or temp file from env)."""
    from config import GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SERVICE_ACCOUNT_JSON

    if GOOGLE_SERVICE_ACCOUNT_JSON:
        tmp = os.path.join(tempfile.gettempdir(), "gsa_vercel.json")
        if not os.path.exists(tmp):
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(json.loads(GOOGLE_SERVICE_ACCOUNT_JSON), f)
        return tmp
    return GOOGLE_SERVICE_ACCOUNT_FILE


def get_credentials(scopes=None):
    path = get_service_account_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            "Service account tidak ditemukan. Set GOOGLE_SERVICE_ACCOUNT_JSON di Vercel "
            "atau GOOGLE_SERVICE_ACCOUNT_FILE secara lokal."
        )
    return Credentials.from_service_account_file(path, scopes=scopes or WRITE_SCOPES)
