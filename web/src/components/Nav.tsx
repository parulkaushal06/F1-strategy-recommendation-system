"use client";

import { useState } from "react";
import Link from "next/link";

const LINKS = [
  { href: "/", label: "Season" },
  { href: "/race-hub", label: "Race Hub" },
  { href: "/strategy", label: "Strategy" },
  { href: "/compare", label: "Compare" },
  { href: "/results", label: "Results" },
];

export default function Nav({ active }: { active: string }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="topnav hairline-bottom">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 h-16 flex items-center justify-between">
        <div className="flex items-center gap-10">
          <Link href="/" className="display text-[20px] tracking-[0.04em]" onClick={() => setOpen(false)}>
            RACECRAFT
          </Link>
          <nav className="hidden md:flex items-center gap-7 eyebrow">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={
                  link.href === active
                    ? "text-[color:var(--ink-primary)]"
                    : "hover:text-[color:var(--ink-primary)]"
                }
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/strategy" className="hidden sm:inline-flex btn btn--accent">
            Open Strategy Engine
          </Link>

          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="md:hidden inline-flex items-center justify-center w-10 h-10 rounded-[var(--radius-sm)] border border-[color:var(--hairline-strong)] bg-[color:var(--surface-2)]"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              {open ? (
                <path d="M3 3l12 12M15 3L3 15" />
              ) : (
                <path d="M2 4.5h14M2 9h14M2 13.5h14" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <nav className="md:hidden hairline-top">
          <div className="max-w-[1280px] mx-auto px-6 py-3 flex flex-col gap-1 eyebrow">
            {LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={
                  "py-2.5 " +
                  (link.href === active
                    ? "text-[color:var(--ink-primary)]"
                    : "hover:text-[color:var(--ink-primary)]")
                }
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/strategy"
              onClick={() => setOpen(false)}
              className="btn btn--accent sm:hidden mt-2 justify-center"
            >
              Open Strategy Engine
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}