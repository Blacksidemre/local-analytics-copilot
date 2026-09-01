import { envConfig } from "@/lib/harness-slot";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

const ALLOWED: Record<string, ReadonlySet<string>> = {
  "api/v1/health": new Set(["GET"]),
  "api/v1/datasets/upload": new Set(["POST"]),
  "api/v1/datasets/profile": new Set(["POST"]),
  "api/v1/analysis/quick": new Set(["POST"]),
  "api/v1/analysis/analyst": new Set(["POST"]),
  "api/v1/analysis/agent": new Set(["POST"]),
  "api/v1/analysis/analyst/report": new Set(["POST"]),
  "api/v1/analysis/analyst/report/html": new Set(["POST"]),
  "api/v1/analysis/analyst/report/pdf": new Set(["POST"]),
};

function typedError(status: number, code: string, message: string, hint: string | null = null) {
  return Response.json(
    { detail: { code, message, hint, details: {} } },
    { status, headers: { "Cache-Control": "no-store" } }
  );
}

function bridgeBaseUrl(): string {
  const configured = envConfig().LAC_BRIDGE_URL ?? "http://127.0.0.1:8765";
  const url = new URL(configured);
  const loopback = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);
  if (url.protocol !== "http:" || !loopback.has(url.hostname)) {
    throw new Error("LAC_BRIDGE_URL yalnızca yerel HTTP loopback adresi olabilir.");
  }
  return url.toString().replace(/\/+$/, "");
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const relativePath = path.join("/");
  if (!ALLOWED[relativePath]?.has(request.method)) {
    return typedError(404, "bridge_route_not_allowed", "Bu LAC Bridge yolu kullanılamaz.");
  }

  let target: URL;
  try {
    target = new URL(`${bridgeBaseUrl()}/${relativePath}`);
  } catch (error) {
    return typedError(
      500,
      "bridge_configuration_invalid",
      error instanceof Error ? error.message : "LAC Bridge yapılandırması geçersiz."
    );
  }

  const headers = new Headers({ Accept: request.headers.get("accept") ?? "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const contentLength = request.headers.get("content-length");
  if (contentLength) headers.set("Content-Length", contentLength);
  const token = envConfig().LAC_API_TOKEN;
  if (token) headers.set("X-LAC-Token", token);

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    body: request.method === "GET" ? undefined : request.body,
    cache: "no-store",
    signal: request.signal,
  };
  if (request.body) init.duplex = "half";

  try {
    const upstream = await fetch(target, init);
    const responseHeaders = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    const upstreamContentType = upstream.headers.get("content-type");
    if (upstreamContentType) responseHeaders.set("Content-Type", upstreamContentType);
    for (const header of [
      "content-disposition",
      "content-length",
      "x-lac-report-schema",
      "x-lac-report-verification",
      "x-lac-report-findings",
      "x-lac-report-cards",
    ]) {
      const value = upstream.headers.get(header);
      if (value) responseHeaders.set(header, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return typedError(
      503,
      "bridge_unavailable",
      "Local Analytics Copilot bağlantısı kurulamadı.",
      "LAC backend'in 127.0.0.1:8765 üzerinde çalıştığını kontrol edin."
    );
  }
}

export const GET = proxy;
export const POST = proxy;
