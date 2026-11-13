"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { adminFetch, adminJSON, type AdminSession } from "@/lib/admin";
export function AdminLogin() {
  const router = useRouter();
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="container page-shell">
      <div className="admin-login">
        <span className="eyebrow">Administrator access</span>
        <h1>Welcome to the review workspace.</h1>
        <p>
          Sign in to manage authorized policy documents and inspect candidate
          rules.
        </p>
        <form
          className="admin-form"
          onSubmit={async (event) => {
            event.preventDefault();
            setError("");
            if (!username.trim() || !password) {
              setError("Enter your username and password.");
              return;
            }
            setBusy(true);
            try {
              await adminFetch<AdminSession>(
                "auth/login",
                adminJSON({
                  username: username.trim().toLowerCase(),
                  password,
                }),
              );
              setPassword("");
              router.replace("/admin");
              router.refresh();
            } catch (reason) {
              setError(
                reason instanceof Error ? reason.message : "Sign-in failed.",
              );
              setBusy(false);
            }
          }}
        >
          <label>
            Username
            <input
              name="username"
              autoComplete="username"
              value={username}
              maxLength={80}
              onChange={(e) => setUsername(e.target.value)}
              disabled={busy || !hydrated}
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              maxLength={1024}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy || !hydrated}
            />
          </label>
          {error && (
            <div role="alert" className="form-error">
              {error}
            </div>
          )}
          <button
            className="button button-primary"
            disabled={busy || !hydrated}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="small-note">
          Accounts are provisioned by the project operator. Public administrator
          registration is unavailable.
        </p>
      </div>
    </div>
  );
}
