from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import apply_fix_to_sheet


class handler(BaseHTTPRequestHandler):
    """POST /api/apply — terapkan formula ke Google Sheets."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        url = (body.get("url") or "").strip()
        cell = body.get("cell", "")
        formula = body.get("formula", "")

        if not url or not cell or not formula:
            send_json(self, 400, {"error": "url, cell, dan formula wajib diisi"})
            return

        try:
            result = apply_fix_to_sheet(url, cell, formula)
            status = 200 if "ok" in result else 400
            send_json(self, status, result)
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
