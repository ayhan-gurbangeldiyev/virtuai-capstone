/**
 * Phase 27 — Confirmation modal for approve/reject.
 *
 * When user clicks Approve or Reject on a DecisionCard, we open this dialog
 * instead of firing the API immediately. The dialog spells out:
 *   - What was proposed
 *   - What happens if accept
 *   - What happens if reject
 *
 * Then the user commits with the action button at the bottom.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Check, X } from "lucide-react";

import RoleAvatar from "./RoleAvatar";
import { getPersona } from "./lib/personas";
import {
  humanizeDecisionType,
  humanizeChange,
} from "./lib/translators";

export default function DecisionApprovalDialog({
  decision,
  open,
  initialMode = "approve",  // 'approve' | 'reject'
  onClose,
  onConfirm,                 // (decision, mode) => Promise
}) {
  const { t } = useTranslation();
  const [mode, setMode] = useState(initialMode);
  const [submitting, setSubmitting] = useState(false);

  if (!decision) return null;
  const p = getPersona(decision.role_responsible);
  const what = humanizeDecisionType(decision.decision_type);
  const changes = humanizeChange(decision.old_value, decision.new_value);

  async function handleConfirm(chosenMode) {
    setSubmitting(true);
    setMode(chosenMode);
    try {
      await onConfirm?.(decision, chosenMode);
      onClose?.();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={!!open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{t("executive.approvalDialog.title", "Kararı onayla")}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Who proposed */}
          <div className="rounded-lg border border-border/60 bg-card/60 p-3">
            <p className="text-xs text-muted-foreground mb-2">
              {t("executive.approvalDialog.proposed", {
                name: p.name,
                title: t(`executive.roles.${decision.role_responsible}.title`, p.titleFallback),
              })}
            </p>
            <div className="flex items-center justify-between gap-2">
              <p className="text-base font-medium text-foreground">{what}</p>
              <RoleAvatar role={decision.role_responsible} size="sm" showTitle={false} />
            </div>
          </div>

          {/* If accept */}
          <section className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
            <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-emerald-300 mb-2">
              <Check className="h-4 w-4" />
              {t("executive.approvalDialog.ifAcceptHeader", "Kabul edersen ne olur")}
            </div>
            <ul className="space-y-1.5 text-[13px] text-foreground/90">
              {changes.length > 0 ? (
                changes.map((c) => (
                  <li key={c.key} className="flex items-start gap-2">
                    <span className="text-emerald-400 mt-0.5">•</span>
                    <span className="flex-1">
                      <span className="text-muted-foreground">{c.label}:</span>{" "}
                      <span className="text-rose-400 line-through">{c.oldDisplay}</span>
                      {" → "}
                      <span className="text-emerald-400 font-medium">{c.newDisplay}</span>
                    </span>
                  </li>
                ))
              ) : (
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">•</span>
                  <span>{what}</span>
                </li>
              )}
              <li className="flex items-start gap-2 text-muted-foreground italic">
                <span className="text-emerald-400 mt-0.5">•</span>
                <span>{t("executive.approvalDialog.ifAcceptFootnote", "Sonraki tüm üretimlerde bu ayar geçerli olur.")}</span>
              </li>
            </ul>
          </section>

          {/* If reject */}
          <section className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3">
            <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-rose-300 mb-2">
              <X className="h-4 w-4" />
              {t("executive.approvalDialog.ifRejectHeader", "Reddedersen ne olur")}
            </div>
            <p className="text-[13px] text-foreground/90 leading-relaxed">
              {t("executive.approvalDialog.ifRejectGeneric", "Mevcut ayarlar değişmez, durum aynen sürer.")}
            </p>
          </section>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitting}>
            {t("executive.approvalDialog.cancel", "İptal")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleConfirm("reject")}
            disabled={submitting}
          >
            <X className="h-3.5 w-3.5 mr-1" />
            {t("executive.decision.reject", "Reddet")}
          </Button>
          <Button size="sm" onClick={() => handleConfirm("approve")} disabled={submitting}>
            <Check className="h-3.5 w-3.5 mr-1" />
            {t("executive.decision.approve", "Kabul et")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
