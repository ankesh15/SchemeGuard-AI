import Link from "next/link";
import {
  ArrowUpRight,
  GraduationCap,
  FlaskConical,
  MapPin,
  Landmark,
} from "lucide-react";
import type { Scheme } from "@/lib/types";
import { categoryLabel } from "@/lib/catalog";
import { Badge } from "./ui";
import { schemeName } from "@/lib/presentation";

export function SchemeCard({
  scheme,
  assessment = false,
}: {
  scheme: Scheme;
  assessment?: boolean;
}) {
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
        {scheme.is_demo
          ? "Guided learning example"
          : categoryLabel(scheme.category)}
      </span>
      <h2>
        <Link href={`/schemes/${scheme.id}`}>
          {schemeName(scheme.name, scheme.is_demo)}
        </Link>
      </h2>
      <p className="card-description">
        {(scheme.is_demo
          ? "A project learning assessment with illustrative criteria."
          : scheme.description) ||
          "Visit the official source for details about this scheme."}
      </p>
      <div className="card-meta">
        <span>
          <Landmark size={14} />
          {scheme.is_demo
            ? "SchemeGuard learning example"
            : scheme.department || scheme.ministry || "Department not verified"}
        </span>
        <span>
          <MapPin size={14} />
          {scheme.applicability === "national"
            ? "National coverage"
            : scheme.applicable_states
              ? scheme.applicable_states.join(", ")
              : "Geographic coverage not verified"}
        </span>
      </div>
      <div className="card-bottom">
        <span
          className={scheme.eligibility_available ? "text-green" : "text-muted"}
        >
          {scheme.policy_currency === "POTENTIALLY_OUTDATED"
            ? "Policy source needs verification"
            : scheme.eligibility_available
              ? scheme.is_demo
                ? "Eligibility demo available"
                : "Approved eligibility rules"
              : scheme.assessment_mode === "ILLUSTRATIVE"
                ? "Illustrative assessment available"
                : "Discovery metadata only"}
        </span>
        <Link
          href={
            assessment
              ? `/eligibility?scheme=${scheme.id}`
              : `/schemes/${scheme.id}`
          }
          aria-label={
            assessment
              ? `Assess ${schemeName(scheme.name, scheme.is_demo)}`
              : `View ${schemeName(scheme.name, scheme.is_demo)}`
          }
        >
          {assessment ? "Select scheme" : "View scheme"}{" "}
          <ArrowUpRight size={16} />
        </Link>
      </div>
    </article>
  );
}
