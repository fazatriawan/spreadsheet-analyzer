"use client";

import { useRef, useState } from "react";
import { AnalysisResult, chatAi } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "Apa masalah paling kritis di spreadsheet ini?",
  "Formula mana yang sebaiknya diperbaiki dulu?",
  "Bagaimana cara mengurangi circular reference?",
  "Rekomendasikan refactor untuk sheet kompleks",
];

export function AiAssistant({ result, url }: { result: AnalysisResult | null; url: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const buildContext = () => {
    if (!result) return { url, note: "Belum ada analisis. User bisa bertanya tentang spreadsheet secara umum." };
    return {
      url,
      title: result.title,
      formula_count: result.formula_count,
      health: result.skills?.health,
      warnings_count: result.warnings.length,
      circular_count: result.circular_count,
      missing_count: result.missing_count,
      recommendations: result.skills?.recommendations?.slice(0, 5),
      top_warnings: result.warnings.slice(0, 5),
      audit_report: result.audit_report,
    };
  };

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text.trim() };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setInput("");
    setLoading(true);
    try {
      const res = await chatAi(text.trim(), buildContext(), nextHistory);
      setMessages([...nextHistory, { role: "assistant", content: res.answer || res.error || "Tidak ada respons" }]);
    } catch (e) {
      setMessages([...nextHistory, { role: "assistant", content: `Error: ${e}` }]);
    } finally {
      setLoading(false);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  };

  return (
    <div>
      <div className="glass-card" style={{ padding: "20px 24px", marginBottom: 16, borderColor: "rgba(129,140,248,0.25)" }}>
        <div className="section-header">
          <div className="section-dot" style={{ background: "#a78bfa" }} />
          <span className="section-title">AI Spreadsheet Assistant</span>
        </div>
        <p style={{ color: "#64748b", fontSize: "0.82rem", marginBottom: 12 }}>
          {result
            ? `Konteks aktif: "${result.title}" — ${result.formula_count.toLocaleString()} formula`
            : "Jalankan analisis dulu untuk konteks lebih akurat, atau tanyakan langsung."}
        </p>

        {!messages.length && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="btn-secondary" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}

        <div style={{
          background: "rgba(0,0,0,0.3)", borderRadius: 12, padding: 16,
          maxHeight: 420, overflowY: "auto", marginBottom: 12,
          border: "1px solid rgba(255,255,255,0.06)",
        }}>
          {messages.length === 0 && (
            <p style={{ color: "#475569", fontSize: "0.85rem", textAlign: "center", padding: "40px 0" }}>
              Tanyakan apapun tentang formula, dependency, atau audit spreadsheet Anda.
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{
              marginBottom: 12, display: "flex",
              justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            }}>
              <div style={{
                maxWidth: "85%", padding: "10px 14px", borderRadius: 12,
                background: m.role === "user" ? "rgba(99,102,241,0.2)" : "rgba(30,41,59,0.6)",
                border: `1px solid ${m.role === "user" ? "rgba(99,102,241,0.3)" : "rgba(255,255,255,0.08)"}`,
                color: m.role === "user" ? "#c7d2fe" : "#cbd5e1",
                fontSize: "0.85rem", lineHeight: 1.6, whiteSpace: "pre-wrap",
              }}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ color: "#64748b", fontSize: "0.83rem", padding: "4px 0" }}>⏳ AI sedang berpikir…</div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="url-input"
            style={{ flex: 1, paddingLeft: 14 }}
            placeholder="Tanya tentang spreadsheet…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            disabled={loading}
          />
          <button className="btn-analyze" onClick={() => send(input)} disabled={loading || !input.trim()}>
            Kirim
          </button>
        </div>
      </div>
    </div>
  );
}
