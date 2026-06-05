"""Shared analysis pipeline for web_app and Vercel API."""
import hashlib
import json
import os
import re
import time

from core.cache_manager import CacheManager
from core.dependency_graph import DependencyGraph
from core.formula_parser import FormulaParser
from core.reader import SpreadsheetReader
from lib.skills import build_skills_payload

_RESULT_CACHE_DIR = os.environ.get("RESULT_CACHE_DIR") or (
    "/tmp/cache" if os.environ.get("VERCEL") else "./cache"
)


def result_cache_path(url: str) -> str:
    sheet_id = CacheManager._extract_sheet_id(url)
    key = hashlib.md5(sheet_id.encode()).hexdigest()[:12]
    return os.path.join(_RESULT_CACHE_DIR, f"{key}_result.json")


def load_result_cache(url: str):
    path = result_cache_path(url)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_result_cache(url: str, result: dict):
    os.makedirs(_RESULT_CACHE_DIR, exist_ok=True)
    path = result_cache_path(url)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


def quick_formula_count(sheet_data: dict) -> int:
    return sum(
        1
        for row in sheet_data.get("formulas", [])
        for cell in row
        if isinstance(cell, str) and cell.startswith("=")
    )


def load_sheets_info(url: str, use_cache: bool = True) -> dict:
    url = url.strip()
    cache = CacheManager()
    if use_cache and cache.has_cache(url):
        data = cache.load(url)
    else:
        data = SpreadsheetReader().read_from_url(url)
        cache.save(url, data)

    sheets_info = [
        {"name": name, "count": quick_formula_count(sd)}
        for name, sd in data["sheets"].items()
    ]
    return {"title": data["title"], "sheets": sheets_info}


def run_analysis(
    url: str,
    selected_sheets: list[str] | None = None,
    use_cache: bool = True,
    use_ai: bool = False,
) -> dict:
    url = url.strip()
    t_start = time.time()
    all_selected = not selected_sheets

    if use_cache and not use_ai and all_selected:
        cached = load_result_cache(url)
        if cached:
            cached["elapsed_seconds"] = round(time.time() - t_start, 1)
            cached["from_cache"] = True
            return cached

    cache = CacheManager()
    if use_cache and cache.has_cache(url):
        data = cache.load(url)
    else:
        data = SpreadsheetReader().read_from_url(url)
        cache.save(url, data)

    if selected_sheets:
        filtered = {k: v for k, v in data["sheets"].items() if k in selected_sheets}
        if filtered:
            data = {**data, "sheets": filtered}

    parser = FormulaParser(data.get("named_ranges", []))
    all_a = {}
    for sn, sd in data["sheets"].items():
        all_a.update(parser.parse_sheet(sd, sn))

    dg = DependencyGraph()
    dg.build(data, all_a)
    gs = dg.get_summary()

    warned = [
        {"cell": k, "warnings": v.warnings, "formula": v.raw_formula}
        for k, v in all_a.items()
        if v.warnings
    ][:50]

    ai_report = ""
    audit_report = ""
    if use_ai:
        from core.ai_suggester import AISuggester

        suggester = AISuggester()
        ai_report = suggester.generate_improvement_report(all_a, gs)

    skills = build_skills_payload(all_a, dg, gs)

    if use_ai and skills.get("health"):
        try:
            from core.ai_suggester import AISuggester

            audit_report = AISuggester().audit_quick(
                skills["health"],
                skills.get("recommendations", []),
                warned[:10],
            )
        except Exception:
            audit_report = ""

    cats = {}
    for a in all_a.values():
        cats[a.formula_category] = cats.get(a.formula_category, 0) + 1

    top_complex = sorted(
        [
            (k, v.complexity_score, v.formula_category, v.raw_formula[:80])
            for k, v in all_a.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )[:30]

    result = {
        "title": data["title"],
        "sheet_count": len(data["sheets"]),
        "sheet_names": list(data["sheets"].keys()),
        "formula_count": len(all_a),
        "categories": cats,
        "top_complex": top_complex,
        "warnings": warned,
        "graph_summary": {
            k: v
            for k, v in gs.items()
            if k not in ("circular_refs", "missing_refs", "orphan_cells")
        },
        "missing_count": len(gs.get("missing_refs", [])),
        "orphan_count": len(gs.get("orphan_cells", [])),
        "circular_count": len(gs.get("circular_refs", [])),
        "ai_report": ai_report,
        "audit_report": audit_report,
        "complexity_scores": [v.complexity_score for v in all_a.values()],
        "skills": skills,
        "elapsed_seconds": round(time.time() - t_start, 1),
        "from_cache": False,
    }

    if not use_ai and all_selected:
        save_result_cache(url, result)

    return result


def extract_cell_refs(formula: str) -> set:
    return set(re.findall(r"\$?[A-Z]+\$?\d+", formula.upper()))


def simple_separator_fix(formula: str) -> str:
    result, in_str, qc = [], False, None
    for ch in formula:
        if not in_str and ch in ('"', "'"):
            in_str, qc = True, ch
        elif in_str and ch == qc:
            in_str, qc = False, None
        elif not in_str and ch == ",":
            ch = ";"
        result.append(ch)
    return "".join(result)


def fix_one_formula(formula: str, warnings: list) -> dict:
    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return {"error": "ANTHROPIC_API_KEY tidak ditemukan"}
        import anthropic as ant

        client = ant.Anthropic(api_key=key)
        masalah = "; ".join(w.split(":")[0] for w in warnings)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Kamu adalah ahli formula spreadsheet Excel/Google Sheets dengan locale Indonesia.\n"
                        "ATURAN WAJIB — PATUHI SEMUA:\n"
                        "1. Gunakan titik koma (;) sebagai pemisah argumen, BUKAN koma (,)\n"
                        "2. JANGAN PERNAH mengubah referensi sel\n"
                        "3. Hanya perbaiki separator, ejaan fungsi, atau kurung\n\n"
                        f"Formula: {formula}\nMasalah: {masalah}\n\n"
                        "Balas HANYA:\nFORMULA: =<fixed>\nALASAN: <penjelasan>"
                    ),
                }
            ],
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
            return {"error": f"AI tidak menghasilkan formula valid: {text[:100]}"}
        orig_refs = extract_cell_refs(formula)
        fixed_refs = extract_cell_refs(fixed)
        if orig_refs and orig_refs != fixed_refs:
            safe = simple_separator_fix(formula)
            return {
                "fixed": safe,
                "explanation": "AI mengubah referensi sel (diblokir). Hanya separator diganti.",
            }
        return {"fixed": fixed, "explanation": reason}
    except Exception as e:
        return {"error": str(e)[:160]}


def apply_fix_to_sheet(url: str, cell_addr: str, fixed_formula: str) -> dict:
    try:
        import gspread as gs

        from lib.credentials import get_credentials

        creds = get_credentials()
        gc = gs.authorize(creds)
        sid = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
        if not sid:
            return {"error": "URL spreadsheet tidak valid"}
        sp = gc.open_by_key(sid.group(1))
        if "!" not in cell_addr:
            return {"error": f"Format cell tidak valid: {cell_addr}"}
        sheet_name, cell_ref = cell_addr.split("!", 1)
        ws = sp.worksheet(sheet_name)
        ws.update_acell(cell_ref, fixed_formula)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)[:200]}


def explain_formula_ai(formula: str, cell: str = "", context: dict | None = None) -> dict:
    try:
        from core.ai_suggester import AISuggester

        text = AISuggester().explain_formula(formula, cell, context)
        return {"explanation": text}
    except Exception as e:
        return {"error": str(e)[:200]}


def chat_with_ai(question: str, context: dict | None = None, history: list | None = None) -> dict:
    try:
        from core.ai_suggester import AISuggester

        answer = AISuggester().chat(question, context, history)
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)[:200]}
