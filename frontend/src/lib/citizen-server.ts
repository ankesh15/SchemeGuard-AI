import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { CitizenSession } from "./citizen";
export async function requireCitizenSession(): Promise<CitizenSession> {
  const token = (await cookies()).get("schemeguard_session")?.value;
  if (!token) redirect("/login");
  const response = await fetch(
    `${process.env.INTERNAL_API_URL || "http://api:8000"}/api/v1/me`,
    { headers: { Cookie: `schemeguard_session=${token}` }, cache: "no-store" },
  );
  if (response.status === 401 || response.status === 403) redirect("/login");
  if (!response.ok)
    throw new Error("Account authentication service is unavailable");
  const session = (await response.json()) as CitizenSession;
  if (session.role !== "citizen") redirect("/admin");
  return session;
}
