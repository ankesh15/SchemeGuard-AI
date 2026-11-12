"use client";
import { createContext, useContext, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { adminFetch, adminJSON, type AdminSession } from "@/lib/admin";
const SessionContext = createContext<AdminSession | null>(null);
export function useAdmin() {
  const session = useContext(SessionContext);
  if (!session) throw new Error("Administrator session required");
  return session;
}
export function AdminWorkspace({
  session,
  children,
}: {
  session: AdminSession;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <SessionContext.Provider value={session}>
      <div className="container page-shell admin-workspace">
        <div className="admin-top">
          <div>
            <span className="eyebrow">Administrator workspace</span>
            <h1>Document intelligence.</h1>
            <p>Official sources. Traceable evidence. Human review.</p>
          </div>
          <div>
            <span className="small-note">Signed in as {session.username}</span>
            <button
              className="button button-secondary button-small"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await adminFetch(
                    "auth/logout",
                    adminJSON({}, session.csrf_token),
                  );
                  router.replace("/admin/login");
                  router.refresh();
                } catch (reason) {
                  setError(
                    reason instanceof Error
                      ? reason.message
                      : "Sign-out failed.",
                  );
                  setBusy(false);
                }
              }}
            >
              Sign out
            </button>
          </div>
        </div>
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <nav className="section-tabs" aria-label="Administrator navigation">
          <Link href="/admin">Overview</Link>
          <Link href="/admin/workflows">Workflows</Link>
          <Link href="/admin/reviews">Human review</Link>
          <Link href="/admin/documents">Documents & sources</Link>
          <Link href="/schemes">Public explorer</Link>
        </nav>
        <div className="notice mt-5">
          <p>
            Extracted rules remain pending until an administrator reviews the
            complete policy. Only an explicit saved human decision can publish a
            new immutable rule version.
          </p>
        </div>
        {children}
      </div>
    </SessionContext.Provider>
  );
}
