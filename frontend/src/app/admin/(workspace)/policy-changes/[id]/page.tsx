import { PolicyChangeDetail } from "@/components/admin/monitoring";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PolicyChangeDetail id={id} />;
}
