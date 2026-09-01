#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { basename } from "node:path";

const [rawBaseUrl, csvPath, xlsxPath] = process.argv.slice(2);

if (!rawBaseUrl || !csvPath || !xlsxPath) {
  console.error("Usage: node scripts/lac-hybrid-smoke.mjs <base-url> <fixture.csv> <fixture.xlsx>");
  process.exit(2);
}

const baseUrl = rawBaseUrl.replace(/\/+$/, "");
const expectedProfile = {
  rows: 1508,
  columns: 22,
  total_missing_cells: 52,
  duplicate_rows: 8,
  duplicate_rows_including_originals: 16,
};
const expectedMissing = {
  monthly_income_try: 24,
  employment_years: 16,
  payment_ratio_3m: 12,
};
const requiredCardIds = new Set([
  "profile.shape.rows",
  "profile.shape.columns",
  "profile.quality.missing_cells",
  "profile.quality.exact_duplicate_copies",
  "profile.quality.score_heuristic",
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function responseJson(response, operation) {
  const payload = await response.json().catch(() => null);
  assert(response.ok, `${operation} failed (${response.status}): ${JSON.stringify(payload)}`);
  assert(payload && typeof payload === "object", `${operation} returned invalid JSON`);
  return payload;
}

function verifyDashboard(dashboard, operation) {
  assert(dashboard?.dashboard_version === 1, `${operation}: wrong dashboard version`);
  assert(
    dashboard?.evidence_policy === "all_numeric_cards_bound_to_finding_id",
    `${operation}: wrong evidence policy`
  );
  const ids = new Set(dashboard.cards?.map((card) => card.finding_id));
  for (const requiredId of requiredCardIds) {
    assert(ids.has(requiredId), `${operation}: missing dashboard card ${requiredId}`);
  }
  assert(ids.size === dashboard.cards.length, `${operation}: duplicate dashboard finding_id`);
  for (const card of dashboard.cards) {
    assert(typeof card.value === "number", `${operation}: non-numeric dashboard card`);
    assert(typeof card.source === "string" && card.source, `${operation}: unbound card source`);
  }
}

function verifyProfile(profile, dashboard, operation) {
  for (const [field, expected] of Object.entries(expectedProfile)) {
    assert(profile?.[field] === expected, `${operation}: ${field} != ${expected}`);
  }
  for (const [column, expected] of Object.entries(expectedMissing)) {
    assert(profile.missing_count?.[column] === expected, `${operation}: ${column} != ${expected}`);
  }
  verifyDashboard(dashboard, operation);
}

async function waitForBridge() {
  let lastError;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/api/v1/health`);
      const payload = await responseJson(response, "health");
      assert(payload.bridge_api_version === 1, "health: wrong bridge API version");
      assert(payload.data_bridge?.status === "ready", "health: Data Bridge is not ready");
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }
  throw new Error(`Data Bridge did not become ready: ${lastError}`);
}

async function uploadAndQuick(filePath, mediaType) {
  const bytes = await readFile(filePath);
  const form = new FormData();
  form.set("file", new File([bytes], basename(filePath), { type: mediaType }));
  form.set("run_profile", "true");
  form.set("interpret", "false");

  const uploadResponse = await fetch(`${baseUrl}/api/v1/datasets/upload`, {
    method: "POST",
    body: form,
  });
  const upload = await responseJson(uploadResponse, `upload ${basename(filePath)}`);
  assert(upload.status === "profiled", `upload ${basename(filePath)} was not profiled`);
  assert(typeof upload.file_path === "string" && upload.file_path, "upload: missing file_path");
  assert(
    typeof upload.selected_sheet === "string" && upload.selected_sheet,
    "upload: missing selected_sheet"
  );
  verifyProfile(upload.profile, upload.dashboard, `upload ${basename(filePath)}`);

  const quickResponse = await fetch(`${baseUrl}/api/v1/analysis/quick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_path: upload.file_path,
      sheet_name: upload.selected_sheet,
      interpret: false,
    }),
  });
  const quick = await responseJson(quickResponse, `quick ${basename(filePath)}`);
  assert(quick.status === "completed" && quick.mode === "quick", "quick: wrong status");
  assert(quick.interpretation?.status === "skipped", "quick: unexpected LLM call");
  verifyProfile(quick.profile, quick.dashboard, `quick ${basename(filePath)}`);
  return upload;
}

function analystRequest(filePath, selectedSheet) {
  return {
    file_path: filePath,
    sheet_name: selectedSheet,
    target_column: "default_next_30d",
    target_kind: "binary",
    predictor_columns: ["utilization_rate", "dpd", "bureau_score"],
    interpret: false,
  };
}

async function verifyAnalystAndReport(upload) {
  const request = analystRequest(upload.file_path, upload.selected_sheet);
  const analystResponse = await fetch(`${baseUrl}/api/v1/analysis/analyst`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  const analyst = await responseJson(analystResponse, "analyst");
  assert(analyst.schema_version === "analyst.v1", "analyst: wrong schema version");
  assert(analyst.verification?.status === "passed", "analyst: verification did not pass");
  assert(analyst.analyses?.length === 3, "analyst: expected three deterministic analyses");
  assert(
    analyst.target_semantics?.business_meaning_status === "unverified",
    "analyst: target business meaning was invented"
  );
  assert(
    analyst.kpi_selection?.status === "requires_approved_definition",
    "analyst: KPI gate was bypassed"
  );
  const findingIds = new Set(analyst.findings.map((finding) => finding.finding_id));
  assert(findingIds.size === analyst.findings.length, "analyst: duplicate finding_id");
  for (const card of analyst.dashboard.cards) {
    assert(findingIds.has(card.finding_id), `analyst: unbound card ${card.finding_id}`);
  }

  const reportContracts = [
    {
      format: "XLSX",
      path: "/api/v1/analysis/analyst/report",
      mediaType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      schema: "analyst-report.v1",
      filename: "ci_analyst_report.xlsx",
      validMagic: (bytes) =>
        bytes.length > 4 &&
        bytes[0] === 0x50 &&
        bytes[1] === 0x4b &&
        bytes[2] === 0x03 &&
        bytes[3] === 0x04,
    },
    {
      format: "HTML",
      path: "/api/v1/analysis/analyst/report/html",
      mediaType: "text/html",
      schema: "analyst-html-report.v1",
      filename: "ci_analyst_report.html",
      validMagic: (bytes) =>
        new TextDecoder().decode(bytes.slice(0, 32)).toLowerCase().startsWith("<!doctype html>"),
    },
    {
      format: "PDF",
      path: "/api/v1/analysis/analyst/report/pdf",
      mediaType: "application/pdf",
      schema: "analyst-pdf-report.v1",
      filename: "ci_analyst_report.pdf",
      validMagic: (bytes) => new TextDecoder().decode(bytes.slice(0, 5)) === "%PDF-",
    },
  ];
  for (const contract of reportContracts) {
    const reportResponse = await fetch(`${baseUrl}${contract.path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: contract.mediaType },
      body: JSON.stringify({ ...request, output_name: contract.filename }),
    });
    assert(
      reportResponse.ok,
      `analyst ${contract.format} report failed (${reportResponse.status})`
    );
    assert(
      reportResponse.headers.get("x-lac-report-schema") === contract.schema,
      `analyst ${contract.format} report: wrong schema`
    );
    assert(
      reportResponse.headers.get("x-lac-report-verification") === "passed",
      `analyst ${contract.format} report: verification did not pass`
    );
    assert(
      Number(reportResponse.headers.get("x-lac-report-findings")) > 0,
      `analyst ${contract.format} report: no findings`
    );
    assert(
      Number(reportResponse.headers.get("x-lac-report-cards")) > 0,
      `analyst ${contract.format} report: no dashboard cards`
    );
    const bytes = new Uint8Array(await reportResponse.arrayBuffer());
    assert(contract.validMagic(bytes), `analyst ${contract.format} report: invalid file signature`);
  }
}

await waitForBridge();
const csvUpload = await uploadAndQuick(csvPath, "text/csv");
await uploadAndQuick(xlsxPath, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
await verifyAnalystAndReport(csvUpload);

console.log(
  "LAC hybrid contract passed: CSV + XLSX + Quick + Analyst + verified XLSX/HTML/PDF reports"
);
