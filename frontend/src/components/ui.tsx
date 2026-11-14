import Link from "next/link";
import {
  ArrowRight,
  FlaskConical,
  ShieldCheck,
  AlertCircle,
  LoaderCircle,
} from "lucide-react";
import type { ReactNode } from "react";

export function Badge({ demo = false }: { demo?: boolean }) {
  return (
    <span className={`badge ${demo ? "badge-demo" : "badge-verified"}`}>
      {demo ? <FlaskConical size={13} /> : <ShieldCheck size={13} />}
      {demo ? "Project example" : "Official source linked"}
    </span>
  );
}
export function ActionLink({
  href,
  children,
  secondary = false,
  arrow = true,
}: {
  href: string;
  children: ReactNode;
  secondary?: boolean;
  arrow?: boolean;
}) {
  return (
    <Link
      className={`button ${secondary ? "button-secondary" : "button-primary"}`}
      href={href}
    >
      {children}
      {arrow && <ArrowRight size={17} />}
    </Link>
  );
}
export function DemoNotice({ compact = false }: { compact?: boolean }) {
  return <ProjectDisclaimer compact={compact} />;
}
export function ProjectDisclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <p className={`small-note project-disclaimer${compact ? " compact" : ""}`}>
      SchemeGuard AI is a project demonstration. Results are estimates and do
      not determine government eligibility.
    </p>
  );
}
export function LoadingState({
  message = "Loading schemes…",
}: {
  message?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle size={24} className="animate-spin" />
      <span>{message}</span>
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="empty-state" role="alert">
      <AlertCircle size={28} />
      <h2>We couldn’t load this information</h2>
      <p>{message}</p>
      {retry && (
        <button className="button button-secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
