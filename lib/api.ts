export type SheetInfo = { name: string; count: number };

export type HealthScore = {
  score: number;
  grade: string;
  label: string;
  penalties: { reason: string; points: number }[];
};

export type SkillsPayload = {
  health: HealthScore;
  sheet_breakdown: {
    sheet: string;
    formula_count: number;
    warning_count: number;
    avg_complexity: number;
    max_complexity: number;
    top_category: string;
  }[];
  impact_cells: {
    cell: string;
    dependents: number;
    depends_on: number;
    impact_score: number;
    is_formula: boolean;
  }[];
  insights: {
    circular_refs: { cells: string[]; length: number }[];
    missing_refs: string[];
    orphan_cells: string[];
  };
  recommendations: {
    priority: string;
    title: string;
    detail: string;
    action: string;
  }[];
  avg_complexity: number;
};

export type AnalysisResult = {
  title: string;
  sheet_count: number;
  sheet_names: string[];
  formula_count: number;
  categories: Record<string, number>;
  top_complex: [string, number, string, string][];
  warnings: { cell: string; warnings: string[]; formula: string }[];
  graph_summary: Record<string, number>;
  missing_count: number;
  orphan_count: number;
  circular_count: number;
  ai_report?: string;
  audit_report?: string;
  complexity_scores: number[];
  skills?: SkillsPayload;
  elapsed_seconds?: number;
  from_cache?: boolean;
};

export type CompareResult = {
  summary: {
    periods: string[];
    sheets_compared: string[];
    schema_changes: number;
    drastic_changes: number;
  };
  schema: { summary: string[]; column_changes?: Record<string, unknown> };
  values: Record<string, {
    sheet: string;
    periods: string[];
    drastic_changes: { column: string; from: string; to: string; change_pct: number }[];
    trend_data: Record<string, Record<string, number>>;
  }>;
  trends: Record<string, Record<string, { direction: string; volatility: number }>>;
  ai_report?: string;
  errors?: Record<string, string>;
  elapsed_seconds?: number;
};

export type FixResult = {
  ok?: boolean;
  fixed?: string;
  explanation?: string;
  error?: string;
};

export type CompareLink = { url: string; label: string };

const BASE =
  typeof window !== "undefined"
    ? ""
    : process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : "http://localhost:3000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data as T;
}

export async function loadSheets(url: string, useCache = true) {
  return post<{ ok: boolean; title: string; sheets: SheetInfo[]; error?: string }>(
    "/api/sheets/load",
    { url, use_cache: useCache }
  );
}

export async function analyze(url: string, selectedSheets: string[], useCache: boolean, useAi: boolean) {
  return post<{ ok: boolean; result: AnalysisResult; error?: string }>("/api/analyze", {
    url,
    selected_sheets: selectedSheets.length ? selectedSheets : null,
    use_cache: useCache,
    use_ai: useAi,
  });
}

export async function comparePeriods(
  links: CompareLink[],
  opts: { sheetName?: string; useCache?: boolean; useAi?: boolean; threshold?: number } = {}
) {
  return post<{ ok: boolean; result: CompareResult; error?: string }>("/api/compare", {
    links,
    sheet_name: opts.sheetName,
    use_cache: opts.useCache ?? true,
    use_ai: opts.useAi ?? false,
    threshold: opts.threshold ?? 20,
  });
}

export async function fixFormula(formula: string, warnings: string[]) {
  return post<FixResult>("/api/fix", { formula, warnings });
}

export async function explainFormula(formula: string, cell: string, context?: object) {
  return post<{ ok: boolean; explanation?: string; error?: string }>("/api/explain", {
    formula,
    cell,
    context,
  });
}

export async function chatAi(question: string, context?: object, history?: { role: string; content: string }[]) {
  return post<{ ok: boolean; answer?: string; error?: string }>("/api/chat", {
    question,
    context,
    history,
  });
}

export async function applyFix(url: string, cell: string, formula: string) {
  return post<{ ok?: boolean; error?: string }>("/api/apply", { url, cell, formula });
}

export async function clearCache() {
  return post<{ ok: boolean; message: string }>("/api/cache/clear", {});
}

export async function checkHealth() {
  const res = await fetch(`${BASE}/api/health`);
  return res.json();
}

export function exportResultJson(result: AnalysisResult, url: string) {
  const blob = new Blob([JSON.stringify({ url, exported_at: new Date().toISOString(), ...result }, null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `analysis-${result.title.replace(/\W+/g, "_").slice(0, 40)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function estimateTimes(totalFormulas: number) {
  const tParse = Math.max(1, totalFormulas / 5000);
  const tGraph = Math.max(1.5, (totalFormulas * 2) / 130000) + 1;
  const tTotal = tParse + tGraph + 2;
  const wEst = Math.max(1, Math.floor(totalFormulas * 0.12));
  const tFixAll = wEst * 1.8;
  return { analysis: tTotal, fixAll: tFixAll, warningsEst: wEst };
}

export function fmtSecs(secs: number) {
  const s = Math.floor(secs);
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

export function perfTier(total: number, nSheets: number) {
  const avg = total / Math.max(1, nSheets);
  if (total === 0) return { emoji: "⚪", msg: "Pilih sheet berformula", color: "#475569" };
  if (total <= 2000) return { emoji: "🟢", msg: "Ringan — selesai dalam hitungan detik", color: "#34d399" };
  if (total <= 8000) {
    const safe = Math.max(2, Math.round(8000 / Math.max(1, avg)));
    const note = nSheets > safe ? ` · disarankan max ${safe} sheet` : "";
    return { emoji: "🟡", msg: `Sedang — beberapa menit${note}`, color: "#fbbf24" };
  }
  if (total <= 25000) {
    const safe = Math.max(2, Math.round(8000 / Math.max(1, avg)));
    return { emoji: "🟠", msg: `Berat — pilih ${safe} sheet utama`, color: "#fb923c" };
  }
  const safe = Math.max(2, Math.round(5000 / Math.max(1, avg)));
  return { emoji: "🔴", msg: `Sangat berat — max ${safe} sheet`, color: "#fb7185" };
}

export const PRIORITY_COLORS: Record<string, string> = {
  critical: "#fb7185",
  high: "#fb923c",
  medium: "#fbbf24",
  low: "#818cf8",
};

export const GRADE_COLORS: Record<string, string> = {
  A: "#34d399",
  B: "#22d3ee",
  C: "#fbbf24",
  D: "#fb923c",
  F: "#fb7185",
};
