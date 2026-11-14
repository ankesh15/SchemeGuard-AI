import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, ArrowUpRight } from "lucide-react";
import "@fontsource-variable/inter";
import "./globals.css";
import { Header } from "@/components/header";
import { DiscoveryProvider } from "@/components/discovery-context";
import { ReportProvider } from "@/components/report-context";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: {
    default: "SchemeGuard AI — Clarity before you apply",
    template: "%s | SchemeGuard AI",
  },
  description:
    "Start with your interests to discover relevant government schemes and understand explainable assessment criteria.",
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
        <DiscoveryProvider>
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
                  <Link href="/find-schemes">Find My Schemes</Link>
                  <Link href="/schemes/all">Browse all schemes</Link>
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
                <span>
                  SchemeGuard AI is a project demonstration. Results are
                  estimates and do not determine government eligibility.
                </span>
              </div>
            </footer>
          </ReportProvider>
        </DiscoveryProvider>
      </body>
    </html>
  );
}
