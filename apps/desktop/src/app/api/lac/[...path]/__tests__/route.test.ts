import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/lac/[...path]/route";

const mockFetch = vi.fn<typeof fetch>();
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

beforeEach(() => {
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
  process.env.LAC_BRIDGE_URL = "http://127.0.0.1:8765";
  process.env.LAC_API_TOKEN = "local-token";
});

afterEach(() => {
  vi.unstubAllGlobals();
  delete process.env.LAC_BRIDGE_URL;
  delete process.env.LAC_API_TOKEN;
});

describe("LAC same-origin proxy", () => {
  it("forwards health only to the local bridge and keeps the token server-side", async () => {
    mockFetch.mockResolvedValue(
      Response.json({ status: "ready" }, { headers: { "Content-Type": "application/json" } })
    );

    const response = await GET(
      new Request("http://hermetic.local/api/lac/api/v1/health"),
      context(["api", "v1", "health"])
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ready" });
    const [target, init] = mockFetch.mock.calls[0];
    expect(String(target)).toBe("http://127.0.0.1:8765/api/v1/health");
    expect(new Headers(init?.headers).get("X-LAC-Token")).toBe("local-token");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });

  it("forwards an allowed Quick request body", async () => {
    mockFetch.mockResolvedValue(Response.json({ status: "completed" }));
    const request = new Request("http://hermetic.local/api/lac/api/v1/analysis/quick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: "/safe/data.csv" }),
    });

    const response = await POST(request, context(["api", "v1", "analysis", "quick"]));

    expect(response.status).toBe(200);
    const [, init] = mockFetch.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect((init as RequestInit & { duplex?: "half" }).duplex).toBe("half");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
  });

  it("forwards an allowlisted local Agent request", async () => {
    mockFetch.mockResolvedValue(Response.json({ status: "planner_unavailable" }));
    const request = new Request("http://hermetic.local/api/lac/api/v1/analysis/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: "incoming/data.csv", question: "Özetle" }),
    });

    const response = await POST(request, context(["api", "v1", "analysis", "agent"]));

    expect(response.status).toBe(200);
    const [target, init] = mockFetch.mock.calls[0];
    expect(String(target)).toBe("http://127.0.0.1:8765/api/v1/analysis/agent");
    expect(init).toEqual(expect.objectContaining({ method: "POST", body: expect.anything() }));
  });

  it("forwards a verified Analyst XLSX response and its safe download headers", async () => {
    mockFetch.mockResolvedValue(
      new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
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
    const request = new Request("http://hermetic.local/api/lac/api/v1/analysis/analyst/report", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      },
      body: JSON.stringify({ target_column: "target" }),
    });

    const response = await POST(request, context(["api", "v1", "analysis", "analyst", "report"]));

    expect(response.status).toBe(200);
    expect(response.headers.get("X-LAC-Report-Verification")).toBe("passed");
    expect(response.headers.get("Content-Disposition")).toContain("analyst_report.xlsx");
    const [, init] = mockFetch.mock.calls[0];
    expect(new Headers(init?.headers).get("Accept")).toContain("spreadsheetml.sheet");
  });

  it.each([
    ["html", "text/html; charset=utf-8", "analyst-html-report.v1", "analyst_report.html"],
    ["pdf", "application/pdf", "analyst-pdf-report.v1", "analyst_report.pdf"],
  ])("forwards a verified Analyst %s response", async (format, mediaType, schema, filename) => {
    mockFetch.mockResolvedValue(
      new Response(format === "pdf" ? "%PDF-1.7" : "<!doctype html>", {
        headers: {
          "Content-Type": mediaType,
          "Content-Disposition": `attachment; filename="${filename}"`,
          "X-LAC-Report-Schema": schema,
          "X-LAC-Report-Verification": "passed",
          "X-LAC-Report-Findings": "4",
          "X-LAC-Report-Cards": "1",
        },
      })
    );
    const path = ["api", "v1", "analysis", "analyst", "report", format];
    const request = new Request(`http://hermetic.local/api/lac/${path.join("/")}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: mediaType },
      body: JSON.stringify({ target_column: "target" }),
    });

    const response = await POST(request, context(path));

    expect(response.status).toBe(200);
    expect(response.headers.get("X-LAC-Report-Schema")).toBe(schema);
    expect(response.headers.get("Content-Disposition")).toContain(filename);
    expect(new Headers(mockFetch.mock.calls[0][1]?.headers).get("Accept")).toBe(mediaType);
  });

  it("rejects paths and methods outside the bridge allowlist", async () => {
    const response = await GET(
      new Request("http://hermetic.local/api/lac/api/v1/admin"),
      context(["api", "v1", "admin"])
    );

    expect(response.status).toBe(404);
    expect((await response.json()).detail.code).toBe("bridge_route_not_allowed");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("rejects a non-loopback bridge target", async () => {
    process.env.LAC_BRIDGE_URL = "https://example.com";

    const response = await GET(
      new Request("http://hermetic.local/api/lac/api/v1/health"),
      context(["api", "v1", "health"])
    );

    expect(response.status).toBe(500);
    expect((await response.json()).detail.code).toBe("bridge_configuration_invalid");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns a typed unavailable error when the local bridge cannot be reached", async () => {
    mockFetch.mockRejectedValue(new Error("connection refused"));

    const response = await GET(
      new Request("http://hermetic.local/api/lac/api/v1/health"),
      context(["api", "v1", "health"])
    );

    expect(response.status).toBe(503);
    const payload = await response.json();
    expect(payload.detail).toMatchObject({
      code: "bridge_unavailable",
      hint: expect.stringContaining("127.0.0.1:8765"),
    });
  });
});
