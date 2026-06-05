"""
Comparison Dashboard: Dashboard interaktif multi-bulan.
Output: file HTML dengan trend charts, alert table, schema changes.
"""
import plotly.graph_objects as go
from plotly.offline import plot
import os
from config import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_comparison_dashboard(
    value_comparisons, schema_changes, trends,
    ai_report="", output_name="comparison"
) -> str:
    os.makedirs(f"{OUTPUT_DIR}/comparison", exist_ok=True)
    path = f"{OUTPUT_DIR}/comparison/{output_name}.html"

    sections = []

    total_periods = max(
        (len(c.get("periods", [])) for c in value_comparisons.values() if "error" not in c),
        default=0
    )
    total_drastic = sum(
        len(c.get("drastic_changes", [])) for c in value_comparisons.values() if "error" not in c
    )
    sections.append(f"""
    <div class="cards">
      <div class="card"><div class="num">{total_periods}</div><div class="lbl">Periode</div></div>
      <div class="card"><div class="num">{len(value_comparisons)}</div><div class="lbl">Sheet</div></div>
      <div class="card {'warn-card' if total_drastic else ''}">
        <div class="num {'warn-num' if total_drastic else ''}">{total_drastic}</div>
        <div class="lbl">Perubahan Drastis</div></div>
      <div class="card {'warn-card' if schema_changes.get('summary') else ''}">
        <div class="num">{len(schema_changes.get('summary', []))}</div>
        <div class="lbl">Perubahan Struktur</div></div>
    </div>""")

    for sname, comp in value_comparisons.items():
        if "error" in comp:
            continue
        periods = comp.get("periods", [])
        trend_data = comp.get("trend_data", {})
        sheet_trends = trends.get(sname, {})
        if not trend_data or not periods:
            continue

        top = sorted(
            trend_data,
            key=lambda c: (max(trend_data[c].values() or [0]) - min(trend_data[c].values() or [0])),
            reverse=True
        )[:8]

        fig = go.Figure()
        for col in top:
            y = [trend_data[col].get(p, 0) or 0 for p in periods]
            t = sheet_trends.get(col, {})
            fig.add_trace(go.Scatter(
                x=periods, y=y, mode="lines+markers", name=col,
                hovertemplate=(
                    f"<b>{col}</b><br>%{{x}}: %{{y:,.2f}}"
                    f"<br>{t.get('direction', '')} avg {t.get('avg_growth_pct', 0)}%<extra></extra>"
                ),
            ))

        fig.update_layout(
            title=f"Tren - {sname}", height=450,
            plot_bgcolor="#f8f9fa", paper_bgcolor="#fff",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        sections.append(
            f'<div class="section"><h2>{sname}</h2>'
            f'{plot(fig, include_plotlyjs=False, output_type="div")}</div>'
        )

        drastic = comp.get("drastic_changes", [])
        if drastic:
            rows = "".join([
                f"<tr><td>{d['column']}</td><td>{d['from']} &rarr; {d['to']}</td>"
                f"<td class=\"{'up' if d['direction']=='up' else 'dn'}\">"
                f"{'&#8593;' if d['direction']=='up' else '&#8595;'} {d['change_pct']}%</td>"
                f"<td>{d['value_from']:,.2f} &rarr; {d['value_to']:,.2f}</td></tr>"
                for d in drastic
            ])
            sections.append(f"""<div class="section warn-section">
              <h3>Perubahan Drastis - {sname}</h3>
              <table class="tbl">
                <thead><tr><th>Kolom</th><th>Periode</th><th>Perubahan</th><th>Nilai</th></tr></thead>
                <tbody>{rows}</tbody>
              </table></div>""")

    if schema_changes.get("summary"):
        items = "".join(f"<li>{s}</li>" for s in schema_changes["summary"])
        sections.append(
            f'<div class="section"><h2>Perubahan Struktur</h2><ul class="chg">{items}</ul></div>'
        )

    ai_sec = ""
    if ai_report:
        try:
            import markdown as md
            ai_html = md.markdown(ai_report)
        except Exception:
            ai_html = f"<pre>{ai_report}</pre>"
        ai_sec = f'<div class="section"><h2>AI Report</h2>{ai_html}</div>'

    html = f"""<!DOCTYPE html><html lang="id"><head><meta charset="UTF-8">
<title>Comparison Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;padding:20px;color:#2d3436}}
h1{{text-align:center;margin:20px 0;font-size:2em}}
h2{{margin:20px 0 12px;border-left:4px solid #4ECDC4;padding-left:12px}}
h3{{margin:12px 0 8px;color:#636e72}}
.cards{{display:flex;gap:15px;justify-content:center;flex-wrap:wrap;margin:20px 0}}
.card{{background:#fff;border-radius:12px;padding:20px 30px;text-align:center;
       box-shadow:0 2px 12px rgba(0,0,0,.08);min-width:140px}}
.warn-card{{border:2px solid #FF6B6B}}
.num{{font-size:2.2em;font-weight:bold;color:#4ECDC4}}
.warn-num{{color:#FF6B6B!important}}
.lbl{{color:#636e72;font-size:.85em;margin-top:5px}}
.section{{background:#fff;border-radius:12px;padding:25px;margin:20px 0;
          box-shadow:0 2px 12px rgba(0,0,0,.08)}}
.warn-section{{border-left:4px solid #FF6B6B}}
.tbl{{width:100%;border-collapse:collapse;margin-top:10px}}
.tbl th,.tbl td{{padding:10px 15px;border-bottom:1px solid #eee;text-align:left}}
.tbl th{{background:#f8f9fa;font-weight:600}}
.up{{color:#00b894;font-weight:bold}}.dn{{color:#d63031;font-weight:bold}}
.chg{{list-style:none;padding:0}}.chg li{{padding:8px 12px;border-radius:6px;
       margin:5px 0;background:#f8f9fa}}
</style></head><body>
<h1>Spreadsheet Comparison Dashboard</h1>
{"".join(sections)}{ai_sec}
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"Comparison dashboard: {path}")
    return path
