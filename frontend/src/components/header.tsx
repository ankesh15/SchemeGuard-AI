"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ShieldCheck, ArrowUpRight, Menu, X } from "lucide-react";

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const links = [
    { href: "/schemes", label: "Explore schemes" },
    { href: "/#how-it-works", label: "How it works" },
    { href: "/dashboard", label: "My workspace" },
    { href: "/admin", label: "Admin" },
  ];
  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link
          href="/"
          className="brand"
          aria-label="SchemeGuard AI home"
          onClick={() => setOpen(false)}
        >
          <span className="brand-mark">
            <ShieldCheck size={23} strokeWidth={1.8} />
          </span>
          <span>
            SchemeGuard<span className="brand-ai">AI</span>
          </span>
        </Link>
        <nav className="desktop-nav" aria-label="Main navigation">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
          <Link
            className="button button-primary button-small"
            href="/eligibility"
          >
            Check eligibility <ArrowUpRight size={16} />
          </Link>
        </nav>
        <button
          className="mobile-toggle"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
      {open && (
        <nav
          id="mobile-nav"
          className="mobile-nav"
          aria-label="Mobile navigation"
        >
          {[...links, { href: "/eligibility", label: "Check eligibility" }].map(
            (link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
              >
                {link.label}
              </Link>
            ),
          )}
        </nav>
      )}
    </header>
  );
}
