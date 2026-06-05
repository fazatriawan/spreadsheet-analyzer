"""
AI Suggester: Claude-powered spreadsheet intelligence.
- Laporan perbaikan
- Analisis multi-bulan
- Penjelasan formula
- Chat assistant kontekstual
"""
import json

import anthropic

from config import ANTHROPIC_API_KEY
from utils.logger import get_logger

logger = get_logger(__name__)

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-20250514"


class AISuggester:
    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY tidak dikonfigurasi")
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = MODEL_HAIKU

    def _ask(self, prompt: str, max_tokens=2000, model: str | None = None) -> str:
        try:
            r = self.client.messages.create(
                model=model or self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.content[0].text.strip()
        except Exception as e:
            logger.error(f"AI error: {e}")
            return f"Error: {e}"

    def generate_improvement_report(self, formula_analyses: dict, graph_summary: dict) -> str:
        warned = [
            (k, v.warnings)
            for k, v in formula_analyses.items()
            if hasattr(v, "warnings") and v.warnings
        ]
        top_complex = sorted(
            [(k, getattr(v, "complexity_score", 0)) for k, v in formula_analyses.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        prompt = f"""Kamu adalah konsultan spreadsheet senior. Buat laporan perbaikan dalam Bahasa Indonesia.

Ringkasan:
- Total formula: {len(formula_analyses)}
- Circular refs: {len(graph_summary.get('circular_refs', []))}
- Missing refs: {len(graph_summary.get('missing_refs', []))}
- Orphan cells: {len(graph_summary.get('orphan_cells', []))}

10 formula terkompleks: {json.dumps(top_complex, default=str)}
Warning: {json.dumps(warned[:20], default=str)}

Buat laporan Markdown mencakup:
1. Ringkasan eksekutif
2. Masalah kritis
3. Rekomendasi perbaikan formula (dengan contoh)
4. Priority action items"""
        return self._ask(prompt, 3000)

    def analyze_multi_month(
        self, periods: list, drastic_changes: list, schema_changes: list, trends: dict
    ) -> str:
        prompt = f"""Kamu adalah data analyst. Buat laporan perbandingan spreadsheet multi-bulan dalam Bahasa Indonesia.

Periode: {periods}
Perubahan drastis ({len(drastic_changes)}): {json.dumps(drastic_changes[:15], default=str)}
Perubahan struktur: {json.dumps(schema_changes[:10], default=str)}
Tren per kolom: {json.dumps({k: v.get('direction', '') for k, v in list(trends.items())[:15]}, default=str)}

Buat analisis Markdown:
1. Kesimpulan utama
2. Kolom paling berfluktuasi
3. Perubahan struktur
4. Rekomendasi konsistensi
5. Alert manual check"""
        return self._ask(prompt, 2500)

    def explain_formula(self, formula: str, cell: str = "", context: dict | None = None) -> str:
        ctx = ""
        if context:
            ctx = f"\nKonteks analisis:\n{json.dumps(context, ensure_ascii=False, default=str)[:1500]}"
        prompt = f"""Jelaskan formula spreadsheet ini dalam Bahasa Indonesia yang mudah dipahami.

Cell: {cell or 'tidak diketahui'}
Formula: {formula}
{ctx}

Jelaskan:
1. Apa yang dihitung formula ini
2. Fungsi-fungsi yang dipakai dan peran masing-masing
3. Dari sel/range mana data diambil
4. Potensi masalah atau risiko
5. Tips optimasi jika ada

Gunakan bullet points, maksimal 250 kata."""
        return self._ask(prompt, 800)

    def chat(self, question: str, context: dict | None = None, history: list | None = None) -> str:
        """Asisten AI dengan konteks spreadsheet."""
        ctx_block = ""
        if context:
            ctx_block = f"""
KONTEKS SPREADSHEET:
{json.dumps(context, ensure_ascii=False, default=str)[:4000]}
"""
        hist_block = ""
        if history:
            lines = []
            for h in history[-6:]:
                role = h.get("role", "user")
                content = h.get("content", "")[:500]
                lines.append(f"{role.upper()}: {content}")
            hist_block = "\nRIWAYAT CHAT:\n" + "\n".join(lines) + "\n"

        prompt = f"""Kamu adalah Spreadsheet Deep Analyzer AI — ahli Google Sheets/Excel, formula, dan audit spreadsheet.
Jawab dalam Bahasa Indonesia. Singkat, teknis, actionable.
{ctx_block}{hist_block}
USER: {question}

Jawab dengan struktur jelas. Jika butuh data yang tidak ada di konteks, katakan apa yang perlu dicek user."""
        return self._ask(prompt, 1200, model=MODEL_SONNET)

    def audit_quick(self, health: dict, recommendations: list, top_warnings: list) -> str:
        """Audit singkat berbasis data skills (tanpa full formula dump)."""
        prompt = f"""Buat audit executive summary spreadsheet dalam Bahasa Indonesia (max 200 kata).

Health Score: {health.get('score')}/100 ({health.get('grade')} — {health.get('label')})
Penalti: {json.dumps(health.get('penalties', []), ensure_ascii=False)}
Rekomendasi: {json.dumps(recommendations[:5], ensure_ascii=False, default=str)}
Top warnings: {json.dumps(top_warnings[:10], ensure_ascii=False, default=str)}

Format: 3 paragraf — situasi, risiko utama, 3 langkah prioritas."""
        return self._ask(prompt, 600)
