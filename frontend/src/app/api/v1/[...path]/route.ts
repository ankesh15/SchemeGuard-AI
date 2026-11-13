import { NextRequest } from "next/server";
export const dynamic = "force-dynamic";
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = path.join("/");
  const uuid = "[0-9a-fA-F-]{36}";
  const valid =
    request.method === "GET"
      ? new RegExp(
          `^(schemes|schemes/filters|schemes/${uuid}(/(requirements|rule-history))?|policy-updates)$`,
        ).test(target)
      : request.method === "POST" &&
        new RegExp(
          `^(eligibility/(check|explain)|schemes/${uuid}/questions)$`,
        ).test(target);
  if (!valid)
    return Response.json(
      { error: { message: "Unknown public route" } },
      { status: 404 },
    );
  let body: Uint8Array<ArrayBuffer> | undefined;
  if (request.method === "POST") {
    const reader = request.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader)
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.length;
        if (size > 16000) {
          await reader.cancel();
          return Response.json(
            { error: { message: "Request too large" } },
            { status: 413 },
          );
        }
        chunks.push(part.value);
      }
    body = new Uint8Array(size);
    let offset = 0;
    for (const part of chunks) {
      body.set(part, offset);
      offset += part.length;
    }
  }
  try {
    const base = (process.env.INTERNAL_API_URL || "http://api:8000").replace(
      /\/$/,
      "",
    );
    const upstream = await fetch(
      `${base}/api/v1/${target}${request.nextUrl.search}`,
      {
        method: request.method,
        body,
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(60000),
      },
    );
    const headers = new Headers({
      "Content-Type":
        upstream.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const key of ["x-request-id", "retry-after"]) {
      const value = upstream.headers.get(key);
      if (value) headers.set(key, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch {
    return Response.json(
      {
        error: { message: "The scheme service is unavailable. Please retry." },
      },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
