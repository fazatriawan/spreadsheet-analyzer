from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import fix_one_formula


class handler(BaseHTTPRequestHandler):
    """POST /api/fix — perbaiki satu formula via AI."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        formula = body.get("formula", "")
        warnings = body.get("warnings") or []

        if not formula:
            send_json(self, 400, {"error": "Formula wajib diisi"})
            return

        try:
            result = fix_one_formula(formula, warnings)
            send_json(self, 200, {"ok": True, **result})
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
