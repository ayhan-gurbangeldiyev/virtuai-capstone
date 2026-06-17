/**
 * Phase 27 — DecisionCard: hero-style, 5-block layout.
 *
 *   ┃ [Persona large avatar + name + title]
 *   ┃ NE İSTİYOR             {humanizeDecisionType(decision_type)}
 *   ┃ NEDEN BU KARARA VARDI  {decision_text}
 *   ┃ DEĞİŞECEK OLAN         {humanizeChange(old, new)}
 *   ┃ ONAY GEREKLİ ÇÜNKÜ     {humanizeBreachReason(threshold_breach)}
 *   ┃ [Approve | Reject]  (or Revert / status chip)
 *
 * Left border accent-color matches persona color.
 */
import { useTranslation } from "react-i18next";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X, Undo2 } from "lucide-react";

import RoleAvatar from "./RoleAvatar";
import { getPersona } from "./lib/personas";
import {
  humanizeDecisionType,
  humanizeStatus,
  humanizeChange,
  humanizeBreachReason,
  relativeTime,
} from "./lib/translators";

function ChangeList({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <dl className="space-y-1.5">
      {items.map((c) => (
        <div key={c.key} className="flex items-start gap-2 text-[13px]">
          <dt className="min-w-[140px] sm:min-w-[180px] text-muted-foreground">{c.label}</dt>
          <dd className="flex-1 leading-snug">
            <span className="text-rose-400 line-through mr-2">{c.oldDisplay}</span>
            <span className="text-muted-foreground/60">→</span>
            <span className="ml-2 text-emerald-400 font-medium">{c.newDisplay}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function StatusChip({ status }) {
  const s = humanizeStatus(status);
  const palette = {
    amber: "bg-amber-500/10 border-amber-500/30 text-amber-300",
    emerald: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
    blue: "bg-blue-500/10 border-blue-500/30 text-blue-300",
    rose: "bg-rose-500/10 border-rose-500/30 text-rose-300",
    muted: "bg-muted/30 border-border text-muted-foreground",
  }[s.color || "muted"];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${palette}`}>
      <span aria-hidden>{s.icon}</span>
      <span>{s.label}</span>
    </span>
  );
}

export default function DecisionCard({ decision, onApprove, onReject, onRevert }) {
  const { t } = useTranslation();
  const p = getPersona(decision.role_responsible);
  const isPending = decision.status === "awaiting_approval";
  const isAutoExecuted = decision.status === "auto_executed" || decision.status === "executed";
  const isFinalized = ["rejected", "reverted", "expired", "failed"].includes(decision.status);

  const what = humanizeDecisionType(decision.decision_type);
  const why = decision.decision_text || decision.rationale_memo || "";
  const changes = humanizeChange(decision.old_value, decision.new_value);
  const breachReason = humanizeBreachReason(decision.threshold_breach);

  return (
    <Card
      className={`relative overflow-hidden border-l-4 ${p.accent.left} border-r border-y border-border/60 transition-all hover:shadow-md`}
    >
      <CardContent className="space-y-4 p-5">
        {/* Header: persona + status + timestamp */}
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <RoleAvatar role={decision.role_responsible} size="lg" />
          <div className="flex flex-col items-end gap-1 text-right">
            <StatusChip status={decision.status} />
            <span className="text-[11px] text-muted-foreground">
              {relativeTime(decision.created_at)}
            </span>
          </div>
        </div>

        {/* NE İSTİYOR */}
        <section>
          <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-semibold mb-1">
            {t("executive.decision.whatWants", "Ne istiyor")}
          </div>
          <p className="text-base font-medium text-foreground leading-snug">{what}</p>
        </section>

        {/* NEDEN BU KARARA VARDI */}
        {why && (
          <section>
            <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-semibold mb-1">
              {t("executive.decision.whyDecided", "Neden bu karara vardı")}
            </div>
            <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">{why}</p>
          </section>
        )}

        {/* DEĞİŞECEK OLAN */}
        {changes.length > 0 ? (
          <section>
            <div className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground font-semibold mb-2">
              {t("executive.decision.whatChanges", "Değişecek olan")}
            </div>
            <ChangeList items={changes} />
          </section>
        ) : (
          <p className="text-[12px] italic text-muted-foreground">
            {t("executive.decision.nochange", "Bu karar bir ayarı değiştirmiyor — yalnızca gözlem paylaşıyor.")}
          </p>
        )}

        {/* ONAY GEREKLİ ÇÜNKÜ */}
        {isPending && breachReason && (
          <section className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
            <div className="text-[10px] uppercase tracking-[0.12em] text-amber-300 font-semibold mb-1">
              {t("executive.decision.needsApproval", "Onay gerekli, çünkü")}
            </div>
            <p className="text-[13px] text-foreground/90 leading-snug">{breachReason}</p>
          </section>
        )}

        {/* Action bar */}
        <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/40">
          {isPending && (
            <>
              <Button variant="ghost" size="sm" onClick={() => onReject?.(decision)}>
                <X className="h-3.5 w-3.5 mr-1" />
                {t("executive.decision.reject", "Reddet")}
              </Button>
              <Button size="sm" onClick={() => onApprove?.(decision)}>
                <Check className="h-3.5 w-3.5 mr-1" />
                {t("executive.decision.approve", "Kabul et")}
              </Button>
            </>
          )}
          {isAutoExecuted && (
            <Button variant="ghost" size="sm" onClick={() => onRevert?.(decision)}>
              <Undo2 className="h-3.5 w-3.5 mr-1" />
              {t("executive.decision.revert", "Geri al")}
            </Button>
          )}
          {isFinalized && (
            <Badge variant="outline" className="text-[11px]">
              {humanizeStatus(decision.status).label}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
