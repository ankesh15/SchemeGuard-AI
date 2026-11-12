import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { AdminSession } from "./admin";
export async function requireAdminSession(): Promise<AdminSession> {
  const token = (await cookies()).get("schemeguard_session")?.value;
  if (!token) redirect("/admin/login");
  const base = process.env.INTERNAL_API_URL || "http://api:8000";
  const response = await fetch(`${base}/api/v1/admin/auth/session`, {
    headers: { Cookie: `schemeguard_session=${token}` },
    cache: "no-store",
  });
  if (response.status === 401 || response.status === 403)
    redirect("/admin/login");
  if (!response.ok)
    throw new Error("Administrator authentication service is unavailable");
  return response.json() as Promise<AdminSession>;
}
