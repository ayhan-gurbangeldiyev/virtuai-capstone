/**
 * StatsRow — 4 glass-morphism counter cards.
 *
 * Sources:
 *  - drafts prop: pending count from current list
 *  - listRecentRuns: approved/rejected this week + weekly cost
 */
import { useEffect, useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Inbox, Check } from "lucide-react";
import { listRecentRuns, getUserFeedbackStats } from "@/services/hypeService";
import { cn } from "@/lib/utils";

export default function StatsRow({ accountId, drafts = [], config = null }) {
  const { t } = useTranslation();
  const [runs, setRuns] = useState([]);
  const [feedback, setFeedback] = useState({ approved: 0, rejected: 0, edited: 0 });

  // Re-fetch when drafts list changes (approve/reject removes an item → stats should update).
  // Also: poll every 30s as a safety net for collaborator actions arriving from other sessions.
  //
  // Phase 28 Fix 2 pattern — omit account_id so backend returns WORKSPACE-WIDE counts
  // across ALL platform accounts (twitter+linkedin+devto+instagram). Otherwise a
  // reject on LinkedIn wouldn't count when Twitter is the active account.
  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    const fetchAll = () => {
      Promise.all([
        listRecentRuns({ limit: 200 }).catch(() => ({ items: [] })),
        getUserFeedbackStats({ days: 7 }).catch(() => ({ counts: { approved: 0, rejected: 0, edited: 0 } })),
      ]).then(([runsRes, feedbackRes]) => {
        if (cancelled) return;
        setRuns(runsRes.items || []);
        setFeedback(feedbackRes.counts || { approved: 0, rejected: 0, edited: 0 });
      });
    };
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [accountId, drafts.length]);

  const stats = useMemo(() => {
    // Phase 28.C — count BOTH 'pending' (legacy) and 'pending_review' (new gated state)
    const pending = drafts.filter((d) => d.status === "pending" || d.status === "pending_review").length;
    const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
    const weekRuns = runs.filter((r) => new Date(r.started_at).getTime() > weekAgo);
    const cost = weekRuns.reduce((s, r) => s + (Number(r.total_cost_usd) || 0), 0);
    // Phase 17.4 — Approved/Rejected reflect USER decisions only, not system Compliance auto-rejects
    // Phase 28.M — backend now counts workspace-wide (owner + collaborators), not just self
    return {
      pending,
      approved: feedback.approved || 0,
      rejected: feedback.rejected || 0,
      cost,
    };
  }, [drafts, runs, feedback]);

  // Phase 41.A — 4 → 2 cards: focus on what matters daily
  // (Rejected count + Weekly cost moved to detay/accordion in V2)
  const cards = [
    {
      icon: Inbox,
      label: t("autoDrafts.stats.pending"),
      value: stats.pending,
      tone: "purple",
      mono: false,
    },
    {
      icon: Check,
      label: t("autoDrafts.stats.approvedWeek"),
      value: stats.approved,
      tone: "emerald",
      mono: false,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3">
      {cards.map((c, i) => (
        <StatCard key={c.label} {...c} delay={i * 0.05} />
      ))}
    </div>
  );
}

const TONE_MAP = {
  purple: "from-purple-500/10 to-transparent border-purple-500/20 text-purple-600 dark:text-purple-400",
  emerald: "from-emerald-500/10 to-transparent border-emerald-500/20 text-emerald-600 dark:text-emerald-400",
  rose: "from-rose-500/10 to-transparent border-rose-500/20 text-rose-600 dark:text-rose-400",
  amber: "from-amber-500/10 to-transparent border-amber-500/20 text-amber-600 dark:text-amber-400",
};

function StatCard({ icon: Icon, label, value, tone, mono, delay = 0 }) {
  const [display, setDisplay] = useState(typeof value === "number" ? 0 : value);

  useEffect(() => {
    if (typeof value !== "number") {
      setDisplay(value);
      return;
    }
    const duration = 600;
    const start = Date.now();
    const from = 0;
    const raf = () => {
      const elapsed = Date.now() - start;
      const ratio = Math.min(elapsed / duration, 1);
      setDisplay(Math.round(from + (value - from) * ratio));
      if (ratio < 1) requestAnimationFrame(raf);
    };
    requestAnimationFrame(raf);
  }, [value]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className={cn(
        "rounded-2xl border bg-gradient-to-br backdrop-blur-sm p-4",
        TONE_MAP[tone]
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
        <Icon className="h-3.5 w-3.5 opacity-60" />
      </div>
      <p className={cn(
        "font-outfit font-bold tracking-tight text-2xl",
        mono && "font-mono text-xl"
      )}>
        {display}
      </p>
    </motion.div>
  );
}
