from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.compare_runner import run_comparison


class handler(BaseHTTPRequestHandler):
    """POST /api/compare — bandingkan banyak spreadsheet (multi-bulan)."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        links = body.get("links") or []
        sheet_name = body.get("sheet_name")
        use_cache = body.get("use_cache", True)
        use_ai = body.get("use_ai", False)
        threshold = float(body.get("threshold", 20))
        force_refresh = body.get("force_refresh", False)

        if len(links) < 2:
            send_json(self, 400, {"error": "Minimal 2 link diperlukan"})
            return

        try:
            result = run_comparison(
                links,
                sheet_name=sheet_name or None,
                use_cache=use_cache,
                use_ai=use_ai,
                threshold=threshold,
                force_refresh=force_refresh,
            )
            if "error" in result and not result.get("summary"):
                send_json(self, 400, result)
            else:
                send_json(self, 200, {"ok": True, "result": result})
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
