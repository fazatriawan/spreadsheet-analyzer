"""
Schema Comparator: Bandingkan STRUKTUR spreadsheet antar bulan.
Deteksi: kolom baru/hilang, sheet baru/hilang, perubahan header.
"""
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_schema(data: dict) -> dict:
    schema = {}
    for sname, sheet in data.get("sheets", {}).items():
        values = sheet.get("values", [])
        headers = [str(h).strip() for h in (values[0] if values else [])]
        schema[sname] = {
            "headers": headers,
            "row_count": len(values),
            "col_count": max((len(r) for r in values), default=0),
        }
    return schema


def compare_schemas(schemas: dict) -> dict:
    labels = list(schemas.keys())
    changes = {
        "new_sheets": {}, "removed_sheets": {},
        "column_changes": {}, "row_count_trend": {}, "summary": []
    }
    for label, schema in schemas.items():
        for sname, info in schema.items():
            changes["row_count_trend"].setdefault(sname, {})[label] = info["row_count"]

    for i in range(len(labels) - 1):
        la, lb = labels[i], labels[i + 1]
        sa, sb = schemas[la], schemas[lb]
        pair = f"{la} -> {lb}"
        new_s = set(sb) - set(sa)
        rem_s = set(sa) - set(sb)
        if new_s:
            changes["new_sheets"][pair] = list(new_s)
            changes["summary"].append(f"Sheet baru ({pair}): {', '.join(new_s)}")
        if rem_s:
            changes["removed_sheets"][pair] = list(rem_s)
            changes["summary"].append(f"Sheet hilang ({pair}): {', '.join(rem_s)}")
        col_ch = {}
        for sname in set(sa) & set(sb):
            added = set(sb[sname]["headers"]) - set(sa[sname]["headers"])
            removed = set(sa[sname]["headers"]) - set(sb[sname]["headers"])
            if added or removed:
                col_ch[sname] = {"added_columns": list(added), "removed_columns": list(removed)}
                if added:
                    changes["summary"].append(f"Kolom baru ({pair}) [{sname}]: {', '.join(added)}")
                if removed:
                    changes["summary"].append(f"Kolom hilang ({pair}) [{sname}]: {', '.join(removed)}")
        if col_ch:
            changes["column_changes"][pair] = col_ch
    return changes
