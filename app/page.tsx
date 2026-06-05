"use client";

import dynamic from "next/dynamic";
import { Fragment, useCallback, useMemo, useState } from "react";
import { AiAssistant } from "@/app/components/AiAssistant";
import { CompareTab } from "@/app/components/CompareTab";
import { SkillsPanel } from "@/app/components/SkillsPanel";
import {
  AnalysisResult,
  SheetInfo,
  analyze,
  applyFix,
  clearCache,
  estimateTimes,
  explainFormula,
  exportResultJson,
  fixFormula,
  fmtSecs,
  loadSheets,
  perfTier,
} from "@/lib/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const CHART_COLORS = ["#818cf8", "#34d399", "#fbbf24", "#fb7185", "#a78bfa", "#22d3ee"];
const CHART_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, sans-serif", color: "#94a3b8", size: 12 },
};

type FixItem = {
  cell: string;
  formula: string;
  warnings: string[];
  fixed?: string;
  explanation?: string;
  error?: string;
};

type Tab = "analyze" | "compare" | "assistant";

export default function HomePage() {
  const [tab, setTab] = useState<Tab>("analyze");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [useCache, setUseCache] = useState(true);
  const [useAi, setUseAi] = useState(false);

  const [loadingSheets, setLoadingSheets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  const [fixItems, setFixItems] = useState<FixItem[]>([]);
  const [fixRunning, setFixRunning] = useState(false);
  const [fixMode, setFixMode] = useState<"all" | "step">("all");
  const [fixIdx, setFixIdx] = useState(0);
  const [applyMsg, setApplyMsg] = useState("");

  const totalSelected = useMemo(
    () => sheets.filter((s) => selected.has(s.name)).reduce((a, s) => a + s.count, 0),
    [sheets, selected]
  );

  const est = useMemo(() => estimateTimes(totalSelected), [totalSelected]);
  const tier = useMemo(() => perfTier(totalSelected, selected.size), [totalSelected, selected.size]);

  const handleLoadSheets = async () => {
    if (!url.trim()) { setError("Masukkan URL Google Sheets"); return; }
    setError(""); setLoadingSheets(true); setStatus("Membaca spreadsheet…");
    setResult(null); setFixItems([]);
    try {
      const data = await loadSheets(url.trim(), useCache);
      setTitle(data.title);
      setSheets(data.sheets);
      const def = new Set(data.sheets.filter((s) => s.count > 0).map((s) => s.name));
      setSelected(def);
      setStatus(`Dimuat: ${data.title} (${data.sheets.length} sheet)`);
    } catch (e) {
      setError(String(e)); setSheets([]);
    } finally {
      setLoadingSheets(false);
    }
  };

  const handleClearCache = async () => {
    try {
      await clearCache();
      setStatus("Cache dihapus");
    } catch (e) {
      setError(String(e));
    }
  };

  const handleAnalyze = async () => {
    if (!url.trim()) return;
    setAnalyzing(true); setError(""); setResult(null); setFixItems([]);
    setStatus("Analisis berjalan — bisa memakan beberapa menit…");
    try {
      const data = await analyze(url.trim(), [...selected], useCache, useAi);
      setResult(data.result);
      setStatus(
        data.result.from_cache
          ? `Selesai (cache) · ${fmtSecs(data.result.elapsed_seconds || 0)}`
          : `Selesai · ${fmtSecs(data.result.elapsed_seconds || 0)}`
      );
    } catch (e) {
      setError(String(e));
      setStatus("");
    } finally {
      setAnalyzing(false);
    }
  };

  const runFix = useCallback(async (items: FixItem[], mode: "all" | "step") => {
    setFixMode(mode); setFixRunning(true); setFixIdx(0); setApplyMsg("");
    const updated = [...items];
    setFixItems(updated);
    for (let i = 0; i < updated.length; i++) {
      setFixIdx(i);
      const res = await fixFormula(updated[i].formula, updated[i].warnings);
      updated[i] = { ...updated[i], ...res };
      setFixItems([...updated]);
    }
    setFixRunning(false);
  }, []);

  const handleApplyAll = async () => {
    let applied = 0;
    const errors: string[] = [];
    for (const item of fixItems) {
      if (!item.fixed) continue;
      const res = await applyFix(url.trim(), item.cell, item.fixed);
      if (res.ok) applied++;
      else errors.push(`${item.cell}: ${res.error}`);
    }
    setApplyMsg(
      errors.length
        ? `✅ ${applied} diterapkan · ⚠ ${errors.length} gagal`
        : `✅ ${applied} formula berhasil diterapkan`
    );
  };

  const handleApplyOne = async () => {
    const item = fixItems[fixIdx];
    if (!item?.fixed) return;
    const res = await applyFix(url.trim(), item.cell, item.fixed);
    setApplyMsg(res.ok ? `✅ ${item.cell} diterapkan` : `Gagal: ${res.error}`);
  };

  const toggleSheet = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  };

  return (
    <main>
      {/* Header */}
      <header style={{ textAlign: "center", padding: "36px 0 28px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 8 }}>
          <span style={{
            background: "linear-gradient(135deg,#6366f1,#22d3ee)",
            borderRadius: 10, padding: "6px 11px", fontWeight: 800,
            fontSize: "0.85rem", color: "#fff", marginRight: 14,
          }}>SA</span>
          <h1 style={{
            background: "linear-gradient(135deg,#818cf8,#a78bfa 45%,#22d3ee)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            fontWeight: 800, fontSize: "1.9rem", letterSpacing: "-0.03em",
          }}>Spreadsheet Deep Analyzer</h1>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.9rem" }}>
          Analisis formula, dependency, perbandingan multi-bulan & AI assistant
        </p>
      </header>

      {/* Tab Navigation */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {([
          ["analyze", "⚡ Analisis"],
          ["compare", "📊 Perbandingan"],
          ["assistant", "🤖 AI Assistant"],
        ] as [Tab, string][]).map(([id, label]) => (
          <button
            key={id}
            className={tab === id ? "btn-analyze" : "btn-secondary"}
            style={{ padding: "8px 18px", fontSize: "0.85rem" }}
            onClick={() => setTab(id)}
          >{label}</button>
        ))}
      </div>

      {tab === "compare" && <CompareTab />}
      {tab === "assistant" && <AiAssistant result={result} url={url} />}

      {tab === "analyze" && <>
      {/* URL Input */}
      <div className="glass-card animate-in" style={{ padding: "20px 24px", marginBottom: 16 }}>
        <div className="flex-row" style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ position: "relative", flex: 1 }}>
            <span style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", fontSize: 16 }}>🔗</span>
            <input
              className="url-input"
              placeholder="Paste URL Google Sheets di sini…"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLoadSheets()}
            />
          </div>
          <button className="btn-analyze" onClick={handleLoadSheets} disabled={loadingSheets}>
            {loadingSheets ? "Memuat…" : "📋 Baca Sheets"}
          </button>
          <button className="btn-clear" onClick={handleClearCache}>✕ Cache</button>
        </div>
      </div>

      {/* Sheet Selector */}
      {sheets.length > 0 && (
        <div className="glass-card animate-in" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(129,140,248,0.2)" }}>
          <div className="section-header">
            <div className="section-dot" />
            <span className="section-title">Pilih Sheet</span>
            <span style={{ color: "#64748b", fontSize: "0.78rem", marginLeft: 8 }}>
              {sheets.length} sheet · {sheets.reduce((a, s) => a + s.count, 0).toLocaleString()} formula
            </span>
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
            <button className="btn-secondary" onClick={() => setSelected(new Set(sheets.map((s) => s.name)))}>Pilih Semua</button>
            <button className="btn-secondary" onClick={() => setSelected(new Set())}>Bersihkan</button>
            <button className="btn-secondary" onClick={() => setSelected(new Set(sheets.filter((s) => s.count > 0).map((s) => s.name)))}>
              Non-Kosong
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 6, marginBottom: 16 }}>
            {sheets.map((s) => (
              <label key={s.name} style={{
                display: "flex", alignItems: "center", padding: "7px 10px",
                borderRadius: 8, cursor: "pointer", background: "rgba(30,41,59,0.3)",
              }}>
                <input
                  type="checkbox"
                  checked={selected.has(s.name)}
                  onChange={() => toggleSheet(s.name)}
                  style={{ marginRight: 8, accentColor: "#6366f1" }}
                />
                <span style={{ flex: 1, fontSize: "0.83rem", color: "#cbd5e1", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {s.name}
                </span>
                <span style={{
                  fontSize: "0.72rem", fontWeight: 600,
                  color: s.count === 0 ? "#475569" : s.count < 500 ? "#22d3ee" : s.count < 3000 ? "#34d399" : "#fbbf24",
                  background: "rgba(0,0,0,0.2)", borderRadius: 100, padding: "1px 9px",
                }}>{s.count.toLocaleString()}</span>
              </label>
            ))}
          </div>

          {/* Estimasi */}
          <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 12, padding: "14px 16px", marginBottom: 14, border: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <StatPill label="Analisis" value={fmtSecs(est.analysis)} color="#818cf8" />
              <StatPill label="Fix Semua" value={fmtSecs(est.fixAll)} color="#34d399" />
              <StatPill label="Perkiraan Warning" value={String(est.warningsEst)} color="#22d3ee" />
            </div>
            <div style={{
              background: `${tier.color}10`, border: `1px solid ${tier.color}30`,
              borderRadius: 8, padding: "7px 14px", display: "inline-flex", alignItems: "center",
            }}>
              <span style={{ marginRight: 5 }}>{tier.emoji}</span>
              <span style={{ color: tier.color, fontSize: "0.8rem", fontWeight: 600 }}>{tier.msg}</span>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 14 }}>
            <label style={{ color: "#94a3b8", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: 12 }}>
              <span><input type="checkbox" checked={useCache} onChange={(e) => setUseCache(e.target.checked)} /> Gunakan cache</span>
              <span><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> AI Report</span>
            </label>
            <button className="btn-analyze" onClick={handleAnalyze} disabled={analyzing || selected.size === 0} style={{ marginLeft: "auto" }}>
              {analyzing ? "⏳ Menganalisis…" : "⚡ Mulai Analisis"}
            </button>
          </div>
        </div>
      )}

      {/* Status */}
      {(status || analyzing) && (
        <div style={{ textAlign: "center", marginBottom: 12 }}>
          {analyzing && (
            <div className="progress-bar"><div className="progress-fill" style={{ width: "60%", animation: "pulse 2s infinite" }} /></div>
          )}
          <span style={{ color: analyzing ? "#818cf8" : "#34d399", fontSize: "0.85rem" }}>{status}</span>
        </div>
      )}

      {error && <div className="error-box animate-in" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Results */}
      {result && (
        <ResultsPanel
          result={result}
          url={url}
          onFixAll={() => runFix(result.warnings.map((w) => ({ ...w })), "all")}
          onFixStep={() => runFix(result.warnings.map((w) => ({ ...w })), "step")}
        />
      )}

      {/* Fix Panel */}
      {fixItems.length > 0 && (
        <FixPanel
          items={fixItems}
          running={fixRunning}
          mode={fixMode}
          idx={fixIdx}
          onPrev={() => setFixIdx((i) => Math.max(0, i - 1))}
          onNext={() => setFixIdx((i) => Math.min(fixItems.length - 1, i + 1))}
          onApplyAll={handleApplyAll}
          onApplyOne={handleApplyOne}
          applyMsg={applyMsg}
        />
      )}
      </>}
    </main>
  );
}

function StatPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ padding: "8px 16px", background: "rgba(0,0,0,0.25)", border: `1px solid ${color}22`, borderRadius: 10, textAlign: "center", minWidth: 100 }}>
      <div style={{ fontSize: "0.62rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: "0.9rem", color, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function ResultsPanel({ result, url, onFixAll, onFixStep }: { result: AnalysisResult; url: string; onFixAll: () => void; onFixStep: () => void }) {
  const [explaining, setExplaining] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<Record<string, string>>({});

  const handleExplain = async (cell: string, formula: string) => {
    setExplaining(cell);
    try {
      const res = await explainFormula(formula, cell, {
        title: result.title,
        health: result.skills?.health,
      });
      setExplanation((prev) => ({ ...prev, [cell]: res.explanation || res.error || "Gagal" }));
    } catch (e) {
      setExplanation((prev) => ({ ...prev, [cell]: String(e) }));
    } finally {
      setExplaining(null);
    }
  };
  const gs = result.graph_summary;
  const cats = result.categories;
  const totalFormula = Object.values(cats).reduce((a, b) => a + b, 0) || 1;
  const threshold = Math.max(1, Math.floor(totalFormula * 0.005));
  const pieData: Record<string, number> = {};
  let other = 0;
  for (const [k, v] of Object.entries(cats)) {
    if (v >= threshold) pieData[k] = v; else other += v;
  }
  if (other > 0) pieData["Lainnya"] = (pieData["Lainnya"] || 0) + other;

  const cleanScores = result.complexity_scores.filter((s) => s > 0);
  const p95 = cleanScores.length ? [...cleanScores].sort((a, b) => a - b)[Math.floor(cleanScores.length * 0.95)] : 1;
  const mainScores = cleanScores.filter((s) => s <= p95 * 1.5);

  const top20 = result.top_complex.slice(0, 20);

  return (
    <div className="animate-in">
      <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ fontSize: "1.15rem", marginBottom: 8 }}>{result.title}</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <Pill text={`${result.sheet_count} sheet`} color="#818cf8" />
              <Pill text={`${result.formula_count.toLocaleString()} formula`} color="#34d399" />
              <Pill text={`${gs.total_nodes?.toLocaleString() || 0} nodes`} color="#a78bfa" />
              <Pill text={`${gs.total_edges?.toLocaleString() || 0} edges`} color="#22d3ee" />
            </div>
          </div>
          <button className="btn-secondary" onClick={() => exportResultJson(result, url)}>⬇ Export JSON</button>
        </div>
      </div>

      {result.skills && <SkillsPanel skills={result.skills} />}

      <div className="grid-stats">
        <StatCard icon="🗂" label="Sheet" value={result.sheet_count} color="#818cf8" />
        <StatCard icon="⚙" label="Formula" value={result.formula_count.toLocaleString()} color="#34d399" />
        <StatCard icon="⚠" label="Warning" value={result.warnings.length} color="#fbbf24" />
        <StatCard icon="🔗" label="Missing Refs" value={result.missing_count} color="#fb7185" />
        <StatCard icon="🔄" label="Circular" value={result.circular_count} color="#fb7185" />
        <StatCard icon="🏝" label="Orphan" value={result.orphan_count} color="#818cf8" />
      </div>

      <div className="grid-charts">
        <div className="glass-card" style={{ padding: 8 }}>
          <Plot
            data={[{ type: "pie", labels: Object.keys(pieData), values: Object.values(pieData), hole: 0.52, marker: { colors: CHART_COLORS } }]}
            layout={{ ...CHART_LAYOUT, title: { text: "Kategori Formula", font: { color: "#f1f5f9" } }, height: 360, showlegend: false }}
            config={{ displayModeBar: false }}
            style={{ width: "100%" }}
          />
        </div>
        <div className="glass-card" style={{ padding: 8 }}>
          <Plot
            data={[{ type: "histogram", x: mainScores, nbinsx: 40, marker: { color: "#818cf8" } }]}
            layout={{ ...CHART_LAYOUT, title: { text: "Distribusi Kompleksitas", font: { color: "#f1f5f9" } }, height: 360 }}
            config={{ displayModeBar: false }}
            style={{ width: "100%" }}
          />
        </div>
      </div>

      <div className="glass-card" style={{ padding: 8, marginBottom: 16 }}>
        <Plot
          data={[{
            type: "bar", orientation: "h",
            y: top20.map((t) => t[0].split("!").pop() || t[0]),
            x: top20.map((t) => t[1]),
            marker: { color: top20.map((t) => t[1]), colorscale: [[0, "#34d399"], [0.4, "#fbbf24"], [1, "#fb7185"]] },
          }]}
          layout={{
            ...CHART_LAYOUT,
            title: { text: "Top 20 Formula Terkompleks", font: { color: "#f1f5f9" } },
            height: Math.max(400, top20.length * 24 + 80),
            yaxis: { autorange: "reversed", tickfont: { color: "#a5b4fc", size: 10 } },
          }}
          config={{ displayModeBar: false }}
          style={{ width: "100%" }}
        />
      </div>

      {result.warnings.length > 0 && (
        <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div className="section-header" style={{ marginBottom: 0 }}>
              <div className="section-dot" />
              <span className="section-title">Formula dengan Warning</span>
              <span style={{ color: "#818cf8", fontSize: "0.72rem", marginLeft: 8 }}>{result.warnings.length} formula</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-success" onClick={onFixAll}>🔧 Benahi Semua</button>
              <button className="btn-secondary" onClick={onFixStep}>📋 Satu Persatu</button>
            </div>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 4px" }}>
              <thead>
                <tr style={{ color: "#64748b", fontSize: "0.75rem", textAlign: "left" }}>
                  <th style={{ padding: "4px 8px" }}>Cell</th>
                  <th style={{ padding: "4px 8px" }}>Formula</th>
                  <th style={{ padding: "4px 8px" }}>Warning</th>
                  <th style={{ padding: "4px 8px" }}></th>
                </tr>
              </thead>
              <tbody>
                {result.warnings.slice(0, 20).map((w) => (
                  <Fragment key={w.cell}>
                    <tr style={{ background: "rgba(30,41,59,0.3)" }}>
                      <td style={{ padding: "8px", fontFamily: "monospace", color: "#a5b4fc", fontSize: "0.8rem" }}>{w.cell.split("!").pop()}</td>
                      <td style={{ padding: "8px" }}><span className="formula-text">{w.formula}</span></td>
                      <td style={{ padding: "8px" }}>{w.warnings.map((wt) => <span key={wt} className="warn-badge">{wt.split(":")[0]}</span>)}</td>
                      <td style={{ padding: "8px" }}>
                        <button className="btn-secondary" style={{ fontSize: "0.68rem", padding: "3px 8px" }}
                          onClick={() => handleExplain(w.cell, w.formula)}
                          disabled={explaining === w.cell}>
                          {explaining === w.cell ? "…" : "💡 Jelaskan"}
                        </button>
                      </td>
                    </tr>
                    {explanation[w.cell] && (
                      <tr>
                        <td colSpan={4} style={{ padding: "8px 16px", background: "rgba(99,102,241,0.08)", borderRadius: 8 }}>
                          <p style={{ color: "#cbd5e1", fontSize: "0.8rem", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{explanation[w.cell]}</p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result.audit_report && (
        <div className="glass-card ai-section" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(52,211,153,0.2)" }}>
          <div className="section-header"><div className="section-dot" style={{ background: "#34d399" }} /><span className="section-title">AI Audit Executive Summary</span></div>
          <div dangerouslySetInnerHTML={{ __html: result.audit_report.replace(/\n/g, "<br/>") }} />
        </div>
      )}

      {result.ai_report && (
        <div className="glass-card ai-section" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(129,140,248,0.2)" }}>
          <div className="section-header"><div className="section-dot" /><span className="section-title">AI Report</span></div>
          <div dangerouslySetInnerHTML={{ __html: result.ai_report.replace(/\n/g, "<br/>") }} />
        </div>
      )}

      <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
        <div className="section-header"><div className="section-dot" /><span className="section-title">Daftar Sheet</span></div>
        <div style={{ marginTop: 12 }}>
          {result.sheet_names.map((s) => <span key={s} className="sheet-badge">{s}</span>)}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string | number; color: string }) {
  return (
    <div className="stat-card">
      <div style={{ fontSize: "1.2rem" }}>{icon}</div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span style={{ background: `${color}20`, color, border: `1px solid ${color}33`, borderRadius: 100, padding: "3px 12px", fontSize: "0.78rem", fontWeight: 600 }}>
      {text}
    </span>
  );
}

function FixPanel({
  items, running, mode, idx, onPrev, onNext, onApplyAll, onApplyOne, applyMsg,
}: {
  items: FixItem[]; running: boolean; mode: "all" | "step"; idx: number;
  onPrev: () => void; onNext: () => void; onApplyAll: () => void; onApplyOne: () => void; applyMsg: string;
}) {
  const display = mode === "step" ? [items[idx]] : items;
  const successCount = items.filter((i) => i.fixed).length;

  return (
    <div className="glass-card animate-in" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(52,211,153,0.2)" }}>
      <div className="section-header">
        <div className="section-dot" style={{ background: "#34d399" }} />
        <span className="section-title">{mode === "all" ? "Perbaikan Otomatis Semua" : "Perbaikan Satu Persatu"}</span>
        <span style={{ color: running ? "#fbbf24" : "#34d399", fontSize: "0.72rem", marginLeft: 8 }}>
          {running ? `Memproses ${idx + 1}/${items.length}…` : "Selesai"}
        </span>
      </div>

      {!running && successCount > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
          {mode === "all" && <button className="btn-success" onClick={onApplyAll}>✅ Terapkan Semua ke Spreadsheet</button>}
          {mode === "step" && items[idx]?.fixed && <button className="btn-success" onClick={onApplyOne}>✅ Terapkan Formula Ini</button>}
        </div>
      )}
      {applyMsg && <p style={{ color: "#34d399", fontSize: "0.83rem", marginBottom: 12 }}>{applyMsg}</p>}

      <div style={{ maxHeight: mode === "all" ? 560 : undefined, overflowY: mode === "all" ? "auto" : undefined }}>
        {display.map((item) => (
          <div key={item.cell} style={{ padding: "14px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontFamily: "monospace", color: "#a5b4fc", fontWeight: 700 }}>{item.cell}</span>
              {item.warnings.map((w) => <span key={w} className="warn-badge">{w.split(":")[0]}</span>)}
            </div>
            <div className="formula-text" style={{ marginBottom: 8 }}>{item.formula}</div>
            {running && !item.fixed && !item.error && <span style={{ color: "#64748b", fontSize: "0.83rem" }}>⏳ Sedang diproses AI…</span>}
            {item.fixed && (
              <div>
                <div className="formula-text" style={{ color: "#34d399", background: "rgba(52,211,153,0.08)", padding: 8, borderRadius: 6 }}>{item.fixed}</div>
                {item.explanation && <p style={{ color: "#64748b", fontSize: "0.78rem", fontStyle: "italic", marginTop: 6 }}>{item.explanation}</p>}
              </div>
            )}
            {item.error && <p style={{ color: "#fbbf24", fontSize: "0.8rem" }}>⚠ {item.error}</p>}
          </div>
        ))}
      </div>

      {mode === "step" && (
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <button className="btn-secondary" onClick={onPrev} disabled={idx === 0}>← Sebelumnya</button>
          <span style={{ color: "#94a3b8" }}>{idx + 1} / {items.length}</span>
          <button className="btn-secondary" onClick={onNext} disabled={idx >= items.length - 1}>Berikutnya →</button>
        </div>
      )}
    </div>
  );
}
