import Link from "next/link";
import { Explorer } from "@/components/explorer";
export default function AllSchemesPage() {
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">Manual exploration</span>
        <h1>Browse all government schemes.</h1>
        <p>
          Search the catalog and follow official sources, or start with your
          interests.
        </p>
        <Link className="text-link" href="/find-schemes">
          Find Schemes for Me →
        </Link>
      </div>
      <Explorer />
    </div>
  );
}
