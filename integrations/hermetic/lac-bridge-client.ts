export type BridgeFinding = {
  finding_id: string;
  kind: "metric";
  label: string;
  value: number;
  unit: string;
  source: string;
};

export type BridgeProfile = {
  profile_version: number;
  rows: number;
  columns: number;
  total_missing_cells: number;
  duplicate_rows: number;
  findings: BridgeFinding[];
  ingestion: Record<string, unknown>;
};

export type UploadResult = {
  status: "uploaded" | "profiled" | "sheet_selection_required";
  file_path: string;
  manifest: Record<string, unknown>;
  selected_sheet?: string;
  sheet_options?: Array<Record<string, unknown>>;
  profile?: BridgeProfile;
  interpretation?: Record<string, unknown>;
};

export type ProfileResult = {
  status: "profiled";
  file_path: string;
  profile: BridgeProfile;
};

export type QuickResult = {
  status: "completed";
  mode: "quick";
  file_path: string;
  profile: BridgeProfile;
  interpretation: Record<string, unknown>;
};

export class LacBridgeError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: unknown
  ) {
    super(message);
  }
}

export class LacBridgeClient {
  constructor(
    private readonly baseUrl = "http://127.0.0.1:8765",
    private readonly token?: string
  ) {}

  private headers(): Record<string, string> {
    return this.token ? { "X-LAC-Token": this.token } : {};
  }

  private async decode<T>(response: Response): Promise<T> {
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload?.detail ?? payload;
      const message = detail?.message ?? detail?.code ?? `LAC Bridge HTTP ${response.status}`;
      throw new LacBridgeError(String(message), response.status, detail);
    }
    return payload as T;
  }

  async health(): Promise<Record<string, unknown>> {
    const response = await fetch(`${this.baseUrl}/api/v1/health`, { headers: this.headers() });
    return this.decode(response);
  }

  async upload(
    file: File,
    options: { sheetName?: string; interpret?: boolean; question?: string } = {}
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
    });
    return this.decode<UploadResult>(response);
  }

  async profile(filePath: string, sheetName = "0"): Promise<ProfileResult> {
    const response = await fetch(`${this.baseUrl}/api/v1/datasets/profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers() },
      body: JSON.stringify({ file_path: filePath, sheet_name: sheetName }),
    });
    return this.decode<ProfileResult>(response);
  }

  async quick(
    filePath: string,
    options: {
      sheetName?: string;
      interpret?: boolean;
      question?: string;
      language?: string;
      model?: string;
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
    });
    return this.decode<QuickResult>(response);
  }
}
