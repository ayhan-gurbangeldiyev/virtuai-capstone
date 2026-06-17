/**
 * Phase 43.E.5 — AuditHistoryRow
 * Accordion-style row that shows a single past audit cycle.
 * Header: "Mayıs 2026 — 8 pass / 2 fail"
 * Body (when expanded): the 10 rated audits as compact list items.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatMonthLabel } from "./lib/time.js";

export default function AuditHistoryRow({
  monthKey,        // ISO date string like "2026-05-01"
  audits = [],     // array of audit items already rated
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const pass = audits.filter((a) => a.rating === "pass").length;
  const fail = audits.filter((a) => a.rating === "fail").length;
  const monthLabel = formatMonthLabel(monthKey);

  return (
    <div className="rounded-xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-sm font-semibold">{monthLabel}</span>
          <span className="text-xs text-muted-foreground font-mono">
            {t("qualityAudit.history.stats", { pass, fail })}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {fail > 0 && (
            <Badge
              variant="outline"
              className="border-rose-500/40 text-rose-600"
            >
              {fail} fail
            </Badge>
          )}
          {pass > 0 && (
            <Badge
              variant="outline"
              className="border-emerald-500/40 text-emerald-600"
            >
              {pass} pass
            </Badge>
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3 space-y-2">
          {audits.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              {t("qualityAudit.history.empty")}
            </p>
          ) : (
            audits.map((a) => {
              const snap = a.draft_snapshot;
              const isPass = a.rating === "pass";
              return (
                <div
                  key={a.id}
                  className={cn(
                    "flex items-start gap-3 rounded-md p-2 text-xs",
                    isPass
                      ? "bg-emerald-500/5 border border-emerald-500/20"
                      : "bg-rose-500/5 border border-rose-500/20"
                  )}
                >
                  {isPass ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="h-4 w-4 text-rose-500 shrink-0 mt-0.5" />
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] text-muted-foreground">
                      <span className="font-medium uppercase tracking-wide">
                        {snap?.platform || "—"}
                      </span>
                      {snap?.trend_topic && (
                        <span className="ml-2 truncate">{snap.trend_topic}</span>
                      )}
                    </div>
                    {snap?.content && (
                      <p className="mt-1 line-clamp-2 text-foreground/80">
                        {snap.content}
                      </p>
                    )}
                    {!isPass && a.notes && (
                      <p className="mt-1 text-rose-600 dark:text-rose-400">
                        ↳ {a.notes}
                      </p>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
