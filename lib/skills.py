"""
Spreadsheet Analyzer Skills — kemampuan analisis lanjutan.
Health score, breakdown per sheet, impact analysis, rekomendasi otomatis.
"""
from collections import Counter, defaultdict


def per_sheet_breakdown(analyses: dict) -> list[dict]:
    """Statistik formula per sheet."""
    by_sheet: dict[str, dict] = defaultdict(lambda: {
        "formula_count": 0, "warning_count": 0, "avg_complexity": 0,
        "max_complexity": 0, "categories": Counter(),
    })
    for addr, a in analyses.items():
        sheet = addr.split("!")[0] if "!" in addr else "Unknown"
        s = by_sheet[sheet]
        s["formula_count"] += 1
        score = getattr(a, "complexity_score", 0)
        s["avg_complexity"] += score
        s["max_complexity"] = max(s["max_complexity"], score)
        s["categories"][a.formula_category] += 1
        if getattr(a, "warnings", None):
            s["warning_count"] += 1

    result = []
    for name, s in sorted(by_sheet.items()):
        n = s["formula_count"] or 1
        result.append({
            "sheet": name,
            "formula_count": s["formula_count"],
            "warning_count": s["warning_count"],
            "avg_complexity": round(s["avg_complexity"] / n, 1),
            "max_complexity": s["max_complexity"],
            "top_category": s["categories"].most_common(1)[0][0] if s["categories"] else "—",
        })
    return result


def top_impact_cells(graph, limit=15) -> list[dict]:
    """Sel dengan fan-in tertinggi (banyak formula bergantung padanya)."""
    if graph is None or graph.number_of_nodes() == 0:
        return []
    scores = []
    for node in graph.nodes():
        if str(node).startswith("RANGE:"):
            continue
        indeg = graph.in_degree(node)
        if indeg >= 2:
            outdeg = graph.out_degree(node)
            scores.append({
                "cell": node,
                "dependents": indeg,
                "depends_on": outdeg,
                "impact_score": indeg * 2 + outdeg,
                "is_formula": graph.nodes[node].get("is_formula", False),
            })
    scores.sort(key=lambda x: x["impact_score"], reverse=True)
    return scores[:limit]


def compute_health_score(
    formula_count: int,
    warning_count: int,
    circular_count: int,
    missing_count: int,
    orphan_count: int,
    avg_complexity: float,
) -> dict:
    """
    Skor kesehatan spreadsheet 0–100.
    Semakin tinggi semakin sehat.
    """
    score = 100.0
    penalties = []

    if formula_count == 0:
        return {"score": 100, "grade": "A", "label": "Tidak ada formula", "penalties": []}

    warn_ratio = warning_count / formula_count
    if warn_ratio > 0.3:
        p = min(25, warn_ratio * 40)
        score -= p
        penalties.append({"reason": f"{warning_count} formula bermasalah ({warn_ratio:.0%})", "points": round(p, 1)})
    elif warn_ratio > 0.1:
        p = warn_ratio * 20
        score -= p
        penalties.append({"reason": f"{warning_count} warning terdeteksi", "points": round(p, 1)})

    if circular_count:
        p = min(30, circular_count * 5)
        score -= p
        penalties.append({"reason": f"{circular_count} circular reference", "points": round(p, 1)})

    if missing_count:
        p = min(20, missing_count * 0.5)
        score -= p
        penalties.append({"reason": f"{missing_count} missing reference", "points": round(p, 1)})

    if orphan_count > formula_count * 0.5:
        p = min(10, orphan_count * 0.05)
        score -= p
        penalties.append({"reason": f"{orphan_count} sel orphan (tidak terhubung)", "points": round(p, 1)})

    if avg_complexity > 20:
        p = min(15, (avg_complexity - 20) * 0.5)
        score -= p
        penalties.append({"reason": f"Kompleksitas rata-rata tinggi ({avg_complexity:.1f})", "points": round(p, 1)})

    score = max(0, min(100, round(score)))
    if score >= 85:
        grade, label = "A", "Sangat Sehat"
    elif score >= 70:
        grade, label = "B", "Baik"
    elif score >= 55:
        grade, label = "C", "Perlu Perhatian"
    elif score >= 40:
        grade, label = "D", "Bermasalah"
    else:
        grade, label = "F", "Kritis"

    return {"score": score, "grade": grade, "label": label, "penalties": penalties}


def rule_based_recommendations(
    analyses: dict,
    graph_summary: dict,
    sheet_breakdown: list[dict],
) -> list[dict]:
    """Rekomendasi otomatis tanpa AI."""
    recs = []
    circular = graph_summary.get("circular_refs") or []
    missing = graph_summary.get("missing_refs") or []

    if circular:
        recs.append({
            "priority": "critical",
            "title": "Perbaiki Circular Reference",
            "detail": f"Ditemukan {len(circular)} siklus. Circular ref menyebabkan hasil tidak deterministik.",
            "action": "Tinjau chain formula yang saling referensi dan pecah dengan sel perantara.",
        })

    if missing:
        recs.append({
            "priority": "high",
            "title": "Missing References",
            "detail": f"{len(missing)} sel direferensikan tapi tidak ada datanya.",
            "action": "Periksa typo nama sheet/sel atau tambahkan data yang hilang.",
        })

    volatile = sum(1 for a in analyses.values() if "INDIRECT" in getattr(a, "functions_used", []))
    if volatile > 5:
        recs.append({
            "priority": "medium",
            "title": "Kurangi INDIRECT/IMPORTRANGE",
            "detail": f"{volatile} formula memakai fungsi volatile.",
            "action": "Ganti dengan referensi langsung untuk performa lebih baik.",
        })

    hardcoded = sum(
        1 for a in analyses.values()
        if any("HARDCODED" in w for w in getattr(a, "warnings", []))
    )
    if hardcoded > 10:
        recs.append({
            "priority": "medium",
            "title": "Kurangi Hardcoded Values",
            "detail": f"{hardcoded} formula punya angka hardcoded.",
            "action": "Buat sheet 'Parameters' untuk konstanta yang sering dipakai.",
        })

    heavy = [s for s in sheet_breakdown if s["avg_complexity"] > 15 and s["formula_count"] > 100]
    for s in heavy[:3]:
        recs.append({
            "priority": "low",
            "title": f"Sheet '{s['sheet']}' Kompleks",
            "detail": f"Rata-rata kompleksitas {s['avg_complexity']}, {s['formula_count']} formula.",
            "action": "Pertimbangkan refactor: helper columns, named ranges, atau LAMBDA.",
        })

    lookup_heavy = sum(
        1 for a in analyses.values() if a.formula_category == "lookup/reference"
    )
    if lookup_heavy > formula_count_threshold(analyses, 0.4):
        recs.append({
            "priority": "low",
            "title": "Dominasi Formula Lookup",
            "detail": f"{lookup_heavy} formula lookup/reference.",
            "action": "Evaluasi apakah XLOOKUP/INDEX-MATCH bisa disederhanakan dengan FILTER/QUERY.",
        })

    return recs[:8]


def formula_count_threshold(analyses: dict, ratio: float) -> int:
    return int(len(analyses) * ratio)


def serialize_insights(gs: dict, limit: int = 20) -> dict:
    """Serialisasi circular/missing/orphan untuk API response."""
    circular = gs.get("circular_refs") or []
    missing = gs.get("missing_refs") or []
    orphan = gs.get("orphan_cells") or []

    return {
        "circular_refs": [
            {"cells": c if isinstance(c, list) else [c], "length": len(c) if isinstance(c, list) else 1}
            for c in circular[:limit]
        ],
        "missing_refs": missing[:limit],
        "orphan_cells": orphan[:limit],
    }


def build_skills_payload(analyses: dict, dg, gs: dict) -> dict:
    """Gabungkan semua skill analysis menjadi satu payload."""
    sheet_bd = per_sheet_breakdown(analyses)
    impact = top_impact_cells(dg.graph if dg else None)
    scores = [getattr(a, "complexity_score", 0) for a in analyses.values()]
    avg_cx = sum(scores) / len(scores) if scores else 0
    warn_count = sum(1 for a in analyses.values() if getattr(a, "warnings", None))

    health = compute_health_score(
        len(analyses), warn_count,
        len(gs.get("circular_refs") or []),
        len(gs.get("missing_refs") or []),
        len(gs.get("orphan_cells") or []),
        avg_cx,
    )
    insights = serialize_insights(gs)
    recommendations = rule_based_recommendations(analyses, gs, sheet_bd)

    return {
        "health": health,
        "sheet_breakdown": sheet_bd,
        "impact_cells": impact,
        "insights": insights,
        "recommendations": recommendations,
        "avg_complexity": round(avg_cx, 1),
    }
