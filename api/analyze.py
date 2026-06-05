from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import run_analysis


class handler(BaseHTTPRequestHandler):
    """POST /api/analyze — jalankan analisis formula & dependency."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        url = (body.get("url") or "").strip()
        selected = body.get("selected_sheets") or None
        use_cache = body.get("use_cache", True)
        use_ai = body.get("use_ai", False)

        if not url:
            send_json(self, 400, {"error": "URL wajib diisi"})
            return

        try:
            result = run_analysis(
                url,
                selected_sheets=selected,
                use_cache=use_cache,
                use_ai=use_ai,
            )
            send_json(self, 200, {"ok": True, "result": result})
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
