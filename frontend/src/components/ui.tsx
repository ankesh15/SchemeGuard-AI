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
      {demo ? "Fictional demo" : "Official source linked"}
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
  return (
    <div className="notice notice-demo">
      <FlaskConical size={18} className="shrink-0" />
      <p>
        <strong>A fictional scholarship. A real explanation.</strong>
        {!compact &&
          " This learning example uses invented policy values. It is not a government scheme and offers no award. Use synthetic information only."}
      </p>
    </div>
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
