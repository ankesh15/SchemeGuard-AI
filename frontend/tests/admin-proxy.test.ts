// Run the route in the node environment; only the fixed API upstream is mocked.
// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/admin/[...path]/route";
const context = (path: string[]) => ({ params: Promise.resolve({ path }) });
describe("administrator proxy security", () => {
  it("rejects untrusted origins before forwarding mutations", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(
      new NextRequest("http://localhost:3000/api/admin/auth/login", {
        method: "POST",
        headers: { Origin: "https://evil.example" },
      }),
      context(["auth", "login"]),
    );
    expect(response.status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("rejects arbitrary targets and path traversal", async () => {
    expect(
      (
        await GET(
          new NextRequest("http://localhost:3000/api/admin/anything"),
          context(["https:", "evil.example"]),
        )
      ).status,
    ).toBe(404);
    expect(
      (
        await GET(
          new NextRequest("http://localhost:3000/api/admin/documents"),
          context(["documents", ".."]),
        )
      ).status,
    ).toBe(404);
  });
  it("forwards only the administrator cookie and CSRF to the fixed upstream", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    await POST(
      new NextRequest("http://localhost:3000/api/admin/documents/doc/extract", {
        method: "POST",
        headers: {
          Origin: "http://localhost:3000",
          Cookie: "schemeguard_session=synthetic-session; other=private",
          "X-CSRF-Token": "test-csrf",
          "Content-Type": "application/json",
        },
        body: '{"mode":"parse_only"}',
      }),
      context(["documents", "doc", "extract"]),
    );
    expect(fetcher.mock.calls[0][0]).toBe(
      "http://api:8000/api/v1/admin/documents/doc/extract",
    );
    expect(fetcher.mock.calls[0][1].headers.get("Cookie")).toBe(
      "schemeguard_session=synthetic-session",
    );
    expect(fetcher.mock.calls[0][1].headers.get("X-CSRF-Token")).toBe(
      "test-csrf",
    );
    expect(fetcher.mock.calls[0][1].redirect).toBe("manual");
  });
  it("bounds request bodies before forwarding", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const response = await POST(
      new NextRequest("http://localhost:3000/api/admin/auth/login", {
        method: "POST",
        headers: {
          Origin: "http://localhost:3000",
          "Content-Type": "application/json",
        },
        body: "x".repeat(16001),
      }),
      context(["auth", "login"]),
    );
    expect(response.status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
