"""
Web UI untuk Spreadsheet Deep Analyzer.
Jalankan: python web_app.py
Buka: http://localhost:8050
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dash import Dash, html, dcc, Input, Output, State, callback_context, ALL, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import json, threading, os, hashlib, glob, time, collections, logging as _logging
from dotenv import load_dotenv

load_dotenv()

# ── In-memory log capture ─────────────────────────────────────────────────────
_LOG_BUFFER: collections.deque = collections.deque(maxlen=400)

class _UILogHandler(_logging.Handler):
    def emit(self, record):
        try:
            _LOG_BUFFER.append((record.levelno, record.name.split(".")[-1],
                                self.format(record)))
        except Exception:
            pass

_ui_log_handler = _UILogHandler()
_ui_log_handler.setFormatter(_logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
_logging.getLogger().addHandler(_ui_log_handler)

from core.cache_manager import CacheManager
from core.reader import SpreadsheetReader
from core.formula_parser import FormulaParser
from core.dependency_graph import DependencyGraph

_RESULT_CACHE_DIR = "./cache"

# ── Chart theme ───────────────────────────────────────────────────────────────
_CHART_COLORS = ["#818cf8","#34d399","#fbbf24","#fb7185","#a78bfa","#22d3ee","#f97316","#06b6d4"]
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#94a3b8", size=12),
    legend=dict(font=dict(color="#94a3b8"), bgcolor="rgba(0,0,0,0)"),
)
_MARGIN = dict(l=12, r=12, t=44, b=12)
_AXIS_STYLE = dict(
    gridcolor="rgba(255,255,255,0.05)",
    zerolinecolor="rgba(255,255,255,0.08)",
    tickfont=dict(color="#64748b", size=11),
    linecolor="rgba(255,255,255,0.06)",
)


# ── Result cache helpers ──────────────────────────────────────────────────────
def _result_cache_path(url: str) -> str:
    sheet_id = CacheManager._extract_sheet_id(url)
    k = hashlib.md5(sheet_id.encode()).hexdigest()[:12]
    return os.path.join(_RESULT_CACHE_DIR, f"{k}_result.json")


def _load_result_cache(url: str):
    p = _result_cache_path(url)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_result_cache(url: str, result: dict):
    os.makedirs(_RESULT_CACHE_DIR, exist_ok=True)
    p = _result_cache_path(url)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
)
app.title = "Spreadsheet Analyzer"

# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = dbc.Container([

    # ── Header ────────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div([
                    html.Span("SA", style={
                        "background": "linear-gradient(135deg,#6366f1,#22d3ee)",
                        "borderRadius": "10px", "padding": "6px 11px",
                        "fontWeight": "800", "fontSize": "0.85rem", "color": "#fff",
                        "letterSpacing": "0.04em", "marginRight": "14px",
                        "boxShadow": "0 4px 12px rgba(99,102,241,0.4)",
                    }),
                    html.H1("Spreadsheet Deep Analyzer", style={
                        "background": "linear-gradient(135deg,#818cf8 0%,#a78bfa 45%,#22d3ee 100%)",
                        "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                        "backgroundClip": "text", "fontWeight": "800",
                        "fontSize": "1.9rem", "letterSpacing": "-0.03em", "margin": "0",
                    }),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center",
                          "marginBottom": "8px"}),
                html.P("Analisis formula, dependency, dan struktur Google Sheets secara mendalam",
                       style={"color": "#64748b", "margin": "0", "fontSize": "0.9rem",
                              "textAlign": "center", "letterSpacing": "0.01em"}),
            ], style={"textAlign": "center", "padding": "36px 0 28px"}),
        ])
    ]),

    # ── Step 1: URL Input ─────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("🔗", style={
                            "position": "absolute", "left": "16px", "top": "50%",
                            "transform": "translateY(-50%)", "fontSize": "16px",
                            "pointerEvents": "none", "zIndex": "1",
                        }),
                        dbc.Input(
                            id="url-input",
                            placeholder="Paste URL Google Sheets di sini…",
                            type="text",
                            className="url-input",
                            style={"paddingLeft": "44px"},
                        ),
                    ], style={"position": "relative", "flex": "1"}),
                    html.Div([
                        dbc.Button([
                            html.Span("📋", style={"marginRight": "6px"}), "Baca Sheets"
                        ], id="load-sheets-btn", className="btn-analyze"),
                        dbc.Button("✕ Cache", id="clear-cache-btn", className="btn-clear",
                                   style={"marginLeft": "8px"}),
                    ], style={"display": "flex", "alignItems": "center", "flexShrink": "0"}),
                ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            ], className="glass-card", style={"padding": "20px 24px"}),
        ], width=12),
    ], className="mb-3"),

    # ── Step 2: Sheet Selector (muncul setelah sheets dimuat) ─────────────────
    html.Div(id="sheet-selector-container"),

    # ── Status ────────────────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col([
            html.Div(id="status-msg", className="text-center mb-2",
                     style={"color": "#64748b", "fontSize": "0.85rem", "minHeight": "28px"}),
            dbc.Progress(id="progress-bar", value=0,
                         style={"height": "6px", "display": "none",
                                "borderRadius": "100px", "background": "rgba(30,41,59,0.6)"},
                         className="mb-4"),
        ])
    ]),

    # ── Log Panel (live durante analisi) ─────────────────────────────────────
    html.Div(id="log-panel"),

    # ── Results ───────────────────────────────────────────────────────────────
    html.Div(id="results-container"),

    # ── Fix Panel ─────────────────────────────────────────────────────────────
    html.Div(id="fix-panel"),

    # ── Apply Controls (static, visibility controlled by callbacks) ────────────
    html.Div([
        html.Button(
            "✅ Terapkan Semua Perbaikan ke Spreadsheet",
            id="terapkan-all-btn", n_clicks=0,
            style={"display": "none"},
        ),
        html.Button(
            "✅ Terapkan Formula Ini ke Spreadsheet",
            id="terapkan-cur-btn", n_clicks=0,
            style={"display": "none"},
        ),
        html.Div(id="apply-status"),
    ], style={"marginTop": "8px"}),

    dcc.Store(id="analysis-store"),
    dcc.Store(id="sheets-store"),
    dcc.Store(id="fix-nav-store", data={"idx": 0}),
    dcc.Interval(id="interval", interval=500, n_intervals=0, disabled=True),
    dcc.Interval(id="fix-interval", interval=900, n_intervals=0, disabled=True),

], fluid=True, style={"maxWidth": "1420px", "padding": "0 24px 60px"})


# ── Callbacks ─────────────────────────────────────────────────────────────────
_analysis_state = {
    "running": False, "result": None, "error": None,
    "progress": 0, "base_status": "", "t_start": 0,
    "url": "",
}

_fix_state = {
    "running": False, "mode": "all",
    "items": [], "results": [], "error": None,
    "url": "", "current_cell": "",
}

def _fmt(secs):
    secs = int(secs)
    return f"{secs//60}m {secs%60}s" if secs >= 60 else f"{secs}s"

def _quick_formula_count(sheet_data: dict) -> int:
    return sum(
        1 for row in sheet_data.get("formulas", [])
        for cell in row
        if isinstance(cell, str) and cell.startswith("=")
    )


import re as _re

def _extract_cell_refs(formula: str) -> set:
    """Ekstrak semua cell references dari formula (contoh: A1, AP5, $D$10)."""
    return set(_re.findall(r'\$?[A-Z]+\$?\d+', formula.upper()))


def _simple_separator_fix(formula: str) -> str:
    """Ganti separator ',' → ';' di luar string literal. Fallback aman tanpa AI."""
    result, in_str, qc = [], False, None
    for ch in formula:
        if not in_str and ch in ('"', "'"):
            in_str, qc = True, ch
        elif in_str and ch == qc:
            in_str, qc = False, None
        elif not in_str and ch == ',':
            ch = ';'
        result.append(ch)
    return ''.join(result)


def _fix_one(formula: str, warnings: list) -> dict:
    """Panggil Claude untuk perbaiki satu formula. Return {fixed, explanation} atau {error}."""
    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return {"error": "ANTHROPIC_API_KEY tidak ditemukan di .env"}
        import anthropic as _ant
        client = _ant.Anthropic(api_key=key)
        masalah = "; ".join(w.split(":")[0] for w in warnings)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": (
                "Kamu adalah ahli formula spreadsheet Excel/Google Sheets dengan locale Indonesia.\n"
                "ATURAN WAJIB — PATUHI SEMUA:\n"
                "1. Gunakan titik koma (;) sebagai pemisah argumen, BUKAN koma (,)\n"
                "2. JANGAN PERNAH mengubah referensi sel (contoh: AP5, AO5, B2, $D$10, Sheet1!A1)\n"
                "3. JANGAN PERNAH mengubah nama sheet, nomor baris, atau huruf kolom\n"
                "4. Hanya perbaiki: ganti semua pemisah ',' menjadi ';', perbaiki ejaan nama fungsi (contoh: 'if' → 'IF'), atau seimbangkan tanda kurung\n"
                "Contoh:\n"
                "  Salah: =IFERROR(IF(AP5=0,0,(AP5/AO5)*100%),0)\n"
                "  Benar: =IFERROR(IF(AP5=0;0;(AP5/AO5)*100%);0)\n"
                "  ← hanya separator yang berubah, AP5 dan AO5 tetap sama!\n\n"
                f"Formula yang perlu diperbaiki:\n{formula}\n\n"
                f"Masalah terdeteksi: {masalah}\n\n"
                "Balas HANYA dengan format ini (tidak ada teks lain):\n"
                "FORMULA: =<formula yang sudah diperbaiki>\n"
                "ALASAN: <penjelasan singkat 1-2 kalimat>"
            )}],
        )
        text = resp.content[0].text.strip()
        fixed = reason = ""
        for line in text.splitlines():
            if line.upper().startswith("FORMULA:"):
                fixed = line.split(":", 1)[1].strip()
            elif line.upper().startswith("ALASAN:"):
                reason = line.split(":", 1)[1].strip()
        if not fixed:
            for line in text.splitlines():
                if line.strip().startswith("="):
                    fixed = line.strip()
                    break
        if not fixed:
            return {"error": f"AI tidak menghasilkan formula valid. Respons: {text[:100]}"}
        # Validasi: AI tidak boleh mengubah cell references
        orig_refs = _extract_cell_refs(formula)
        fixed_refs = _extract_cell_refs(fixed)
        if orig_refs and orig_refs != fixed_refs:
            # AI mengubah cell refs — gunakan fallback separator fix
            safe = _simple_separator_fix(formula)
            return {
                "fixed": safe,
                "explanation": f"AI mengubah referensi sel (diblokir). Perbaikan aman: hanya separator diganti. Cek manual jika ada masalah lain.",
            }
        return {"fixed": fixed, "explanation": reason}
    except Exception as e:
        return {"error": str(e)[:160]}


def _apply_fix_to_sheet(url: str, cell_addr: str, fixed_formula: str) -> dict:
    """Tulis formula yang sudah diperbaiki langsung ke Google Sheets."""
    try:
        import gspread as _gs, re as _re
        from google.oauth2.service_account import Credentials as _Creds
        from config import GOOGLE_SERVICE_ACCOUNT_FILE
        WRITE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = _Creds.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=WRITE_SCOPES)
        gc = _gs.authorize(creds)
        sid = _re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if not sid:
            return {"error": "URL spreadsheet tidak valid"}
        sp = gc.open_by_key(sid.group(1))
        if "!" not in cell_addr:
            return {"error": f"Format cell tidak valid (butuh Sheet!Cell): {cell_addr}"}
        sheet_name, cell_ref = cell_addr.split("!", 1)
        ws = sp.worksheet(sheet_name)
        ws.update_acell(cell_ref, fixed_formula)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)[:200]}


# ── Estimation helpers ────────────────────────────────────────────────────────
def _estimate_times(total_formulas: int) -> dict:
    """Perkiraan waktu dalam detik berdasarkan jumlah formula."""
    t_parse   = max(1.0, total_formulas / 5_000)          # ~5k formula/detik
    t_graph   = max(1.5, total_formulas * 2 / 130_000) + 1  # SCC pada 2× nodes
    t_total   = t_parse + t_graph + 2                     # overhead koneksi/IO
    w_est     = max(1, int(total_formulas * 0.12))         # ~12% formula punya warning
    t_fix_all = w_est * 1.8                                # ~1.8s per fix (Haiku)
    return {
        "analysis": t_total,
        "fix_all": t_fix_all,
        "warnings_est": w_est,
    }

def _perf_tier(total_formulas: int, n_sheets: int):
    """Returns (emoji, pesan, hex_color)."""
    avg = total_formulas / max(1, n_sheets)
    if total_formulas == 0:
        return "⚪", "Pilih setidaknya satu sheet berformula", "#475569"
    if total_formulas <= 2_000:
        return "🟢", "Ringan — analisis selesai dalam hitungan detik", "#34d399"
    if total_formulas <= 8_000:
        safe = max(2, round(8_000 / max(1, avg)))
        note = f" · disarankan max {safe} sheet" if n_sheets > safe else ""
        return "🟡", f"Sedang — beberapa menit{note}", "#fbbf24"
    if total_formulas <= 25_000:
        safe = max(2, round(8_000 / max(1, avg)))
        return "🟠", f"Berat — pilih {safe} sheet terpenting untuk kinerja optimal", "#fb923c"
    safe = max(2, round(5_000 / max(1, avg)))
    return "🔴", f"Sangat berat — sangat disarankan max {safe} sheet utama", "#fb7185"

def _build_selection_summary(sheets_info: list, sel_names: set) -> html.Div:
    """Panel estimasi waktu berdasarkan sheet yang dipilih."""
    sel = [s for s in sheets_info if s["name"] in sel_names]
    n_sel  = len(sel)
    total_f = sum(s["count"] for s in sel)

    if n_sel == 0:
        return html.Div("Belum ada sheet dipilih.", style={
            "color": "#475569", "fontSize": "0.8rem", "padding": "8px 0",
        })

    est = _estimate_times(total_f)
    emoji, tier_msg, tier_color = _perf_tier(total_f, n_sel)

    def stat_pill(label, value, color):
        return html.Div([
            html.Div(label, style={
                "fontSize": "0.62rem", "color": "#64748b",
                "textTransform": "uppercase", "letterSpacing": "0.07em",
                "marginBottom": "3px", "fontWeight": "600",
            }),
            html.Div(value, style={
                "fontSize": "0.9rem", "color": color,
                "fontWeight": "700", "fontVariantNumeric": "tabular-nums",
            }),
        ], style={
            "padding": "8px 16px", "background": "rgba(0,0,0,0.25)",
            "border": f"1px solid {color}22",
            "borderRadius": "10px", "textAlign": "center", "minWidth": "100px",
        })

    return html.Div([
        # Ringkasan seleksi
        html.Div([
            html.Span(f"{n_sel} sheet", style={"color": "#94a3b8", "fontWeight": "600",
                                                "fontSize": "0.82rem"}),
            html.Span(" · ", style={"color": "#334155", "margin": "0 4px"}),
            html.Span(f"{total_f:,} formula", style={"color": "#64748b", "fontSize": "0.82rem"}),
            html.Span(" · ", style={"color": "#334155", "margin": "0 4px"}),
            html.Span(f"~{est['warnings_est']:,} perkiraan warning",
                      style={"color": "#64748b", "fontSize": "0.78rem"}),
        ], style={"marginBottom": "10px", "display": "flex", "flexWrap": "wrap",
                  "alignItems": "center"}),

        # Estimasi waktu
        html.Div([
            stat_pill("Analisis", _fmt(est["analysis"]), "#818cf8"),
            stat_pill("Fix Semua", _fmt(est["fix_all"]), "#34d399"),
            stat_pill("Fix 1×1", f"{est['warnings_est']} langkah", "#22d3ee"),
        ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap",
                  "marginBottom": "10px"}),

        # Tier rekomendasi
        html.Div([
            html.Span(emoji + " ", style={"marginRight": "5px", "fontSize": "0.95rem"}),
            html.Span(tier_msg, style={"color": tier_color, "fontSize": "0.8rem",
                                        "fontWeight": "600"}),
        ], style={
            "background": f"{tier_color}10",
            "border": f"1px solid {tier_color}30",
            "borderRadius": "8px", "padding": "7px 14px",
            "display": "inline-flex", "alignItems": "center",
        }),
    ])


# ── Step 1: Load sheet list ───────────────────────────────────────────────────
@app.callback(
    Output("sheets-store", "data"),
    Output("sheet-selector-container", "children"),
    Input("load-sheets-btn", "n_clicks"),
    Input("clear-cache-btn", "n_clicks"),
    State("url-input", "value"),
    prevent_initial_call=True,
)
def load_sheets(load_clicks, clear_clicks, url):
    ctx = callback_context.triggered[0]["prop_id"]

    if "clear-cache-btn" in ctx:
        CacheManager().invalidate_all()
        for f in glob.glob(os.path.join(_RESULT_CACHE_DIR, "*_result.json")):
            os.remove(f)
        return None, html.Div()

    if not url or not url.strip():
        return None, _error_box("Masukkan URL Google Sheets terlebih dahulu.")

    u = url.strip()
    cache = CacheManager()

    if cache.has_cache(u):
        data = cache.load(u)
    else:
        try:
            data = SpreadsheetReader().read_from_url(u)
            cache.save(u, data)
        except Exception as e:
            return None, _error_box(f"Gagal fetch: {e}")

    sheets_info = [
        {"name": name, "count": _quick_formula_count(sd)}
        for name, sd in data["sheets"].items()
    ]

    return sheets_info, _render_sheet_selector(sheets_info, data["title"])


def _render_sheet_selector(sheets_info, title):
    total_formula = sum(s["count"] for s in sheets_info)
    non_empty = sum(1 for s in sheets_info if s["count"] > 0)

    def badge_meta(count):
        t = _estimate_times(count)["analysis"] if count else 0
        hint = f" ~{_fmt(t)}" if count else ""
        warn = " ⚠" if count >= 3000 else ""
        if count == 0:   return "#475569", "rgba(71,85,105,0.15)", ""
        if count < 500:  return "#22d3ee", "rgba(34,211,238,0.12)", hint
        if count < 3000: return "#34d399", "rgba(52,211,153,0.12)", hint
        return "#fbbf24", "rgba(251,191,36,0.12)", hint + warn

    sheet_items = []
    for s in sheets_info:
        col, bg, hint = badge_meta(s["count"])
        sheet_items.append(
            html.Label([
                dbc.Checkbox(
                    id={"type": "sheet-check", "index": s["name"]},
                    value=s["count"] > 0,
                    style={"marginRight": "8px", "accentColor": "#6366f1"},
                ),
                html.Span(s["name"], style={
                    "fontSize": "0.83rem", "color": "#cbd5e1",
                    "marginRight": "6px", "flex": "1",
                    "overflow": "hidden", "textOverflow": "ellipsis",
                    "whiteSpace": "nowrap",
                }),
                html.Span([
                    html.Span(f"{s['count']:,}", style={
                        "fontSize": "0.72rem", "fontWeight": "600", "color": col,
                    }),
                    html.Span(hint, style={"fontSize": "0.66rem", "color": "#64748b"}),
                ], style={
                    "background": bg, "border": f"1px solid {col}33",
                    "borderRadius": "100px", "padding": "1px 9px",
                    "flexShrink": "0", "display": "inline-flex", "alignItems": "center",
                }),
            ], style={
                "display": "flex", "alignItems": "center",
                "padding": "7px 10px", "borderRadius": "8px", "cursor": "pointer",
                "transition": "background 0.15s",
                "background": "rgba(30,41,59,0.3)", "marginBottom": "3px",
            })
        )

    # Split into 3 columns
    n = len(sheet_items)
    col_size = max(1, (n + 2) // 3)
    cols = [sheet_items[i:i+col_size] for i in range(0, n, col_size)]
    while len(cols) < 3:
        cols.append([])

    default_sel = {s["name"] for s in sheets_info if s["count"] > 0}

    return html.Div([
        # Header
        html.Div([
            html.Div([
                html.Div(className="section-dot"),
                html.Span("Pilih Sheet yang Akan Dianalisis", className="section-title"),
                html.Span(f"{len(sheets_info)} sheet · {total_formula:,} formula total",
                          style={"color": "#64748b", "fontSize": "0.78rem", "marginLeft": "10px"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                      "marginBottom": "12px"}),
            # Shortcut buttons
            html.Div([
                html.Button("Pilih Semua", id="sel-all-btn", n_clicks=0, style=_shortcut_style("#818cf8")),
                html.Button("Bersihkan", id="sel-none-btn", n_clicks=0, style=_shortcut_style("#64748b")),
                html.Button(f"Non-Kosong ({non_empty})", id="sel-nonempty-btn", n_clicks=0,
                            style=_shortcut_style("#34d399")),
            ], style={"display": "flex", "gap": "8px", "marginBottom": "14px", "flexWrap": "wrap"}),
        ]),

        # Sheet grid
        html.Div([
            html.Div(col, style={"flex": "1", "minWidth": "220px"})
            for col in cols
        ], style={"display": "flex", "gap": "10px", "marginBottom": "14px"}),

        # Estimasi waktu (diupdate oleh callback saat pilihan berubah)
        html.Div([
            html.Div([
                html.Div(className="section-dot", style={"background": "#fbbf24"}),
                html.Span("⏱ Estimasi Waktu", style={
                    "fontWeight": "600", "color": "#94a3b8", "fontSize": "0.78rem",
                }),
                html.Span("— diperbarui saat pilihan berubah", style={
                    "color": "#475569", "fontSize": "0.68rem", "marginLeft": "6px",
                }),
            ], style={"display": "flex", "alignItems": "center", "gap": "5px",
                      "marginBottom": "10px"}),
            html.Div(
                id="selection-summary",
                children=_build_selection_summary(sheets_info, default_sel),
            ),
        ], style={
            "background": "rgba(0,0,0,0.2)", "borderRadius": "12px",
            "padding": "14px 16px", "marginBottom": "14px",
            "border": "1px solid rgba(255,255,255,0.05)",
        }),

        # Bottom bar: options + analyze button
        html.Div([
            dbc.Checklist(
                id="options-check",
                options=[
                    {"label": " Gunakan cache", "value": "cache"},
                    {"label": " AI Report (butuh API key)", "value": "ai"},
                ],
                value=["cache"],
                inline=True,
                className="custom-check",
                style={"flex": "1"},
            ),
            dbc.Button([
                html.Span("⚡", style={"marginRight": "6px"}), "Mulai Analisis"
            ], id="analyze-btn", className="btn-analyze"),
        ], style={"display": "flex", "alignItems": "center", "gap": "16px",
                  "borderTop": "1px solid rgba(255,255,255,0.06)", "paddingTop": "14px"}),
    ], className="glass-card animate-in mb-3",
       style={"padding": "20px 24px", "borderColor": "rgba(129,140,248,0.2)"})


def _shortcut_style(color):
    return {
        "background": f"{color}18", "color": color,
        "border": f"1px solid {color}40", "borderRadius": "8px",
        "padding": "5px 12px", "fontSize": "0.78rem", "fontWeight": "600",
        "cursor": "pointer", "transition": "all 0.15s",
    }

def _error_box(msg):
    return html.Div(msg, style={
        "color": "#fb7185", "background": "rgba(251,113,133,0.08)",
        "border": "1px solid rgba(251,113,133,0.2)",
        "borderRadius": "12px", "padding": "12px 16px",
        "fontSize": "0.85rem", "marginBottom": "12px",
    })


# ── Shortcut button callbacks ─────────────────────────────────────────────────
@app.callback(
    Output({"type": "sheet-check", "index": ALL}, "value"),
    Input("sel-all-btn", "n_clicks"),
    Input("sel-none-btn", "n_clicks"),
    Input("sel-nonempty-btn", "n_clicks"),
    State({"type": "sheet-check", "index": ALL}, "id"),
    State("sheets-store", "data"),
    prevent_initial_call=True,
)
def handle_shortcuts(all_clicks, none_clicks, nonempty_clicks, ids, sheets_info):
    if not ids:
        return []
    ctx = callback_context.triggered[0]["prop_id"]
    if "sel-all-btn" in ctx:
        return [True] * len(ids)
    elif "sel-none-btn" in ctx:
        return [False] * len(ids)
    elif "sel-nonempty-btn" in ctx:
        nonempty = {s["name"] for s in (sheets_info or []) if s.get("count", 0) > 0}
        return [id_obj["index"] in nonempty for id_obj in ids]
    return [True] * len(ids)


@app.callback(
    Output("selection-summary", "children"),
    Input({"type": "sheet-check", "index": ALL}, "value"),
    State({"type": "sheet-check", "index": ALL}, "id"),
    State("sheets-store", "data"),
    prevent_initial_call=True,
)
def update_selection_summary(values, ids, sheets_info):
    if not sheets_info or not ids:
        raise PreventUpdate
    sel = {id_obj["index"] for val, id_obj in zip(values or [], ids or []) if val}
    return _build_selection_summary(sheets_info, sel)


# ── Step 2: Start analysis ────────────────────────────────────────────────────
@app.callback(
    Output("analysis-store", "data"),
    Output("interval", "disabled"),
    Output("status-msg", "children"),
    Input("analyze-btn", "n_clicks"),
    State("url-input", "value"),
    State("options-check", "value"),
    State("sheets-store", "data"),
    State({"type": "sheet-check", "index": ALL}, "value"),
    State({"type": "sheet-check", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def start_analysis(n_clicks, url, options, sheets_info, check_values, check_ids):
    if not url or not url.strip():
        return None, True, "Masukkan URL terlebih dahulu."

    # Build selected set from actual checkbox states
    sel_names = set()
    for val, id_obj in zip(check_values or [], check_ids or []):
        if val:
            sel_names.add(id_obj["index"])
    if not sel_names and sheets_info:
        # Fallback: non-empty sheets
        sel_names = {s["name"] for s in sheets_info if s.get("count", 0) > 0}

    use_cache = "cache" in (options or [])
    use_ai = "ai" in (options or [])

    t_start = time.time()
    _LOG_BUFFER.clear()
    _fix_state.update({"running": False, "mode": "all", "items": [], "results": [], "error": None, "url": ""})
    _analysis_state.update({
        "running": True, "result": None, "error": None,
        "progress": 5, "base_status": "Memulai analisis…", "t_start": t_start,
        "url": url.strip(),
    })

    def _set(status, progress):
        _analysis_state["base_status"] = status
        _analysis_state["progress"] = progress

    # Capture for thread closure
    _sel_names = sel_names

    def run():
        try:
            u = url.strip()

            # Result cache only if all sheets selected and no AI
            all_selected = not _sel_names or not sheets_info
            if use_cache and not use_ai and all_selected:
                cached_result = _load_result_cache(u)
                if cached_result:
                    _analysis_state["result"] = cached_result
                    _analysis_state["progress"] = 100
                    _analysis_state["base_status"] = "Selesai (result cache)"
                    _analysis_state["running"] = False
                    return

            _set("Membaca spreadsheet…", 10)
            cache = CacheManager()

            if use_cache and cache.has_cache(u):
                data = cache.load(u)
                _set(f"Cache hit: {data['title']}", 20)
            else:
                _set("Fetching dari Google Sheets — santai, bisa 2–5 menit…", 12)
                data = SpreadsheetReader().read_from_url(u)
                cache.save(u, data)

            # Filter ke sheet yang dipilih
            if _sel_names:
                filtered = {k: v for k, v in data["sheets"].items() if k in _sel_names}
                if filtered:
                    data = {**data, "sheets": filtered}

            n_sheets = len(data["sheets"])
            _set(f"Parsing {n_sheets} sheet…", 30)

            parser = FormulaParser(data.get("named_ranges", []))
            all_a = {}
            sheets = list(data["sheets"].items())
            t_parse = time.time()
            for i, (sn, sd) in enumerate(sheets):
                all_a.update(parser.parse_sheet(sd, sn))
                pct = 30 + int((i / n_sheets) * 35)
                done_ratio = (i + 1) / n_sheets
                eta = (time.time() - t_parse) / done_ratio * (1 - done_ratio) if done_ratio > 0 else 0
                _analysis_state["progress"] = pct
                _analysis_state["base_status"] = (
                    f"Parsing sheet {i+1}/{n_sheets}: {sn}"
                    + (f" · estimasi {_fmt(eta)} lagi" if eta > 1 else "")
                )

            _set(f"Building dependency graph ({len(all_a):,} formula)…", 67)
            dg = DependencyGraph()
            dg.build(data, all_a)

            n_nodes = dg.graph.number_of_nodes()
            _set(
                f"Circular ref check — {n_nodes:,} nodes via SCC"
                f" (estimasi ~{max(2, n_nodes // 60000)}s)…",
                78,
            )
            gs = dg.get_summary()

            ai_report = ""
            if use_ai:
                _set("Generating AI report — Claude sedang menulis…", 94)
                from core.ai_suggester import AISuggester
                ai_report = AISuggester().generate_improvement_report(all_a, gs)

            _set("Menyiapkan tampilan…", 97)
            cats = {}
            for a in all_a.values():
                cats[a.formula_category] = cats.get(a.formula_category, 0) + 1

            top_complex = sorted(
                [(k, v.complexity_score, v.formula_category, v.raw_formula[:80])
                 for k, v in all_a.items()],
                key=lambda x: x[1], reverse=True
            )[:30]

            warned = [
                {"cell": k, "warnings": v.warnings, "formula": v.raw_formula}
                for k, v in all_a.items() if v.warnings
            ][:50]

            result = {
                "title": data["title"],
                "sheet_count": len(data["sheets"]),
                "sheet_names": list(data["sheets"].keys()),
                "formula_count": len(all_a),
                "categories": cats,
                "top_complex": top_complex,
                "warnings": warned,
                "graph_summary": {k: v for k, v in gs.items()
                                  if k not in ("circular_refs", "missing_refs", "orphan_cells")},
                "missing_count": len(gs.get("missing_refs", [])),
                "orphan_count": len(gs.get("orphan_cells", [])),
                "circular_count": len(gs.get("circular_refs", [])),
                "ai_report": ai_report,
                "complexity_scores": [v.complexity_score for v in all_a.values()],
            }

            if not use_ai and all_selected:
                _save_result_cache(u, result)

            total = time.time() - t_start
            _analysis_state["result"] = result
            _analysis_state["progress"] = 100
            _analysis_state["base_status"] = f"Selesai dalam {_fmt(total)}"
            _analysis_state["running"] = False

        except Exception as e:
            elapsed = time.time() - t_start
            _analysis_state["error"] = str(e)
            _analysis_state["running"] = False
            _analysis_state["base_status"] = f"Error setelah {_fmt(elapsed)}: {e}"

    threading.Thread(target=run, daemon=True).start()
    return None, False, "Analisis dimulai…"


@app.callback(
    Output("results-container", "children"),
    Output("progress-bar", "value"),
    Output("progress-bar", "style"),
    Output("interval", "disabled", allow_duplicate=True),
    Output("status-msg", "children", allow_duplicate=True),
    Output("log-panel", "children"),
    Input("interval", "n_intervals"),
    prevent_initial_call=True,
)
def update_progress(n):
    state = _analysis_state
    progress = state["progress"]
    base_status = state["base_status"]
    running = state["running"]
    error = state["error"]
    result = state["result"]

    bar_style = {
        "height": "6px", "borderRadius": "100px",
        "background": "rgba(30,41,59,0.6)",
        "display": "block" if (running or progress > 0) else "none",
    }

    log_panel = _build_log_panel(show=running or bool(error))

    if error:
        err_div = html.Div([
            html.Div([
                html.Span("⚠", style={"fontSize": "1.4rem", "marginRight": "12px"}),
                html.Div([
                    html.P("Terjadi Error", style={"fontWeight": "700", "margin": "0 0 4px",
                                                    "color": "#fb7185"}),
                    html.P(str(error), style={"margin": "0", "fontSize": "0.85rem",
                                               "color": "#94a3b8", "fontFamily": "monospace"}),
                ]),
            ], style={"display": "flex", "alignItems": "flex-start"}),
        ], className="glass-card animate-in",
           style={"borderColor": "rgba(251,113,133,0.25)", "padding": "20px 24px",
                  "background": "rgba(251,113,133,0.08)"})
        return (err_div, 0, {"display": "none"}, True,
                html.Span(base_status, style={"color": "#fb7185"}), log_panel)

    if result and not running:
        return (build_results(result), 100, {"display": "none"}, True,
                html.Span(base_status, style={"color": "#34d399", "fontSize": "0.85rem"}),
                html.Div())

    if running:
        elapsed = time.time() - state.get("t_start", time.time())
        status_el = html.Div([
            html.Span(className="status-dot"),
            html.Span(f"{progress}%", style={
                "color": "#818cf8", "fontWeight": "700",
                "marginRight": "6px", "fontVariantNumeric": "tabular-nums",
            }),
            html.Span(f"{base_status}  [{_fmt(int(elapsed))}]", style={"color": "#94a3b8"}),
        ], className="status-pill", style={"display": "inline-flex"})
    else:
        status_el = html.Span(base_status, style={"color": "#64748b", "fontSize": "0.83rem"})

    return [], progress, bar_style, False, status_el, log_panel


# ── Log panel builder ─────────────────────────────────────────────────────────
def _build_log_panel(show=True, max_lines=60):
    if not show or not _LOG_BUFFER:
        return html.Div()

    lines = list(reversed(list(_LOG_BUFFER)[-max_lines:]))  # newest first

    def _line_color(levelno):
        if levelno >= _logging.ERROR:   return "#fb7185"
        if levelno >= _logging.WARNING: return "#fbbf24"
        return "#64748b"

    def _line_weight(levelno):
        return "600" if levelno >= _logging.WARNING else "400"

    rows = [
        html.Div(msg, style={
            "color": _line_color(lvl),
            "fontWeight": _line_weight(lvl),
            "fontFamily": "'Cascadia Code','Fira Code','Consolas',monospace",
            "fontSize": "0.72rem",
            "lineHeight": "1.6",
            "whiteSpace": "pre-wrap",
            "wordBreak": "break-all",
        })
        for lvl, _name, msg in lines
    ]

    return html.Div([
        html.Div([
            html.Span("📋", style={"marginRight": "6px"}),
            html.Span("Log Pipeline", style={
                "fontWeight": "600", "color": "#94a3b8", "fontSize": "0.8rem",
            }),
            html.Span(f"{len(lines)} baris", style={
                "color": "#475569", "fontSize": "0.7rem", "marginLeft": "8px",
            }),
        ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center"}),
        html.Div(
            rows,
            id="log-scroll",
            style={
                "background": "rgba(0,0,0,0.35)",
                "border": "1px solid rgba(255,255,255,0.06)",
                "borderRadius": "8px",
                "padding": "10px 14px",
                "maxHeight": "220px",
                "overflowY": "auto",
            },
        ),
    ], className="glass-card mb-3",
       style={"padding": "16px 20px", "borderColor": "rgba(99,102,241,0.15)"})


# ── Fix panel builder ─────────────────────────────────────────────────────────
def _build_fix_panel_ui(mode="all", nav_idx=0):
    items = _fix_state["items"]
    results = _fix_state["results"]
    running = _fix_state["running"]
    total = len(items)
    done = len(results)
    if not items:
        return html.Div()

    def _formula_box(text, color="#94a3b8", bg="rgba(0,0,0,0.3)", border="rgba(255,255,255,0.06)"):
        return html.Div(text or "—", style={
            "fontFamily": "'Cascadia Code','Fira Code','Consolas',monospace",
            "fontSize": "0.78rem", "color": color,
            "background": bg, "border": f"1px solid {border}",
            "borderRadius": "6px", "padding": "8px 12px",
            "wordBreak": "break-all", "lineHeight": "1.5",
        })

    def _fix_card(i):
        item = items[i]
        res = results[i] if i < done else None
        cell_short = item["cell"].split("!")[-1] if "!" in item["cell"] else item["cell"]
        sheet_name = item["cell"].split("!")[0] if "!" in item["cell"] else ""

        header = html.Div([
            html.Span(cell_short, style={
                "fontFamily": "monospace", "color": "#a5b4fc",
                "fontWeight": "700", "fontSize": "0.9rem", "marginRight": "8px",
            }),
            html.Span(sheet_name, style={
                "color": "#475569", "fontSize": "0.72rem", "marginRight": "10px",
            }),
            *[html.Span(w.split(":")[0], className="warn-badge",
                        style={"marginRight": "3px"}) for w in item["warnings"]],
        ], style={"marginBottom": "10px", "display": "flex", "flexWrap": "wrap",
                  "alignItems": "center"})

        orig = html.Div([
            html.Div("Formula asli:", style={"color": "#64748b", "fontSize": "0.7rem",
                                              "marginBottom": "3px", "fontWeight": "600",
                                              "textTransform": "uppercase", "letterSpacing": "0.05em"}),
            _formula_box(item["formula"]),
        ], style={"marginBottom": "10px"})

        if res is None:
            fix_content = html.Div([
                html.Div([
                    html.Span(className="status-dot", style={"marginRight": "8px"}),
                    html.Span("Sedang diproses AI…", style={"color": "#64748b", "fontSize": "0.83rem"}),
                ], style={"display": "flex", "alignItems": "center",
                          "padding": "10px 12px",
                          "background": "rgba(0,0,0,0.2)",
                          "borderRadius": "6px", "border": "1px solid rgba(255,255,255,0.05)"}),
            ])
        elif "error" in res:
            fix_content = html.Div([
                html.Div("Hasil perbaikan:", style={"color": "#64748b", "fontSize": "0.7rem",
                                                     "marginBottom": "3px", "fontWeight": "600",
                                                     "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                html.Div([
                    html.Span("⚠ ", style={"color": "#fbbf24"}),
                    html.Span(res["error"], style={"color": "#fbbf24", "fontSize": "0.8rem"}),
                ], style={"padding": "8px 12px", "background": "rgba(251,191,36,0.08)",
                          "border": "1px solid rgba(251,191,36,0.2)", "borderRadius": "6px"}),
            ])
        else:
            fix_content = html.Div([
                html.Div("Hasil perbaikan:", style={"color": "#34d399", "fontSize": "0.7rem",
                                                     "marginBottom": "3px", "fontWeight": "600",
                                                     "textTransform": "uppercase", "letterSpacing": "0.05em"}),
                _formula_box(res["fixed"], color="#34d399",
                             bg="rgba(52,211,153,0.08)", border="rgba(52,211,153,0.25)"),
                html.Div(res.get("explanation", ""), style={
                    "color": "#64748b", "fontSize": "0.78rem",
                    "fontStyle": "italic", "marginTop": "8px",
                }) if res.get("explanation") else html.Div(),
            ])

        return html.Div([header, orig, fix_content],
                        style={"padding": "14px 0" if mode == "all" else "0"})

    def _status_badge():
        current_cell = _fix_state.get("current_cell", "")
        if not running:
            txt = "Selesai"
        elif current_cell:
            cell_short = current_cell.split("!")[-1] if "!" in current_cell else current_cell
            sheet_short = current_cell.split("!")[0] if "!" in current_cell else ""
            txt = f"Mengerjakan {cell_short} ({sheet_short}) — {done}/{total}"
        else:
            txt = f"Memproses {done}/{total}…"
        color = "#34d399" if not running else "#fbbf24"
        bg = "rgba(52,211,153,0.1)" if not running else "rgba(251,191,36,0.1)"
        border = "rgba(52,211,153,0.25)" if not running else "rgba(251,191,36,0.25)"
        return html.Span(txt, style={
            "color": color, "fontSize": "0.72rem", "fontWeight": "600",
            "background": bg, "border": f"1px solid {border}",
            "borderRadius": "100px", "padding": "2px 10px",
        })

    if mode == "step":
        nav_idx = max(0, min(nav_idx, total - 1))
        nav_bar = html.Div([
            html.Button("← Sebelumnya", id="fix-prev-btn", n_clicks=0,
                        disabled=nav_idx == 0,
                        style={"background": "rgba(99,102,241,0.15)",
                               "border": "1px solid rgba(99,102,241,0.3)",
                               "color": "#818cf8" if nav_idx > 0 else "#475569",
                               "borderRadius": "8px", "padding": "6px 14px",
                               "fontSize": "0.78rem", "fontWeight": "600", "cursor": "pointer"}),
            html.Span(f"{nav_idx+1}  /  {total}", style={
                "color": "#94a3b8", "fontSize": "0.85rem",
                "fontVariantNumeric": "tabular-nums",
            }),
            html.Button("Berikutnya →", id="fix-next-btn", n_clicks=0,
                        disabled=nav_idx >= total - 1,
                        style={"background": "rgba(99,102,241,0.15)",
                               "border": "1px solid rgba(99,102,241,0.3)",
                               "color": "#818cf8" if nav_idx < total - 1 else "#475569",
                               "borderRadius": "8px", "padding": "6px 14px",
                               "fontSize": "0.78rem", "fontWeight": "600", "cursor": "pointer"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                  "marginTop": "18px", "paddingTop": "14px",
                  "borderTop": "1px solid rgba(255,255,255,0.06)"})
        content = html.Div([_fix_card(nav_idx), nav_bar])

    else:  # all mode
        divider = html.Hr(style={"borderColor": "rgba(255,255,255,0.05)", "margin": "0"})
        cards = []
        for i in range(total):
            cards.append(_fix_card(i))
            if i < total - 1:
                cards.append(divider)
        content = html.Div(cards, style={"maxHeight": "560px", "overflowY": "auto"})

    success_count = sum(1 for r in results if "fixed" in r)
    done_banner = html.Div() if running or not success_count else html.Div([
        html.Span("✅", style={"fontSize": "1rem"}),
        html.Span(
            f"{success_count} formula siap diterapkan — klik tombol hijau di bawah panel ini",
            style={"fontSize": "0.78rem", "fontWeight": "600", "color": "#34d399"},
        ),
    ], style={
        "display": "flex", "alignItems": "center", "gap": "8px",
        "background": "rgba(52,211,153,0.08)", "border": "1px solid rgba(52,211,153,0.2)",
        "borderRadius": "8px", "padding": "8px 14px", "marginBottom": "14px",
    })

    title = "Perbaikan Otomatis Semua" if mode == "all" else "Perbaikan Satu Persatu"
    return html.Div([
        html.Div([
            html.Div(className="section-dot"),
            html.Span(title, className="section-title"),
            _status_badge(),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                  "marginBottom": "12px"}),
        done_banner,
        content,
    ], className="glass-card animate-in mb-3",
       style={"padding": "20px 24px", "borderColor": "rgba(52,211,153,0.2)"})


# ── Fix callbacks ─────────────────────────────────────────────────────────────

_SHOW_BTN = {
    "display": "inline-flex", "alignItems": "center", "gap": "8px",
    "background": "linear-gradient(135deg,rgba(52,211,153,0.18),rgba(16,185,129,0.12))",
    "border": "1px solid rgba(52,211,153,0.35)",
    "color": "#34d399", "borderRadius": "10px", "padding": "8px 18px",
    "fontSize": "0.82rem", "fontWeight": "700", "cursor": "pointer",
    "marginTop": "4px",
}
_HIDE_BTN = {"display": "none"}


@app.callback(
    Output("fix-panel", "children"),
    Output("fix-interval", "disabled"),
    Output("fix-nav-store", "data"),
    Output("terapkan-all-btn", "style"),
    Output("terapkan-cur-btn", "style"),
    Output("apply-status", "children", allow_duplicate=True),
    Input("fix-all-btn", "n_clicks"),
    Input("fix-step-btn", "n_clicks"),
    prevent_initial_call=True,
)
def start_fix(all_n, step_n):
    if _fix_state.get("running"):
        raise PreventUpdate  # cegah double-run
    ctx = callback_context.triggered[0]["prop_id"]
    mode = "step" if "fix-step-btn" in ctx else "all"

    result = _analysis_state.get("result")
    if not result:
        return _error_box("Tidak ada hasil analisis."), True, {"idx": 0}, _HIDE_BTN, _HIDE_BTN, html.Div()
    warned = result.get("warnings", [])
    if not warned:
        return _error_box("Tidak ada formula warning untuk dibenahi."), True, {"idx": 0}, _HIDE_BTN, _HIDE_BTN, html.Div()

    _fix_state.update({
        "running": True, "mode": mode,
        "items": warned, "results": [], "error": None,
        "url": _analysis_state.get("url", ""),
        "current_cell": "",
    })
    _items = warned

    def run():
        for i, w in enumerate(_items):
            _fix_state["current_cell"] = w["cell"]
            res = _fix_one(w["formula"], w["warnings"])
            _fix_state["results"].append({"cell": w["cell"], "original": w["formula"], **res})
        _fix_state["current_cell"] = ""
        _fix_state["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return _build_fix_panel_ui(mode, 0), False, {"idx": 0}, _HIDE_BTN, _HIDE_BTN, html.Div()


@app.callback(
    Output("fix-panel", "children", allow_duplicate=True),
    Output("fix-interval", "disabled", allow_duplicate=True),
    Output("terapkan-all-btn", "style", allow_duplicate=True),
    Output("terapkan-cur-btn", "style", allow_duplicate=True),
    Input("fix-interval", "n_intervals"),
    Input("fix-nav-store", "data"),
    prevent_initial_call=True,
)
def poll_fix(n, nav):
    if not _fix_state["items"]:
        raise PreventUpdate
    mode = _fix_state["mode"]
    idx = (nav or {}).get("idx", 0)
    still_running = _fix_state["running"]
    results = _fix_state["results"]
    success_count = sum(1 for r in results if "fixed" in r)

    if not still_running and success_count > 0:
        all_style = {**_SHOW_BTN, "display": "inline-flex"} if mode == "all" else _HIDE_BTN
        cur_style = {**_SHOW_BTN, "display": "inline-flex"} if mode == "step" else _HIDE_BTN
    else:
        all_style = _HIDE_BTN
        cur_style = _HIDE_BTN

    return _build_fix_panel_ui(mode, idx), not still_running, all_style, cur_style


@app.callback(
    Output("apply-status", "children"),
    Input("terapkan-all-btn", "n_clicks"),
    Input("terapkan-cur-btn", "n_clicks"),
    State("fix-nav-store", "data"),
    prevent_initial_call=True,
)
def do_apply(all_n, cur_n, nav):
    if not (all_n or cur_n):
        raise PreventUpdate
    url = _fix_state.get("url", "")
    if not url:
        return _error_box("URL spreadsheet tidak tersedia. Jalankan analisis ulang.")
    results = _fix_state.get("results", [])
    if not results:
        return _error_box("Tidak ada hasil perbaikan yang tersedia.")
    ctx = callback_context.triggered[0]["prop_id"]
    if "terapkan-all-btn" in ctx:
        applied, errors = 0, []
        for r in results:
            if "fixed" in r:
                res = _apply_fix_to_sheet(url, r["cell"], r["fixed"])
                if "ok" in res:
                    applied += 1
                else:
                    errors.append(f"{r['cell']}: {res['error']}")
        msg_parts = [f"✅ {applied} formula berhasil diterapkan ke spreadsheet."]
        if errors:
            msg_parts.append(f"⚠ {len(errors)} gagal: {', '.join(errors[:3])}")
        return html.Div(" | ".join(msg_parts),
                        style={"color": "#34d399", "fontSize": "0.83rem", "padding": "8px 0",
                               "fontWeight": "600"})
    else:
        idx = (nav or {}).get("idx", 0)
        if idx >= len(results):
            return _error_box("Formula ini belum selesai diproses AI.")
        r = results[idx]
        if "error" in r:
            return _error_box(f"Formula ini masih bermasalah: {r['error']}")
        res = _apply_fix_to_sheet(url, r["cell"], r["fixed"])
        if "ok" in res:
            return html.Div(
                f"✅ {r['cell']} berhasil diterapkan ke spreadsheet.",
                style={"color": "#34d399", "fontSize": "0.83rem", "padding": "8px 0",
                       "fontWeight": "600"})
        return _error_box(f"Gagal menulis ke spreadsheet: {res['error']}")


@app.callback(
    Output("fix-nav-store", "data", allow_duplicate=True),
    Input("fix-prev-btn", "n_clicks"),
    Input("fix-next-btn", "n_clicks"),
    State("fix-nav-store", "data"),
    prevent_initial_call=True,
)
def nav_fix(prev_n, next_n, nav):
    if not (prev_n or next_n):
        raise PreventUpdate
    idx = (nav or {}).get("idx", 0)
    total = len(_fix_state["items"])
    ctx = callback_context.triggered[0]["prop_id"]
    if "fix-prev-btn" in ctx:
        idx = max(0, idx - 1)
    elif "fix-next-btn" in ctx:
        idx = min(total - 1, idx + 1)
    return {"idx": idx}


# ── Result builder ────────────────────────────────────────────────────────────
def build_results(r):
    cats = r["categories"]
    top = r["top_complex"]
    warned = r["warnings"]
    scores = r["complexity_scores"]
    gs = r["graph_summary"]

    # ── Banner ────────────────────────────────────────────────────────────────
    banner = html.Div([
        html.Div([
            html.H4(r["title"], style={
                "margin": "0 0 6px", "fontWeight": "700", "color": "#f1f5f9",
                "fontSize": "1.15rem",
            }),
            html.Div([
                _pill(f"{r['sheet_count']} sheet", "#818cf8", "rgba(99,102,241,0.12)"),
                _pill(f"{r['formula_count']:,} formula", "#34d399", "rgba(52,211,153,0.12)"),
                _pill(f"{gs.get('total_nodes',0):,} nodes", "#a78bfa", "rgba(167,139,250,0.12)"),
                _pill(f"{gs.get('total_edges',0):,} edges", "#22d3ee", "rgba(34,211,238,0.12)"),
            ], style={"display": "flex", "flexWrap": "wrap", "gap": "6px"}),
        ]),
    ], className="result-banner animate-in mb-4"),

    # ── Stat Cards ────────────────────────────────────────────────────────────
    cards = dbc.Row([
        dbc.Col(_stat_card("🗂", "Total Sheet", r["sheet_count"], "indigo"), width=6, md=2),
        dbc.Col(_stat_card("⚙", "Total Formula", f"{r['formula_count']:,}", "emerald"), width=6, md=2),
        dbc.Col(_stat_card("⚠", "Formula Warning", len(warned), "amber"), width=6, md=2),
        dbc.Col(_stat_card("🔗", "Missing Refs", r["missing_count"], "rose"), width=6, md=2),
        dbc.Col(_stat_card("🔄", "Circular Refs", r["circular_count"], "rose"), width=6, md=2),
        dbc.Col(_stat_card("🏝", "Orphan Cells", r["orphan_count"], "indigo"), width=6, md=2),
    ], className="mb-4 g-3")

    # ── Pie chart: formula categories ─────────────────────────────────────────
    # Filter kategori kosong dan gabung kategori sangat kecil (<1%) ke "Lainnya"
    total_formula = sum(cats.values()) or 1
    threshold = max(1, int(total_formula * 0.005))  # < 0.5% digabung
    pie_data = {k: v for k, v in cats.items() if v >= threshold}
    other = sum(v for k, v in cats.items() if v < threshold)
    if other > 0:
        pie_data["Lainnya"] = pie_data.get("Lainnya", 0) + other

    fig_pie = go.Figure(go.Pie(
        labels=list(pie_data.keys()),
        values=list(pie_data.values()),
        hole=0.52,
        marker=dict(colors=_CHART_COLORS, line=dict(color="rgba(15,23,42,0.8)", width=2)),
        textfont=dict(color="#f1f5f9", size=11),
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>%{value:,} formula (%{percent})<extra></extra>",
        sort=True,
    ))
    fig_pie.update_layout(
        **_CHART_LAYOUT,
        margin=_MARGIN,
        title=dict(text="Kategori Formula", font=dict(color="#f1f5f9", size=14, weight='bold'), x=0.02),
        height=360,
        showlegend=False,
        annotations=[dict(text=f"<b>{len(cats)}</b><br><span style='font-size:10px'>tipe</span>",
                          x=0.5, y=0.5, font_size=20, showarrow=False,
                          font_color="#f1f5f9")],
    )

    # ── Histogram: complexity distribution ────────────────────────────────────
    # Pisahkan outlier ekstrem agar distribusi utama terlihat jelas
    clean_scores = [s for s in scores if s > 0]
    p95 = sorted(clean_scores)[int(len(clean_scores) * 0.95)] if clean_scores else 1
    main_scores = [s for s in clean_scores if s <= p95 * 1.5]
    outlier_count = len(clean_scores) - len(main_scores)

    fig_hist = go.Figure()
    if main_scores:
        fig_hist.add_trace(go.Histogram(
            x=main_scores, nbinsx=40,
            name="Formula",
            marker=dict(
                color=main_scores,
                colorscale=[[0, "#34d399"], [0.5, "#fbbf24"], [1, "#fb7185"]],
                line=dict(color="rgba(15,23,42,0.4)", width=0.3),
            ),
            opacity=0.85,
            hovertemplate="Score: %{x:.0f}<br>Jumlah: %{y}<extra></extra>",
        ))
    subtitle = f" ({outlier_count} outlier ekstrem disembunyikan)" if outlier_count else ""
    fig_hist.update_layout(
        **_CHART_LAYOUT,
        margin=_MARGIN,
        title=dict(text=f"Distribusi Kompleksitas{subtitle}",
                   font=dict(color="#f1f5f9", size=14, weight='bold'), x=0.02),
        height=360,
        xaxis=dict(title="Complexity Score", title_font=dict(color="#64748b", size=11), **_AXIS_STYLE),
        yaxis=dict(title="Jumlah Formula", title_font=dict(color="#64748b", size=11), **_AXIS_STYLE),
        bargap=0.05,
    )

    charts_row = dbc.Row([
        dbc.Col(_chart_card(fig_pie, "animate-in animate-in-2"), width=12, md=6),
        dbc.Col(_chart_card(fig_hist, "animate-in animate-in-3"), width=12, md=6),
    ], className="mb-3 g-3")

    # ── Bar chart: top complex formulas ───────────────────────────────────────
    # Sanitasi label: potong nama sheet yang sangat panjang, tambahkan sheet prefix
    top20 = top[:20]
    bar_vals = [t[1] for t in top20]
    max_val = max(bar_vals) if bar_vals else 1

    def _bar_label(addr, max_len=30):
        parts = addr.split("!")
        if len(parts) == 2:
            sheet, cell = parts
            sheet = sheet[:14] + "…" if len(sheet) > 15 else sheet
            return f"{sheet}!{cell}"
        return addr[:max_len]

    fig_bar = go.Figure(go.Bar(
        y=[_bar_label(t[0]) for t in top20],
        x=bar_vals,
        orientation="h",
        marker=dict(
            color=bar_vals,
            colorscale=[[0, "#34d399"], [0.4, "#fbbf24"], [1, "#fb7185"]],
            showscale=True,
            colorbar=dict(
                tickfont=dict(color="#64748b", size=10), outlinewidth=0,
                len=0.7, thickness=12,
                title=dict(text="Score", font=dict(color="#64748b", size=11)),
            ),
            line=dict(color="rgba(15,23,42,0.4)", width=0.5),
        ),
        customdata=[(t[2], t[3][:60]) for t in top20],
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Score: <b>%{x}</b><br>"
            "Kategori: %{customdata[0]}<br>"
            "Formula: %{customdata[1]}<extra></extra>"
        ),
    ))
    fig_bar.update_layout(
        **_CHART_LAYOUT,
        title=dict(text="Top 20 Formula Terkompleks", font=dict(color="#f1f5f9", size=14, weight='bold'), x=0.02),
        height=max(400, len(top20) * 24 + 80),
        margin=dict(l=12, r=90, t=44, b=12),
        xaxis=dict(**_AXIS_STYLE, title="Complexity Score",
                   title_font=dict(color="#64748b", size=11)),
        yaxis=dict(autorange="reversed", tickfont=dict(color="#a5b4fc", size=10),
                   gridcolor="rgba(255,255,255,0.04)"),
    )
    bar_section = _chart_card(fig_bar, "animate-in animate-in-4", height_auto=True)

    # ── Sheet badges ──────────────────────────────────────────────────────────
    sheet_section = html.Div([
        _section_header("Daftar Sheet", f"{r['sheet_count']} sheet"),
        html.Div([
            html.Span(s, className="sheet-badge") for s in r["sheet_names"]
        ], style={"marginTop": "14px"}),
    ], className="glass-card animate-in animate-in-5 mb-3",
       style={"padding": "20px 24px"})

    # ── Warnings table ────────────────────────────────────────────────────────
    if warned:
        warn_rows = [
            html.Tr([
                html.Td(html.Span(w["cell"].split("!")[-1], className="cell-label")),
                html.Td(html.Span(w["formula"], className="formula-text")),
                html.Td(html.Div(
                    [html.Span(wt.split(":")[0], className="warn-badge") for wt in w["warnings"]],
                    style={"display": "flex", "flexWrap": "wrap", "gap": "2px"}
                )),
            ]) for w in warned[:20]
        ]
        warn_body = html.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Cell"), html.Th("Formula"), html.Th("Warning"),
                ]), className="warn-table"),
                html.Tbody(warn_rows),
            ],
            className="warn-table w-100",
            style={"borderCollapse": "separate", "borderSpacing": "0 4px"}
        )
    else:
        warn_body = html.Div([
            html.Span("✓", style={"color": "#34d399", "fontSize": "1.2rem", "marginRight": "8px"}),
            html.Span("Tidak ada formula dengan warning!", style={"color": "#34d399"}),
        ], style={"display": "flex", "alignItems": "center", "padding": "8px 0"})

    fix_buttons = html.Div([
        dbc.Button("🔧 Benahi Semua", id="fix-all-btn", n_clicks=0, style={
            "fontSize": "0.78rem", "padding": "5px 14px",
            "background": "linear-gradient(135deg,rgba(52,211,153,0.2),rgba(34,211,238,0.15))",
            "border": "1px solid rgba(52,211,153,0.35)", "color": "#34d399",
            "borderRadius": "8px", "fontWeight": "600",
        }),
        dbc.Button("📋 Satu Persatu", id="fix-step-btn", n_clicks=0, style={
            "fontSize": "0.78rem", "padding": "5px 14px", "marginLeft": "8px",
            "background": "rgba(129,140,248,0.12)",
            "border": "1px solid rgba(129,140,248,0.3)", "color": "#818cf8",
            "borderRadius": "8px", "fontWeight": "600",
        }),
    ], style={"display": "flex", "flexShrink": "0"}) if warned else html.Div()

    warn_section = html.Div([
        html.Div([
            _section_header("Formula dengan Warning",
                            f"{len(warned)} formula" if warned else "Bersih"),
            fix_buttons,
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "marginBottom": "14px"}),
        html.Div(warn_body, style={"overflowX": "auto"}),
    ], className="glass-card animate-in animate-in-6 mb-3",
       style={"padding": "20px 24px"})

    # ── AI Report ─────────────────────────────────────────────────────────────
    ai_section = html.Div()
    if r.get("ai_report"):
        ai_section = html.Div([
            _section_header("AI Report", "powered by Claude"),
            dcc.Markdown(
                r["ai_report"],
                dangerously_allow_html=True,
                className="ai-section",
                style={"marginTop": "14px"},
            ),
        ], className="glass-card animate-in mb-3",
           style={"padding": "20px 24px",
                  "borderColor": "rgba(129,140,248,0.2)",
                  "background": "rgba(99,102,241,0.06)"})

    return html.Div([
        *banner,
        cards,
        charts_row,
        bar_section,
        html.Div(style={"marginBottom": "12px"}),
        sheet_section,
        warn_section,
        ai_section,
    ])


# ── UI helpers ────────────────────────────────────────────────────────────────
def _pill(text, color, bg):
    return html.Span(text, style={
        "background": bg, "color": color,
        "border": f"1px solid {color}33",
        "borderRadius": "100px", "padding": "3px 12px",
        "fontSize": "0.78rem", "fontWeight": "600",
    })


def _stat_card(icon, label, value, accent):
    return html.Div([
        html.Div(icon, className=f"stat-icon {accent}"),
        html.Div(str(value), className=f"stat-value {accent}"),
        html.Div(label, className="stat-label"),
    ], className=f"stat-card {accent} animate-in")


def _chart_card(fig, extra_class="", height_auto=False):
    return html.Div([
        dcc.Graph(figure=fig, config={"displayModeBar": False},
                  style={"height": "100%" if height_auto else "auto"}),
    ], className=f"glass-card {extra_class} mb-3",
       style={"padding": "8px"})


def _section_header(title, badge_text=""):
    return html.Div([
        html.Div(className="section-dot"),
        html.Span(title, className="section-title"),
        html.Span(badge_text, style={
            "background": "rgba(99,102,241,0.12)",
            "color": "#818cf8", "border": "1px solid rgba(129,140,248,0.2)",
            "borderRadius": "100px", "padding": "2px 10px",
            "fontSize": "0.72rem", "fontWeight": "600", "marginLeft": "8px",
        }) if badge_text else html.Span(),
    ], style={"display": "flex", "alignItems": "center", "gap": "8px"})


if __name__ == "__main__":
    print("Buka browser: http://localhost:8050")
    app.run(debug=False, host="0.0.0.0", port=8050)
