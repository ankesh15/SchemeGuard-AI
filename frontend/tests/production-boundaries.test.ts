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
