"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import { CompareLink, CompareResult, comparePeriods, fmtSecs } from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const CHART_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, sans-serif", color: "#94a3b8", size: 12 },
};

export function CompareTab() {
  const [links, setLinks] = useState<CompareLink[]>([
    { url: "", label: "Periode 1" },
    { url: "", label: "Periode 2" },
  ]);
  const [useAi, setUseAi] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [selectedSheet, setSelectedSheet] = useState("");

  const addLink = () => {
    setLinks([...links, { url: "", label: `Periode ${links.length + 1}` }]);
  };

  const updateLink = (i: number, field: keyof CompareLink, value: string) => {
    const next = [...links];
    next[i] = { ...next[i], [field]: value };
    setLinks(next);
  };

  const removeLink = (i: number) => {
    if (links.length <= 2) return;
    setLinks(links.filter((_, idx) => idx !== i));
  };

  const handleCompare = async () => {
    const valid = links.filter((l) => l.url.trim());
    if (valid.length < 2) {
      setError("Minimal 2 URL valid diperlukan");
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await comparePeriods(valid, { useAi, sheetName: selectedSheet || undefined });
      setResult(data.result);
      if (!selectedSheet && data.result.summary.sheets_compared.length) {
        setSelectedSheet(data.result.summary.sheets_compared[0]);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const sheetData = selectedSheet ? result?.values[selectedSheet] : undefined;
  const trendEntries = sheetData?.trend_data ? Object.entries(sheetData.trend_data).slice(0, 8) : [];

  return (
    <div>
      <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
        <div className="section-header">
          <div className="section-dot" style={{ background: "#22d3ee" }} />
          <span className="section-title">Perbandingan Multi-Periode</span>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.82rem", marginBottom: 16 }}>
          Bandingkan spreadsheet antar bulan — deteksi perubahan struktur, nilai drastis, dan tren.
        </p>

        {links.map((link, i) => (
          <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
            <input
              className="url-input"
              style={{ flex: "0 0 140px", paddingLeft: 12 }}
              placeholder="Label"
              value={link.label}
              onChange={(e) => updateLink(i, "label", e.target.value)}
            />
            <input
              className="url-input"
              style={{ flex: 1, paddingLeft: 12 }}
              placeholder="URL Google Sheets"
              value={link.url}
              onChange={(e) => updateLink(i, "url", e.target.value)}
            />
            {links.length > 2 && (
              <button className="btn-clear" style={{ padding: "8px 12px" }} onClick={() => removeLink(i)}>✕</button>
            )}
          </div>
        ))}

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
          <button className="btn-secondary" onClick={addLink}>+ Tambah Periode</button>
          <label style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
            <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> AI Report
          </label>
          <button className="btn-analyze" onClick={handleCompare} disabled={loading} style={{ marginLeft: "auto" }}>
            {loading ? "⏳ Membandingkan…" : "📊 Bandingkan"}
          </button>
        </div>
      </div>

      {error && <div className="error-box" style={{ marginBottom: 16 }}>{error}</div>}

      {result && (
        <div className="animate-in">
          <div className="grid-stats">
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#818cf8" }}>{result.summary.periods.length}</div>
              <div className="stat-label">Periode</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#fbbf24" }}>{result.summary.schema_changes}</div>
              <div className="stat-label">Perubahan Struktur</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#fb7185" }}>{result.summary.drastic_changes}</div>
              <div className="stat-label">Perubahan Drastis</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "#34d399" }}>{fmtSecs(result.elapsed_seconds || 0)}</div>
              <div className="stat-label">Durasi</div>
            </div>
          </div>

          {result.schema.summary.length > 0 && (
            <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
              <div className="section-header">
                <div className="section-dot" style={{ background: "#fbbf24" }} />
                <span className="section-title">Perubahan Struktur</span>
              </div>
              <ul style={{ marginTop: 12, paddingLeft: 20, color: "#94a3b8", fontSize: "0.85rem" }}>
                {result.schema.summary.map((s) => <li key={s} style={{ marginBottom: 4 }}>{s}</li>)}
              </ul>
            </div>
          )}

          {result.summary.sheets_compared.length > 0 && (
            <div style={{ marginBottom: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
              {result.summary.sheets_compared.map((s) => (
                <button
                  key={s}
                  className={selectedSheet === s ? "btn-analyze" : "btn-secondary"}
                  onClick={() => setSelectedSheet(s)}
                >{s}</button>
              ))}
            </div>
          )}

          {sheetData && sheetData.drastic_changes.length > 0 && (
            <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
              <div className="section-header">
                <div className="section-dot" style={{ background: "#fb7185" }} />
                <span className="section-title">Perubahan Drastis — {selectedSheet}</span>
              </div>
              <table style={{ width: "100%", marginTop: 12, fontSize: "0.8rem" }}>
                <thead>
                  <tr style={{ color: "#64748b", textAlign: "left" }}>
                    <th style={{ padding: 6 }}>Kolom</th>
                    <th style={{ padding: 6 }}>Periode</th>
                    <th style={{ padding: 6 }}>Nilai Awal</th>
                    <th style={{ padding: 6 }}>Nilai Akhir</th>
                    <th style={{ padding: 6 }}>Δ%</th>
                  </tr>
                </thead>
                <tbody>
                  {sheetData.drastic_changes.slice(0, 15).map((d) => (
                    <tr key={`${d.column}-${d.from}`} style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                      <td style={{ padding: 8, color: "#a5b4fc" }}>{d.column}</td>
                      <td style={{ padding: 8, color: "#94a3b8" }}>{d.from} → {d.to}</td>
                      <td style={{ padding: 8, color: "#94a3b8" }}>{(d as { value_from?: number }).value_from?.toLocaleString?.() ?? "—"}</td>
                      <td style={{ padding: 8, color: "#94a3b8" }}>{(d as { value_to?: number }).value_to?.toLocaleString?.() ?? "—"}</td>
                      <td style={{ padding: 8, color: "#fb7185", fontWeight: 700 }}>{d.change_pct?.toFixed?.(1) ?? d.change_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {trendEntries.length > 0 && (
            <div className="glass-card" style={{ padding: 8, marginBottom: 16 }}>
              <Plot
                data={trendEntries.map(([col, vals]) => ({
                  type: "scatter",
                  mode: "lines+markers",
                  name: col,
                  x: Object.keys(vals),
                  y: Object.values(vals),
                }))}
                layout={{
                  ...CHART_LAYOUT,
                  title: { text: `Tren Nilai — ${selectedSheet}`, font: { color: "#f1f5f9" } },
                  height: 380,
                  legend: { font: { color: "#94a3b8", size: 10 } },
                }}
                config={{ displayModeBar: false }}
                style={{ width: "100%" }}
              />
            </div>
          )}

          {result.ai_report && (
            <div className="glass-card ai-section" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(129,140,248,0.2)" }}>
              <div className="section-header"><div className="section-dot" /><span className="section-title">AI Analisis Perbandingan</span></div>
              <div dangerouslySetInnerHTML={{ __html: result.ai_report.replace(/\n/g, "<br/>") }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
