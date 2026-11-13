import { beforeEach, describe, it, expect, vi } from "vitest";
const cookie = vi.fn();
vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: cookie }) }));
vi.mock("next/navigation", () => ({
  redirect: (path: string) => {
    throw new Error(`Redirect:${path}`);
  },
}));
import { requireCitizenSession } from "@/lib/citizen-server";
describe("server-protected citizen routes", () => {
  beforeEach(() => {
    cookie.mockReturnValue(undefined);
  });
  it("redirects unauthenticated requests before loading private pages", async () => {
    await expect(requireCitizenSession()).rejects.toThrow("Redirect:/login");
  });
  it("rejects expired sessions", async () => {
    cookie.mockReturnValue({ value: "opaque-fixture" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 401 })),
    );
    await expect(requireCitizenSession()).rejects.toThrow("Redirect:/login");
  });
  it("keeps administrators in the protected admin workspace", async () => {
    cookie.mockReturnValue({ value: "opaque-fixture" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json({ role: "admin" })),
    );
    await expect(requireCitizenSession()).rejects.toThrow("Redirect:/admin");
  });
});
