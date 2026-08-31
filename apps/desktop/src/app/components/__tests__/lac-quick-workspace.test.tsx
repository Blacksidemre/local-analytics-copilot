// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const bridge = vi.hoisted(() => ({
  health: vi.fn(),
  upload: vi.fn(),
  quick: vi.fn(),
  analyst: vi.fn(),
  agent: vi.fn(),
  analystReport: vi.fn(),
  analystHtmlReport: vi.fn(),
  analystPdfReport: vi.fn(),
}));

vi.mock("@/lib/lac-bridge-client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/lac-bridge-client")>();
  return {
    ...original,
    LacBridgeClient: vi.fn(function MockLacBridgeClient() {
      return bridge;
    }),
  };
});

import { LacQuickWorkspace } from "@/app/components/lac-quick-workspace";

const cards = [
  ["profile.shape.rows", "Satır", 1508, "rows"],
  ["profile.shape.columns", "Sütun", 22, "columns"],
  ["profile.quality.missing_cells", "Eksik", 52, "cells"],
  ["profile.quality.exact_duplicate_copies", "Tekrar", 8, "rows"],
  ["profile.quality.score_heuristic", "Kalite", 98.4, "score_0_100"],
].map(([finding_id, label, value, unit]) => ({
  finding_id,
  kind: "metric",
  label,
  value,
  unit,
  source: "deterministic:test",
}));

const analysis = {
  status: "completed",
  mode: "quick",
  file_path: "/safe/book.xlsx",
  profile: {
    profile_version: 1,
    rows: 1508,
    columns: 22,
    total_cells: 33176,
    total_missing_cells: 52,
    duplicate_rows: 8,
    duplicate_rows_including_originals: 16,
    duplicate_pct: 0.53,
    quality_score_heuristic: 98.4,
    roles: {},
    schema: [
      {
        name: "utilization_rate",
        dtype: "float64",
        role: "numeric",
        missing: 0,
        unique: 100,
      },
      {
        name: "default_next_30d",
        dtype: "int64",
        role: "numeric",
        missing: 0,
        unique: 2,
      },
    ],
    missing_count: {},
    missing_pct: {},
    constant_columns: [],
    findings: cards,
    ingestion: {},
  },
  dashboard: {
    dashboard_version: 1,
    title: "Quick Dashboard",
    cards,
    missing_by_column: [],
    role_counts: [{ role: "numeric", count: 3 }],
    constant_columns: [],
    ingestion: {},
    warnings: [],
    evidence_policy: "all_numeric_cards_bound_to_finding_id",
  },
  interpretation: {
    status: "completed",
    model: "qwen3.5:9b",
    text: "Satır sayısı profile.shape.rows bulgusuna dayanır.",
    verification: {},
    evidence_finding_ids: ["profile.shape.rows"],
    available_finding_ids: cards.map((card) => card.finding_id),
  },
};

const analystFinding = {
  finding_id: "analyst.target.21.association.column.10.effect",
  kind: "statistical_metric",
  label: "utilization_rate association effect",
  value: 0.62,
  unit: "rank_biserial",
  source: "rank_biserial_from_mann_whitney_u",
};

const analystResult = {
  schema_version: "analyst.v1",
  status: "completed",
  mode: "analyst",
  target_semantics: {
    column: "default_next_30d",
    statistical_role: "binary",
    selection_source: "explicit_request",
    business_meaning_status: "unverified",
    business_meaning: null,
  },
  kpi_selection: {
    status: "requires_approved_definition",
    selected: [],
    reason: "Onaylanmış business KPI tanımı gerekli.",
  },
  analyses: [
    {
      analysis_id: "analyst.target.21.association.column.10",
      predictor: "utilization_rate",
      method: "mann_whitney_u",
      effect_name: "rank_biserial",
      assumption_status: "passed",
    },
  ],
  findings: [analystFinding],
  dashboard: {
    schema_version: 1,
    cards: [analystFinding],
    evidence_policy: "all_numeric_cards_bound_to_finding_id",
  },
  verification: { status: "passed", errors: [] },
  interpretation: {
    status: "completed",
    model: "qwen3.5:9b",
    text: "Doğrulanmış Analyst açıklaması.",
    verification: { status: "passed" },
    evidence_finding_ids: [analystFinding.finding_id],
    available_finding_ids: [analystFinding.finding_id],
  },
};

const agentResult = {
  schema_version: "agent-api.v1",
  status: "completed",
  mode: "agent",
  file_path: "/safe/book.xlsx",
  selected_sheet: "0",
  dataset: {
    rows: 1508,
    columns: 22,
    total_missing_cells: 52,
    missing_cell_pct: 0.1567,
    exact_duplicate_copies: 8,
    schema: analysis.profile.schema,
  },
  dashboard: analysis.dashboard,
  history: { status: "saved", run_id: "a".repeat(32) },
  agent: {
    schema_version: "investigate-response.v1",
    status: "completed",
    planner: { status: "completed", model: "qwen3.5:9b" },
    plan: {
      objective: "Deterministik veri kalitesini özetle.",
      completion_criteria: ["profile_verified"],
      steps: [
        {
          step_id: "profile",
          purpose: "Veri kalitesini doğrula.",
          tool: "profile_dataset",
          depends_on: [],
        },
      ],
    },
    run: {
      schema_version: "investigate-run.v1",
      status: "completed",
      stop_reason: "goal_completed",
      completion: { required: ["profile_verified"], completed: ["profile_verified"] },
      budget: { max_steps: 6, max_failed_calls: 2, failed_calls: 0 },
      events: [
        {
          step_id: "profile",
          tool: "profile_dataset",
          status: "completed",
          verification: { status: "passed", errors: [] },
        },
      ],
      evidence: cards,
      verification: { status: "passed", scope: "evidence", errors: [] },
    },
    synthesis: {
      status: "completed",
      model: "qwen3.5:9b",
      document: {
        schema_version: "investigate-synthesis.v1",
        summary: [
          {
            text: "Veri setinde 1.508 satır bulunuyor.",
            finding_ids: ["profile.shape.rows"],
          },
        ],
        limitations: ["İş anlamı onaylı metadata olmadan belirlenemiyor."],
        recommended_next_step: "Gerekirse açık bir hedef seçin.",
      },
      verification: {
        status: "passed",
        cited_finding_ids: ["profile.shape.rows"],
        errors: [],
      },
    },
  },
};

beforeEach(() => {
  bridge.health.mockReset().mockResolvedValue({
    status: "ready",
    ollama: {
      status: "ready",
      models: ["qwen3.5:9b", "qwen3:14b"],
      configured_model: "qwen3.5:9b",
      configured_model_available: true,
    },
  });
  bridge.upload.mockReset();
  bridge.quick.mockReset();
  bridge.analyst.mockReset();
  bridge.agent.mockReset();
  bridge.analystReport.mockReset();
  bridge.analystHtmlReport.mockReset();
  bridge.analystPdfReport.mockReset();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LacQuickWorkspace", () => {
  it("offers a recoverable health check when the local bridge is unavailable", async () => {
    bridge.health.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({
      status: "ready",
      ollama: {
        status: "ready",
        models: ["qwen3.5:9b"],
        configured_model: "qwen3.5:9b",
        configured_model_available: true,
      },
    });
    render(<LacQuickWorkspace />);

    expect(await screen.findByText("LAC bağlantısı sınırlı")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Yeniden dene" }));

    expect(await screen.findByText("LAC hazır")).toBeInTheDocument();
    expect(bridge.health).toHaveBeenCalledTimes(2);
  });

  it("shows operation-specific progress while deterministic profiling is running", async () => {
    let resolveUpload: ((value: unknown) => void) | undefined;
    bridge.upload.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        })
    );
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });

    expect(
      await screen.findByText("Dosya güvenli biçimde okunuyor ve profilleniyor...")
    ).toBeInTheDocument();
    resolveUpload?.({ ...analysis, status: "profiled", manifest: {} });
    expect(await screen.findByText("Deterministik Quick Dashboard")).toBeInTheDocument();
  });

  it("renders finding-bound KPI cards and local Qwen interpretation", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
      selected_sheet: undefined,
    });
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });

    expect(await screen.findByText("Deterministik Quick Dashboard")).toBeInTheDocument();
    expect(screen.getByText("1.508")).toBeInTheDocument();
    expect(screen.getByText("profile.shape.rows")).toBeInTheDocument();
    expect(screen.getByText(/Satır sayısı profile.shape.rows/)).toBeInTheDocument();
  });

  it("selects an Excel sheet using the stored path without uploading again", async () => {
    bridge.upload.mockResolvedValue({
      status: "sheet_selection_required",
      file_path: "/safe/book.xlsx",
      manifest: {},
      sheet_options: [
        {
          index: 0,
          name: "Data",
          header_row: 1,
          estimated_rows: 1508,
          estimated_columns: 22,
          columns: [],
          empty: false,
        },
      ],
    });
    bridge.quick.mockResolvedValue(analysis);
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["xlsx"], "book.xlsx")] } });
    await screen.findByText("Çalışma sayfası seç");
    fireEvent.click(screen.getByRole("button", { name: /Data[\s\S]*Analiz et/ }));

    await waitFor(() => expect(bridge.quick).toHaveBeenCalledTimes(1));
    expect(bridge.upload).toHaveBeenCalledTimes(1);
    expect(bridge.quick).toHaveBeenCalledWith(
      "/safe/book.xlsx",
      expect.objectContaining({ sheetName: "Data", interpret: true })
    );
    expect(await screen.findByText("Sayfa: Data")).toBeInTheDocument();
  });

  it("does not display model prose rejected by the LAC verifier", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
      interpretation: {
        status: "rejected",
        model: "qwen3.5:9b",
        message: "Yerel model yorumu kanıt doğrulamasını geçmedi.",
        verification: { status: "needs_review" },
        evidence_finding_ids: [],
        available_finding_ids: cards.map((card) => card.finding_id),
      },
    });
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });

    expect(
      await screen.findByText("Yerel model yorumu kanıt doğrulamasını geçmedi.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/Satır sayısı profile.shape.rows/)).not.toBeInTheDocument();
  });

  it("runs the verified Analyst pipeline only after an explicit target selection", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
    });
    bridge.analyst.mockResolvedValue(analystResult);
    bridge.analystReport.mockResolvedValue({
      format: "xlsx",
      schemaVersion: "analyst-report.v1",
      filename: "analyst_report.xlsx",
      blob: new Blob(["xlsx"]),
      verification: { status: "passed", findingCount: 1, dashboardCardCount: 1 },
    });
    bridge.analystHtmlReport.mockResolvedValue({
      format: "html",
      schemaVersion: "analyst-html-report.v1",
      filename: "analyst_report.html",
      blob: new Blob(["html"]),
      verification: { status: "passed", findingCount: 1, dashboardCardCount: 1 },
    });
    bridge.analystPdfReport.mockResolvedValue({
      format: "pdf",
      schemaVersion: "analyst-pdf-report.v1",
      filename: "analyst_report.pdf",
      blob: new Blob(["pdf"]),
      verification: { status: "passed", findingCount: 1, dashboardCardCount: 1 },
    });
    class DownloadURL extends URL {
      static createObjectURL = vi.fn(() => "blob:analyst-report");
      static revokeObjectURL = vi.fn();
    }
    vi.stubGlobal("URL", DownloadURL);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });
    await screen.findByText("Deterministik Quick Dashboard");
    fireEvent.change(screen.getByLabelText("Analyst hedef sütunu"), {
      target: { value: "default_next_30d" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyst taramasını çalıştır" }));

    await waitFor(() => expect(bridge.analyst).toHaveBeenCalledTimes(1));
    expect(bridge.analyst).toHaveBeenCalledWith(
      "/safe/book.xlsx",
      "default_next_30d",
      expect.objectContaining({
        targetKind: undefined,
        interpret: true,
        question: expect.any(String),
        language: "tr",
      })
    );
    expect(await screen.findByText("Sayısal sonuçlar doğrulandı")).toBeInTheDocument();
    expect(screen.getByText("analyst.target.21.association.column.10.effect")).toBeInTheDocument();
    expect(screen.getByText("Doğrulanmış Analyst açıklaması.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Doğrulanmış Excel raporunu indir" }));
    await waitFor(() => expect(bridge.analystReport).toHaveBeenCalledTimes(1));
    expect(bridge.analystReport).toHaveBeenCalledWith(
      "/safe/book.xlsx",
      "default_next_30d",
      expect.objectContaining({ interpret: true, language: "tr" })
    );
    expect(
      await screen.findByText("Doğrulanmış Excel raporu indirildi: analyst_report.xlsx")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Doğrulanmış HTML raporunu indir" }));
    await waitFor(() => expect(bridge.analystHtmlReport).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText("Doğrulanmış HTML raporu indirildi: analyst_report.html")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Doğrulanmış PDF raporunu indir" }));
    await waitFor(() => expect(bridge.analystPdfReport).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText("Doğrulanmış PDF raporu indirildi: analyst_report.pdf")
    ).toBeInTheDocument();
  });

  it("runs the bounded local Agent and renders only verified synthesis", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
    });
    bridge.agent.mockResolvedValue(agentResult);
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });
    await screen.findByText("Deterministik Quick Dashboard");
    fireEvent.change(screen.getByLabelText("Agent analiz isteği"), {
      target: { value: "Bu veri setini özetle." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agent ile araştır" }));

    await waitFor(() => expect(bridge.agent).toHaveBeenCalledTimes(1));
    expect(bridge.agent).toHaveBeenCalledWith(
      "/safe/book.xlsx",
      "Bu veri setini özetle.",
      expect.objectContaining({
        targetColumn: undefined,
        targetKind: undefined,
        language: "tr",
      })
    );
    expect(await screen.findByText("Agent kanıtları doğrulandı")).toBeInTheDocument();
    expect(screen.getByText(/Veri profili/)).toBeInTheDocument();
    expect(screen.getByText("Doğrulanmış Agent özeti")).toBeInTheDocument();
    expect(screen.getByText("Veri setinde 1.508 satır bulunuyor.")).toBeInTheDocument();
  });

  it("requires an explicit statistical kind for a non-binary target", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
      profile: {
        ...analysis.profile,
        schema: [
          ...analysis.profile.schema,
          {
            name: "continuous_target",
            dtype: "float64",
            role: "numeric",
            missing: 0,
            unique: 1508,
          },
        ],
      },
    });
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });
    await screen.findByText("Deterministik Quick Dashboard");
    fireEvent.change(screen.getByLabelText("Analyst hedef sütunu"), {
      target: { value: "continuous_target" },
    });

    const runButton = screen.getByRole("button", { name: "Analyst taramasını çalıştır" });
    expect(runButton).toBeDisabled();
    expect(
      screen.getByText("Bu hedef ikili görünmüyor. Devam etmek için hedef türünü açıkça seçin.")
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Analyst hedef türü"), {
      target: { value: "continuous" },
    });
    expect(runButton).toBeEnabled();
  });

  it("does not render rejected Analyst prose", async () => {
    bridge.upload.mockResolvedValue({
      ...analysis,
      status: "profiled",
      manifest: {},
    });
    bridge.analyst.mockResolvedValue({
      ...analystResult,
      interpretation: {
        status: "rejected",
        model: "qwen3.5:9b",
        text: "GÖSTERİLMEMESİ GEREKEN ANALYST METNİ",
        message: "Analyst açıklaması kanıt doğrulamasını geçmedi.",
        verification: { status: "needs_review" },
        evidence_finding_ids: [],
        available_finding_ids: [analystFinding.finding_id],
      },
    });
    const { container } = render(<LacQuickWorkspace />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["a,b\n1,2"], "data.csv")] } });
    await screen.findByText("Deterministik Quick Dashboard");
    fireEvent.change(screen.getByLabelText("Analyst hedef sütunu"), {
      target: { value: "default_next_30d" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Analyst taramasını çalıştır" }));

    expect(
      await screen.findByText("Analyst açıklaması kanıt doğrulamasını geçmedi.")
    ).toBeInTheDocument();
    expect(screen.queryByText("GÖSTERİLMEMESİ GEREKEN ANALYST METNİ")).not.toBeInTheDocument();
  });
});
