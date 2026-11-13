import { NextRequest } from "next/server";
export const dynamic = "force-dynamic";
const cookieName = "schemeguard_session";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  // Fixed upstream routes only: never accept a hostname or arbitrary target URL.
  if (
    !path.length ||
    path.some((part) => !/^[-a-zA-Z0-9_]+$/.test(part)) ||
    ![
      "auth",
      "documents",
      "sources",
      "extractions",
      "overview",
      "workflows",
      "reviews",
      "monitors",
      "monitoring-runs",
      "policy-changes",
      "audit",
      "schemes",
    ].includes(path[0])
  )
    return Response.json(
      { error: { message: "Unknown administrator route" } },
      { status: 404 },
    );
  const origins = JSON.parse(
    process.env.ADMIN_ALLOWED_ORIGINS || '["http://localhost:3000"]',
  ) as string[];
  const origin = request.headers.get("origin");
  if (request.method !== "GET" && (!origin || !origins.includes(origin)))
    return Response.json(
      { error: { message: "Administrator origin is not allowed" } },
      { status: 403 },
    );
  if (path[0] === "schemes" && (request.method !== "GET" || path.length > 1))
    return Response.json(
      { error: { message: "Unknown lookup route" } },
      { status: 404 },
    );
  const base = (process.env.INTERNAL_API_URL || "http://api:8000").replace(
    /\/$/,
    "",
  );
  const target = `${base}/api/v1/${path[0] === "schemes" ? "" : "admin/"}${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  if (origin) headers.set("Origin", origin);
  const csrf = request.headers.get("x-csrf-token");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const cookie = request.cookies.get(cookieName)?.value;
  if (cookie) headers.set("Cookie", `${cookieName}=${cookie}`);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  let body: Uint8Array<ArrayBuffer> | undefined;
  if (request.method !== "GET") {
    const maximum = contentType?.startsWith("application/pdf")
      ? 10 * 1024 * 1024
      : path[0] === "reviews"
        ? 131072
        : 16000;
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        size += next.value.byteLength;
        if (size > maximum) {
          await reader.cancel();
          return Response.json(
            {
              error: {
                message: "Administrator request exceeds its byte limit",
              },
            },
            { status: 413 },
          );
        }
        chunks.push(next.value);
      }
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(330000),
    });
    const output = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const key of [
      "content-type",
      "content-disposition",
      "set-cookie",
      "retry-after",
      "x-request-id",
      "x-document-duplicate",
      "content-security-policy",
    ]) {
      const value = upstream.headers.get(key);
      if (value) output.set(key, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: output,
    });
  } catch {
    return Response.json(
      {
        error: {
          message:
            "The administrator API could not be reached. Check document status before retrying a long extraction.",
        },
      },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
