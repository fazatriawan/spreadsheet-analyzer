"""
Value Comparator: Bandingkan nilai numerik antar bulan.
Deteksi: perubahan drastis, nilai yang tidak pernah berubah, kolom selalu kosong.
"""
import pandas as pd
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_df(data: dict, sheet_name: str) -> pd.DataFrame:
    values = data.get("sheets", {}).get(sheet_name, {}).get("values", [])
    if not values:
        return pd.DataFrame()
    headers = values[0]
    rows = values[1:]
    max_c = max(len(headers), max((len(r) for r in rows), default=0))
    rows = [r + [""] * (max_c - len(r)) for r in rows]
    df = pd.DataFrame(
        rows,
        columns=headers[:max_c] + [f"C{i}" for i in range(len(headers), max_c)]
    )
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def compare_numeric_values(monthly_data: dict, sheet_name: str, threshold=20.0) -> dict:
    dfs = {
        lb: extract_df(d, sheet_name)
        for lb, d in monthly_data.items() if "error" not in d
    }
    dfs = {k: v for k, v in dfs.items() if not v.empty}
    if len(dfs) < 2:
        return {"error": f"Data tidak cukup untuk '{sheet_name}'"}

    labels = list(dfs.keys())
    result = {
        "sheet": sheet_name, "periods": labels,
        "drastic_changes": [], "always_same": [], "always_empty": [], "trend_data": {},
    }

    common = set(dfs[labels[0]].columns)
    for lb in labels[1:]:
        common &= set(dfs[lb].columns)

    for col in common:
        totals = {lb: dfs[lb][col].sum() for lb in labels}
        result["trend_data"][col] = totals
        vals = [v for v in totals.values() if pd.notna(v)]
        if not vals:
            result["always_empty"].append(col)
            continue
        if len(set(round(v, 4) for v in vals)) == 1:
            result["always_same"].append(col)
            continue
        for i in range(len(labels) - 1):
            a = totals.get(labels[i], 0) or 0
            b = totals.get(labels[i + 1], 0) or 0
            if a == 0:
                continue
            pct = abs((b - a) / a * 100)
            if pct > threshold:
                result["drastic_changes"].append({
                    "column": col, "from": labels[i], "to": labels[i + 1],
                    "value_from": round(a, 2), "value_to": round(b, 2),
                    "change_pct": round(pct, 1), "direction": "up" if b > a else "down"
                })
    return result
