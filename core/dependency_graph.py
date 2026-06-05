"""
Dependency Graph: Build DAG dari formula.
Deteksi: circular refs, missing refs, orphan cells, impact score.
"""
import time
import networkx as nx
from utils.logger import get_logger

logger = get_logger(__name__)


class DependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.all_cells = set()
        self.formula_cells = set()

    def build(self, data: dict, analyses: dict):
        for sname, sheet in data["sheets"].items():
            for ri, row in enumerate(sheet.get("values", [])):
                for ci, val in enumerate(row):
                    if val not in ("", None):
                        col = self._col_letter(ci)
                        addr = f"{sname}!{col}{ri + 1}"
                        self.all_cells.add(addr)
                        self.graph.add_node(addr, value=val, sheet=sname)

        for addr, a in analyses.items():
            self.formula_cells.add(addr)
            if not self.graph.has_node(addr):
                self.graph.add_node(addr)
            self.graph.nodes[addr].update({
                "is_formula": True, "formula": a.raw_formula,
                "functions": a.functions_used, "complexity": a.complexity_score,
                "category": a.formula_category, "warnings": a.warnings,
            })
            for ref in a.cell_references:
                tgt = self._normalize(ref, addr)
                if tgt:
                    self.graph.add_edge(addr, tgt)
            for rng in a.range_references:
                rid = f"RANGE:{rng['full']}"
                self.graph.add_node(rid, is_range=True)
                self.graph.add_edge(addr, rid)

        logger.info(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")

    def find_circular_references(self, limit=200, scc_cycle_threshold=12):
        """
        Deteksi circular references via SCC — O(V+E), aman untuk graph besar.

        Untuk SCC kecil (<= scc_cycle_threshold node): enumerate cycles eksak.
        Untuk SCC besar: laporkan node group (tetap informatif, tidak hang).
        """
        t0 = time.time()
        n = self.graph.number_of_nodes()
        logger.info(f"Circular ref check: {n:,} nodes, {self.graph.number_of_edges():,} edges…")

        sccs = [s for s in nx.strongly_connected_components(self.graph) if len(s) > 1]
        t_scc = time.time() - t0
        logger.info(f"SCC selesai: {len(sccs)} grup circular ({t_scc:.1f}s)")

        if not sccs:
            return []

        result = []
        for scc in sorted(sccs, key=len):
            if len(result) >= limit:
                break
            if len(scc) <= scc_cycle_threshold:
                sub = self.graph.subgraph(scc)
                try:
                    for cycle in nx.simple_cycles(sub):
                        result.append(cycle)
                        if len(result) >= limit:
                            break
                except Exception:
                    result.append(sorted(scc))
            else:
                # SCC besar: kembalikan sample node sebagai representasi grup
                result.append(sorted(scc)[:20])

        logger.info(f"Circular refs: {len(result)} cycle/grup ({time.time()-t0:.1f}s total)")
        return result

    def find_missing_references(self, limit=500):
        result = []
        for n in self.graph.nodes():
            if len(result) >= limit:
                break
            if (not str(n).startswith("RANGE:")
                    and n not in self.all_cells
                    and n not in self.formula_cells
                    and self.graph.in_degree(n) == 0
                    and self.graph.out_degree(n) > 0):
                result.append(n)
        return result

    def find_orphan_cells(self, limit=500):
        result = []
        for c in self.all_cells:
            if len(result) >= limit:
                break
            if c not in self.formula_cells and self.graph.in_degree(c) == 0:
                result.append(c)
        return result

    def get_summary(self):
        t0 = time.time()
        circular = self.find_circular_references()
        missing = self.find_missing_references()
        orphan = self.find_orphan_cells()
        logger.info(f"get_summary selesai ({time.time()-t0:.1f}s)")
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "total_cells": len(self.all_cells),
            "formula_cells": len(self.formula_cells),
            "circular_refs": circular,
            "missing_refs": missing,
            "orphan_cells": orphan,
        }

    def _normalize(self, ref, current):
        sheet = ref.get("sheet") or (current.split("!")[0] if "!" in current else "Sheet1")
        col, row = ref.get("col", ""), ref.get("row", "")
        return f"{sheet}!{col}{row}" if col and row else None

    @staticmethod
    def _col_letter(idx):
        r = ""
        while idx >= 0:
            r = chr(idx % 26 + ord('A')) + r
            idx = idx // 26 - 1
        return r
