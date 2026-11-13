import { SavedAssessmentDetail } from "@/components/citizen/assessments";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SavedAssessmentDetail id={id} />;
}
