import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LacBridgeClient,
  LacBridgeError,
  type AgentResult,
  type AnalystResult,
  type BridgeDashboard,
  type BridgeProfile,
} from "@/lib/lac-bridge-client";

const cards = [
  ["profile.shape.rows", "Satır", 1508, "rows"],
  ["profile.shape.columns", "Sütun", 22, "columns"],
  ["profile.quality.missing_cells", "Eksik", 52, "cells"],
  ["profile.quality.exact_duplicate_copies", "Tekrar", 8, "rows"],
  ["profile.quality.score_heuristic", "Kalite", 98.4, "score_0_100"],
].map(([finding_id, label, value, unit]) => ({
  finding_id: finding_id as string,
  kind: "metric" as const,
  label: label as string,
  value: value as number,
  unit: unit as string,
  source: "deterministic:test",
}));

const dashboard: BridgeDashboard = {
  dashboard_version: 1,
  title: "Quick Dashboard",
  cards,
  missing_by_column: [],
  role_counts: [{ role: "numeric", count: 3 }],
  constant_columns: [],
  ingestion: {},
  warnings: [],
  evidence_policy: "all_numeric_cards_bound_to_finding_id",
};

const profile: BridgeProfile = {
  profile_version: 1,
  rows: 1508,
  columns: 22,
  total_cells: 33176,
  total_missing_cells: 52,
  duplicate_rows: 8,
  duplicate_rows_including_originals: 16,
  duplicate_pct: 0.53,
  quality_score_heuristic: 98.4,
  roles: { numeric: ["amount"] },
  schema: [],
  missing_count: {},
  missing_pct: {},
  constant_columns: [],
  findings: cards,
  ingestion: {},
};

const analystFindings = [
  {
    finding_id: "analyst.target.2.association.column.1.effect",
    kind: "statistical_metric" as const,
    label: "value association effect",
    value: 0.62,
    unit: "rank_biserial",
    source: "rank_biserial_from_mann_whitney_u",
  },
  {
    finding_id: "analyst.target.2.association.column.1.p_value",
    kind: "statistical_metric" as const,
    label: "value raw p-value",
    value: 0.01,
    unit: "p_value",
    source: "scipy_mannwhitneyu",
  },
  {
    finding_id: "analyst.target.2.association.column.1.adjusted_p_value",
    kind: "statistical_metric" as const,
    label: "value adjusted p-value",
    value: 0.02,
    unit: "adjusted_p_value",
    source: "benjamini_hochberg_all_executed_tests",
  },
  {
    finding_id: "analyst.target.2.association.column.1.n",
    kind: "statistical_metric" as const,
    label: "value complete observations",
    value: 1508,
    unit: "observations",
    source: "pairwise_complete_observation_count",
  },
];

const analystResult: AnalystResult = {
  schema_version: "analyst.v1",
  status: "completed",
  mode: "analyst",
  file_path: "/safe/data.csv",
  selected_sheet: "0",
  profile,
  target_semantics: {
    column: "target",
    statistical_role: "binary",
    selection_source: "explicit_request",
    business_meaning_status: "unverified",
    business_meaning: null,
  },
  kpi_selection: {
    status: "requires_approved_definition",
    selected: [],
    reason: "Approved definition required.",
  },
  analyses: [
    {
      analysis_id: "analyst.target.2.association.column.1",
      target: "target",
      predictor: "value",
      predictor_kind: "numeric",
      method: "mann_whitney_u",
      effect_name: "rank_biserial",
      finding_ids: {
        effect: analystFindings[0].finding_id,
        p_value: analystFindings[1].finding_id,
        adjusted_p_value: analystFindings[2].finding_id,
        n: analystFindings[3].finding_id,
      },
      assumption_status: "passed",
    },
  ],
  findings: analystFindings,
  dashboard: {
    schema_version: 1,
    title: "Deterministic target association screening",
    cards: [analystFindings[0]],
    ranking_basis: "adjusted_p_value_then_finding_id",
    evidence_policy: "all_numeric_cards_bound_to_finding_id",
    warning: "Association is not causality.",
  },
  verification: { status: "passed", scope: "evidence", errors: [] },
  interpretation: {
    status: "completed",
    model: "qwen3.5:9b",
    text: "Kanıtlı Analyst açıklaması.",
    verification: { status: "passed" },
    evidence_finding_ids: [analystFindings[0].finding_id],
    available_finding_ids: analystFindings.map((finding) => finding.finding_id),
  },
};

const agentResult: AgentResult = {
  schema_version: "agent-api.v1",
  status: "completed",
  mode: "agent",
  file_path: "/safe/data.csv",
  selected_sheet: "0",
  dataset: {
    rows: 1508,
    columns: 22,
    total_missing_cells: 52,
    missing_cell_pct: 0.1567,
    exact_duplicate_copies: 8,
    schema: profile.schema,
  },
  dashboard,
  history: { status: "saved", run_id: "a".repeat(32) },
  agent: {
    schema_version: "investigate-response.v1",
    status: "completed",
    planner: { status: "completed", model: "qwen3.5:9b" },
    plan: {
      objective: "Deterministik profili özetle.",
      completion_criteria: ["profile_verified"],
      steps: [
        {
          step_id: "profile",
          purpose: "Profili doğrula.",
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
          { text: "Veri setinde 1508 satır bulunuyor.", finding_ids: ["profile.shape.rows"] },
        ],
        limitations: ["İş anlamı doğrulanmadı."],
        recommended_next_step: null,
      },
      verification: {
        status: "passed",
        cited_finding_ids: ["profile.shape.rows"],
        errors: [],
      },
    },
  },
};

const mockFetch = vi.fn<typeof fetch>();

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
});

afterEach(() => vi.unstubAllGlobals());

describe("LacBridgeClient", () => {
  it("reads bridge health through the same-origin proxy", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        status: "ready",
        bridge_api_version: 1,
        data_bridge: { status: "ready", parser: "lac", supported_extensions: [".csv"] },
        ollama: {
          status: "ready",
          models: ["qwen3.5:9b"],
          configured_model: "qwen3.5:9b",
          configured_model_available: true,
        },
      })
    );

    const result = await new LacBridgeClient().health();

    expect(result.status).toBe("ready");
    expect(mockFetch).toHaveBeenCalledWith("/api/lac/api/v1/health", { signal: undefined });
  });

  it("keeps a multi-sheet upload for selection without requiring a dashboard", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        status: "sheet_selection_required",
        file_path: "/safe/book.xlsx",
        manifest: {},
        sheet_options: [
          {
            index: 0,
            name: "Data",
            header_row: 1,
            estimated_rows: 100,
            estimated_columns: 8,
            columns: [],
            empty: false,
          },
        ],
      })
    );

    const result = await new LacBridgeClient().upload(new File(["xlsx"], "book.xlsx"));

    expect(result.status).toBe("sheet_selection_required");
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/lac/api/v1/datasets/upload");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeInstanceOf(FormData);
    expect((init?.body as FormData).get("run_profile")).toBe("true");
  });

  it("accepts only a finding-bound profiled upload dashboard", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        status: "profiled",
        file_path: "/safe/data.csv",
        manifest: {},
        profile,
        dashboard,
        interpretation: { status: "skipped" },
      })
    );

    const result = await new LacBridgeClient().upload(new File(["a,b\n1,2"], "data.csv"));

    expect(result.dashboard?.cards).toHaveLength(5);
  });

  it("uses the stored file path and selected sheet for Quick analysis", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        status: "completed",
        mode: "quick",
        file_path: "/safe/book.xlsx",
        profile,
        dashboard,
        interpretation: { status: "skipped" },
      })
    );

    const result = await new LacBridgeClient().quick("/safe/book.xlsx", {
      sheetName: "Data",
      question: "Özetle",
      model: "qwen3.5:9b",
    });

    expect(result.dashboard.cards[0].finding_id).toBe("profile.shape.rows");
    const body = JSON.parse(String(mockFetch.mock.calls[0][1]?.body));
    expect(body).toMatchObject({
      file_path: "/safe/book.xlsx",
      sheet_name: "Data",
      interpret: true,
      question: "Özetle",
      language: "tr",
      model: "qwen3.5:9b",
    });
  });

  it("requests a verified Analyst result for an explicit target", async () => {
    mockFetch.mockResolvedValue(Response.json(analystResult));

    const result = await new LacBridgeClient().analyst("/safe/data.csv", "target", {
      targetKind: "binary",
      sheetName: "Data",
      interpret: true,
      question: "İlişkileri açıkla",
    });

    expect(result.verification.status).toBe("passed");
    expect(result.dashboard.cards[0].finding_id).toBe(
      "analyst.target.2.association.column.1.effect"
    );
    const body = JSON.parse(String(mockFetch.mock.calls[0][1]?.body));
    expect(body).toMatchObject({
      file_path: "/safe/data.csv",
      sheet_name: "Data",
      target_column: "target",
      target_kind: "binary",
      interpret: true,
      question: "İlişkileri açıkla",
      language: "tr",
    });
  });

  it("requests and accepts only a verifier-passed bounded Agent result", async () => {
    mockFetch.mockResolvedValue(Response.json(agentResult));

    const result = await new LacBridgeClient().agent("/safe/data.csv", "Veriyi özetle.", {
      sheetName: "Data",
      targetColumn: "target",
      targetKind: "binary",
    });

    expect(result.agent.run?.verification.status).toBe("passed");
    expect(result.agent.synthesis?.status).toBe("completed");
    const body = JSON.parse(String(mockFetch.mock.calls[0][1]?.body));
    expect(body).toMatchObject({
      file_path: "/safe/data.csv",
      sheet_name: "Data",
      question: "Veriyi özetle.",
      target_column: "target",
      target_kind: "binary",
      language: "tr",
    });
  });

  it("rejects Agent synthesis that cites fake evidence", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        ...agentResult,
        agent: {
          ...agentResult.agent,
          synthesis: {
            ...agentResult.agent.synthesis,
            document: {
              ...agentResult.agent.synthesis?.document,
              summary: [{ text: "Sahte sonuç.", finding_ids: ["fake.finding"] }],
            },
          },
        },
      })
    );

    await expect(
      new LacBridgeClient().agent("/safe/data.csv", "Kanıtsız sayı üret.")
    ).rejects.toMatchObject({ status: 502, detail: { code: "invalid_agent_evidence" } });
  });

  it("rejects Analyst interpretation prose that did not pass verification", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        ...analystResult,
        interpretation: {
          status: "completed",
          model: "qwen3.5:9b",
          text: "Unverified prose",
          verification: { status: "needs_review" },
          evidence_finding_ids: [],
          available_finding_ids: [],
        },
      })
    );

    await expect(new LacBridgeClient().analyst("/safe/data.csv", "target")).rejects.toMatchObject({
      status: 502,
      detail: { code: "unsupported_analyst_contract" },
    });
  });

  it("rejects an Analyst card that is not bound to its finding", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        ...analystResult,
        dashboard: {
          ...analystResult.dashboard,
          cards: [{ ...analystResult.dashboard.cards[0], value: 999 }],
        },
      })
    );

    await expect(new LacBridgeClient().analyst("/safe/data.csv", "target")).rejects.toMatchObject({
      status: 502,
      detail: { code: "invalid_analyst_evidence" },
    });
  });

  it("downloads only a verifier-passed Analyst XLSX contract", async () => {
    mockFetch.mockResolvedValue(
      new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04, 1, 2, 3]), {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": 'attachment; filename="analyst_report.xlsx"',
          "X-LAC-Report-Schema": "analyst-report.v1",
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "4",
          "X-LAC-Report-Cards": "1",
        },
      })
    );

    const result = await new LacBridgeClient().analystReport("/safe/data.csv", "target", {
      sheetName: "Data",
      targetKind: "binary",
      interpret: false,
      outputName: "analyst_report.xlsx",
    });

    expect(result.format).toBe("xlsx");
    expect(result.filename).toBe("analyst_report.xlsx");
    expect(result.verification).toEqual({
      status: "passed",
      findingCount: 4,
      dashboardCardCount: 1,
    });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/lac/api/v1/analysis/analyst/report");
    expect(new Headers(init?.headers).get("Accept")).toContain("spreadsheetml.sheet");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      file_path: "/safe/data.csv",
      target_column: "target",
      target_kind: "binary",
      sheet_name: "Data",
      interpret: false,
      output_name: "analyst_report.xlsx",
    });
  });

  it.each([
    {
      format: "html" as const,
      path: "/api/v1/analysis/analyst/report/html",
      mediaType: "text/html; charset=utf-8",
      schema: "analyst-html-report.v1",
      filename: "analyst_report.html",
      body: "<!doctype html><html><body>verified</body></html>",
    },
    {
      format: "pdf" as const,
      path: "/api/v1/analysis/analyst/report/pdf",
      mediaType: "application/pdf",
      schema: "analyst-pdf-report.v1",
      filename: "analyst_report.pdf",
      body: "%PDF-1.7 verified",
    },
  ])("downloads only a verifier-passed Analyst $format contract", async (contract) => {
    mockFetch.mockResolvedValue(
      new Response(contract.body, {
        status: 200,
        headers: {
          "Content-Type": contract.mediaType,
          "Content-Disposition": `attachment; filename="${contract.filename}"`,
          "X-LAC-Report-Schema": contract.schema,
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "4",
          "X-LAC-Report-Cards": "1",
        },
      })
    );
    const client = new LacBridgeClient();

    const result =
      contract.format === "html"
        ? await client.analystHtmlReport("/safe/data.csv", "target")
        : await client.analystPdfReport("/safe/data.csv", "target");

    expect(result).toMatchObject({
      format: contract.format,
      schemaVersion: contract.schema,
      filename: contract.filename,
      verification: { status: "passed", findingCount: 4, dashboardCardCount: 1 },
    });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe(`/api/lac${contract.path}`);
    expect(new Headers(init?.headers).get("Accept")).toBe(contract.mediaType.split(";")[0]);
    expect(JSON.parse(String(init?.body)).output_name).toBe(contract.filename);
  });

  it.each([
    {
      format: "xlsx" as const,
      mediaType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      schema: "agent-report.v1",
      filename: "agent_report.xlsx",
      body: new Uint8Array([0x50, 0x4b, 0x03, 0x04, 1]),
    },
    {
      format: "html" as const,
      mediaType: "text/html; charset=utf-8",
      schema: "agent-html-report.v1",
      filename: "agent_report.html",
      body: "<!doctype html><html><body>verified</body></html>",
    },
    {
      format: "pdf" as const,
      mediaType: "application/pdf",
      schema: "agent-pdf-report.v1",
      filename: "agent_report.pdf",
      body: "%PDF-1.7 verified",
    },
  ])("downloads only a verifier-passed Agent $format evidence contract", async (contract) => {
    mockFetch.mockResolvedValue(
      new Response(contract.body, {
        status: 200,
        headers: {
          "Content-Type": contract.mediaType,
          "Content-Disposition": `attachment; filename="${contract.filename}"`,
          "X-LAC-Report-Schema": contract.schema,
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "5",
          "X-LAC-Report-Cards": "0",
        },
      })
    );

    const result = await new LacBridgeClient().agentReport("a".repeat(32), contract.format);

    expect(result).toMatchObject({
      format: contract.format,
      schemaVersion: contract.schema,
      filename: contract.filename,
      verification: { status: "passed", findingCount: 5, dashboardCardCount: 0 },
    });
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/lac/api/v1/analysis/agent/report");
    expect(JSON.parse(String(init?.body))).toEqual({
      run_id: "a".repeat(32),
      format: contract.format,
      output_name: contract.filename,
    });
  });

  it("rejects an Agent report that claims dashboard cards or an invalid run ID", async () => {
    await expect(new LacBridgeClient().agentReport("not-a-run", "xlsx")).rejects.toMatchObject({
      status: 400,
      detail: { code: "invalid_agent_report_run_id" },
    });
    expect(mockFetch).not.toHaveBeenCalled();

    mockFetch.mockResolvedValue(
      new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": 'attachment; filename="agent_report.xlsx"',
          "X-LAC-Report-Schema": "agent-report.v1",
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "5",
          "X-LAC-Report-Cards": "1",
        },
      })
    );
    await expect(new LacBridgeClient().agentReport("a".repeat(32), "xlsx")).rejects.toMatchObject({
      status: 502,
      detail: { code: "invalid_agent_report_contract" },
    });
  });

  it("rejects a PDF download with valid headers but invalid file magic", async () => {
    mockFetch.mockResolvedValue(
      new Response("<!doctype html>", {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="analyst_report.pdf"',
          "X-LAC-Report-Schema": "analyst-pdf-report.v1",
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "4",
          "X-LAC-Report-Cards": "1",
        },
      })
    );

    await expect(
      new LacBridgeClient().analystPdfReport("/safe/data.csv", "target")
    ).rejects.toMatchObject({
      status: 502,
      detail: { code: "invalid_analyst_report_contract" },
    });
  });

  it("rejects a report download without verified XLSX headers", async () => {
    mockFetch.mockResolvedValue(
      new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": 'attachment; filename="analyst_report.xlsx"',
          "X-LAC-Report-Schema": "analyst-report.v1",
          "X-LAC-Report-Verification": "failed",
          "X-LAC-Report-Findings": "4",
          "X-LAC-Report-Cards": "1",
        },
      })
    );

    await expect(
      new LacBridgeClient().analystReport("/safe/data.csv", "target")
    ).rejects.toMatchObject({
      status: 502,
      detail: { code: "invalid_analyst_report_contract" },
    });
  });

  it("preserves typed ingestion errors", async () => {
    mockFetch.mockResolvedValue(
      Response.json(
        {
          detail: {
            code: "csv_malformed_rows",
            message: "CSV satırları tutarsız.",
            hint: "Ayırıcıyı kontrol edin.",
            details: { row: 9 },
          },
        },
        { status: 422 }
      )
    );

    const promise = new LacBridgeClient().upload(new File(["a,b\n1"], "bad.csv"));

    await expect(promise).rejects.toMatchObject({
      status: 422,
      detail: {
        code: "csv_malformed_rows",
        message: "CSV satırları tutarsız.",
        hint: "Ayırıcıyı kontrol edin.",
        details: { row: 9 },
      },
    } satisfies Partial<LacBridgeError>);
  });

  it("rejects missing or duplicate required finding IDs", async () => {
    mockFetch.mockResolvedValue(
      Response.json({
        status: "completed",
        mode: "quick",
        file_path: "/safe/data.csv",
        profile,
        dashboard: { ...dashboard, cards: [...cards.slice(1), cards[1]] },
        interpretation: { status: "skipped" },
      })
    );

    await expect(new LacBridgeClient().quick("/safe/data.csv")).rejects.toMatchObject({
      status: 502,
      detail: { code: "invalid_dashboard_findings" },
    });
  });

  it("rejects an unsupported dashboard contract and invalid JSON", async () => {
    mockFetch.mockResolvedValueOnce(
      Response.json({
        status: "completed",
        mode: "quick",
        file_path: "/safe/data.csv",
        profile,
        dashboard: { ...dashboard, dashboard_version: 2 },
        interpretation: { status: "skipped" },
      })
    );
    await expect(new LacBridgeClient().quick("/safe/data.csv")).rejects.toMatchObject({
      detail: { code: "unsupported_dashboard_contract" },
    });

    mockFetch.mockResolvedValueOnce(new Response("not-json"));
    await expect(new LacBridgeClient().health()).rejects.toMatchObject({
      detail: { code: "invalid_json" },
    });
  });
});
