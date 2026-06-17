/**
 * ControlChrome — thin top bar shared by /control routes.
 *
 * Connects the islands so the operator can move between Bugün (Home),
 * Karar İzi (decision-trail), Onay Bekleyenler (approval queue) and
 * Yayın Yöneticisi (Social Manager) without bouncing back to /dashboard.
 *
 * Source of truth: projects/post-capstone/product-structure.md — Layer 1
 * (Home) lives at /control and was previously orphaned: no link from
 * /dashboard reached it, and Home itself had no exit to the approval
 * console where pending drafts wait. This component is the smallest
 * surface that fixes that without adding chrome (no logo, no sidebar,
 * no banner — just a single horizontal nav row + slot).
 *
 * Hard rules (parity with HomePage):
 *   - No internal system names. The links read as operator verbs.
 *   - No KPI tiles. The pending badge is a single integer next to its
 *     label, not a styled chip.
 *   - The bar is the only chrome; the page renders into the slot.
 */
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAccount } from "@/contexts/AccountContext";
import { listAutoDrafts } from "@/services/hypeService";

const ITEMS = [
  { to: "/control", label: "Bugün", match: (p) => p === "/control" },
  { to: "/control/karar-izi", label: "Seçimler", match: (p) => p.startsWith("/control/karar-izi") },
  { to: "/control/health", label: "Sağlık", match: (p) => p.startsWith("/control/health") },
  { to: "/dashboard/auto-drafts", label: "Onay Bekleyenler", match: (p) => p.startsWith("/dashboard/auto-drafts"), pendingBadge: true },
  { to: "/dashboard/social", label: "Yayın Yöneticisi", match: (p) => p.startsWith("/dashboard/social") },
];

export default function ControlChrome({ children }) {
  const { effectiveAccountId } = useAccount();
  const { pathname } = useLocation();
  const [pendingCount, setPendingCount] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!effectiveAccountId) return;
      try {
        const drafts = await listAutoDrafts({
          accountId: effectiveAccountId,
          status: "pending",
          limit: 50,
        });
        if (cancelled) return;
        const list = Array.isArray(drafts) ? drafts : drafts?.drafts || [];
        setPendingCount(list.length);
      } catch {
        if (!cancelled) setPendingCount(null);
      }
    }
    load();
    const id = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [effectiveAccountId]);

  return (
    <div className="min-h-screen bg-neutral-50">
      <nav className="sticky top-0 z-20 border-b border-neutral-200 bg-neutral-50/95 backdrop-blur">
        <div className="mx-auto w-full max-w-3xl px-6 md:px-12">
          <ul className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3">
            {ITEMS.map((it) => {
              const active = it.match(pathname);
              const badge = it.pendingBadge && pendingCount != null && pendingCount > 0;
              return (
                <li key={it.to}>
                  <Link
                    to={it.to}
                    className={
                      "text-[12px] tracking-[0.04em] " +
                      (active
                        ? "text-neutral-900 font-semibold underline underline-offset-[6px] decoration-2"
                        : "text-neutral-500 hover:text-neutral-900")
                    }
                  >
                    {it.label}
                    {badge && (
                      <span className="ml-1.5 text-neutral-900 font-semibold">
                        {pendingCount}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
      {children}
    </div>
  );
}

/**
 * HomePendingCTA — surfaces "N taslak onay bekliyor →" under the
 * editorial decision, linking into the approval queue. Hidden when
 * there is nothing pending so quiet days stay quiet.
 */
export function HomePendingCTA() {
  const { effectiveAccountId } = useAccount();
  const [count, setCount] = useState(null);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!effectiveAccountId) return;
      try {
        const drafts = await listAutoDrafts({
          accountId: effectiveAccountId,
          status: "pending",
          limit: 50,
        });
        if (cancelled) return;
        const list = Array.isArray(drafts) ? drafts : drafts?.drafts || [];
        setCount(list.length);
      } catch {
        if (!cancelled) setCount(0);
      }
    }
    load();
  }, [effectiveAccountId]);

  if (!count) return null;

  return (
    <section className="mt-8">
      <Link
        to="/dashboard/auto-drafts"
        className="inline-flex items-center gap-2 text-sm text-neutral-900 underline underline-offset-4 decoration-2 hover:text-neutral-700"
      >
        {count} taslak onay bekliyor
        <span aria-hidden>→</span>
      </Link>
    </section>
  );
}
