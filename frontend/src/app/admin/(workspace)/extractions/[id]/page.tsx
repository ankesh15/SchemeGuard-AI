import { ExtractionDetail } from "@/components/admin/extraction-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExtractionDetail id={id} />;
}
