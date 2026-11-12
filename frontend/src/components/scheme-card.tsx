import Link from "next/link";
import {
  ArrowUpRight,
  GraduationCap,
  FlaskConical,
  MapPin,
  Landmark,
} from "lucide-react";
import type { Scheme } from "@/lib/types";
import { Badge } from "./ui";

export function SchemeCard({ scheme }: { scheme: Scheme }) {
  return (
    <article
      className={`scheme-card ${scheme.is_demo ? "scheme-card-demo" : ""}`}
    >
      <div className="card-top">
        <span
          className={`scheme-icon ${scheme.is_demo ? "scheme-icon-demo" : ""}`}
        >
          {scheme.is_demo ? (
            <FlaskConical size={23} />
          ) : (
            <GraduationCap size={24} />
          )}
        </span>
        <Badge demo={scheme.is_demo} />
      </div>
      <span className="eyebrow">
        {scheme.is_demo ? "Guided learning example" : "Scholarship"}
      </span>
      <h2>
        <Link href={`/schemes/${scheme.id}`}>{scheme.name}</Link>
      </h2>
      <p className="card-description">
        {scheme.description ||
          "Visit the official source for details about this scholarship."}
      </p>
      <div className="card-meta">
        <span>
          <Landmark size={14} />
          {scheme.is_demo
            ? "SchemeGuard development fixture"
            : scheme.department || scheme.ministry || "Department not verified"}
        </span>
        <span>
          <MapPin size={14} />
          {scheme.applicable_states
            ? `${scheme.applicable_states.length} verified states`
            : "Geographic coverage not verified"}
        </span>
      </div>
      <div className="card-bottom">
        <span className={scheme.is_demo ? "text-green" : "text-muted"}>
          {scheme.is_demo
            ? "Eligibility demo available"
            : "Source metadata available"}
        </span>
        <Link href={`/schemes/${scheme.id}`} aria-label={`View ${scheme.name}`}>
          View scheme <ArrowUpRight size={16} />
        </Link>
      </div>
    </article>
  );
}
