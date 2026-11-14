"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  citizenFetch,
  type ProfileRead,
  type SavedAssessment,
  type PolicyUpdate,
} from "@/lib/citizen";
import type { Recommendation } from "@/lib/recommendations";
import { RecommendationCard } from "@/components/recommendations";
import { useOptionalDiscovery } from "@/components/discovery-context";
import { categoryLabel } from "@/lib/catalog";
import { ErrorState, LoadingState } from "@/components/ui";
import { useCitizen } from "./session";
import { schemeName } from "@/lib/presentation";
export function CitizenDashboard() {
  const discovery = useOptionalDiscovery();
  const session = useCitizen();
  const remember = discovery?.remember;
  const [data, setData] = useState<{
    username: string;
    profile: ProfileRead;
    recent_assessments: SavedAssessment[];
    assessment_count: number;
    unread_count: number;
    policy_updates: PolicyUpdate[];
    relevant_schemes: Recommendation[];
    recommendation_categories: string[];
    recommendation_total: number;
    discovery_notice: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    citizenFetch<typeof data>("dashboard", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          if (value) remember?.(value.relevant_schemes);
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [retry, remember]);
  if (error)
    return (
      <ErrorState
        message={error}
        retry={() => {
          setError("");
          setRetry((value) => value + 1);
        }}
      />
    );
  if (!data) return <LoadingState message="Loading your private dashboard…" />;
  return (
    <>
      <div className="admin-stats">
        {[
          ["Profile completeness", `${data.profile.completeness.percent}%`],
          ["Saved assessments", data.assessment_count],
          ["Unread notifications", data.unread_count],
        ].map(([label, value]) => (
          <article className="aside-card" key={label}>
            <span className="eyebrow">{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      <section className="admin-card">
        <span className="eyebrow">Welcome, {data.username}</span>
        <h2>Your next step starts with evidence.</h2>
        <p>
          Maintain only the profile information you need, explore official
          scheme sources, and save versioned assessments. A missing answer stays
          unknown.
        </p>
        <div className="admin-actions">
          <Link
            className="button button-primary"
            href="/find-schemes"
            onClick={() =>
              discovery?.setProfile(data.profile.profile, session.user_id)
            }
          >
            Find Schemes for Me
          </Link>
          <Link className="button button-secondary" href="/dashboard/profile">
            Manage private profile
          </Link>
          <Link className="text-link" href="/dashboard/assessments/new">
            Create an assessment →
          </Link>
        </div>
      </section>
      <section className="admin-card">
        <h2>Recommended schemes for you</h2>
        <p>{data.discovery_notice}</p>
        {!data.relevant_schemes?.length && (
          <p>
            Complete the questionnaire with an interest, occupation or student
            status to discover relevant schemes.
          </p>
        )}
        <div className="profile-interest-tags">
          {data.recommendation_categories?.map((category) => (
            <span key={category}>{categoryLabel(category)}</span>
          ))}
        </div>
        <div className="scheme-grid">
          {data.relevant_schemes
            ?.filter((scheme) => !scheme.is_demo)
            .map((scheme) => (
              <RecommendationCard key={scheme.id} item={scheme} />
            ))}
        </div>
        <Link
          className="text-link"
          href="/schemes"
          onClick={() =>
            discovery?.setProfile(data.profile.profile, session.user_id)
          }
        >
          View personalized recommendations →
        </Link>
      </section>
      <section className="admin-card">
        <h2>Recent assessments</h2>
        {!data.recent_assessments.length ? (
          <p>No saved assessments yet. Select a supported scheme to begin.</p>
        ) : (
          data.recent_assessments.map((item) => (
            <article key={item.id} className="review-condition">
              <strong>{schemeName(item.scheme_name)}</strong>
              <p>
                {item.assessment} · Policy {item.rule_version ?? "unavailable"}{" "}
                · {new Date(item.created_at).toLocaleDateString("en-IN")}
              </p>
              <Link
                className="text-link"
                href={`/dashboard/assessments/${item.id}`}
              >
                Read saved assessment →
              </Link>
            </article>
          ))
        )}
      </section>
      <section className="admin-card">
        <h2>Verified policy updates</h2>
        {!data.policy_updates.length ? (
          <p>
            No verified policy updates for your saved schemes. Unapproved
            proposals are never shown as facts.
          </p>
        ) : (
          data.policy_updates.map((item) => (
            <p key={item.id}>
              <Link
                className="text-link"
                href={`/schemes/${item.scheme_id}#policy-history`}
              >
                Published{" "}
                {new Date(item.published_at).toLocaleDateString("en-IN")} ·{" "}
                {item.classification}
              </Link>
            </p>
          ))
        )}
        <Link className="text-link" href="/dashboard/notifications">
          View notifications →
        </Link>
      </section>
    </>
  );
}
export function CitizenPolicyUpdates() {
  const [items, setItems] = useState<PolicyUpdate[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    citizenFetch<{ items: PolicyUpdate[] }>("me/policy-updates", {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setItems(value.items);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, []);
  return (
    <section className="admin-card">
      <h2>Published updates for your saved schemes</h2>
      <p>
        Only verified policy publications appear here. Reassessment, when
        authorized, creates a separate result and preserves your original
        assessment.
      </p>
      {error ? (
        <ErrorState message={error} />
      ) : !items ? (
        <LoadingState message="Loading verified updates…" />
      ) : !items.length ? (
        <p>No published changes affect your saved schemes.</p>
      ) : (
        items.map((item) => (
          <article key={item.id} className="review-condition">
            <strong>{item.classification}</strong>
            <p>
              Published {new Date(item.published_at).toLocaleString()} ·
              Effective {item.effective_from || "Unverified"}
            </p>
            <Link
              className="text-link"
              href={`/schemes/${item.scheme_id}#policy-history`}
            >
              View source and policy history →
            </Link>
          </article>
        ))
      )}
    </section>
  );
}
