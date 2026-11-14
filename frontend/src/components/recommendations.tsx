"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Check,
  CircleHelp,
  Landmark,
  SlidersHorizontal,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AdminError } from "@/lib/admin";
import {
  citizenFetch,
  type CitizenSession,
  type ProfileRead,
} from "@/lib/citizen";
import { categoryLabel } from "@/lib/catalog";
import {
  relevanceLabel,
  type Recommendation,
  type RecommendationPage,
} from "@/lib/recommendations";
import { useDiscovery, useOptionalDiscovery } from "./discovery-context";
import { ErrorState, LoadingState, ProjectDisclaimer } from "./ui";

export function RecommendationCard({ item }: { item: Recommendation }) {
  return (
    <article className="scheme-card recommendation-card">
      <div className="recommendation-meta">
        <span className="category-pill">{categoryLabel(item.category)}</span>
        <span
          className={`relevance-tag relevance-${item.relevance.toLowerCase()}`}
        >
          {relevanceLabel[item.relevance]}
        </span>
      </div>
      <h3>
        <Link href={`/schemes/${item.id}`}>{item.name}</Link>
      </h3>
      <p className="scheme-description">{item.description}</p>
      <p className="recommendation-ministry">
        <Landmark size={15} />
        {item.department ||
          item.ministry ||
          "See official source for administering body"}
      </p>
      <div className="recommendation-reasons">
        <strong>Why this scheme?</strong>
        <ul>
          {item.matching_reasons.map((reason) => (
            <li key={reason}>
              <Check size={14} />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="small-note assessment-availability">
        {item.assessment_mode === "APPROVED_POLICY"
          ? "Reviewed policy assessment available"
          : item.assessment_mode === "ILLUSTRATIVE"
            ? "Illustrative assessment available · not verified eligibility"
            : "Detailed assessment criteria are not yet available for this scheme."}
      </p>
      {item.missing_information.length > 0 && (
        <details className="recommendation-missing">
          <summary>
            <CircleHelp size={15} />
            Information still needed
          </summary>
          <ul>
            {item.missing_information.map((value) => (
              <li key={value}>{value}</li>
            ))}
          </ul>
        </details>
      )}
      {item.policy_currency === "POTENTIALLY_OUTDATED" && (
        <p className="small-note">
          Policy source needs verification. Check current official guidance.
        </p>
      )}
      <div className="recommendation-footer">
        <Link
          className="button button-secondary button-small"
          href={`/schemes/${item.id}`}
        >
          View Details
          <ArrowRight size={15} />
        </Link>
        {item.official_source_url && (
          <a
            className="text-link"
            href={item.official_source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Official source ↗
          </a>
        )}
      </div>
    </article>
  );
}

// Resolves the primary /schemes route without loading an unrelated catalog.
export function DiscoveryEntry() {
  const router = useRouter();
  const { profile, setProfile } = useDiscovery();
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    if (profile) {
      router.replace("/schemes/recommended");
      return;
    }
    async function load() {
      try {
        const account = await citizenFetch<CitizenSession>("me", {
          signal: controller.signal,
        });
        if (account.role !== "citizen") {
          router.replace("/find-schemes");
          return;
        }
        const saved = await citizenFetch<ProfileRead>("profiles/me", {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (saved.exists) {
          setProfile(saved.profile, account.user_id);
          router.replace("/schemes/recommended");
        } else router.replace("/find-schemes");
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof AdminError && reason.status === 401)
          router.replace("/find-schemes");
        else
          setError(
            reason instanceof Error
              ? reason.message
              : "Your details could not be loaded",
          );
      }
    }
    void load();
    return () => controller.abort();
  }, [profile, setProfile, router]);
  return error ? (
    <ErrorState message={error} retry={() => router.refresh()} />
  ) : (
    <LoadingState message="Finding your starting point…" />
  );
}

export function RecommendationResults() {
  const { profile, remember } = useDiscovery();
  const [data, setData] = useState<RecommendationPage | null>(null);
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("relevance");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!profile) return;
    const controller = new AbortController();
    setBusy(true);
    setError("");
    apiFetch<RecommendationPage>("/api/v1/recommendations", {
      method: "POST",
      body: JSON.stringify({
        ...profile,
        page,
        page_size: 9,
        category: category || null,
        sort_by: sort,
      }),
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          remember(value.items);
        }
      })
      .catch((reason) => {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Recommendations could not be loaded",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [profile, page, category, sort, retry, remember]);
  if (!profile) return <DiscoveryEntry />;
  return (
    <>
      <section className="recommendation-summary">
        <div>
          <span className="eyebrow">Your discovery profile</span>
          <p>
            {[
              profile.state,
              profile.age_years !== null ? `Age ${profile.age_years}` : null,
              profile.current_student === true ? "Currently studying" : null,
              profile.occupation?.replaceAll("_", " "),
            ]
              .filter(Boolean)
              .join(" · ") || "Optional details not provided"}
          </p>
          <div className="profile-interest-tags">
            {profile.interests?.map((value) => (
              <span key={value}>{categoryLabel(value)}</span>
            ))}
          </div>
          <p className="small-note">
            Sensitive financial details are used only when supported by reviewed
            rules. Recommendations are relevance matches, not eligibility
            decisions.
          </p>
        </div>
        <Link className="button button-secondary" href="/find-schemes">
          Edit Details
          <SlidersHorizontal size={16} />
        </Link>
      </section>
      <div className="recommendation-toolbar">
        <p aria-live="polite">
          {data ? (
            <>
              <strong>{data.total}</strong> relevant schemes
            </>
          ) : (
            "Finding relevant schemes…"
          )}
        </p>
        <div>
          <label htmlFor="recommended-category">Category</label>
          <select
            id="recommended-category"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All relevant categories</option>
            {data?.categories.map((value) => (
              <option key={value} value={value}>
                {categoryLabel(value)}
              </option>
            ))}
          </select>
          <label htmlFor="recommendation-sort">Sort by</label>
          <select
            id="recommendation-sort"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setPage(1);
            }}
          >
            <option value="relevance">Relevance</option>
            <option value="name">Scheme name</option>
          </select>
        </div>
      </div>
      {error ? (
        <ErrorState
          message={error}
          retry={() => setRetry((value) => value + 1)}
        />
      ) : busy ? (
        <LoadingState message="Matching your interests with the scheme catalog…" />
      ) : data && data.items.length ? (
        <>
          <div className="scheme-grid recommendation-grid">
            {data.items.map((item) => (
              <RecommendationCard key={item.id} item={item} />
            ))}
          </div>
          <nav className="pagination" aria-label="Recommendation pages">
            <button
              className="button button-secondary button-small"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </button>
            <span>
              Page {page} of {Math.max(1, data.pages)}
            </span>
            <button
              className="button button-secondary button-small"
              disabled={page >= data.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Next page
            </button>
          </nav>
        </>
      ) : (
        data && (
          <section className="empty-state">
            <CircleHelp size={32} />
            <h2>Let’s make your recommendations more useful.</h2>
            <p>
              {category
                ? "No matches in this category. Try another filter or update your interests."
                : "Choose an interest, occupation or student status so we can find relevant schemes. Missing information never counts as a failed requirement."}
            </p>
            <Link className="button button-primary" href="/find-schemes">
              Update my details
            </Link>
            <Link className="text-link" href="/schemes/all">
              Browse all schemes →
            </Link>
          </section>
        )
      )}
      <div className="recommendation-bottom">
        <ProjectDisclaimer />
        <Link className="text-link" href="/schemes/all">
          Browse all schemes instead →
        </Link>
        <Link className="text-link" href="/register">
          Create an account to save a private profile →
        </Link>
      </div>
    </>
  );
}
export function RecommendationReason({ schemeId }: { schemeId: string }) {
  const discovery = useOptionalDiscovery();
  const item = discovery?.matches[schemeId];
  if (!item) return null;
  return (
    <section className="recommendation-summary detail-recommendation">
      <div>
        <span className="eyebrow">{relevanceLabel[item.relevance]}</span>
        <h2>Why this was recommended</h2>
        <ul>
          {item.matching_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <p className="small-note">
          Relevance does not determine government eligibility.
        </p>
      </div>
      <Link className="text-link" href="/schemes/recommended">
        Back to recommendations →
      </Link>
    </section>
  );
}
