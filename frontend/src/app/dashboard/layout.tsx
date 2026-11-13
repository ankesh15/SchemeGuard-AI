import { requireCitizenSession } from "@/lib/citizen-server";
import { CitizenWorkspace } from "@/components/citizen/session";
export const dynamic = "force-dynamic";
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireCitizenSession();
  return <CitizenWorkspace session={session}>{children}</CitizenWorkspace>;
}
