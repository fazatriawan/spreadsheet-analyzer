from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import explain_formula_ai


class handler(BaseHTTPRequestHandler):
    """POST /api/explain — jelaskan formula via AI."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        formula = body.get("formula", "")
        cell = body.get("cell", "")
        context = body.get("context")

        if not formula:
            send_json(self, 400, {"error": "Formula wajib diisi"})
            return

        result = explain_formula_ai(formula, cell, context)
        status = 200 if "explanation" in result else 500
        send_json(self, status, {"ok": status == 200, **result})
