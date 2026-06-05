"""
Trend Analyzer: Analisis tren dari nilai multi-bulan.
Output siap untuk chart Plotly + forecast sederhana.
"""
import numpy as np


def analyze_trends(value_comparison: dict) -> dict:
    trends = {}
    periods = value_comparison.get("periods", [])
    for col, monthly in value_comparison.get("trend_data", {}).items():
        vals = [monthly.get(p, 0) or 0 for p in periods]
        if len([v for v in vals if v]) < 2:
            continue
        try:
            slope, _ = np.polyfit(range(len(vals)), vals, 1)
        except Exception:
            slope = 0
        gr = [
            (vals[i] - vals[i - 1]) / abs(vals[i - 1]) * 100
            for i in range(1, len(vals)) if vals[i - 1]
        ]
        avg_gr = sum(gr) / len(gr) if gr else 0
        trends[col] = {
            "values": vals, "periods": periods, "slope": round(slope, 4),
            "direction": "Naik" if slope > 0 else ("Turun" if slope < 0 else "Stabil"),
            "avg_growth_pct": round(avg_gr, 2),
            "forecast_next": round(vals[-1] + slope, 2) if vals else 0,
            "volatility": round(float(np.std(vals)), 2),
        }
    return trends
