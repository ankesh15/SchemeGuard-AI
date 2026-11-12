import type { Metadata } from "next";
import { Explorer } from "@/components/explorer";
export const metadata: Metadata = { title: "Explore government schemes" };
export default function SchemesPage() {
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">The scheme explorer</span>
        <h1>Find a place to start.</h1>
        <p>
          Browse government scheme records, follow official sources, and
          understand what’s known.
        </p>
      </div>
      <Explorer />
    </div>
  );
}
