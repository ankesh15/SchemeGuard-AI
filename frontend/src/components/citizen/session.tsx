"use client";
import { createContext, useContext, useState } from "react";
import Link from "next/link";
import { useOptionalReport } from "@/components/report-context";
import { useOptionalDiscovery } from "@/components/discovery-context";
import { useRouter } from "next/navigation";
import { citizenFetch, citizenJSON, type CitizenSession } from "@/lib/citizen";
const SessionContext = createContext<CitizenSession | null>(null);
export function useCitizen() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Citizen session required");
  return value;
}
export function CitizenWorkspace({
  session,
  children,
}: {
  session: CitizenSession;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const discovery = useOptionalDiscovery();
  const transientReport = useOptionalReport();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <SessionContext.Provider value={session}>
      <div className="container page-shell admin-workspace citizen-workspace">
        <div className="admin-top">
          <div>
            <span className="eyebrow">Your private workspace</span>
            <h1>Clarity for your next step.</h1>
            <p>
              Signed in as {session.username}. Assessments are informational,
              not government approval.
            </p>
          </div>
          <button
            className="button button-secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await citizenFetch(
                  "auth/logout",
                  citizenJSON({}, session.csrf_token),
                );
                discovery?.clear();
                transientReport?.setReport(null);
                transientReport?.setExplanation(null);
                router.replace("/login");
                router.refresh();
              } catch (reason) {
                setError(
                  reason instanceof Error ? reason.message : "Sign-out failed",
                );
                setBusy(false);
              }
            }}
          >
            Sign out
          </button>
        </div>
        <nav className="section-tabs" aria-label="Citizen navigation">
          {[
            ["/dashboard", "Overview"],
            ["/dashboard/profile", "Profile"],
            ["/dashboard/schemes", "Schemes"],
            ["/dashboard/assessments", "Assessments"],
            ["/dashboard/notifications", "Notifications"],
            ["/dashboard/policy-updates", "Policy updates"],
            ["/dashboard/settings", "Settings"],
          ].map(([href, label]) => (
            <Link key={href} href={href}>
              {label}
            </Link>
          ))}
        </nav>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {children}
      </div>
    </SessionContext.Provider>
  );
}
