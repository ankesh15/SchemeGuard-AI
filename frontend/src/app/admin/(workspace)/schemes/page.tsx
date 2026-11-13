import { Explorer } from "@/components/explorer";
export default function Page() {
  return (
    <>
      <section className="admin-card">
        <h2>Schemes & approved versions</h2>
        <p>
          Select a scheme to inspect official sources, approved rule history,
          and policy currency. Metadata imports remain append-only through the
          validated seed command. Use Documents & sources to register new
          evidence.
        </p>
      </section>
      <Explorer />
    </>
  );
}
