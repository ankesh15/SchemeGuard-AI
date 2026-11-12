import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, ArrowUpRight } from "lucide-react";
import "@fontsource-variable/inter";
import "./globals.css";
import { Header } from "@/components/header";
import { ReportProvider } from "@/components/report-context";

export const metadata: Metadata = {
  title: {
    default: "SchemeGuard AI — Clarity before you apply",
    template: "%s | SchemeGuard AI",
  },
  description:
    "Explore government scheme sources and understand a deterministic eligibility assessment with a clearly labeled fictional development example.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <ReportProvider>
          <Header />
          <main id="main-content">{children}</main>
          <footer className="site-footer">
            <div className="container footer-grid">
              <div>
                <Link className="brand" href="/">
                  <ShieldCheck size={24} />
                  <span>
                    SchemeGuard<span className="brand-ai">AI</span>
                  </span>
                </Link>
                <p>
                  Understand the requirements.
                  <br />
                  Make your next step an informed one.
                </p>
              </div>
              <div className="footer-links">
                <Link href="/schemes">Explore schemes</Link>
                <Link href="/eligibility">Try the eligibility demo</Link>
                <a
                  href="https://scholarships.gov.in/Students"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  National Scholarship Portal <ArrowUpRight size={14} />
                </a>
              </div>
            </div>
            <div className="container footer-bottom">
              <span>© 2026 SchemeGuard AI · Academic project</span>
              <span>Independent project. Not a government service.</span>
            </div>
          </footer>
        </ReportProvider>
      </body>
    </html>
  );
}
