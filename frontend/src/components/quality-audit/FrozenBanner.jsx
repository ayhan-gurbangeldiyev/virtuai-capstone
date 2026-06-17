/**
 * Phase 43.E.5 — FrozenBanner
 * Sticky red strip shown when auto_publish_enabled was just flipped to false
 * by an audit fail cascade. CTA leads to Settings.
 */
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function FrozenBanner({
  failCount,
  onOpenSettings,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleOpenSettings = () => {
    if (onOpenSettings) {
      onOpenSettings();
      return;
    }
    // Default: navigate to Auto-Drafts config sheet (Phase 18.1 HypeConfigSheet)
    // Berkay flips auto_publish_enabled there. If a dedicated Settings page
    // exists later, swap this path.
    navigate("/dashboard/auto-drafts");
  };

  return (
    <div
      role="alert"
      className="rounded-xl border border-rose-500/40 bg-rose-500/5 px-4 py-3
                 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" aria-hidden />
        <div>
          <p className="text-sm font-semibold text-rose-600 dark:text-rose-400">
            {t("qualityAudit.frozenBanner.title")}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {t("qualityAudit.frozenBanner.body", { fail: failCount ?? "?" })}
          </p>
        </div>
      </div>
      <Button
        size="sm"
        variant="outline"
        className="border-rose-500/40 text-rose-600 hover:bg-rose-500/10
                   self-start sm:self-auto shrink-0"
        onClick={handleOpenSettings}
      >
        {t("qualityAudit.frozenBanner.cta")}
        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
