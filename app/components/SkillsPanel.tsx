"use client";

import { GRADE_COLORS, PRIORITY_COLORS, SkillsPayload } from "@/lib/api";

export function SkillsPanel({ skills }: { skills: SkillsPayload }) {
  const { health, sheet_breakdown, impact_cells, insights, recommendations } = skills;
  const gradeColor = GRADE_COLORS[health.grade] || "#818cf8";

  return (
    <div className="animate-in">
      {/* Health Score */}
      <div className="glass-card" style={{ padding: "24px", marginBottom: 16, borderColor: `${gradeColor}40` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          <div style={{
            width: 100, height: 100, borderRadius: "50%",
            background: `conic-gradient(${gradeColor} ${health.score}%, rgba(255,255,255,0.08) 0)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            position: "relative",
          }}>
            <div style={{
              width: 76, height: 76, borderRadius: "50%", background: "#0f172a",
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            }}>
              <span style={{ fontSize: "1.6rem", fontWeight: 800, color: gradeColor }}>{health.score}</span>
              <span style={{ fontSize: "0.7rem", color: "#64748b" }}>/100</span>
            </div>
          </div>
          <div>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: gradeColor }}>
              Grade {health.grade} — {health.label}
            </div>
            <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: 4 }}>
              Rata-rata kompleksitas: {skills.avg_complexity}
            </p>
            {health.penalties.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {health.penalties.map((p) => (
                  <div key={p.reason} style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: 2 }}>
                    −{p.points} poin: {p.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
          <div className="section-header">
            <div className="section-dot" style={{ background: "#fbbf24" }} />
            <span className="section-title">Rekomendasi Otomatis</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
            {recommendations.map((r) => {
              const color = PRIORITY_COLORS[r.priority] || "#818cf8";
              return (
                <div key={r.title} style={{
                  padding: "12px 16px", borderRadius: 10,
                  background: `${color}10`, border: `1px solid ${color}30`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: "0.65rem", fontWeight: 700, color, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {r.priority}
                    </span>
                    <span style={{ fontWeight: 700, color: "#f1f5f9", fontSize: "0.88rem" }}>{r.title}</span>
                  </div>
                  <p style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: 4 }}>{r.detail}</p>
                  <p style={{ color: "#64748b", fontSize: "0.78rem", fontStyle: "italic" }}>→ {r.action}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sheet Breakdown */}
      <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
        <div className="section-header">
          <div className="section-dot" />
          <span className="section-title">Breakdown per Sheet</span>
        </div>
        <div style={{ overflowX: "auto", marginTop: 12 }}>
          <table style={{ width: "100%", fontSize: "0.8rem", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ color: "#64748b", textAlign: "left" }}>
                <th style={{ padding: "6px 8px" }}>Sheet</th>
                <th style={{ padding: "6px 8px" }}>Formula</th>
                <th style={{ padding: "6px 8px" }}>Warning</th>
                <th style={{ padding: "6px 8px" }}>Avg CX</th>
                <th style={{ padding: "6px 8px" }}>Kategori</th>
              </tr>
            </thead>
            <tbody>
              {sheet_breakdown.map((s) => (
                <tr key={s.sheet} style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ padding: "8px", color: "#a5b4fc", fontWeight: 600 }}>{s.sheet}</td>
                  <td style={{ padding: "8px", color: "#94a3b8" }}>{s.formula_count.toLocaleString()}</td>
                  <td style={{ padding: "8px", color: s.warning_count ? "#fbbf24" : "#34d399" }}>{s.warning_count}</td>
                  <td style={{ padding: "8px", color: "#94a3b8" }}>{s.avg_complexity}</td>
                  <td style={{ padding: "8px", color: "#64748b" }}>{s.top_category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Impact Cells */}
      {impact_cells.length > 0 && (
        <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
          <div className="section-header">
            <div className="section-dot" style={{ background: "#a78bfa" }} />
            <span className="section-title">Sel Berdampak Tinggi</span>
            <span style={{ color: "#64748b", fontSize: "0.72rem", marginLeft: 8 }}>banyak formula bergantung padanya</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
            {impact_cells.map((c) => (
              <div key={c.cell} style={{
                padding: "8px 14px", borderRadius: 10, background: "rgba(167,139,250,0.1)",
                border: "1px solid rgba(167,139,250,0.25)",
              }}>
                <div style={{ fontFamily: "monospace", color: "#a5b4fc", fontSize: "0.78rem", fontWeight: 700 }}>{c.cell}</div>
                <div style={{ fontSize: "0.68rem", color: "#64748b", marginTop: 2 }}>
                  {c.dependents} dependents · score {c.impact_score}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deep Insights */}
      {(insights.circular_refs.length > 0 || insights.missing_refs.length > 0) && (
        <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16 }}>
          <div className="section-header">
            <div className="section-dot" style={{ background: "#fb7185" }} />
            <span className="section-title">Deep Insights</span>
          </div>
          {insights.circular_refs.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ color: "#fb7185", fontSize: "0.82rem", marginBottom: 8 }}>Circular References</h4>
              {insights.circular_refs.slice(0, 5).map((c, i) => (
                <div key={i} className="formula-text" style={{ marginBottom: 6, padding: 8, background: "rgba(251,113,133,0.08)", borderRadius: 6 }}>
                  {c.cells.join(" → ")}
                </div>
              ))}
            </div>
          )}
          {insights.missing_refs.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ color: "#fbbf24", fontSize: "0.82rem", marginBottom: 8 }}>Missing References</h4>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {insights.missing_refs.slice(0, 15).map((m) => (
                  <span key={m} style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "#fbbf24", background: "rgba(251,191,36,0.1)", padding: "2px 8px", borderRadius: 6 }}>{m}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
