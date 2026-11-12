import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  FileText,
  Fingerprint,
  Search,
  ShieldCheck,
  Sparkles,
  CircleHelp,
  LockKeyhole,
  BookOpen,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { SchemePage } from "@/lib/types";
import { ActionLink } from "@/components/ui";
import { SchemeCard } from "@/components/scheme-card";

export const dynamic = "force-dynamic";
export default async function Home() {
  const page = await apiFetch<SchemePage>("/api/v1/schemes?page_size=100");
  const demo = page.items.find((scheme) => scheme.is_demo);
  const featured = [
    demo,
    ...page.items.filter((scheme) => !scheme.is_demo).slice(0, 2),
  ].filter((scheme) => scheme !== undefined);
  return (
    <>
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <span className="hero-kicker">
              <span className="status-dot" /> A clearer path to educational
              opportunity
            </span>
            <h1>
              Clarity before
              <br />
              you <em>apply.</em>
            </h1>
            <p className="hero-description">
              Discover scholarship schemes. Understand their requirements. See
              the reasoning behind every assessment, one condition at a time.
            </p>
            <div className="hero-actions">
              <ActionLink href="/schemes">Explore scholarships</ActionLink>
              <ActionLink href="/eligibility" secondary arrow={false}>
                Try the eligibility demo <ArrowUpRight size={17} />
              </ActionLink>
            </div>
            <div className="hero-footnote">
              <ShieldCheck size={16} />
              <span>Official source references</span>
              <span className="dot-divider">·</span>
              <span>No sign-up needed</span>
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Illustration of an explainable fictional assessment"
          >
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <span className="floating-note">
              <FileText size={17} /> Every condition has a source
            </span>
            <div className="preview-report">
              <div className="preview-heading">
                <span className="preview-icon">
                  <ShieldCheck size={23} />
                </span>
                <div>
                  <strong>Your next step, explained</strong>
                  <span>Fictional scholarship · Sample report</span>
                </div>
                <span className="preview-dots">•••</span>
              </div>
              <div className="preview-result">
                <span className="eyebrow">Assessment snapshot</span>
                <h2>
                  Known conditions
                  <br />
                  satisfied <span>↗</span>
                </h2>
                <p>
                  A result you can understand, with the evidence to explore.
                </p>
              </div>
              <div className="preview-conditions">
                {["Age requirement", "Study pathway", "Income requirement"].map(
                  (label) => (
                    <div key={label}>
                      <span>
                        <Check size={14} />
                      </span>
                      {label}
                      <small>Satisfied</small>
                    </div>
                  ),
                )}
              </div>
              <div className="preview-report-footer">
                <BookOpen size={15} />
                <span>Policy v1</span>
                <span className="ml-auto">
                  View the reasoning <ArrowRight size={14} />
                </span>
              </div>
            </div>
            <span className="floating-note note-bottom">
              <Fingerprint size={18} /> Synthetic inputs. No profile storage.
            </span>
          </div>
        </div>
      </section>
      <div className="principle-strip">
        <div className="container principles">
          <span>
            <FileText size={18} /> Source-grounded discovery
          </span>
          <span>
            <CheckCheck size={18} /> Deterministic decisions
          </span>
          <span>
            <CircleHelp size={18} /> Unknown stays unknown
          </span>
          <span>
            <LockKeyhole size={18} /> Your profile isn’t saved
          </span>
        </div>
      </div>
      <section className="section container" id="how-it-works">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Less guesswork. More understanding.</span>
            <h2>A little clarity goes a long way.</h2>
          </div>
          <p>
            From finding a scheme to understanding an assessment, the reasoning
            stays in view.
          </p>
        </div>
        <div className="steps-grid">
          {[
            {
              number: "01",
              icon: Search,
              title: "Find your starting point",
              text: "Explore scholarship records with their administering bodies and official source links.",
            },
            {
              number: "02",
              icon: FileText,
              title: "Check the known conditions",
              text: "Try a synthetic profile against the approved fictional policy. Leave anything unknown blank.",
            },
            {
              number: "03",
              icon: Sparkles,
              title: "Understand every result",
              text: "See satisfied, unmet, and unknown requirements, with the policy version and evidence attached.",
            },
          ].map(({ number, icon: Icon, title, text }) => (
            <article className="step-card" key={number}>
              <div>
                <span className="step-icon">
                  <Icon size={23} />
                </span>
                <span className="step-number">{number}</span>
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="section section-tinted">
        <div className="container">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Start exploring</span>
              <h2>Opportunities worth understanding.</h2>
            </div>
            <Link href="/schemes" className="text-link">
              View all schemes <ArrowRight size={17} />
            </Link>
          </div>
          <div className="scheme-grid">
            {featured.map((scheme) => (
              <SchemeCard key={scheme.id} scheme={scheme} />
            ))}
          </div>
          <p className="section-note">
            <CircleHelp size={16} /> Government records are discovery metadata.
            The eligibility check currently uses one clearly labeled fictional
            policy.
          </p>
        </div>
      </section>
      <section className="container section">
        <div className="closing-panel">
          <div>
            <span className="eyebrow">An assessment you can follow</span>
            <h2>
              Every answer deserves
              <br />
              an explanation.
            </h2>
            <p>
              Try the working example and see how missing information,
              exclusions, and policy conditions affect a result.
            </p>
          </div>
          <ActionLink
            href={demo ? `/eligibility?scheme=${demo.id}` : "/eligibility"}
          >
            Try a synthetic profile
          </ActionLink>
        </div>
      </section>
    </>
  );
}
