import { requireAdminSession } from "@/lib/admin-server";
import { AdminWorkspace } from "@/components/admin/session";
export const dynamic = "force-dynamic";
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await requireAdminSession();
  return <AdminWorkspace session={session}>{children}</AdminWorkspace>;
}
