export type BridgeFinding = {
  finding_id: string;
  kind: "metric" | "statistical_metric";
  label: string;
  value: number;
  unit: string;
  source: string;
  warning?: string;
  dimension?: Record<string, string>;
};

export type BridgeProfile = {
  profile_version: number;
  rows: number;
  columns: number;
  total_cells: number;
  total_missing_cells: number;
  duplicate_rows: number;
  duplicate_rows_including_originals: number;
  duplicate_pct: number;
  quality_score_heuristic: number;
  roles: Record<string, string[]>;
  schema: Array<{
    name: string;
    dtype: string;
    role: string;
    missing: number;
    unique: number;
  }>;
  missing_count: Record<string, number>;
  missing_pct: Record<string, number>;
  constant_columns: string[];
  findings: BridgeFinding[];
  ingestion: Record<string, unknown>;
};

export type BridgeDashboard = {
  dashboard_version: 1;
  title: string;
  cards: BridgeFinding[];
  missing_by_column: Array<{
    finding_id: string;
    pct_finding_id: string;
    column: string;
    count: number;
    pct: number;
  }>;
  role_counts: Array<{ role: string; count: number }>;
  constant_columns: string[];
  ingestion: Record<string, unknown>;
  warnings: string[];
  evidence_policy: "all_numeric_cards_bound_to_finding_id";
};

export type BridgeInterpretation =
  | { status: "skipped" }
  | {
      status: "rejected";
      model: string;
      message: string;
      verification: Record<string, unknown>;
      evidence_finding_ids: string[];
      available_finding_ids: string[];
    }
  | {
      status: "unavailable";
      model?: string;
      message: string;
      reason?: string;
      available_finding_ids?: string[];
    }
  | {
      status: "completed";
      model: string;
      text: string;
      verification: Record<string, unknown>;
      evidence_finding_ids: string[];
      available_finding_ids: string[];
    };

export type BridgeSheetOption = {
  index: number;
  name: string;
  header_row: number;
  estimated_rows: number;
  estimated_columns: number;
  columns: string[];
  empty: boolean;
};

export type BridgeErrorDetail = {
  code: string;
  message: string;
  hint: string | null;
  details: Record<string, unknown>;
};

export type BridgeHealth = {
  status: "ready" | "degraded";
  bridge_api_version: number;
  data_bridge: { status: "ready"; parser: string; supported_extensions: string[] };
  ollama: {
    status: "ready" | "unavailable";
    models: string[];
    configured_model: string;
    configured_model_available: boolean;
    reason?: string;
  };
};

export type UploadResult = {
  status: "uploaded" | "profiled" | "sheet_selection_required";
  file_path: string;
  manifest: Record<string, unknown>;
  selected_sheet?: string;
  sheet_options?: BridgeSheetOption[];
  profile?: BridgeProfile;
  dashboard?: BridgeDashboard;
  interpretation?: BridgeInterpretation;
};

export type QuickResult = {
  status: "completed";
  mode: "quick";
  file_path: string;
  profile: BridgeProfile;
  dashboard: BridgeDashboard;
  interpretation: BridgeInterpretation;
};

export type AnalystTargetKind = "binary" | "continuous" | "categorical";

export type AnalystResult = {
  schema_version: "analyst.v1";
  status: "completed";
  mode: "analyst";
  file_path: string;
  selected_sheet: string;
  profile: BridgeProfile;
  target_semantics: {
    column: string;
    statistical_role: AnalystTargetKind;
    selection_source: "explicit_request";
    business_meaning_status: "unverified";
    business_meaning: null;
  };
  kpi_selection: {
    status: "requires_approved_definition";
    selected: [];
    reason: string;
  };
  analyses: Array<{
    analysis_id: string;
    target: string;
    predictor: string;
    predictor_kind: "numeric" | "categorical";
    method: string;
    effect_name: string;
    finding_ids: {
      effect: string;
      p_value: string;
      adjusted_p_value: string;
      n: string;
    };
    assumption_status: "passed" | "warning";
    warning?: string;
  }>;
  findings: BridgeFinding[];
  dashboard: {
    schema_version: 1;
    title: string;
    cards: BridgeFinding[];
    ranking_basis: "adjusted_p_value_then_finding_id";
    evidence_policy: "all_numeric_cards_bound_to_finding_id";
    warning: string;
  };
  verification: {
    status: "passed" | "failed";
    scope: string;
    errors: Array<{ code: string; message: string }>;
  };
  interpretation: BridgeInterpretation;
};

export type AnalystReportFormat = "xlsx" | "html" | "pdf";

export type AnalystReportDownload = {
  format: AnalystReportFormat;
  schemaVersion: "analyst-report.v1" | "analyst-html-report.v1" | "analyst-pdf-report.v1";
  filename: string;
  blob: Blob;
  verification: {
    status: "passed";
    findingCount: number;
    dashboardCardCount: number;
  };
};

export type AgentReportDownload = {
  format: AnalystReportFormat;
  schemaVersion: "agent-report.v1" | "agent-html-report.v1" | "agent-pdf-report.v1";
  filename: string;
  blob: Blob;
  verification: {
    status: "passed";
    findingCount: number;
    dashboardCardCount: 0;
  };
};

export type AgentToolName =
  | "profile_dataset"
  | "screen_target_associations"
  | "describe_columns"
  | "categorical_frequency"
  | "aggregate_by_segment"
  | "analyze_time_trend"
  | "screen_outliers";

export type AgentResult = {
  schema_version: "agent-api.v1";
  status: "completed" | "partial" | "planner_unavailable" | "execution_failed";
  mode: "agent";
  file_path: string;
  selected_sheet: string;
  dataset: {
    rows: number;
    columns: number;
    total_missing_cells: number;
    missing_cell_pct: number;
    exact_duplicate_copies: number;
    schema: BridgeProfile["schema"];
  };
  dashboard: BridgeDashboard;
  history?:
    | { status: "saved"; run_id: string }
    | { status: "disabled" }
    | { status: "not_saved"; reason: "run_not_verified" | "storage_error" };
  agent: {
    schema_version: "investigate-response.v1";
    status: "completed" | "partial" | "planner_unavailable" | "execution_failed";
    message?: string;
    reason?: string;
    planner?: { status: "completed"; model: string };
    plan?: {
      objective: string;
      completion_criteria: string[];
      steps: Array<{
        step_id: string;
        purpose: string;
        tool: AgentToolName;
        depends_on: string[];
      }>;
    };
    run?: {
      schema_version: "investigate-run.v1";
      status: "completed" | "stopped";
      stop_reason: string;
      completion: { required: string[]; completed: string[] };
      budget: { max_steps: number; max_failed_calls: number; failed_calls: number };
      events: Array<{
        step_id: string;
        tool: AgentToolName;
        status: "completed" | "failed";
        verification?: { status: "passed" | "failed"; errors: unknown[] };
        error?: { code: string; type?: string };
      }>;
      evidence: BridgeFinding[];
      verification: { status: "passed" | "failed"; scope: string; errors: unknown[] };
    };
    synthesis?:
      | {
          status: "completed";
          model: string;
          document: {
            schema_version: "investigate-synthesis.v1";
            summary: Array<{ text: string; finding_ids: string[] }>;
            limitations: string[];
            recommended_next_step: string | null;
          };
          verification: { status: "passed"; cited_finding_ids: string[]; errors: [] };
        }
      | { status: "blocked" | "unavailable" | "rejected"; message: string; document?: never };
  };
};

export type AnalysisHistoryRunSummary = {
  run_id: string;
  dataset_id: string;
  dataset_ref: string;
  source_name: string;
  sheet_name: string;
  mode: "agent";
  question: string;
  run_status: string;
  verifier_status: "passed";
  finding_count: number;
  tools: AgentToolName[];
  created_at: string;
};

export type AnalysisHistoryRun = AnalysisHistoryRunSummary & {
  findings: Array<{
    finding_id: string;
    kind?: string;
    label?: string;
    value: number;
    unit?: string;
    source: string;
    dimension?: Record<string, string>;
    warning?: string;
  }>;
};

export type AnalysisHistoryList = {
  schema_version: "analysis-history-list.v1";
  runs: AnalysisHistoryRunSummary[];
};

export type AnalysisHistoryComparisonStatus =
  "changed" | "unchanged" | "added" | "removed" | "incompatible";

export type AnalysisHistoryComparison = {
  schema_version: "analysis-history-comparison.v1";
  status: "completed";
  baseline: AnalysisHistoryRunSummary;
  current: AnalysisHistoryRunSummary;
  dataset_relation: "same_dataset_version" | "same_source_new_version" | "different_sources";
  period_semantics: "not_inferred";
  summary: Record<AnalysisHistoryComparisonStatus | "total", number>;
  changes: Array<{
    finding_id: string;
    status: AnalysisHistoryComparisonStatus;
    label: string;
    baseline_value: number | null;
    current_value: number | null;
    absolute_delta: number | null;
    relative_change_pct: number | null;
    unit: string | null;
    source: string | null;
    dimension: Record<string, string> | null;
    incompatible_fields?: string[];
  }>;
  manifest_sha256: string;
  verification: {
    status: "passed";
    scope: "archived_verified_finding_manifests";
    evidence_only: true;
    errors: [];
  };
};

type AnalystReportOptions = {
  sheetName?: string;
  targetKind?: AnalystTargetKind;
  predictorColumns?: string[];
  interpret?: boolean;
  question?: string;
  language?: string;
  model?: string;
  outputName?: string;
  signal?: AbortSignal;
};

type AgentReportOptions = {
  outputName?: string;
  signal?: AbortSignal;
};

const ANALYST_REPORT_FORMATS = {
  xlsx: {
    path: "/api/v1/analysis/analyst/report",
    extension: ".xlsx",
    mediaType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    schemaVersion: "analyst-report.v1",
  },
  html: {
    path: "/api/v1/analysis/analyst/report/html",
    extension: ".html",
    mediaType: "text/html",
    schemaVersion: "analyst-html-report.v1",
  },
  pdf: {
    path: "/api/v1/analysis/analyst/report/pdf",
    extension: ".pdf",
    mediaType: "application/pdf",
    schemaVersion: "analyst-pdf-report.v1",
  },
} as const;

const AGENT_REPORT_FORMATS = {
  xlsx: {
    extension: ".xlsx",
    mediaType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    schemaVersion: "agent-report.v1",
  },
  html: {
    extension: ".html",
    mediaType: "text/html",
    schemaVersion: "agent-html-report.v1",
  },
  pdf: {
    extension: ".pdf",
    mediaType: "application/pdf",
    schemaVersion: "agent-pdf-report.v1",
  },
} as const;

const REQUIRED_CARD_IDS = [
  "profile.shape.rows",
  "profile.shape.columns",
  "profile.quality.missing_cells",
  "profile.quality.exact_duplicate_copies",
  "profile.quality.score_heuristic",
] as const;

export class LacBridgeError extends Error {
  public readonly status: number;
  public readonly detail: BridgeErrorDetail;

  constructor(message: string, status: number, detail: BridgeErrorDetail) {
    super(message);
    this.name = "LacBridgeError";
    this.status = status;
    this.detail = detail;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeErrorDetail(payload: unknown, status: number): BridgeErrorDetail {
  const wrapped = isRecord(payload) && "detail" in payload ? payload.detail : payload;
  if (isRecord(wrapped)) {
    return {
      code: typeof wrapped.code === "string" ? wrapped.code : `http_${status}`,
      message: typeof wrapped.message === "string" ? wrapped.message : `LAC Bridge HTTP ${status}`,
      hint: typeof wrapped.hint === "string" ? wrapped.hint : null,
      details: isRecord(wrapped.details) ? wrapped.details : {},
    };
  }
  return {
    code: `http_${status}`,
    message: typeof wrapped === "string" ? wrapped : `LAC Bridge HTTP ${status}`,
    hint: null,
    details: {},
  };
}

function validateDashboard(dashboard: BridgeDashboard | undefined): asserts dashboard {
  if (
    !dashboard ||
    dashboard.dashboard_version !== 1 ||
    dashboard.evidence_policy !== "all_numeric_cards_bound_to_finding_id"
  ) {
    const detail = normalizeErrorDetail(
      {
        code: "unsupported_dashboard_contract",
        message: "Desteklenmeyen Quick Dashboard sözleşmesi.",
      },
      502
    );
    throw new LacBridgeError(detail.message, 502, detail);
  }
  const ids = new Set(dashboard.cards.map((card) => card.finding_id));
  const missing = REQUIRED_CARD_IDS.filter((id) => !ids.has(id));
  if (missing.length > 0 || ids.size !== dashboard.cards.length) {
    const detail: BridgeErrorDetail = {
      code: "invalid_dashboard_findings",
      message: "Quick Dashboard finding kimlikleri geçersiz.",
      hint: null,
      details: { missing_finding_ids: missing },
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
}

function validateAnalystResult(result: AnalystResult | undefined): asserts result {
  const interpretation = result?.interpretation as unknown;
  const interpretationStatus = isRecord(interpretation) ? interpretation.status : undefined;
  const validInterpretation =
    isRecord(interpretation) &&
    ((interpretationStatus === "skipped" && Object.keys(interpretation).length === 1) ||
      (interpretationStatus === "unavailable" && typeof interpretation.message === "string") ||
      (interpretationStatus === "rejected" &&
        typeof interpretation.message === "string" &&
        !("text" in interpretation)) ||
      (interpretationStatus === "completed" &&
        typeof interpretation.text === "string" &&
        isRecord(interpretation.verification) &&
        interpretation.verification.status === "passed"));
  if (
    !result ||
    result.schema_version !== "analyst.v1" ||
    result.mode !== "analyst" ||
    result.verification?.status !== "passed" ||
    result.dashboard?.schema_version !== 1 ||
    result.dashboard?.evidence_policy !== "all_numeric_cards_bound_to_finding_id" ||
    !Array.isArray(result.findings) ||
    !Array.isArray(result.analyses) ||
    !Array.isArray(result.dashboard?.cards) ||
    !validInterpretation
  ) {
    const detail: BridgeErrorDetail = {
      code: "unsupported_analyst_contract",
      message: "Desteklenmeyen veya doğrulanmamış Analyst sözleşmesi.",
      hint: null,
      details: {},
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
  const findingIndex = new Map(result.findings.map((finding) => [finding.finding_id, finding]));
  if (findingIndex.size !== result.findings.length) {
    const detail: BridgeErrorDetail = {
      code: "invalid_analyst_findings",
      message: "Analyst finding kimlikleri benzersiz değil.",
      hint: null,
      details: {},
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
  const unboundCards = result.dashboard.cards.filter((card) => {
    const finding = findingIndex.get(card.finding_id);
    return !finding || finding.value !== card.value || finding.source !== card.source;
  });
  const unknownReferences = result.analyses.flatMap((analysis) =>
    Object.values(analysis.finding_ids).filter((findingId) => !findingIndex.has(findingId))
  );
  const invalidSemantics =
    result.target_semantics?.selection_source !== "explicit_request" ||
    result.target_semantics?.business_meaning_status !== "unverified" ||
    result.kpi_selection?.status !== "requires_approved_definition" ||
    result.kpi_selection?.selected?.length !== 0;
  if (unboundCards.length > 0 || unknownReferences.length > 0 || invalidSemantics) {
    const detail: BridgeErrorDetail = {
      code: "invalid_analyst_evidence",
      message: "Analyst sonucu kanıt veya semantik doğrulamasını geçmedi.",
      hint: null,
      details: {
        unbound_card_ids: unboundCards.map((card) => card.finding_id),
        unknown_finding_ids: unknownReferences,
        invalid_semantics: invalidSemantics,
      },
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
}

const AGENT_TOOLS = new Set<AgentToolName>([
  "profile_dataset",
  "screen_target_associations",
  "describe_columns",
  "categorical_frequency",
  "aggregate_by_segment",
  "analyze_time_trend",
  "screen_outliers",
]);

const HISTORY_RUN_ID = /^[0-9a-f]{32}$/;
const HISTORY_DATASET_ID = /^[0-9a-f]{64}$/;
const HISTORY_MANIFEST_ID = /^[0-9a-f]{64}$/;
const HISTORY_CHANGE_STATUSES = new Set<AnalysisHistoryComparisonStatus>([
  "changed",
  "unchanged",
  "added",
  "removed",
  "incompatible",
]);

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validateHistorySummary(value: unknown): asserts value is AnalysisHistoryRunSummary {
  if (
    !isRecord(value) ||
    typeof value.run_id !== "string" ||
    !HISTORY_RUN_ID.test(value.run_id) ||
    typeof value.dataset_id !== "string" ||
    !HISTORY_DATASET_ID.test(value.dataset_id) ||
    typeof value.dataset_ref !== "string" ||
    typeof value.source_name !== "string" ||
    typeof value.sheet_name !== "string" ||
    value.mode !== "agent" ||
    typeof value.question !== "string" ||
    typeof value.run_status !== "string" ||
    value.verifier_status !== "passed" ||
    !Number.isSafeInteger(value.finding_count) ||
    (value.finding_count as number) < 1 ||
    (value.finding_count as number) > 48 ||
    !Array.isArray(value.tools) ||
    value.tools.length > 6 ||
    !value.tools.every((tool) => AGENT_TOOLS.has(tool as AgentToolName)) ||
    typeof value.created_at !== "string"
  ) {
    throw invalidHistoryContract("Geçmiş analiz özeti doğrulama sözleşmesini geçmedi.");
  }
}

function validateHistoryFinding(value: unknown): boolean {
  if (
    !isRecord(value) ||
    typeof value.finding_id !== "string" ||
    !value.finding_id ||
    typeof value.source !== "string" ||
    !value.source ||
    !isFiniteNumber(value.value)
  ) {
    return false;
  }
  const dimension = value.dimension;
  return (
    dimension === undefined ||
    (isRecord(dimension) &&
      Object.entries(dimension).every(([key, item]) => key.length > 0 && typeof item === "string"))
  );
}

function invalidHistoryContract(message: string): LacBridgeError {
  const detail: BridgeErrorDetail = {
    code: "invalid_analysis_history_contract",
    message,
    hint: "Geçmiş kayıtlarını yenileyin; doğrulanmamış içerik gösterilmedi.",
    details: {},
  };
  return new LacBridgeError(detail.message, 502, detail);
}

function validateHistoryList(value: unknown): asserts value is AnalysisHistoryList {
  if (
    !isRecord(value) ||
    value.schema_version !== "analysis-history-list.v1" ||
    !Array.isArray(value.runs) ||
    value.runs.length > 100
  ) {
    throw invalidHistoryContract("Geçmiş analiz listesi geçersiz.");
  }
  value.runs.forEach(validateHistorySummary);
}

function validateHistoryRun(value: unknown): asserts value is AnalysisHistoryRun {
  validateHistorySummary(value);
  const findings = (value as unknown as { findings?: unknown }).findings;
  if (
    !Array.isArray(findings) ||
    findings.length !== value.finding_count ||
    !findings.every(validateHistoryFinding) ||
    new Set(findings.map((finding) => (finding as { finding_id: string }).finding_id)).size !==
      findings.length
  ) {
    throw invalidHistoryContract("Geçmiş finding manifesti geçersiz.");
  }
}

function validateHistoryComparison(value: unknown): asserts value is AnalysisHistoryComparison {
  if (
    !isRecord(value) ||
    value.schema_version !== "analysis-history-comparison.v1" ||
    value.status !== "completed" ||
    !new Set(["same_dataset_version", "same_source_new_version", "different_sources"]).has(
      value.dataset_relation as string
    ) ||
    value.period_semantics !== "not_inferred" ||
    typeof value.manifest_sha256 !== "string" ||
    !HISTORY_MANIFEST_ID.test(value.manifest_sha256) ||
    !isRecord(value.summary) ||
    !Array.isArray(value.changes) ||
    value.changes.length > 96 ||
    !isRecord(value.verification) ||
    value.verification.status !== "passed" ||
    value.verification.scope !== "archived_verified_finding_manifests" ||
    value.verification.evidence_only !== true ||
    !Array.isArray(value.verification.errors) ||
    value.verification.errors.length !== 0
  ) {
    throw invalidHistoryContract("Geçmiş analiz karşılaştırması doğrulanamadı.");
  }
  validateHistorySummary(value.baseline);
  validateHistorySummary(value.current);
  const statuses = ["changed", "unchanged", "added", "removed", "incompatible"] as const;
  const summary = value.summary as Record<string, unknown>;
  if (
    !Number.isSafeInteger(summary.total) ||
    summary.total !== value.changes.length ||
    !statuses.every((status) => Number.isSafeInteger(summary[status])) ||
    statuses.reduce((total, status) => total + Number(summary[status]), 0) !== value.changes.length
  ) {
    throw invalidHistoryContract("Geçmiş karşılaştırma özeti geçersiz.");
  }
  const findingIds = new Set<string>();
  for (const item of value.changes) {
    if (
      !isRecord(item) ||
      typeof item.finding_id !== "string" ||
      !item.finding_id ||
      findingIds.has(item.finding_id) ||
      !HISTORY_CHANGE_STATUSES.has(item.status as AnalysisHistoryComparisonStatus) ||
      typeof item.label !== "string" ||
      ![
        item.baseline_value,
        item.current_value,
        item.absolute_delta,
        item.relative_change_pct,
      ].every((number) => number === null || isFiniteNumber(number)) ||
      !(item.unit === null || typeof item.unit === "string") ||
      !(item.source === null || typeof item.source === "string") ||
      !(item.dimension === null || isRecord(item.dimension))
    ) {
      throw invalidHistoryContract("Geçmiş karşılaştırma değişiklik kaydı geçersiz.");
    }
    findingIds.add(item.finding_id);
  }
}

function validateAgentResult(result: AgentResult | undefined): asserts result {
  validateDashboard(result?.dashboard);
  const agent = result?.agent;
  const validStatus = new Set(["completed", "partial", "planner_unavailable", "execution_failed"]);
  if (
    !result ||
    result.schema_version !== "agent-api.v1" ||
    result.mode !== "agent" ||
    !validStatus.has(result.status) ||
    !agent ||
    agent.schema_version !== "investigate-response.v1" ||
    agent.status !== result.status
  ) {
    const detail: BridgeErrorDetail = {
      code: "unsupported_agent_contract",
      message: "Desteklenmeyen Agent yanıt sözleşmesi.",
      hint: null,
      details: {},
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
  const history = result.history;
  if (
    history &&
    !(
      history.status === "disabled" ||
      (history.status === "saved" && /^[0-9a-f]{32}$/.test(history.run_id)) ||
      (history.status === "not_saved" &&
        new Set(["run_not_verified", "storage_error"]).has(history.reason))
    )
  ) {
    const detail: BridgeErrorDetail = {
      code: "invalid_agent_history",
      message: "Agent geçmiş kaydı sözleşmesi geçersiz.",
      hint: null,
      details: {},
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
  if (agent.status === "planner_unavailable" || agent.status === "execution_failed") {
    if (typeof agent.message === "string" && !agent.synthesis?.document) return;
  } else if (
    agent.plan &&
    agent.run &&
    agent.run.verification?.status === "passed" &&
    Array.isArray(agent.run.events) &&
    Array.isArray(agent.run.evidence) &&
    agent.plan.steps.length <= 6 &&
    agent.plan.steps.every((step) => AGENT_TOOLS.has(step.tool)) &&
    agent.run.events.every(
      (event) => event.status !== "completed" || event.verification?.status === "passed"
    )
  ) {
    const ids = new Set(agent.run.evidence.map((finding) => finding.finding_id));
    const synthesis = agent.synthesis;
    const safeSynthesis =
      synthesis?.status === "completed"
        ? synthesis.verification?.status === "passed" &&
          synthesis.document?.schema_version === "investigate-synthesis.v1" &&
          synthesis.document.summary.every((statement) =>
            statement.finding_ids.every((findingId) => ids.has(findingId))
          )
        : Boolean(synthesis?.message) && !("document" in (synthesis ?? {}));
    if (ids.size === agent.run.evidence.length && safeSynthesis) return;
  }
  const detail: BridgeErrorDetail = {
    code: "invalid_agent_evidence",
    message: "Agent sonucu kanıt veya verifier kontrolünü geçmedi.",
    hint: "Deterministik Quick Dashboard kullanılabilir; Agent sonucunu yeniden çalıştırın.",
    details: {},
  };
  throw new LacBridgeError(detail.message, 502, detail);
}

function reportFilename(response: Response, extension: string): string | null {
  const disposition = response.headers.get("content-disposition") ?? "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  let candidate = plain;
  if (encoded) {
    try {
      candidate = decodeURIComponent(encoded);
    } catch {
      return null;
    }
  }
  if (!candidate || candidate.includes("/") || candidate.includes("\\")) return null;
  return candidate.toLowerCase().endsWith(extension) ? candidate : null;
}

async function hasReportMagic(blob: Blob, format: AnalystReportFormat): Promise<boolean> {
  const prefix = new Uint8Array(await blob.slice(0, 32).arrayBuffer());
  if (format === "xlsx") {
    return (
      prefix.length >= 4 &&
      prefix[0] === 0x50 &&
      prefix[1] === 0x4b &&
      prefix[2] === 0x03 &&
      prefix[3] === 0x04
    );
  }
  const text = new TextDecoder("utf-8", { fatal: false }).decode(prefix);
  if (format === "pdf") return text.startsWith("%PDF-");
  return text.trimStart().toLowerCase().startsWith("<!doctype html>");
}

export class LacBridgeClient {
  private readonly baseUrl: string;

  constructor(baseUrl = "/api/lac") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private async decode<T>(response: Response): Promise<T> {
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = normalizeErrorDetail(payload, response.status);
      throw new LacBridgeError(detail.message, response.status, detail);
    }
    if (payload === null) {
      const detail = normalizeErrorDetail(
        { code: "invalid_json", message: "LAC Bridge boş veya geçersiz JSON döndürdü." },
        502
      );
      throw new LacBridgeError(detail.message, 502, detail);
    }
    return payload as T;
  }

  async health(signal?: AbortSignal): Promise<BridgeHealth> {
    const response = await fetch(`${this.baseUrl}/api/v1/health`, { signal });
    return this.decode<BridgeHealth>(response);
  }

  async upload(
    file: File,
    options: {
      interpret?: boolean;
      question?: string;
      language?: string;
      model?: string;
      signal?: AbortSignal;
    } = {}
  ): Promise<UploadResult> {
    const form = new FormData();
    form.set("file", file);
    form.set("run_profile", "true");
    form.set("interpret", String(options.interpret ?? true));
    if (options.question) form.set("question", options.question);
    form.set("language", options.language ?? "tr");
    if (options.model) form.set("model", options.model);
    const response = await fetch(`${this.baseUrl}/api/v1/datasets/upload`, {
      method: "POST",
      body: form,
      signal: options.signal,
    });
    const result = await this.decode<UploadResult>(response);
    if (result.status === "profiled") validateDashboard(result.dashboard);
    return result;
  }

  async quick(
    filePath: string,
    options: {
      sheetName?: string;
      interpret?: boolean;
      question?: string;
      language?: string;
      model?: string;
      signal?: AbortSignal;
    } = {}
  ): Promise<QuickResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/quick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: filePath,
        sheet_name: options.sheetName ?? "0",
        interpret: options.interpret ?? true,
        question: options.question ?? "",
        language: options.language ?? "tr",
        model: options.model,
      }),
      signal: options.signal,
    });
    const result = await this.decode<QuickResult>(response);
    validateDashboard(result.dashboard);
    return result;
  }

  async analyst(
    filePath: string,
    targetColumn: string,
    options: {
      sheetName?: string;
      targetKind?: AnalystTargetKind;
      predictorColumns?: string[];
      interpret?: boolean;
      question?: string;
      language?: string;
      model?: string;
      signal?: AbortSignal;
    } = {}
  ): Promise<AnalystResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/analyst`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: filePath,
        sheet_name: options.sheetName ?? "0",
        target_column: targetColumn,
        target_kind: options.targetKind,
        predictor_columns: options.predictorColumns,
        interpret: options.interpret ?? true,
        question: options.question ?? "",
        language: options.language ?? "tr",
        model: options.model,
      }),
      signal: options.signal,
    });
    const result = await this.decode<AnalystResult>(response);
    validateAnalystResult(result);
    return result;
  }

  async agent(
    filePath: string,
    question: string,
    options: {
      sheetName?: string;
      targetColumn?: string;
      targetKind?: AnalystTargetKind;
      predictorColumns?: string[];
      language?: "tr" | "en";
      model?: string;
      signal?: AbortSignal;
    } = {}
  ): Promise<AgentResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        file_path: filePath,
        sheet_name: options.sheetName ?? "0",
        question,
        target_column: options.targetColumn,
        target_kind: options.targetKind,
        predictor_columns: options.predictorColumns,
        language: options.language ?? "tr",
        model: options.model,
      }),
      signal: options.signal,
    });
    const result = await this.decode<AgentResult>(response);
    validateAgentResult(result);
    return result;
  }

  async analysisHistory(
    options: { limit?: number; datasetId?: string; signal?: AbortSignal } = {}
  ): Promise<AnalysisHistoryList> {
    const limit = options.limit ?? 50;
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) {
      throw invalidHistoryContract("Geçmiş analiz limiti 1-100 olmalıdır.");
    }
    const parameters = new URLSearchParams({ limit: String(limit) });
    if (options.datasetId) parameters.set("dataset_id", options.datasetId);
    const response = await fetch(
      `${this.baseUrl}/api/v1/analysis/history?${parameters.toString()}`,
      { signal: options.signal }
    );
    const result = await this.decode<unknown>(response);
    validateHistoryList(result);
    return result;
  }

  async analysisHistoryRun(runId: string, signal?: AbortSignal): Promise<AnalysisHistoryRun> {
    if (!HISTORY_RUN_ID.test(runId)) {
      throw invalidHistoryContract("Geçmiş analiz kimliği geçersiz.");
    }
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/history/${runId}`, { signal });
    const envelope = await this.decode<unknown>(response);
    if (!isRecord(envelope) || envelope.schema_version !== "analysis-history.v1") {
      throw invalidHistoryContract("Geçmiş analiz kaydı sözleşmesi geçersiz.");
    }
    const run = envelope.run;
    validateHistoryRun(run);
    return run;
  }

  async deleteAnalysisHistoryRun(runId: string, signal?: AbortSignal): Promise<void> {
    if (!HISTORY_RUN_ID.test(runId)) {
      throw invalidHistoryContract("Silinecek geçmiş analiz kimliği geçersiz.");
    }
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/history/${runId}`, {
      method: "DELETE",
      signal,
    });
    const result = await this.decode<unknown>(response);
    if (
      !isRecord(result) ||
      result.status !== "deleted" ||
      result.run_id !== runId ||
      Object.keys(result).some((key) => !["status", "run_id"].includes(key))
    ) {
      throw invalidHistoryContract("Geçmiş analiz silme yanıtı geçersiz.");
    }
  }

  async compareAnalysisHistory(
    baselineRunId: string,
    currentRunId: string,
    signal?: AbortSignal
  ): Promise<AnalysisHistoryComparison> {
    if (
      !HISTORY_RUN_ID.test(baselineRunId) ||
      !HISTORY_RUN_ID.test(currentRunId) ||
      baselineRunId === currentRunId
    ) {
      throw invalidHistoryContract("Karşılaştırma için iki farklı geçerli analiz seçilmelidir.");
    }
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/history/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        baseline_run_id: baselineRunId,
        current_run_id: currentRunId,
      }),
      signal,
    });
    const result = await this.decode<unknown>(response);
    validateHistoryComparison(result);
    return result;
  }

  async agentReport(
    runId: string,
    format: AnalystReportFormat,
    options: AgentReportOptions = {}
  ): Promise<AgentReportDownload> {
    if (!/^[0-9a-f]{32}$/.test(runId)) {
      const detail: BridgeErrorDetail = {
        code: "invalid_agent_report_run_id",
        message: "Agent raporu için geçerli bir yerel analiz kaydı gerekli.",
        hint: "Agent analizini yeniden çalıştırıp doğrulanmış kaydı kullanın.",
        details: {},
      };
      throw new LacBridgeError(detail.message, 400, detail);
    }
    const contract = AGENT_REPORT_FORMATS[format];
    const response = await fetch(`${this.baseUrl}/api/v1/analysis/agent/report`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: contract.mediaType,
      },
      body: JSON.stringify({
        run_id: runId,
        format,
        output_name: options.outputName ?? `agent_report${contract.extension}`,
      }),
      signal: options.signal,
    });
    if (!response.ok) await this.decode<never>(response);
    const contentType = response.headers.get("content-type") ?? "";
    const schemaVersion = response.headers.get("x-lac-report-schema");
    const verificationStatus = response.headers.get("x-lac-report-verification");
    const filename = reportFilename(response, contract.extension);
    const findingCount = Number(response.headers.get("x-lac-report-findings"));
    const dashboardCardCount = Number(response.headers.get("x-lac-report-cards"));
    const blob = await response.blob();
    const validMagic = await hasReportMagic(blob, format);
    if (
      !contentType.startsWith(contract.mediaType) ||
      schemaVersion !== contract.schemaVersion ||
      verificationStatus !== "passed" ||
      !filename ||
      !Number.isSafeInteger(findingCount) ||
      findingCount < 1 ||
      dashboardCardCount !== 0 ||
      !validMagic
    ) {
      const detail: BridgeErrorDetail = {
        code: "invalid_agent_report_contract",
        message: `Agent ${format.toUpperCase()} raporu doğrulanmış indirme sözleşmesini geçmedi.`,
        hint: null,
        details: {},
      };
      throw new LacBridgeError(detail.message, 502, detail);
    }
    return {
      format,
      schemaVersion: contract.schemaVersion,
      filename,
      blob,
      verification: {
        status: "passed",
        findingCount,
        dashboardCardCount: 0,
      },
    };
  }

  async analystReport(
    filePath: string,
    targetColumn: string,
    options: AnalystReportOptions = {}
  ): Promise<AnalystReportDownload> {
    return this.downloadAnalystReport("xlsx", filePath, targetColumn, options);
  }

  async analystHtmlReport(
    filePath: string,
    targetColumn: string,
    options: AnalystReportOptions = {}
  ): Promise<AnalystReportDownload> {
    return this.downloadAnalystReport("html", filePath, targetColumn, options);
  }

  async analystPdfReport(
    filePath: string,
    targetColumn: string,
    options: AnalystReportOptions = {}
  ): Promise<AnalystReportDownload> {
    return this.downloadAnalystReport("pdf", filePath, targetColumn, options);
  }

  private async downloadAnalystReport(
    format: AnalystReportFormat,
    filePath: string,
    targetColumn: string,
    options: AnalystReportOptions
  ): Promise<AnalystReportDownload> {
    const contract = ANALYST_REPORT_FORMATS[format];
    const response = await fetch(`${this.baseUrl}${contract.path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: contract.mediaType,
      },
      body: JSON.stringify({
        file_path: filePath,
        sheet_name: options.sheetName ?? "0",
        target_column: targetColumn,
        target_kind: options.targetKind,
        predictor_columns: options.predictorColumns,
        interpret: options.interpret ?? true,
        question: options.question ?? "",
        language: options.language ?? "tr",
        model: options.model,
        output_name: options.outputName ?? `analyst_report${contract.extension}`,
      }),
      signal: options.signal,
    });
    if (!response.ok) await this.decode<never>(response);
    const contentType = response.headers.get("content-type") ?? "";
    const schemaVersion = response.headers.get("x-lac-report-schema");
    const verificationStatus = response.headers.get("x-lac-report-verification");
    const filename = reportFilename(response, contract.extension);
    const findingCount = Number(response.headers.get("x-lac-report-findings"));
    const dashboardCardCount = Number(response.headers.get("x-lac-report-cards"));
    const blob = await response.blob();
    const validMagic = await hasReportMagic(blob, format);
    if (
      !contentType.startsWith(contract.mediaType) ||
      schemaVersion !== contract.schemaVersion ||
      verificationStatus !== "passed" ||
      !filename ||
      !Number.isSafeInteger(findingCount) ||
      findingCount < 1 ||
      !Number.isSafeInteger(dashboardCardCount) ||
      dashboardCardCount < 1 ||
      !validMagic
    ) {
      const detail: BridgeErrorDetail = {
        code: "invalid_analyst_report_contract",
        message: `Analyst ${format.toUpperCase()} raporu doğrulanmış indirme sözleşmesini geçmedi.`,
        hint: null,
        details: {},
      };
      throw new LacBridgeError(detail.message, 502, detail);
    }
    return {
      format,
      schemaVersion: contract.schemaVersion,
      filename,
      blob,
      verification: {
        status: "passed",
        findingCount,
        dashboardCardCount,
      },
    };
  }
}
