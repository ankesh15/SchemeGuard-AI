import type { Metadata } from "next";
import { RecommendationResults } from "@/components/recommendations";
export const metadata: Metadata = { title: "Your recommended schemes" };
export default function RecommendedPage() {
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">Personalized for your next step</span>
        <h1>Government Schemes Recommended for You</h1>
        <p>
          Based on your profile and interests, here are schemes worth exploring.
        </p>
      </div>
      <RecommendationResults />
    </div>
  );
}
