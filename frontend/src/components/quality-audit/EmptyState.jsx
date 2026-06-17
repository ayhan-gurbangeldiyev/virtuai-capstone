/**
 * Phase 43.E.5 — EmptyState
 *
 * Two variants:
 *   - "noAudit"          → nothing left to review this cycle (success-y)
 *   - "autoPublishOff"   → manual approval mode, no auto-published posts
 */
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Pause, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function EmptyState({
  variant = "noAudit",
  lastCycleStats = null, // { pass, fail }
  onTriggerAudit = null,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (variant === "autoPublishOff") {
    return (
      <div className="rounded-2xl border border-border bg-card p-8 text-center space-y-4 max-w-2xl mx-auto">
        <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center">
          <Pause className="h-6 w-6 text-muted-foreground" />
        </div>
        <div>
          <h3 className="text-lg font-semibold">
            {t("qualityAudit.empty.autoPublishOff.title")}
          </h3>
          <p className="mt-2 text-sm text-muted-foreground">
            {t("qualityAudit.empty.autoPublishOff.body")}
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigate("/dashboard/auto-drafts")}
        >
          {t("qualityAudit.empty.autoPublishOff.cta")}
          <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
        </Button>
      </div>
    );
  }

  // noAudit
  return (
    <div className="rounded-2xl border border-border bg-card p-8 text-center space-y-4 max-w-2xl mx-auto">
      <div className="mx-auto w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center">
        <CheckCircle2 className="h-6 w-6 text-emerald-500" />
      </div>
      <div>
        <h3 className="text-lg font-semibold">
          {t("qualityAudit.empty.noAudit.title")}
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("qualityAudit.empty.noAudit.body")}
        </p>
      </div>
      {lastCycleStats && (
        <p className="text-xs font-mono text-muted-foreground">
          {t("qualityAudit.empty.lastCycleSummary", {
            pass: lastCycleStats.pass ?? 0,
            fail: lastCycleStats.fail ?? 0,
          })}
        </p>
      )}
      {onTriggerAudit && (
        <Button size="sm" variant="ghost" onClick={onTriggerAudit}>
          {t("qualityAudit.trigger.cta")}
        </Button>
      )}
    </div>
  );
}
