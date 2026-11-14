import type { Metadata } from "next";
import { DiscoveryForm } from "@/components/discovery-form";
export const metadata: Metadata = { title: "Find My Schemes" };
export default function FindSchemesPage() {
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">Personalized discovery</span>
        <h1>Let’s find what matters to you.</h1>
        <p>
          Tell us a little about yourself. Explore schemes with a clear reason
          for every match.
        </p>
      </div>
      <DiscoveryForm />
    </div>
  );
}
