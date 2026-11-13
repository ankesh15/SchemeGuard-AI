import { NextRequest } from "next/server";
export const dynamic = "force-dynamic";
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const allowed = [
    "auth",
    "me",
    "profiles",
    "assessments",
    "notifications",
    "notification-preferences",
    "dashboard",
  ];
  if (
    !path.length ||
    path.some((part) => !/^[-a-zA-Z0-9_]+$/.test(part)) ||
    !allowed.includes(path[0])
  )
    return Response.json(
      { error: { message: "Unknown account route" } },
      { status: 404 },
    );
  const origins = JSON.parse(
    process.env.ADMIN_ALLOWED_ORIGINS || '["http://localhost:3000"]',
  ) as string[];
  const origin = request.headers.get("origin");
  if (request.method !== "GET" && (!origin || !origins.includes(origin)))
    return Response.json(
      { error: { message: "Account origin is not allowed" } },
      { status: 403 },
    );
  const headers = new Headers();
  if (origin) headers.set("Origin", origin);
  const cookie = request.cookies.get("schemeguard_session")?.value;
  if (cookie) headers.set("Cookie", `schemeguard_session=${cookie}`);
  const csrf = request.headers.get("x-csrf-token");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const type = request.headers.get("content-type");
  if (type) headers.set("Content-Type", type);
  let body: Uint8Array<ArrayBuffer> | undefined;
  if (request.method !== "GET") {
    const chunks: Uint8Array[] = [];
    let size = 0;
    const reader = request.body?.getReader();
    if (reader)
      while (true) {
        const item = await reader.read();
        if (item.done) break;
        size += item.value.byteLength;
        if (size > 16000) {
          await reader.cancel();
          return Response.json(
            { error: { message: "Account request exceeds its byte limit" } },
            { status: 413 },
          );
        }
        chunks.push(item.value);
      }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.length;
    }
  }
  try {
    const base = (process.env.INTERNAL_API_URL || "http://api:8000").replace(
      /\/$/,
      "",
    );
    const upstream = await fetch(
      `${base}/api/v1/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        body,
        headers,
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(30000),
      },
    );
    const output = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const key of [
      "content-type",
      "set-cookie",
      "retry-after",
      "x-request-id",
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
        error: { message: "The private account service could not be reached." },
      },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
