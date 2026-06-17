/**
 * Phase 43.E.5 — AuditProgressBar
 * Linear progress + freeze warning strip.
 * Colors: 0-1 fail = emerald, 2 fail = amber, 3+ fail = rose.
 */
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export default function AuditProgressBar({
  rated = 0,
  pass = 0,
  fail = 0,
  total = 10,
  failThreshold = 3,
  className,
}) {
  const { t } = useTranslation();
  const safeTotal = Math.max(1, total);
  const pct = Math.min(100, Math.round((rated / safeTotal) * 100));
  const passPct = Math.min(100, Math.round((pass / safeTotal) * 100));
  const failPct = Math.min(100, Math.round((fail / safeTotal) * 100));

  const tone =
    fail >= failThreshold
      ? "danger"
      : fail >= failThreshold - 1
      ? "amber"
      : "emerald";

  const triggered = fail >= failThreshold;
  const remaining = Math.max(0, failThreshold - fail);

  const warnText = triggered
    ? t("qualityAudit.progress.failTriggered")
    : fail >= failThreshold - 1
    ? t("qualityAudit.progress.failAmber", { fail })
    : fail > 0
    ? t("qualityAudit.progress.failDanger", { fail })
    : t("qualityAudit.progress.failOk");

  return (
    <div className={cn("w-full space-y-2", className)}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-mono">
          {t("qualityAudit.progress.label", { rated, total: safeTotal })}
        </span>
        <span
          className={cn(
            "font-medium",
            tone === "danger" && "text-rose-500",
            tone === "amber" && "text-amber-500",
            tone === "emerald" && "text-emerald-500"
          )}
          aria-live="polite"
        >
          {warnText}
        </span>
      </div>

      {/* Stacked bar: pass (emerald) + fail (rose) over neutral track */}
      <div className="relative h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 bg-emerald-500/70 transition-[width] duration-300"
          style={{ width: `${passPct}%` }}
        />
        <div
          className="absolute inset-y-0 bg-rose-500/80 transition-[width] duration-300"
          style={{ left: `${passPct}%`, width: `${failPct}%` }}
        />
      </div>

      {!triggered && fail > 0 && (
        <p className="text-[11px] text-muted-foreground">
          {remaining === 1
            ? "1 fail daha freeze tetikler"
            : `${remaining} fail daha freeze tetikler`}
        </p>
      )}
    </div>
  );
}
