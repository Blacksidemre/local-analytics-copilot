export type BridgeFinding = {
  finding_id: string;
  kind: "metric";
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
  name: string;
  index?: number;
  rows?: number;
  columns?: number;
  header_row?: number;
  empty?: boolean;
  warnings?: string[];
};

export type BridgeErrorDetail = {
  code: string;
  message: string;
  hint: string | null;
  details: Record<string, unknown>;
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

export type ProfileResult = {
  status: "profiled";
  file_path: string;
  selected_sheet: string;
  profile: BridgeProfile;
  dashboard: BridgeDashboard;
};

export type QuickResult = {
  status: "completed";
  mode: "quick";
  file_path: string;
  profile: BridgeProfile;
  dashboard: BridgeDashboard;
  interpretation: BridgeInterpretation;
};

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
      message:
        typeof wrapped.message === "string"
          ? wrapped.message
          : `LAC Bridge HTTP ${status}`,
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

export class LacBridgeClient {
  private readonly baseUrl: string;
  private readonly token?: string;

  constructor(
    baseUrl = "http://127.0.0.1:8765",
    token?: string
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.token = token;
  }

  private headers(): Record<string, string> {
    return this.token ? { "X-LAC-Token": this.token } : {};
  }

  private async decode<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => null);
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

  private validateDashboard(dashboard: BridgeDashboard | undefined): void {
    if (!dashboard) return;
    if (
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
    const ids = dashboard.cards.map((card) => card.finding_id);
    if (ids.some((id) => !id) || new Set(ids).size !== ids.length) {
      const detail = normalizeErrorDetail(
        {
          code: "invalid_dashboard_findings",
          message: "Quick Dashboard finding kimlikleri geçersiz.",
        },
        502
      );
      throw new LacBridgeError(detail.message, 502, detail);
    }
  }

  async health(): Promise<Record<string, unknown>> {
    const response = await fetch(`${this.baseUrl}/api/v1/health`, { headers: this.headers() });
    return this.decode(response);
  }

  async upload(
    file: File,
    options: {
      sheetName?: string;
      interpret?: boolean;
      question?: string;
      signal?: AbortSignal;
    } = {}
  ): Promise<UploadResult> {
    const form = new FormData();
    form.set("file", file);
    form.set("run_profile", "true");
    form.set("interpret", String(options.interpret ?? false));
    if (options.sheetName) form.set("sheet_name", options.sheetName);
    if (options.question) form.set("question", options.question);
    const response = await fetch(`${this.baseUrl}/api/v1/datasets/upload`, {
      method: "POST",
      headers: this.headers(),
      body: form,
      signal: options.signal,
    });
    const result = await this.decode<UploadResult>(response);
    this.validateDashboard(result.dashboard);
    return result;
  }

  async profile(
    filePath: string,
    sheetName = "0",
    signal?: AbortSignal
  ): Promise<ProfileResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/datasets/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify({ file_path: filePath, sheet_name: sheetName }),
      signal,
    });
    const result = await this.decode<ProfileResult>(response);
    this.validateDashboard(result.dashboard);
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
      headers: { "Content-Type": "application/json", ...this.headers() },
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
    this.validateDashboard(result.dashboard);
    return result;
  }
}

export function dashboardCard(
  dashboard: BridgeDashboard,
  findingId: string
): BridgeFinding {
  const card = dashboard.cards.find((item) => item.finding_id === findingId);
  if (!card) {
    const detail: BridgeErrorDetail = {
      code: "dashboard_card_missing",
      message: `Quick Dashboard kartı bulunamadı: ${findingId}`,
      hint: null,
      details: { finding_id: findingId },
    };
    throw new LacBridgeError(detail.message, 502, detail);
  }
  return card;
}
