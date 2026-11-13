import { Explorer } from "@/components/explorer";
import Link from "next/link";
export default function Page() {
  return (
    <>
      <section className="admin-card">
        <h2>Find schemes using official sources.</h2>
        <p>
          Discovery-only listings cannot produce eligibility decisions. Approved
          rules and policy currency are labeled separately.
        </p>
        <Link className="text-link" href="/dashboard/assessments/new">
          Start a supported private assessment →
        </Link>
      </section>
      <Explorer />
    </>
  );
}
