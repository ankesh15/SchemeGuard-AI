"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { citizenFetch, citizenJSON, type Preferences } from "@/lib/citizen";
import { useCitizen } from "./session";
import { LoadingState } from "@/components/ui";
export function CitizenSettings() {
  const session = useCitizen();
  const router = useRouter();
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [username, setUsername] = useState(session.username);
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    citizenFetch<Preferences>("notification-preferences", {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setPrefs(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, []);
  async function action(
    path: string,
    body: unknown,
    method = "POST",
    leave = false,
  ) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await citizenFetch(path, citizenJSON(body, session.csrf_token, method));
      if (leave) {
        router.replace("/login");
        router.refresh();
      } else {
        setNotice("Settings saved.");
        router.refresh();
      }
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Settings could not be updated",
      );
    } finally {
      setCurrent("");
      setPassword("");
      setConfirmation("");
      setBusy(false);
    }
  }
  function passwordChange(event: FormEvent) {
    event.preventDefault();
    if (password.length < 12 || password.length > 128) {
      setError("Use a password with 12 to 128 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    void action(
      "auth/password",
      { current_password: current, new_password: password },
      "POST",
      true,
    );
  }
  return (
    <>
      <section className="admin-card">
        <span className="eyebrow">Account control</span>
        <h2>Settings & privacy</h2>
        <p>
          Profile data and assessment snapshots are encrypted in storage.
          Reassessment requires consent on each saved assessment as well as the
          preference below.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
        <h3>Notification preferences</h3>
        {!prefs ? (
          <LoadingState message="Loading preferences…" />
        ) : (
          <form
            className="admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              void action("notification-preferences", prefs, "PUT");
            }}
          >
            <fieldset disabled={busy}>
              {(
                [
                  ["in_app", "In-app notifications"],
                  [
                    "automatic_reassessment",
                    "Automatically reassess assessments I have explicitly authorized",
                  ],
                  [
                    "policy_updates",
                    "Notify me about published policy updates for saved schemes",
                  ],
                ] as const
              ).map(([key, label]) => (
                <label className="review-check" key={key}>
                  <input
                    type="checkbox"
                    checked={prefs[key]}
                    onChange={(event) =>
                      setPrefs({ ...prefs, [key]: event.target.checked })
                    }
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <p className="small-note">
              Turning off in-app notifications does not remove existing
              messages. Policy history remains available.
            </p>
            <button className="button button-primary" disabled={busy}>
              Save preferences
            </button>
          </form>
        )}
      </section>
      <section className="admin-card">
        <h3>Account credentials</h3>
        <p>
          No email or recovery delivery service is configured. Password reset is
          unavailable; keep your password safely.
        </p>
        <label>
          Current password (required for account changes)
          <input
            type="password"
            autoComplete="current-password"
            maxLength={1024}
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            disabled={busy}
          />
        </label>
        <form
          className="admin-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!/^[a-z][a-z0-9_.-]{2,79}$/.test(username)) {
              setError(
                "Use 3–80 lowercase letters, numbers, dots, hyphens or underscores.",
              );
              return;
            }
            void action("me", { username, current_password: current }, "PATCH");
          }}
        >
          <label>
            Username
            <input
              autoComplete="username"
              maxLength={80}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={busy}
            />
          </label>
          <button
            className="button button-secondary"
            disabled={busy || !current}
          >
            Update username
          </button>
        </form>
        <form className="admin-form" onSubmit={passwordChange} noValidate>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              maxLength={128}
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              disabled={busy}
            />
          </label>
          <p>Changing your password revokes all sessions and signs you out.</p>
          <button
            className="button button-secondary"
            disabled={busy || !current}
          >
            Change password
          </button>
        </form>
      </section>
      <section className="admin-card">
        <h3>Delete your account</h3>
        <p>
          This permanently removes your private profile, assessment snapshots,
          reassessments and notifications. Sessions are revoked. A disabled
          anonymous account reference remains for security audit integrity;
          government documents and policy histories are preserved. Encrypted
          backups expire according to the operator’s retention policy.
        </p>
        <label className="review-check">
          <input
            type="checkbox"
            checked={ack}
            onChange={(event) => setAck(event.target.checked)}
            disabled={busy}
          />
          I understand that my private data will be deleted.
        </label>
        <button
          className="button button-secondary"
          disabled={busy || !ack || !current}
          onClick={() =>
            void action(
              "me",
              { current_password: current, acknowledge_deletion: ack },
              "DELETE",
              true,
            )
          }
        >
          Delete account and private data
        </button>
      </section>
    </>
  );
}
