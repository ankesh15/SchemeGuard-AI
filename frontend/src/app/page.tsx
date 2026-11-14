import Link from "next/link";
import {
  ArrowRight,
  CheckCheck,
  CircleHelp,
  FileText,
  Fingerprint,
  HeartHandshake,
  LockKeyhole,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { ActionLink, ProjectDisclaimer } from "@/components/ui";

export default function Home() {
  return (
    <>
      <section className="hero profile-first-hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <span className="hero-kicker">
              <span className="status-dot" />A little about you. A world of
              possibilities.
            </span>
            <h1>
              Discover Government Schemes <em>Made for You</em>
            </h1>
            <p className="hero-description">
              Tell us a little about yourself, and SchemeGuard AI will help you
              discover government schemes that match your profile and interests.
            </p>
            <div className="hero-actions">
              <ActionLink href="/find-schemes">Find My Schemes</ActionLink>
              <ActionLink href="#how-it-works" secondary arrow={false}>
                How It Works
              </ActionLink>
            </div>
            <div className="hero-footnote">
              <LockKeyhole size={16} />
              <span>No sign-up needed</span>
              <span className="dot-divider">·</span>
              <span>Every answer is optional</span>
            </div>
            <ProjectDisclaimer />
          </div>
          <div
            className="hero-visual discovery-visual"
            aria-label="Illustration of profile-based discovery"
          >
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <span className="floating-note">
              <Fingerprint size={18} />
              Your interests lead the way
            </span>
            <div className="discovery-preview">
              <span className="preview-icon">
                <HeartHandshake size={26} />
              </span>
              <span className="eyebrow">Your next opportunity</span>
              <h2>
                Start with you.
                <br />
                <em>Explore with clarity.</em>
              </h2>
              <p>
                One profile. Relevant possibilities.
                <br />
                Clear reasons for every match.
              </p>
              <div className="preview-interest-list">
                {["Education", "Growing a business", "Building new skills"].map(
                  (label) => (
                    <span key={label}>
                      <CheckCheck size={15} />
                      {label}
                    </span>
                  ),
                )}
              </div>
              <div className="discovery-preview-footer">
                <Sparkles size={17} />
                Personalized discovery
                <ArrowRight size={17} />
              </div>
            </div>
            <span className="floating-note note-bottom">
              <ShieldCheck size={18} />
              Official sources. Informed next steps.
            </span>
          </div>
        </div>
      </section>
      <div className="principle-strip">
        <div className="container principles">
          <span>
            <SlidersHorizontal size={18} />
            Built around your needs
          </span>
          <span>
            <FileText size={18} />
            Official source references
          </span>
          <span>
            <CircleHelp size={18} />
            Unknown stays unknown
          </span>
          <span>
            <LockKeyhole size={18} />
            Private by choice
          </span>
        </div>
      </div>
      <section className="section container" id="how-it-works">
        <div className="section-heading">
          <div>
            <span className="eyebrow">
              From your interests to your next step
            </span>
            <h2>A clearer way to discover.</h2>
          </div>
          <p>
            You do not need to search hundreds of schemes. Start with the
            details you know.
          </p>
        </div>
        <div className="steps-grid discovery-steps">
          {[
            {
              icon: Fingerprint,
              title: "Tell Us About Yourself",
              text: "Share your interests and a few optional details. No names or identity documents needed.",
            },
            {
              icon: Search,
              title: "Discover Relevant Schemes",
              text: "Explore recommendations with clear reasons based on your profile and the scheme catalog.",
            },
            {
              icon: FileText,
              title: "Explore and Check Requirements",
              text: "Read official sources and continue to an available reviewed or illustrative assessment.",
            },
            {
              icon: CheckCheck,
              title: "Understand Your Assessment",
              text: "See satisfied, unmet and unknown conditions. Results inform your next step, not government approval.",
            },
          ].map(({ icon: Icon, title, text }, index) => (
            <article className="step-card" key={title}>
              <div>
                <span className="step-icon">
                  <Icon size={23} />
                </span>
                <span className="step-number">0{index + 1}</span>
              </div>
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="container section">
        <div className="closing-panel">
          <div>
            <span className="eyebrow">Your next step starts here</span>
            <h2>
              Good opportunities
              <br />
              begin with your needs.
            </h2>
            <p>
              Find the schemes worth exploring, then understand their
              requirements at your own pace.
            </p>
            <Link className="text-link" href="/schemes/all">
              Prefer to browse the full catalog? →
            </Link>
          </div>
          <ActionLink href="/find-schemes">Find My Schemes</ActionLink>
        </div>
      </section>
    </>
  );
}
