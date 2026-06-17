/**
 * Phase 27 — Decisions queue (3 sections, hero-style cards).
 *
 *   1. Onayını bekleyen kararlar      (status='awaiting_approval')
 *   2. Otomatik yapılanlar (24h)       (status='auto_executed' last 24h)
 *   3. Geçmiş kararlar (7d)            (rejected / reverted / expired / failed)
 *
 * Approve/Reject opens DecisionApprovalDialog. Revert acts inline (no dialog,
 * since it's just an undo).
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Inbox } from "lucide-react";

import DecisionCard from "./DecisionCard";
import DecisionApprovalDialog from "./DecisionApprovalDialog";
import {
  listDecisions,
  approveExecDecision,
  rejectExecDecision,
  revertExecDecision,
} from "@/services/execService";

const SECTION_PROPS = {
  hero: "text-base font-semibold tracking-tight text-foreground",
  small: "text-xs font-medium uppercase tracking-wider text-muted-foreground",
};

function Section({ title, count, hero = false, emptyText, items, onApprove, onReject, onRevert }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <h3 className={hero ? SECTION_PROPS.hero : SECTION_PROPS.small}>{title}</h3>
        {count > 0 && (
          <span className="rounded-full bg-muted/40 px-2 py-0.5 text-[11px] text-foreground/80">{count}</span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/60 bg-card/30 px-4 py-6 text-center">
          <Inbox className="h-5 w-5 mx-auto text-muted-foreground/60 mb-2" />
          <p className="text-xs text-muted-foreground italic">{emptyText}</p>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence initial={false}>
            {items.map((d) => (
              <motion.div
                key={d.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ duration: 0.2 }}
              >
                <DecisionCard
                  decision={d}
                  onApprove={onApprove}
                  onReject={onReject}
                  onRevert={onRevert}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}

export default function DecisionsQueue({ accountId }) {
  const { t } = useTranslation();
  const [pending, setPending] = useState([]);
  const [auto, setAuto] = useState([]);
  const [past, setPast] = useState([]);
  const [dialogDecision, setDialogDecision] = useState(null);
  const [dialogMode, setDialogMode] = useState("approve");

  const refresh = useCallback(async () => {
    if (!accountId) return;
    try {
      const [p, a, all] = await Promise.all([
        listDecisions({ accountId, status: "awaiting_approval", days: 14, limit: 50 }),
        listDecisions({ accountId, status: "auto_executed", days: 1, limit: 50 }),
        listDecisions({ accountId, days: 7, limit: 100 }),
      ]);
      setPending(p.items || []);
      setAuto(a.items || []);
      setPast(
        (all.items || []).filter((x) =>
          ["rejected", "reverted", "expired", "failed", "executed"].includes(x.status),
        ),
      );
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Yüklenemedi");
    }
  }, [accountId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  function openApprove(decision) {
    setDialogMode("approve");
    setDialogDecision(decision);
  }
  function openReject(decision) {
    setDialogMode("reject");
    setDialogDecision(decision);
  }

  async function handleConfirm(decision, mode) {
    try {
      if (mode === "approve") {
        await approveExecDecision(decision.id);
        toast.success(t("executive.approvalDialog.toastApproved", "Onaylandı — ekip ~10 saniye içinde uyguluyor"));
      } else {
        await rejectExecDecision(decision.id);
        toast.success(t("executive.approvalDialog.toastRejected", "Reddedildi"));
      }
      setPending((prev) => prev.filter((x) => x.id !== decision.id));
      // Defer a re-fetch so backend has time to settle resume_worker
      setTimeout(refresh, 1500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || t("executive.approvalDialog.toastFail", "İşlem başarısız"));
    }
  }

  async function handleRevert(decision) {
    try {
      await revertExecDecision(decision.id);
      toast.success(t("executive.approvalDialog.toastReverted", "Geri alındı"));
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || t("executive.approvalDialog.toastFail", "İşlem başarısız"));
    }
  }

  return (
    <div className="space-y-8">
      <Section
        title={t("executive.decision.sectionAwaiting", "Onayını bekleyen kararlar")}
        hero
        count={pending.length}
        emptyText={t("executive.decision.emptyAwaiting", "Bekleyen karar yok. Ekip sessiz çalışıyor.")}
        items={pending}
        onApprove={openApprove}
        onReject={openReject}
        onRevert={handleRevert}
      />
      <Section
        title={t("executive.decision.sectionAuto", "Otomatik yapılanlar (son 24 saat)")}
        count={auto.length}
        emptyText={t("executive.decision.emptyAuto", "Son 24 saatte otomatik yapılan karar yok.")}
        items={auto}
        onApprove={openApprove}
        onReject={openReject}
        onRevert={handleRevert}
      />
      <Section
        title={t("executive.decision.sectionPast", "Geçmiş kararlar (son 7 gün)")}
        count={past.length}
        emptyText={t("executive.decision.emptyPast", "Henüz tamamlanmış karar yok.")}
        items={past}
        onApprove={openApprove}
        onReject={openReject}
        onRevert={handleRevert}
      />

      <DecisionApprovalDialog
        decision={dialogDecision}
        open={!!dialogDecision}
        initialMode={dialogMode}
        onClose={() => setDialogDecision(null)}
        onConfirm={handleConfirm}
      />
    </div>
  );
}
