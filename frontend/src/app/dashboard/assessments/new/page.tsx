import { NewAssessment } from "@/components/citizen/assessments";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ scheme?: string }>;
}) {
  const { scheme } = await searchParams;
  return <NewAssessment initialScheme={scheme} />;
}
