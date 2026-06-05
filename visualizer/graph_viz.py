"""Dependency Graph visualizer menggunakan pyvis."""
from pyvis.network import Network
import os
from config import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger(__name__)

COLORS = {
    "lookup/reference": "#FF6B6B",
    "math/aggregation": "#4ECDC4",
    "logical":          "#45B7D1",
    "array/query":      "#96CEB4",
    "other":            "#FFEAA7",
    "simple":           "#DDA0DD",
    "unknown":          "#C0C0C0",
}


def generate_dependency_graph(graph, analyses, output_name="dependency_graph") -> str:
    os.makedirs(f"{OUTPUT_DIR}/graphs", exist_ok=True)
    path = f"{OUTPUT_DIR}/graphs/{output_name}.html"
    net = Network(height="800px", width="100%", bgcolor="#1a1a2e", font_color="white", directed=True)
    net.set_options('{"physics":{"forceAtlas2Based":{"gravitationalConstant":-50},"solver":"forceAtlas2Based"}}')

    for nid, attrs in graph.nodes(data=True):
        if str(nid).startswith("RANGE:"):
            net.add_node(nid, label=str(nid).replace("RANGE:", ""), color="#888", size=10, shape="diamond")
            continue
        a = analyses.get(nid)
        cat = a.formula_category if a else "simple"
        color = COLORS.get(cat, "#C0C0C0")
        if a and a.warnings:
            color = "#FF4757"
        net.add_node(
            nid,
            label=str(nid).split("!")[-1],
            color=color,
            size=max(15, min(40, 15 + (a.complexity_score if a else 0))),
            shape="dot" if a else "square",
            title=f"{nid}<br>{'Formula: ' + a.raw_formula[:60] if a else 'Data cell'}"
        )

    for s, t, _ in graph.edges(data=True):
        net.add_edge(s, t)

    net.save_graph(path)
    logger.info(f"Graph saved: {path}")
    return path
