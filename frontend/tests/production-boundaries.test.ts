import { describe, it, expect, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/v1/[...path]/route";
import { proxy } from "@/proxy";
describe("production request boundaries", () => {
  it("does not forward credentials or permit private paths through the public proxy", async () => {
    const fetcher = vi.fn(async (_url: string, _options?: RequestInit) =>
      Response.json({ items: [] }),
    );
    vi.stubGlobal("fetch", fetcher);
    const response = await GET(
      new NextRequest("http://localhost/api/v1/schemes", {
        headers: { Cookie: "schemeguard_session=synthetic" },
      }),
      { params: Promise.resolve({ path: ["schemes"] }) },
    );
    expect(response.status).toBe(200);
    expect(fetcher.mock.calls[0]?.[1]?.headers).toEqual({
      "Content-Type": "application/json",
    });
    expect(
      (
        await GET(new NextRequest("http://localhost/api/v1/me"), {
          params: Promise.resolve({ path: ["me"] }),
        })
      ).status,
    ).toBe(404);
  });
  it("bounds public JSON before contacting the backend", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(
      new NextRequest("http://localhost/api/v1/eligibility/check", {
        method: "POST",
        body: "x".repeat(16001),
      }),
      { params: Promise.resolve({ path: ["eligibility", "check"] }) },
    );
    expect(response.status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("gives each production response a fresh restrictive script nonce", () => {
    vi.stubEnv("NODE_ENV", "production");
    const first = proxy(new NextRequest("https://localhost/login"));
    const second = proxy(new NextRequest("https://localhost/login"));
    const csp = first.headers.get("Content-Security-Policy")!;
    expect(csp).toContain("strict-dynamic");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toContain("script-src 'self' 'unsafe-inline'");
    expect(csp).not.toBe(second.headers.get("Content-Security-Policy"));
    expect(first.headers.get("Strict-Transport-Security")).toContain(
      "31536000",
    );
  });
});

it("allows stateless assessment routes without forwarding sessions or exposing private saving", async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) =>
    Response.json({ result: "UNKNOWN" }),
  );
  vi.stubGlobal("fetch", fetcher);
  const response = await POST(
    new NextRequest("http://localhost/api/v1/assessment/check", {
      method: "POST",
      headers: {
        Cookie: "schemeguard_session=synthetic",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scheme_id: "11111111-1111-4111-8111-111111111111",
        profile: {},
      }),
    }),
    { params: Promise.resolve({ path: ["assessment", "check"] }) },
  );
  expect(response.status).toBe(200);
  expect(fetcher.mock.calls[0]?.[1]?.headers).toEqual({
    "Content-Type": "application/json",
  });
  const rejected = await POST(
    new NextRequest("http://localhost/api/v1/assessments", { method: "POST" }),
    { params: Promise.resolve({ path: ["assessments"] }) },
  );
  expect(rejected.status).toBe(404);
});

it("proxies recommendations as transient POST without citizen credentials and bounds input", async () => {
  const fetcher = vi.fn(async (_url: string, _options?: RequestInit) =>
    Response.json({ items: [] }),
  );
  vi.stubGlobal("fetch", fetcher);
  const response = await POST(
    new NextRequest("http://localhost/api/v1/recommendations", {
      method: "POST",
      headers: { Cookie: "schemeguard_session=private" },
      body: JSON.stringify({ interests: ["education"] }),
    }),
    { params: Promise.resolve({ path: ["recommendations"] }) },
  );
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(fetcher.mock.calls[0][1]?.headers).not.toHaveProperty("Cookie");
  const large = await POST(
    new NextRequest("http://localhost/api/v1/recommendations", {
      method: "POST",
      body: "x".repeat(16001),
    }),
    { params: Promise.resolve({ path: ["recommendations"] }) },
  );
  expect(large.status).toBe(413);
});
