import glob
import os
from http.server import BaseHTTPRequestHandler

from api._http import handle_options, send_json
from core.cache_manager import CacheManager
from lib.analysis_runner import _RESULT_CACHE_DIR


class handler(BaseHTTPRequestHandler):
    """POST /api/cache_clear — hapus cache."""

    def do_OPTIONS(self):
        handle_options(self)

    def do_POST(self):
        try:
            CacheManager().invalidate_all()
            for f in glob.glob(os.path.join(_RESULT_CACHE_DIR, "*_result.json")):
                os.remove(f)
            send_json(self, 200, {"ok": True, "message": "Cache dihapus"})
        except Exception as e:
            send_json(self, 500, {"error": str(e)})
