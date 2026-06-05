"""
Reader: Baca Google Sheets atau Excel.
Return format standar: { id, title, url, sheets: {name: {values, formulas, ...}} }
"""
import gspread, openpyxl, re, os, time
from google.oauth2.service_account import Credentials
from gspread.utils import ValueRenderOption
from gspread.exceptions import APIError
from utils.logger import get_logger

logger = get_logger(__name__)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _load_google_client():
    try:
        from lib.credentials import get_credentials
        creds = get_credentials(scopes=SCOPES)
    except ImportError:
        from config import GOOGLE_SERVICE_ACCOUNT_FILE
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


class SpreadsheetReader:
    def __init__(self):
        self.gc = None
        try:
            self.gc = _load_google_client()
            logger.info("Google Sheets client ready")
        except Exception as e:
            logger.warning(f"Google client gagal: {e}")

    def read_from_url(self, url: str) -> dict:
        if not self.gc:
            raise ConnectionError("Google client tidak tersedia. Pastikan service_account.json ada.")
        sid = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if not sid:
            raise ValueError(f"URL tidak valid: {url}")
        sid = sid.group(1)
        sp = self.gc.open_by_key(sid)
        result = {"id": sid, "title": sp.title, "url": url, "sheets": {}, "named_ranges": []}
        try:
            result["named_ranges"] = sp.list_named_ranges()
        except Exception:
            pass
        for ws in sp.worksheets():
            logger.info(f"  Sheet: {ws.title}")
            result["sheets"][ws.title] = self._read_worksheet(ws)
            time.sleep(1.2)
        return result

    def _read_worksheet(self, ws, retries=3) -> dict:
        for attempt in range(retries):
            try:
                values = ws.get_all_values(value_render_option=ValueRenderOption.unformatted)
                time.sleep(0.5)
                formulas = ws.get_all_values(value_render_option=ValueRenderOption.formula)
                return {
                    "id": ws.id, "row_count": ws.row_count, "col_count": ws.col_count,
                    "values": values, "formulas": formulas,
                }
            except APIError as e:
                if "429" in str(e) and attempt < retries - 1:
                    wait = (attempt + 1) * 15
                    logger.warning(f"  Rate limit, tunggu {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        return {"id": ws.id, "row_count": 0, "col_count": 0, "values": [], "formulas": []}

    def read_from_excel(self, path: str) -> dict:
        wb = openpyxl.load_workbook(path, data_only=False)
        wb_v = openpyxl.load_workbook(path, data_only=True)
        result = {
            "id": os.path.basename(path), "title": os.path.basename(path),
            "url": path, "sheets": {}, "named_ranges": []
        }
        for name in wb.sheetnames:
            ws, ws_v = wb[name], wb_v[name]
            formulas, values = [], []
            for row in ws.iter_rows():
                formulas.append([c.value or "" for c in row])
                values.append([ws_v.cell(c.row, c.column).value or "" for c in row])
            result["sheets"][name] = {
                "id": name, "row_count": ws.max_row, "col_count": ws.max_column,
                "values": values, "formulas": formulas,
            }
        return result
