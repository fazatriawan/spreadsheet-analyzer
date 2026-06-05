"""Single-sheet analysis dashboard."""
import plotly.graph_objects as go
import plotly.subplots as sp
from plotly.offline import plot
import os
from config import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_dashboard(analyses, graph_summary, ai_report="", output_name="analysis") -> str:
    os.makedirs(f"{OUTPUT_DIR}/reports", exist_ok=True)
    path = f"{OUTPUT_DIR}/reports/{output_name}.html"

    cats = {}
    for a in analyses.values():
        cats[a.formula_category] = cats.get(a.formula_category, 0) + 1

    top = sorted(analyses.items(), key=lambda x: x[1].complexity_score, reverse=True)[:20]

    fig = sp.make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Formula Categories", "Complexity Distribution",
            "Top Complex Formulas", "Health Overview"
        ),
        specs=[[{"type": "pie"}, {"type": "histogram"}], [{"type": "bar"}, {"type": "bar"}]]
    )

    fig.add_trace(go.Pie(labels=list(cats.keys()), values=list(cats.values()), hole=0.4), 1, 1)
    fig.add_trace(
        go.Histogram(x=[a.complexity_score for a in analyses.values()], marker_color="#4ECDC4"), 1, 2
    )
    fig.add_trace(go.Bar(
        x=[a.split("!")[-1] for a, _ in top],
        y=[s.complexity_score for _, s in top],
        marker=dict(
            color=[s.complexity_score for _, s in top],
            colorscale="RdYlGn_r", showscale=True
        )
    ), 2, 1)

    hl = ["Total Cells", "Formula Cells", "Missing Refs", "Orphan Cells", "Circular Refs"]
    hv = [
        graph_summary.get("total_cells", 0),
        graph_summary.get("formula_cells", 0),
        len(graph_summary.get("missing_refs", [])),
        len(graph_summary.get("orphan_cells", [])),
        len(graph_summary.get("circular_refs", [])),
    ]
    fig.add_trace(go.Bar(
        x=hl, y=hv,
        marker_color=["#4ECDC4", "#45B7D1", "#FF6B6B", "#FFEAA7", "#FF4757"],
        text=hv, textposition="outside"
    ), 2, 2)

    fig.update_layout(
        title="Spreadsheet Analysis", height=900, showlegend=False,
        paper_bgcolor="#f8f9fa", plot_bgcolor="#fff"
    )

    ai_sec = ""
    if ai_report:
        try:
            import markdown as md
            ah = md.markdown(ai_report)
        except Exception:
            ah = f"<pre>{ai_report}</pre>"
        ai_sec = (
            '<div style="background:#fff;border-radius:8px;padding:20px;margin:20px 0;'
            'box-shadow:0 2px 10px rgba(0,0,0,.1)"><h2>AI Report</h2>'
            f'{ah}</div>'
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Spreadsheet Analysis</title></head>
<body style="font-family:Arial;background:#f8f9fa;padding:20px">
<h1 style="text-align:center">Spreadsheet Deep Analysis</h1>
{plot(fig, include_plotlyjs=True, output_type="div")}
{ai_sec}</body></html>""")

    logger.info(f"Dashboard: {path}")
    return path
