"use client";
import { useEffect, useState } from "react";
import {
  Search,
  SlidersHorizontal,
  ArrowLeft,
  ArrowRight,
  RotateCcw,
  Info,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { SchemePage } from "@/lib/types";
import { SchemeCard } from "./scheme-card";
import { ErrorState, LoadingState } from "./ui";

const states = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
];
export function Explorer() {
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [state, setState] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<SchemePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const timer = setTimeout(() => {
      setTerm(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ page: String(page), page_size: "6" });
    if (term) query.set("search", term);
    if (state) query.set("state", state);
    if (category) query.set("category", category);
    apiFetch<SchemePage>(`/api/v1/schemes?${query}`, {
      signal: controller.signal,
    })
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") {
          setError(
            "Please check that the scholarship service is running and try again.",
          );
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [term, state, category, page, retry]);
  function reset() {
    setSearch("");
    setTerm("");
    setState("");
    setCategory("");
    setPage(1);
  }
  return (
    <>
      <div className="filter-panel">
        <div className="search-input">
          <Search size={19} />
          <input
            aria-label="Search scholarships"
            placeholder="Search by scheme name or keyword…"
            value={search}
            maxLength={200}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <label className="filter-select">
          <SlidersHorizontal size={17} />
          <span className="sr-only">Category</span>
          <select
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All categories</option>
            <option value="scholarship">Scholarships</option>
          </select>
        </label>
        <label className="filter-select">
          <span className="sr-only">State or union territory</span>
          <select
            value={state}
            onChange={(event) => {
              setState(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All regions</option>
            {states.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="results-toolbar">
        <p role="status">
          {loading
            ? "Finding scholarships…"
            : `${data?.total ?? 0} scheme${data?.total === 1 ? "" : "s"} to explore`}
        </p>
        {(term || state || category) && (
          <button className="text-link" onClick={reset}>
            <RotateCcw size={14} />
            Clear filters
          </button>
        )}
        <span className="results-label">Evidence comes first</span>
      </div>
      {error ? (
        <ErrorState message={error} retry={() => setRetry(retry + 1)} />
      ) : loading ? (
        <LoadingState />
      ) : data?.items.length ? (
        <div className="scheme-grid">
          {data.items.map((scheme) => (
            <SchemeCard key={scheme.id} scheme={scheme} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Search size={28} />
          <h2>No schemes match these filters</h2>
          <p>
            Try a different keyword or clear the filters. Unknown geographic
            coverage is excluded from state-specific results.
          </p>
          <button className="button button-secondary" onClick={reset}>
            Clear filters
          </button>
        </div>
      )}
      {data && data.pages > 1 && !loading && (
        <nav aria-label="Scheme pagination" className="pagination">
          <button
            className="button button-secondary button-small"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            <ArrowLeft size={16} />
            Previous
          </button>
          <span>
            Page {page} of {data.pages}
          </span>
          <button
            className="button button-secondary button-small"
            disabled={page >= data.pages}
            onClick={() => setPage(page + 1)}
          >
            Next
            <ArrowRight size={16} />
          </button>
        </nav>
      )}
      <div className="notice mt-8">
        <Info size={18} className="shrink-0" />
        <p>
          State filters use verified coverage only. Missing coverage does not
          mean a scheme is unavailable to you. Scheme discovery is not an
          eligibility decision.
        </p>
      </div>
    </>
  );
}
