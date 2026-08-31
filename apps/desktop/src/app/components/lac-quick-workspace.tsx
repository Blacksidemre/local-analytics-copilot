"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActionButton } from "@/components/ui/action-button";
import { Card } from "@/components/ui/card";
import {
  LacBridgeClient,
  LacBridgeError,
  type AgentResult,
  type AnalystReportFormat,
  type AnalystResult,
  type AnalystTargetKind,
  type BridgeDashboard,
  type BridgeErrorDetail,
  type BridgeHealth,
  type BridgeInterpretation,
  type BridgeProfile,
  type BridgeSheetOption,
} from "@/lib/lac-bridge-client";

type ReadyAnalysis = {
  filePath: string;
  fileName: string;
  selectedSheet?: string;
  profile: BridgeProfile;
  dashboard: BridgeDashboard;
  interpretation: BridgeInterpretation;
};

type ActiveOperation =
  "upload" | "sheet" | "quick" | "analyst" | "agent" | "report-xlsx" | "report-html" | "report-pdf";

const DEFAULT_QUESTION = "Bu veri setinin hızlı profilini Türkçe ve kanıta bağlı biçimde yorumla.";
const REPORT_LABELS: Record<AnalystReportFormat, string> = {
  xlsx: "Excel",
  html: "HTML",
  pdf: "PDF",
};
const OPERATION_LABELS: Record<ActiveOperation, string> = {
  upload: "Dosya güvenli biçimde okunuyor ve profilleniyor...",
  sheet: "Seçilen çalışma sayfası profilleniyor...",
  quick: "Doğrulanmış profil Qwen tarafından yorumlanıyor...",
  analyst: "Deterministik testler ve verifier çalışıyor...",
  agent: "Yerel planner uygun deterministik araçları seçiyor ve verifier çalışıyor...",
  "report-xlsx": "Doğrulanmış Excel raporu hazırlanıyor...",
  "report-html": "Doğrulanmış HTML raporu hazırlanıyor...",
  "report-pdf": "Doğrulanmış PDF raporu hazırlanıyor...",
};

function fallbackError(error: unknown): BridgeErrorDetail {
  if (error instanceof LacBridgeError) return error.detail;
  return {
    code: "unexpected_error",
    message: error instanceof Error ? error.message : "Beklenmeyen bir hata oluştu.",
    hint: null,
    details: {},
  };
}

function formatValue(value: number, unit: string): string {
  return new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: unit === "score_0_100" ? 2 : Number.isInteger(value) ? 0 : 2,
  }).format(value);
}

function roleLabel(role: string): string {
  return (
    {
      numeric: "Sayısal",
      categorical: "Kategorik",
      datetime: "Tarih/Zaman",
      identifier: "Kimlik",
      text: "Metin",
      boolean: "Mantıksal",
    }[role] ?? role
  );
}

function agentToolLabel(tool: string): string {
  return (
    {
      profile_dataset: "Veri profili",
      screen_target_associations: "Hedef ilişki taraması",
      describe_columns: "Sayısal özet",
      categorical_frequency: "Kategori dağılımı",
      aggregate_by_segment: "Segment karşılaştırması",
      analyze_time_trend: "Zaman trendi",
      screen_outliers: "Aykırı değer taraması",
    }[tool] ?? "Deterministik analiz"
  );
}

export function LacQuickWorkspace() {
  const client = useMemo(() => new LacBridgeClient(), []);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const [health, setHealth] = useState<"checking" | "ready" | "degraded" | "unavailable">(
    "checking"
  );
  const [healthDetails, setHealthDetails] = useState<BridgeHealth | null>(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [activeOperation, setActiveOperation] = useState<ActiveOperation | null>(null);
  const [error, setError] = useState<BridgeErrorDetail | null>(null);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [pendingFileName, setPendingFileName] = useState("");
  const [pendingFilePath, setPendingFilePath] = useState("");
  const [sheetOptions, setSheetOptions] = useState<BridgeSheetOption[]>([]);
  const [ready, setReady] = useState<ReadyAnalysis | null>(null);
  const [analyst, setAnalyst] = useState<AnalystResult | null>(null);
  const [agent, setAgent] = useState<AgentResult | null>(null);
  const [reportStatus, setReportStatus] = useState("");
  const [targetColumn, setTargetColumn] = useState("");
  const [targetKind, setTargetKind] = useState<"" | AnalystTargetKind>("");

  const busy = activeOperation !== null;
  const selectedTarget = ready?.profile.schema.find((column) => column.name === targetColumn);
  const targetKindRequired = Boolean(targetColumn && selectedTarget?.unique !== 2 && !targetKind);

  const checkHealth = useCallback(
    async (signal?: AbortSignal) => {
      setHealth("checking");
      try {
        const result = await client.health(signal);
        setHealth(result.status);
        setHealthDetails(result);
        setSelectedModel((current) =>
          current && result.ollama.models.includes(current)
            ? current
            : result.ollama.configured_model_available
              ? result.ollama.configured_model
              : (result.ollama.models[0] ?? "")
        );
      } catch {
        if (!signal?.aborted) {
          setHealth("unavailable");
          setHealthDetails(null);
        }
      }
    },
    [client]
  );

  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(controller.signal);
    return () => controller.abort();
  }, [checkHealth]);

  useEffect(() => () => requestRef.current?.abort(), []);

  const startRequest = (operation: ActiveOperation) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setActiveOperation(operation);
    setError(null);
    return controller;
  };

  const finishRequest = (controller: AbortController) => {
    if (requestRef.current === controller) {
      requestRef.current = null;
      setActiveOperation(null);
    }
  };

  const upload = async (file: File) => {
    const controller = startRequest("upload");
    setReady(null);
    setAnalyst(null);
    setAgent(null);
    setReportStatus("");
    setTargetColumn("");
    setTargetKind("");
    setSheetOptions([]);
    setPendingFileName(file.name);
    try {
      const result = await client.upload(file, {
        interpret: true,
        question,
        model: selectedModel || undefined,
        signal: controller.signal,
      });
      if (result.status === "sheet_selection_required") {
        setPendingFilePath(result.file_path);
        setSheetOptions(result.sheet_options ?? []);
        return;
      }
      if (result.status === "profiled" && result.profile && result.dashboard) {
        setReady({
          filePath: result.file_path,
          fileName: file.name,
          selectedSheet: result.selected_sheet,
          profile: result.profile,
          dashboard: result.dashboard,
          interpretation: result.interpretation ?? { status: "skipped" },
        });
        return;
      }
      throw new Error("LAC Bridge profilli bir upload sonucu döndürmedi.");
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const selectSheet = async (sheetName: string) => {
    const controller = startRequest("sheet");
    try {
      const result = await client.quick(pendingFilePath, {
        sheetName,
        interpret: true,
        question,
        model: selectedModel || undefined,
        signal: controller.signal,
      });
      setSheetOptions([]);
      setAnalyst(null);
      setAgent(null);
      setReportStatus("");
      setTargetColumn("");
      setTargetKind("");
      setReady({
        filePath: result.file_path,
        fileName: pendingFileName,
        selectedSheet: sheetName,
        profile: result.profile,
        dashboard: result.dashboard,
        interpretation: result.interpretation,
      });
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const reinterpret = async () => {
    if (!ready) return;
    const controller = startRequest("quick");
    try {
      const result = await client.quick(ready.filePath, {
        sheetName: ready.selectedSheet,
        interpret: true,
        question,
        model: selectedModel || undefined,
        signal: controller.signal,
      });
      setReady((current) =>
        current
          ? {
              ...current,
              profile: result.profile,
              dashboard: result.dashboard,
              interpretation: result.interpretation,
            }
          : current
      );
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const runAnalyst = async () => {
    if (!ready || !targetColumn) return;
    const controller = startRequest("analyst");
    try {
      const result = await client.analyst(ready.filePath, targetColumn, {
        sheetName: ready.selectedSheet,
        targetKind: targetKind || undefined,
        interpret: true,
        question,
        language: "tr",
        model: selectedModel || undefined,
        signal: controller.signal,
      });
      setAnalyst(result);
      setReportStatus("");
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const runAgent = async () => {
    if (!ready || !question.trim()) return;
    const controller = startRequest("agent");
    const approvedTargetKind =
      targetKind || (targetColumn && selectedTarget?.unique === 2 ? "binary" : undefined);
    try {
      const result = await client.agent(ready.filePath, question.trim(), {
        sheetName: ready.selectedSheet,
        targetColumn: targetColumn || undefined,
        targetKind: approvedTargetKind || undefined,
        language: "tr",
        model: selectedModel || undefined,
        signal: controller.signal,
      });
      setAgent(result);
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const downloadAnalystReport = async (format: AnalystReportFormat) => {
    if (!ready || !targetColumn || !analyst) return;
    const controller = startRequest(`report-${format}`);
    setReportStatus("");
    try {
      const options = {
        sheetName: ready.selectedSheet,
        targetKind: targetKind || undefined,
        interpret: true,
        question,
        language: "tr",
        model: selectedModel || undefined,
        signal: controller.signal,
      };
      const result =
        format === "html"
          ? await client.analystHtmlReport(ready.filePath, targetColumn, options)
          : format === "pdf"
            ? await client.analystPdfReport(ready.filePath, targetColumn, options)
            : await client.analystReport(ready.filePath, targetColumn, options);
      const objectUrl = URL.createObjectURL(result.blob);
      try {
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = result.filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      } finally {
        URL.revokeObjectURL(objectUrl);
      }
      setReportStatus(`Doğrulanmış ${REPORT_LABELS[format]} raporu indirildi: ${result.filename}`);
    } catch (caught) {
      if (!controller.signal.aborted) setError(fallbackError(caught));
    } finally {
      finishRequest(controller);
    }
  };

  const reset = () => {
    requestRef.current?.abort();
    requestRef.current = null;
    setActiveOperation(null);
    setError(null);
    setPendingFileName("");
    setPendingFilePath("");
    setSheetOptions([]);
    setReady(null);
    setAnalyst(null);
    setAgent(null);
    setReportStatus("");
    setTargetColumn("");
    setTargetKind("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="min-h-screen bg-surface-0 text-t-primary">
      <header className="border-b border-border-default bg-surface-1">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold tracking-tight">Local Analytics Copilot</span>
            <span className="rounded-badge bg-accent-subtle px-2 py-1 text-[11px] font-medium text-accent">
              Quick · Analyst · Agent
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-t-secondary">
            {healthDetails && healthDetails.ollama.models.length > 0 && (
              <select
                aria-label="Yerel Ollama modeli"
                value={selectedModel}
                onChange={(event) => {
                  setSelectedModel(event.target.value);
                  setAgent(null);
                  setAnalyst(null);
                }}
                className="max-w-[220px] border border-border-default bg-surface-0 px-2 py-1 text-xs outline-none focus:border-accent"
                style={{ borderRadius: "var(--radius-input)" }}
              >
                {healthDetails.ollama.models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            )}
            <span
              className={`h-2 w-2 rounded-full ${
                health === "ready"
                  ? "bg-success"
                  : health === "checking"
                    ? "bg-warning"
                    : "bg-error"
              }`}
            />
            {health === "ready"
              ? "LAC hazır"
              : health === "checking"
                ? "Bağlantı kontrol ediliyor"
                : "LAC bağlantısı sınırlı"}
            {(health === "degraded" || health === "unavailable") && (
              <button
                type="button"
                onClick={() => void checkHealth()}
                className="ml-1 font-medium text-accent hover:underline"
              >
                Yeniden dene
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-8">
        {error && (
          <div
            role="alert"
            className="mb-6 border border-error-border bg-error-bg px-4 py-3 text-sm text-error-text"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium">{error.message}</p>
                {error.hint && <p className="mt-1 text-xs opacity-80">{error.hint}</p>}
                <details className="mt-2 text-[10px] opacity-70">
                  <summary className="cursor-pointer">Teknik ayrıntı</summary>
                  <p className="mt-1 font-mono">{error.code}</p>
                </details>
              </div>
              <button onClick={() => setError(null)} className="text-xs font-medium">
                Kapat
              </button>
            </div>
          </div>
        )}

        {activeOperation && (
          <p
            role="status"
            aria-live="polite"
            className="mb-6 border border-accent/30 bg-accent-subtle px-4 py-3 text-sm text-accent"
            style={{ borderRadius: "var(--radius-card)" }}
          >
            {OPERATION_LABELS[activeOperation]}
          </p>
        )}

        {!ready && sheetOptions.length === 0 && (
          <div
            className="flex min-h-[68vh] items-center justify-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const file = event.dataTransfer.files?.[0];
              if (file && !busy) void upload(file);
            }}
          >
            <Card className="w-full max-w-[720px] p-8 text-center">
              <h1 className="text-2xl font-semibold tracking-tight">
                Dosyanı ver, ne istediğini söyle.
              </h1>
              <p className="mx-auto mt-3 max-w-[560px] text-sm leading-6 text-t-secondary">
                CSV veya Excel dosyan deterministik LAC Data Bridge tarafından okunur. Quick,
                Analyst veya kontrollü yerel Agent ile ilerleyebilirsin; sayısal gerçekleri model
                hesaplamaz.
              </p>
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx,.xlsm,.parquet"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void upload(file);
                }}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => inputRef.current?.click()}
                className="mt-6 bg-accent px-5 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                style={{ borderRadius: "var(--radius-button)" }}
              >
                {activeOperation === "upload" ? "Profil çıkarılıyor..." : "CSV / XLSX seç"}
              </button>
              <p className="mt-4 text-xs text-t-tertiary">
                Veriler yerel makinede kalır · Qwen yalnız doğrulanmış profil özetini yorumlar
              </p>
            </Card>
          </div>
        )}

        {!ready && sheetOptions.length > 0 && (
          <Card className="mx-auto max-w-[820px]">
            <h1 className="text-xl font-semibold">Çalışma sayfası seç</h1>
            <p className="mt-1 text-sm text-t-secondary">{pendingFileName}</p>
            <div className="mt-6 divide-y divide-border-default border-y border-border-default">
              {sheetOptions.map((sheet) => (
                <button
                  key={sheet.name}
                  type="button"
                  disabled={busy}
                  onClick={() => void selectSheet(sheet.name)}
                  className="flex w-full items-center justify-between px-2 py-4 text-left hover:bg-surface-btn disabled:opacity-50"
                >
                  <span>
                    <span className="block text-sm font-medium">{sheet.name}</span>
                    <span className="mt-1 block text-xs text-t-tertiary">
                      {sheet.estimated_rows.toLocaleString("tr-TR")} satır ·{" "}
                      {sheet.estimated_columns.toLocaleString("tr-TR")} sütun · başlık satırı{" "}
                      {sheet.header_row}
                    </span>
                  </span>
                  <span className="text-sm font-medium text-accent">Analiz et</span>
                </button>
              ))}
            </div>
            <ActionButton className="mt-5" onClick={reset} disabled={busy}>
              Vazgeç
            </ActionButton>
          </Card>
        )}

        {ready && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.16em] text-accent">
                  Deterministik Quick Dashboard
                </p>
                <h1 className="mt-1 text-2xl font-semibold tracking-tight">{ready.fileName}</h1>
                {ready.selectedSheet && (
                  <p className="mt-1 text-sm text-t-secondary">Sayfa: {ready.selectedSheet}</p>
                )}
              </div>
              <ActionButton onClick={reset}>Yeni dosya</ActionButton>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {ready.dashboard.cards.map((card) => (
                <Card key={card.finding_id} className="p-4">
                  <p className="text-xs text-t-secondary">{card.label}</p>
                  <p className="mt-2 text-2xl font-semibold tabular-nums">
                    {formatValue(card.value, card.unit)}
                  </p>
                  <p
                    className="mt-2 truncate font-mono text-[9px] text-t-tertiary"
                    title={card.finding_id}
                  >
                    {card.finding_id}
                  </p>
                </Card>
              ))}
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
              <Card>
                <h2 className="text-base font-semibold">Veri kalitesi</h2>
                {ready.dashboard.missing_by_column.length === 0 ? (
                  <p className="mt-4 text-sm text-t-secondary">Eksik hücre bulunmadı.</p>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="text-xs text-t-tertiary">
                        <tr>
                          <th className="pb-2 font-medium">Sütun</th>
                          <th className="pb-2 text-right font-medium">Eksik</th>
                          <th className="pb-2 text-right font-medium">Oran</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border-default">
                        {ready.dashboard.missing_by_column.map((item) => (
                          <tr key={item.finding_id}>
                            <td className="py-2.5 font-mono text-xs">{item.column}</td>
                            <td className="py-2.5 text-right tabular-nums">{item.count}</td>
                            <td className="py-2.5 text-right tabular-nums">{item.pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>

              <Card>
                <h2 className="text-base font-semibold">Sütun rolleri</h2>
                <div className="mt-4 space-y-3">
                  {ready.dashboard.role_counts.map((item) => (
                    <div key={item.role} className="flex items-center justify-between text-sm">
                      <span className="text-t-secondary">{roleLabel(item.role)}</span>
                      <span className="font-medium tabular-nums">{item.count}</span>
                    </div>
                  ))}
                </div>
                {ready.dashboard.constant_columns.length > 0 && (
                  <p className="mt-5 border-t border-border-default pt-4 text-xs text-t-tertiary">
                    Sabit sütunlar: {ready.dashboard.constant_columns.join(", ")}
                  </p>
                )}
              </Card>
            </div>

            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-accent">
                    Yerel Agent · Milestone 3
                  </p>
                  <h2 className="mt-1 text-base font-semibold">Dosyana doğal dilde soru sor</h2>
                  <p className="mt-1 max-w-[780px] text-xs leading-5 text-t-tertiary">
                    Qwen yalnız planlar ve doğrulanmış kanıtı açıklar. Hesaplar allowlist içindeki
                    bounded LAC araçlarında yapılır; shell, Python, keyfi SQL, internet ve ham satır
                    aktarımı kapalıdır.
                  </p>
                </div>
                {agent?.agent.run?.verification.status === "passed" && (
                  <span className="rounded-badge bg-success-subtle px-2 py-1 text-[11px] font-medium text-success-text">
                    Agent kanıtları doğrulandı
                  </span>
                )}
              </div>

              <textarea
                value={question}
                onChange={(event) => {
                  setQuestion(event.target.value);
                  setAgent(null);
                }}
                maxLength={4000}
                rows={3}
                aria-label="Agent analiz isteği"
                placeholder="Örnek: Bölgelere göre tutarı karşılaştır, eksik veriyi değerlendir ve kanıta bağlı bir yönetici özeti hazırla."
                className="mt-5 w-full resize-y border border-border-default bg-surface-0 px-3 py-2 text-sm leading-6 outline-none focus:border-accent"
                style={{ borderRadius: "var(--radius-input)" }}
              />
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr_220px_auto]">
                <select
                  aria-label="Agent hedef sütunu"
                  value={targetColumn}
                  onChange={(event) => {
                    setTargetColumn(event.target.value);
                    setAgent(null);
                    setAnalyst(null);
                    setReportStatus("");
                  }}
                  className="border border-border-default bg-surface-0 px-3 py-2 text-sm outline-none focus:border-accent"
                  style={{ borderRadius: "var(--radius-input)" }}
                >
                  <option value="">Hedef yok / Agent karar versin</option>
                  {ready.profile.schema
                    .filter((column) => ["numeric", "categorical", "boolean"].includes(column.role))
                    .map((column) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                </select>
                <select
                  aria-label="Agent hedef türü"
                  value={targetKind}
                  onChange={(event) => {
                    setTargetKind(event.target.value as "" | AnalystTargetKind);
                    setAgent(null);
                    setAnalyst(null);
                    setReportStatus("");
                  }}
                  className="border border-border-default bg-surface-0 px-3 py-2 text-sm outline-none focus:border-accent"
                  style={{ borderRadius: "var(--radius-input)" }}
                >
                  <option value="">Otomatik (yalnız ikili)</option>
                  <option value="binary">İkili sınıf</option>
                  <option value="continuous">Sürekli ölçüm</option>
                  <option value="categorical">Kategorik sınıf</option>
                </select>
                <button
                  type="button"
                  disabled={busy || !question.trim() || targetKindRequired}
                  onClick={() => void runAgent()}
                  className="bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ borderRadius: "var(--radius-button)" }}
                >
                  {activeOperation === "agent" ? "Araştırılıyor..." : "Agent ile araştır"}
                </button>
              </div>
              <p className="mt-2 text-xs text-t-tertiary">
                {targetKindRequired
                  ? "Seçilen hedef ikili görünmüyor; Agent için hedef türünü açıkça onaylayın."
                  : "Hedef seçmek zorunlu değildir. Sütun adı tek başına iş anlamı veya KPI tanımı sayılmaz."}
              </p>

              {agent && (
                <div className="mt-6 space-y-5 border-t border-border-default pt-5">
                  {(agent.status === "planner_unavailable" ||
                    agent.status === "execution_failed") && (
                    <div className="border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning-text">
                      <p className="font-medium">{agent.agent.message}</p>
                      <p className="mt-1 text-xs">
                        Deterministik Quick Dashboard kullanılabilir. Ollama hazır olduğunda Agent
                        isteğini yeniden çalıştırabilirsiniz.
                      </p>
                    </div>
                  )}

                  {agent.agent.plan && agent.agent.run && (
                    <>
                      <div>
                        <h3 className="text-sm font-semibold">Analiz planı</h3>
                        <p className="mt-1 text-xs text-t-tertiary">{agent.agent.plan.objective}</p>
                        <ol className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                          {agent.agent.plan.steps.map((step, index) => {
                            const event = agent.agent.run?.events.find(
                              (item) => item.step_id === step.step_id
                            );
                            return (
                              <li
                                key={step.step_id}
                                className="border border-border-default bg-surface-0 px-3 py-3 text-sm"
                                style={{ borderRadius: "var(--radius-card)" }}
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-medium">
                                    {index + 1}. {agentToolLabel(step.tool)}
                                  </span>
                                  <span
                                    className={
                                      event?.status === "completed"
                                        ? "text-xs text-success-text"
                                        : event?.status === "failed"
                                          ? "text-xs text-warning-text"
                                          : "text-xs text-t-tertiary"
                                    }
                                  >
                                    {event?.status === "completed"
                                      ? "Doğrulandı"
                                      : event?.status === "failed"
                                        ? "Tamamlanamadı"
                                        : "Çalıştırılmadı"}
                                  </span>
                                </div>
                                <p className="mt-1 text-xs leading-5 text-t-tertiary">
                                  {step.purpose}
                                </p>
                              </li>
                            );
                          })}
                        </ol>
                      </div>

                      <div>
                        <div className="flex items-center justify-between gap-3">
                          <h3 className="text-sm font-semibold">Doğrulanmış bulgular</h3>
                          <span className="text-xs text-t-tertiary">
                            {agent.agent.run.evidence.length.toLocaleString("tr-TR")} kanıt
                          </span>
                        </div>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                          {agent.agent.run.evidence.slice(0, 8).map((finding) => (
                            <div
                              key={finding.finding_id}
                              className="border border-border-default bg-surface-0 p-3"
                              style={{ borderRadius: "var(--radius-card)" }}
                            >
                              <p
                                className="truncate text-xs text-t-secondary"
                                title={finding.label}
                              >
                                {finding.label}
                              </p>
                              <p className="mt-2 text-lg font-semibold tabular-nums">
                                {formatValue(finding.value, finding.unit)}
                              </p>
                              <p
                                className="mt-2 truncate font-mono text-[9px] text-t-tertiary"
                                title={finding.finding_id}
                              >
                                {finding.finding_id}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  {agent.agent.synthesis?.status === "completed" && (
                    <div className="border border-success-border bg-success-subtle px-4 py-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold text-t-primary">
                          Doğrulanmış Agent özeti
                        </h3>
                        <span className="text-[11px] font-medium text-success-text">
                          {agent.agent.synthesis.model}
                        </span>
                      </div>
                      <ul className="mt-3 space-y-2 text-sm leading-6 text-t-secondary">
                        {agent.agent.synthesis.document.summary.map((statement, index) => (
                          <li key={`${index}-${statement.finding_ids.join("-")}`}>
                            {statement.text}
                          </li>
                        ))}
                      </ul>
                      {agent.agent.synthesis.document.limitations.length > 0 && (
                        <p className="mt-3 text-xs leading-5 text-t-tertiary">
                          Sınırlar: {agent.agent.synthesis.document.limitations.join(" ")}
                        </p>
                      )}
                      {agent.agent.synthesis.document.recommended_next_step && (
                        <p className="mt-2 text-xs font-medium text-t-secondary">
                          Önerilen sonraki adım:{" "}
                          {agent.agent.synthesis.document.recommended_next_step}
                        </p>
                      )}
                    </div>
                  )}
                  {agent.history?.status === "saved" && (
                    <p className="text-xs text-t-tertiary">
                      Doğrulanmış bulgu manifesti yerel analiz geçmişine kaydedildi.
                    </p>
                  )}
                  {agent.agent.synthesis && agent.agent.synthesis.status !== "completed" && (
                    <div className="border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning-text">
                      {agent.agent.synthesis.message}
                    </div>
                  )}
                </div>
              )}
            </Card>

            <Card>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.14em] text-accent">
                    Analyst Pipeline · Milestone 2
                  </p>
                  <h2 className="mt-1 text-base font-semibold">Kanıta bağlı ilişki taraması</h2>
                  <p className="mt-1 max-w-[760px] text-xs leading-5 text-t-tertiary">
                    Hedefi siz seçersiniz. LAC uygun testi deterministik çalıştırır, çoklu test
                    düzeltmesi uygular ve her sayıyı sabit finding kimliğine bağlar. Sütun adı iş
                    anlamı veya KPI tanımı sayılmaz.
                  </p>
                </div>
                {analyst?.verification.status === "passed" && (
                  <span className="rounded-badge bg-success-subtle px-2 py-1 text-[11px] font-medium text-success-text">
                    Sayısal sonuçlar doğrulandı
                  </span>
                )}
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-[1fr_220px_auto]">
                <select
                  aria-label="Analyst hedef sütunu"
                  value={targetColumn}
                  onChange={(event) => {
                    setTargetColumn(event.target.value);
                    setAgent(null);
                    setAnalyst(null);
                    setReportStatus("");
                  }}
                  className="border border-border-default bg-surface-0 px-3 py-2 text-sm outline-none focus:border-accent"
                  style={{ borderRadius: "var(--radius-input)" }}
                >
                  <option value="">Hedef sütun seçin</option>
                  {ready.profile.schema
                    .filter((column) => ["numeric", "categorical", "boolean"].includes(column.role))
                    .map((column) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                </select>
                <select
                  aria-label="Analyst hedef türü"
                  value={targetKind}
                  onChange={(event) => {
                    setTargetKind(event.target.value as "" | AnalystTargetKind);
                    setAgent(null);
                    setAnalyst(null);
                    setReportStatus("");
                  }}
                  className="border border-border-default bg-surface-0 px-3 py-2 text-sm outline-none focus:border-accent"
                  style={{ borderRadius: "var(--radius-input)" }}
                >
                  <option value="">Otomatik (yalnız ikili)</option>
                  <option value="binary">İkili sınıf</option>
                  <option value="continuous">Sürekli ölçüm</option>
                  <option value="categorical">Kategorik sınıf</option>
                </select>
                <button
                  type="button"
                  disabled={busy || !targetColumn || targetKindRequired}
                  onClick={() => void runAnalyst()}
                  className="bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ borderRadius: "var(--radius-button)" }}
                >
                  {activeOperation === "analyst" ? "Taranıyor..." : "Analyst taramasını çalıştır"}
                </button>
              </div>
              <p className="mt-2 text-xs text-t-tertiary">
                {targetKindRequired
                  ? "Bu hedef ikili görünmüyor. Devam etmek için hedef türünü açıkça seçin."
                  : "Otomatik seçim yalnız iki değerli hedeflerde kullanılır; diğer hedeflerde türü siz onaylarsınız."}
              </p>

              {analyst && (
                <div className="mt-6 space-y-5 border-t border-border-default pt-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs text-t-tertiary">
                      Excel, HTML ve PDF yalnız doğrulanmış finding manifestinden üretilir ve
                      indirmeden önce yeniden açılıp kontrol edilir.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {(["xlsx", "html", "pdf"] as const).map((format) => (
                        <button
                          key={format}
                          type="button"
                          disabled={busy}
                          onClick={() => void downloadAnalystReport(format)}
                          className="border border-accent px-4 py-2 text-sm font-medium text-accent hover:bg-accent-subtle disabled:opacity-50"
                          style={{ borderRadius: "var(--radius-button)" }}
                        >
                          {activeOperation === `report-${format}`
                            ? `${REPORT_LABELS[format]} hazırlanıyor...`
                            : `Doğrulanmış ${REPORT_LABELS[format]} raporunu indir`}
                        </button>
                      ))}
                    </div>
                  </div>
                  {reportStatus && (
                    <p className="border border-success-border bg-success-subtle px-3 py-2 text-sm text-success-text">
                      {reportStatus}
                    </p>
                  )}
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {analyst.dashboard.cards.map((card) => (
                      <div
                        key={card.finding_id}
                        className="border border-border-default bg-surface-0 p-3"
                        style={{ borderRadius: "var(--radius-card)" }}
                      >
                        <p className="truncate text-xs text-t-secondary" title={card.label}>
                          {card.label}
                        </p>
                        <p className="mt-2 text-xl font-semibold tabular-nums">
                          {formatValue(card.value, card.unit)}
                        </p>
                        <p
                          className="mt-2 truncate font-mono text-[9px] text-t-tertiary"
                          title={card.finding_id}
                        >
                          {card.finding_id}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="text-xs text-t-tertiary">
                        <tr>
                          <th className="pb-2 font-medium">Predictor</th>
                          <th className="pb-2 font-medium">Yöntem</th>
                          <th className="pb-2 font-medium">Etki ölçüsü</th>
                          <th className="pb-2 font-medium">Kontrol</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border-default">
                        {analyst.analyses.map((analysis) => (
                          <tr key={analysis.analysis_id}>
                            <td className="py-2.5 font-mono text-xs">{analysis.predictor}</td>
                            <td className="py-2.5">{analysis.method}</td>
                            <td className="py-2.5">{analysis.effect_name}</td>
                            <td className="py-2.5">{analysis.assumption_status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="border border-warning-border bg-warning-bg px-3 py-2 text-xs text-warning-text">
                    {analyst.kpi_selection.reason}
                  </p>
                  <div className="border border-border-default bg-surface-0 px-4 py-3">
                    <p className="text-xs font-medium text-t-primary">Analyst Qwen açıklaması</p>
                    <p className="mt-1 text-[11px] text-t-tertiary">
                      Ham satırlar değil, yalnız doğrulanmış Analyst finding kanıtları kullanılır.
                    </p>
                    {analyst.interpretation.status === "completed" && (
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-t-secondary">
                        {analyst.interpretation.text}
                      </p>
                    )}
                    {(analyst.interpretation.status === "rejected" ||
                      analyst.interpretation.status === "unavailable") && (
                      <p className="mt-3 text-sm text-warning-text">
                        {analyst.interpretation.message}
                      </p>
                    )}
                    {analyst.interpretation.status === "skipped" && (
                      <p className="mt-3 text-sm text-t-secondary">
                        Analyst model açıklaması çalıştırılmadı.
                      </p>
                    )}
                  </div>
                </div>
              )}
            </Card>

            <Card>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Yerel Qwen yorumu</h2>
                  <p className="mt-1 text-xs text-t-tertiary">
                    Ham satırlar modele gönderilmez; yalnız LAC profil özeti kullanılır.
                  </p>
                </div>
                {ready.interpretation.status === "completed" && (
                  <span className="rounded-badge bg-success-subtle px-2 py-1 text-[11px] font-medium text-success-text">
                    {ready.interpretation.model}
                  </span>
                )}
              </div>

              {ready.interpretation.status === "completed" && (
                <p className="mt-5 whitespace-pre-wrap text-sm leading-6 text-t-secondary">
                  {ready.interpretation.text}
                </p>
              )}
              {ready.interpretation.status === "unavailable" && (
                <div className="mt-5 border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning-text">
                  {ready.interpretation.message}
                </div>
              )}
              {ready.interpretation.status === "rejected" && (
                <div className="mt-5 border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning-text">
                  {ready.interpretation.message}
                </div>
              )}
              {ready.interpretation.status === "skipped" && (
                <p className="mt-5 text-sm text-t-secondary">Model yorumu çalıştırılmadı.</p>
              )}

              <div className="mt-6 flex flex-col gap-3 border-t border-border-default pt-5 sm:flex-row">
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  maxLength={20000}
                  className="min-w-0 flex-1 border border-border-default bg-surface-0 px-3 py-2 text-sm outline-none focus:border-accent"
                  style={{ borderRadius: "var(--radius-input)" }}
                  aria-label="Qwen yorum sorusu"
                />
                <button
                  type="button"
                  disabled={busy || !question.trim()}
                  onClick={() => void reinterpret()}
                  className="bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                  style={{ borderRadius: "var(--radius-button)" }}
                >
                  {activeOperation === "quick" ? "Yorumlanıyor..." : "Yeniden yorumla"}
                </button>
              </div>
            </Card>

            <p className="pb-4 text-center text-[11px] text-t-tertiary">
              Tüm sayısal kartlar LAC `finding_id` ve deterministic source alanlarından gelir.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
