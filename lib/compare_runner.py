"""Multi-spreadsheet comparison pipeline for API."""
import time

from comparator.schema_comparator import compare_schemas, extract_schema
from comparator.trend_analyzer import analyze_trends
from comparator.value_comparator import compare_numeric_values
from core.cache_manager import CacheManager
from core.reader import SpreadsheetReader


def _read_links_quiet(links: list[dict], use_cache: bool = True, force_refresh: bool = False) -> dict:
    reader = SpreadsheetReader()
    cache = CacheManager()
    results = {}

    for entry in links:
        url = entry.get("url", "").strip()
        label = entry.get("label") or url[:40]
        if not url:
            continue
        try:
            if use_cache and not force_refresh and cache.has_cache(url):
                data = cache.load(url)
            else:
                data = (
                    reader.read_from_excel(url)
                    if url.endswith((".xlsx", ".xls"))
                    else reader.read_from_url(url)
                )
                if use_cache:
                    cache.save(url, data, label)
            results[label or data.get("title", url[:40])] = data
        except Exception as e:
            results[label] = {"error": str(e)}

    return results


def run_comparison(
    links: list[dict],
    sheet_name: str | None = None,
    use_cache: bool = True,
    use_ai: bool = False,
    threshold: float = 20.0,
    force_refresh: bool = False,
) -> dict:
    t_start = time.time()
    monthly = _read_links_quiet(links, use_cache=use_cache, force_refresh=force_refresh)
    valid = {k: v for k, v in monthly.items() if "error" not in v}

    if len(valid) < 2:
        return {"error": "Minimal 2 spreadsheet valid diperlukan", "periods_loaded": list(monthly.keys())}

    schemas = {lb: extract_schema(d) for lb, d in valid.items()}
    schema_changes = compare_schemas(schemas)

    all_sheets = set()
    for d in valid.values():
        all_sheets.update(d.get("sheets", {}).keys())
    targets = [sheet_name] if sheet_name else sorted(all_sheets)

    value_comparisons = {}
    trends = {}
    for sn in targets:
        comp = compare_numeric_values(valid, sn, threshold)
        if "error" not in comp:
            value_comparisons[sn] = comp
            trends[sn] = analyze_trends(comp)

    ai_report = ""
    if use_ai:
        from core.ai_suggester import AISuggester

        all_drastic = [
            d for c in value_comparisons.values() for d in c.get("drastic_changes", [])
        ]
        all_trends = {
            col: t for sheet_t in trends.values() for col, t in sheet_t.items()
        }
        ai_report = AISuggester().analyze_multi_month(
            list(valid.keys()),
            all_drastic,
            schema_changes.get("summary", []),
            all_trends,
        )

    summary_stats = {
        "periods": list(valid.keys()),
        "sheets_compared": list(value_comparisons.keys()),
        "schema_changes": len(schema_changes.get("summary", [])),
        "drastic_changes": sum(
            len(c.get("drastic_changes", [])) for c in value_comparisons.values()
        ),
    }

    return {
        "summary": summary_stats,
        "schema": schema_changes,
        "values": value_comparisons,
        "trends": trends,
        "ai_report": ai_report,
        "errors": {k: v["error"] for k, v in monthly.items() if "error" in v},
        "elapsed_seconds": round(time.time() - t_start, 1),
    }
