"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Status = "checking" | "waking" | "ready" | "down";

const SHOW_AFTER_MS = 3000; // don't flash the banner when the API answers quickly
const POLL_MS = 5000;
const GIVE_UP_MS = 120000;

/**
 * The backend runs on a free hosting tier that sleeps when idle, so the first
 * request after a quiet period can take up to a minute. This banner tells the
 * visitor that, polls /health until the API answers, then disappears.
 * It renders nothing at all when the API is already awake.
 */
export default function ApiWakeBanner() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();

    const showTimer = setTimeout(() => {
      if (!cancelled) setStatus((s) => (s === "checking" ? "waking" : s));
    }, SHOW_AFTER_MS);

    (async () => {
      while (!cancelled) {
        const ok = await api.health();
        if (cancelled) return;
        if (ok) {
          setStatus("ready");
          return;
        }
        if (Date.now() - started > GIVE_UP_MS) {
          setStatus("down");
          return;
        }
        setStatus("waking");
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(showTimer);
    };
  }, []);

  if (status === "checking" || status === "ready") return null;

  return (
    <div className="max-w-[1280px] mx-auto px-6 md:px-10 pt-4">
      <div className="card p-4 text-[13px]" role="status" aria-live="polite">
        {status === "waking" ? (
          <>
            <strong>Waking up the server…</strong>{" "}
            <span className="text-[color:var(--ink-secondary)]">
              The backend runs on a free tier and sleeps when idle, so the first load can take up to a minute.
              The page will fill in automatically.
            </span>
          </>
        ) : (
          <>
            <strong>The strategy API isn&apos;t responding right now.</strong>{" "}
            <span className="text-[color:var(--ink-secondary)]">Please refresh in a minute.</span>
          </>
        )}
      </div>
    </div>
  );
}
