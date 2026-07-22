import Link from "next/link";

const LINKS = [
  { href: "/", label: "Season" },
  { href: "/race-hub", label: "Race Hub" },
  { href: "/strategy", label: "Strategy" },
  { href: "/compare", label: "Compare" },
  { href: "/results", label: "Results" },
];

export default function Nav({ active }: { active: string }) {
  return (
    <header className="topnav hairline-bottom">
      <div className="max-w-[1280px] mx-auto px-6 md:px-10 h-16 flex items-center justify-between">
        <div className="flex items-center gap-10">
          <Link href="/" className="display text-[20px] tracking-[0.04em]">
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
        <Link href="/strategy" className="btn btn--accent">
          Open Strategy Engine
        </Link>
      </div>
    </header>
  );
}
