from http.server import BaseHTTPRequestHandler

from api._http import handle_options, read_json, send_json
from lib.analysis_runner import chat_with_ai


class handler(BaseHTTPRequestHandler):
    """POST /api/chat — asisten AI kontekstual."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        body = read_json(self)
        question = (body.get("question") or "").strip()
        context = body.get("context")
        history = body.get("history") or []

        if not question:
            send_json(self, 400, {"error": "Pertanyaan wajib diisi"})
            return

        result = chat_with_ai(question, context, history)
        status = 200 if "answer" in result else 500
        send_json(self, status, {"ok": status == 200, **result})
