from http.server import BaseHTTPRequestHandler

from api._http import handle_options, send_json


class handler(BaseHTTPRequestHandler):
    """GET /api/health — cek status deployment."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_GET(self):
        import os

        send_json(
            self,
            200,
            {
                "ok": True,
                "service": "spreadsheet-analyzer",
                "runtime": "vercel-python" if os.getenv("VERCEL") else "local",
                "has_google_creds": bool(
                    os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
                    or os.path.exists(os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"))
                ),
                "has_anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
        )
