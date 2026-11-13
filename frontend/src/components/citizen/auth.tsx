"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { citizenFetch, citizenJSON, type CitizenSession } from "@/lib/citizen";
export function CitizenAuth({ register = false }: { register?: boolean }) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!/^[a-z][a-z0-9_.-]{2,79}$/.test(username)) {
      setError(
        "Use a lowercase username of 3–80 letters, numbers, dots, hyphens or underscores.",
      );
      return;
    }
    if (!password || (register && password.length < 12)) {
      setError("Use a password of at least 12 characters.");
      return;
    }
    if (register && password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const session = await citizenFetch<CitizenSession>(
        register ? "auth/register" : "auth/login",
        citizenJSON({ username, password }),
      );
      setPassword("");
      setConfirmation("");
      router.replace(session.role === "admin" ? "/admin" : "/dashboard");
      router.refresh();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Authentication failed",
      );
      setPassword("");
      setConfirmation("");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="container page-shell">
      <section className="admin-login admin-card citizen-workspace">
        <span className="eyebrow">Citizen account</span>
        <h1>{register ? "Create your private workspace." : "Welcome back."}</h1>
        <p>
          Save profiles and source-backed assessments, and review verified
          policy updates. No Aadhaar number or identity document is requested.
        </p>
        <form
          className="admin-form"
          onSubmit={(event) => void submit(event)}
          noValidate
        >
          <label>
            Username
            <input
              autoComplete="username"
              maxLength={80}
              value={username}
              disabled={busy}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              maxLength={128}
              value={password}
              disabled={busy}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {register && (
            <label>
              Confirm password
              <input
                type="password"
                autoComplete="new-password"
                maxLength={128}
                value={confirmation}
                disabled={busy}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
          )}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="button button-primary" disabled={busy}>
            {busy ? "Please wait…" : register ? "Create account" : "Sign in"}
          </button>
        </form>
        <p className="small-note">
          Session cookies are HttpOnly. Private profiles and assessment
          snapshots are encrypted on the backend.
        </p>
        <Link className="text-link" href={register ? "/login" : "/register"}>
          {register
            ? "Already registered? Sign in"
            : "Create a citizen account"}
        </Link>
        {!register && (
          <p className="small-note">
            Password reset delivery is not configured. No reset link or insecure
            recovery token is issued.
          </p>
        )}
      </section>
    </div>
  );
}
