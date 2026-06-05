from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import load_sheets_info


class handler(BaseHTTPRequestHandler):
    """POST /api/load_sheets — muat daftar sheet dari URL."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        url = (body.get("url") or "").strip()
        use_cache = body.get("use_cache", True)

        if not url:
            send_json(self, 400, {"error": "URL wajib diisi"})
            return

        try:
            result = load_sheets_info(url, use_cache=use_cache)
            send_json(self, 200, {"ok": True, **result})
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
