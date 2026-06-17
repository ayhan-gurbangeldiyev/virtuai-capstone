/**
 * @deprecated KULLANILMIYOR (2026-06-14) — route + nav kaldırıldı, sitede erişilemez.
 * Referans için tutuluyor; aktif uygulama akışının parçası DEĞİL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * Phase 43.E.4 + 43.E.6 — Quality Audit dashboard page.
 *
 * Layout:
 *   - Header (title + subtitle + trigger CTA)
 *   - FrozenBanner (conditional, when auto-publish was paused by audit)
 *   - Hero: pending cards grid + AuditProgressBar  OR  EmptyState variant
 *   - History accordion
 *
 * Data flow:
 *   - getQualityAuditSummary() → top stats + freeze status + sidebar badge
 *   - listQualityAudits({status:"pending"}) → hero cards
 *   - listQualityAudits({status:"history",limit:60}) → past cycles
 *   - Polling: 30s on pending only, throttled when document.hidden
 */
import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Plus, AlertCircle, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import AuditCard from "@/components/quality-audit/AuditCard";
import AuditProgressBar from "@/components/quality-audit/AuditProgressBar";
import FrozenBanner from "@/components/quality-audit/FrozenBanner";
import EmptyState from "@/components/quality-audit/EmptyState";
import FailDialog from "@/components/quality-audit/FailDialog";
import AuditHistoryRow from "@/components/quality-audit/AuditHistoryRow";

import {
  listQualityAudits,
  getQualityAuditSummary,
  rateAudit,
  triggerQualityAudit,
} from "@/services/qualityAuditService";

const POLL_INTERVAL_MS = 30_000;

function aggregatePendingByPersona(items, freezeMeta) {
  // Build per-persona [{pending: [...], meta}] groupings; preserve order
  const map = new Map();
  for (const it of items) {
    const key = it.persona_id || "_";
    if (!map.has(key)) {
      map.set(key, {
        persona_id: it.persona_id,
        persona_slug: it.persona_slug,
        meta: freezeMeta?.[it.persona_id] || null,
        items: [],
      });
    }
    map.get(key).items.push(it);
  }
  return Array.from(map.values());
}

function groupHistoryByMonth(items) {
  const map = new Map();
  for (const it of items) {
    const key = it.audit_month || "_";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(it);
  }
  // newest first
  return Array.from(map.entries())
    .sort((a, b) => (a[0] < b[0] ? 1 : -1))
    .map(([month, list]) => ({ month, items: list }));
}

export default function QualityAuditPage() {
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [summary, setSummary] = useState(null);
  const [pendingRes, setPendingRes] = useState(null); // {items, freeze_meta, ...}
  const [historyRes, setHistoryRes] = useState(null);

  // Optimistic state — set of audit_ids currently being rated
  const [pendingIds, setPendingIds] = useState(new Set());

  // FailDialog state
  const [failTarget, setFailTarget] = useState(null);

  // Trigger confirm state
  const [triggerConfirmOpen, setTriggerConfirmOpen] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const pollRef = useRef(null);

  const refresh = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [sum, pend, hist] = await Promise.all([
        getQualityAuditSummary().catch(() => null),
        listQualityAudits({ status: "pending", limit: 80 }),
        listQualityAudits({ status: "history", limit: 60 }),
      ]);
      setSummary(sum);
      setPendingRes(pend);
      setHistoryRes(hist);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // First load
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Polling on pending tab only (page is single-tab).
  useEffect(() => {
    function tick() {
      if (document.hidden) return;
      refresh({ silent: true });
    }
    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refresh]);

  // --- Derived UI state -------------------------------------------------

  const items = pendingRes?.items || [];
  const freezeMeta = pendingRes?.freeze_meta || {};
  const failThreshold =
    pendingRes?.freeze_threshold || summary?.personas?.[0]?.freeze_threshold || 3;

  const personaGroups = useMemo(
    () => aggregatePendingByPersona(items, freezeMeta),
    [items, freezeMeta]
  );

  // Overall aggregate (collapsed across personas — useful for the single-persona case)
  const totals = useMemo(() => {
    const allMetas = Object.values(freezeMeta);
    return allMetas.reduce(
      (acc, m) => {
        acc.total += m.total || 0;
        acc.rated += m.rated || 0;
        acc.pass += m.pass || 0;
        acc.fail += m.fail || 0;
        acc.pending += m.pending || 0;
        return acc;
      },
      { total: 0, rated: 0, pass: 0, fail: 0, pending: 0 }
    );
  }, [freezeMeta]);

  // Frozen banner: surface when any persona has fail_count >= threshold THIS month
  const frozenInfo = useMemo(() => {
    for (const m of Object.values(freezeMeta)) {
      if ((m.fail || 0) >= failThreshold) {
        return { fail: m.fail };
      }
    }
    return null;
  }, [freezeMeta, failThreshold]);

  // Last-cycle summary for the noAudit empty state (newest history month)
  const lastCycleStats = useMemo(() => {
    const grouped = groupHistoryByMonth(historyRes?.items || []);
    const first = grouped[0];
    if (!first) return null;
    return {
      pass: first.items.filter((a) => a.rating === "pass").length,
      fail: first.items.filter((a) => a.rating === "fail").length,
    };
  }, [historyRes]);

  const autoPublishOn = summary?.auto_publish_enabled_anywhere === true;
  const noPending = items.length === 0;

  // --- Action handlers --------------------------------------------------

  const setItemPending = (auditId, isPending) => {
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (isPending) next.add(auditId);
      else next.delete(auditId);
      return next;
    });
  };

  const removeItem = (auditId) => {
    setPendingRes((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.filter((a) => a.id !== auditId),
          }
        : prev
    );
  };

  const handlePass = async (audit) => {
    if (pendingIds.has(audit.id)) return;
    setItemPending(audit.id, true);
    try {
      const result = await rateAudit(audit.id, { rating: "pass" });
      removeItem(audit.id);
      toast.success(t("qualityAudit.toast.passSaved"));
      if (result?.froze_accounts?.length) {
        toast.error(t("qualityAudit.toast.freezeTriggered"));
      }
      // Refresh summary so progress + banner stay accurate
      refresh({ silent: true });
    } catch (e) {
      setItemPending(audit.id, false);
      toast.error(t("qualityAudit.toast.rateFailed"));
    }
  };

  const handleFailClick = (audit) => {
    if (pendingIds.has(audit.id)) return;
    setFailTarget(audit);
  };

  const handleFailSubmit = async (notes) => {
    if (!failTarget) return;
    const audit = failTarget;
    setFailTarget(null);
    setItemPending(audit.id, true);
    try {
      const result = await rateAudit(audit.id, { rating: "fail", notes });
      removeItem(audit.id);
      toast.success(t("qualityAudit.toast.failSaved"));
      if (result?.froze_accounts?.length) {
        toast.error(t("qualityAudit.toast.freezeTriggered"));
      }
      refresh({ silent: true });
    } catch (e) {
      setItemPending(audit.id, false);
      toast.error(t("qualityAudit.toast.rateFailed"));
    }
  };

  const handleTriggerConfirm = async () => {
    if (triggering) return;
    setTriggering(true);
    try {
      const res = await triggerQualityAudit({ sampleSize: 10 });
      setTriggerConfirmOpen(false);
      const inserted = res?.inserted_total || 0;
      if (inserted > 0) {
        toast.success(t("qualityAudit.trigger.success", { n: inserted }));
      } else {
        toast.message(t("qualityAudit.trigger.successEmpty"));
      }
      refresh();
    } catch (e) {
      const status = e?.response?.status;
      if (status === 409) {
        toast.error(t("qualityAudit.trigger.cooldownToast"));
      } else {
        toast.error(t("qualityAudit.trigger.error"));
      }
    } finally {
      setTriggering(false);
    }
  };

  // --- Render -----------------------------------------------------------

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-emerald-500" />
            {t("qualityAudit.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {t("qualityAudit.subtitle")}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setTriggerConfirmOpen(true)}
          disabled={triggering}
          className="self-start sm:self-auto"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          {t("qualityAudit.trigger.cta")}
        </Button>
      </header>

      {/* Frozen banner */}
      {frozenInfo && <FrozenBanner failCount={frozenInfo.fail} />}

      {/* Error */}
      {error && !loading && (
        <div
          role="alert"
          className="rounded-md border border-rose-500/40 bg-rose-500/5 p-4 text-sm
                     text-rose-600 dark:text-rose-400 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">{t("qualityAudit.error")}</p>
            <p className="text-xs text-muted-foreground mt-1">{String(error)}</p>
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={() => refresh()}
            >
              {t("qualityAudit.retry")}
            </Button>
          </div>
        </div>
      )}

      {/* Hero */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-72 rounded-2xl border border-border bg-card animate-pulse" />
          <div className="h-72 rounded-2xl border border-border bg-card animate-pulse" />
        </div>
      ) : noPending ? (
        autoPublishOn ? (
          <EmptyState
            variant="noAudit"
            lastCycleStats={lastCycleStats}
            onTriggerAudit={() => setTriggerConfirmOpen(true)}
          />
        ) : (
          <EmptyState variant="autoPublishOff" />
        )
      ) : (
        <section className="space-y-5">
          <div className="rounded-2xl border border-border bg-card p-4 sm:p-5">
            <div className="mb-2">
              <h2 className="text-lg font-semibold">
                {t("qualityAudit.hero.heading")}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t("qualityAudit.hero.subheading")}
              </p>
            </div>
            <AuditProgressBar
              rated={totals.rated}
              pass={totals.pass}
              fail={totals.fail}
              total={totals.total || items.length}
              failThreshold={failThreshold}
              className="mt-2"
            />
          </div>

          {personaGroups.map((group) => (
            <div key={group.persona_id || "_"} className="space-y-3">
              {personaGroups.length > 1 && group.persona_slug && (
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {group.persona_slug}
                </p>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {group.items.map((audit) => (
                  <AuditCard
                    key={audit.id}
                    audit={audit}
                    pending={pendingIds.has(audit.id)}
                    onPass={() => handlePass(audit)}
                    onFailClick={() => handleFailClick(audit)}
                  />
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* History */}
      <section className="space-y-3 pt-4">
        <div>
          <h2 className="text-lg font-semibold">
            {t("qualityAudit.history.title")}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t("qualityAudit.history.subtitle")}
          </p>
        </div>
        {loading ? (
          <div className="space-y-2">
            <div className="h-12 rounded-xl border border-border bg-card animate-pulse" />
            <div className="h-12 rounded-xl border border-border bg-card animate-pulse" />
          </div>
        ) : (
          <div className="space-y-2">
            {groupHistoryByMonth(historyRes?.items || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t("qualityAudit.history.empty")}
              </p>
            ) : (
              groupHistoryByMonth(historyRes?.items || []).map((cycle) => (
                <AuditHistoryRow
                  key={cycle.month}
                  monthKey={cycle.month}
                  audits={cycle.items}
                />
              ))
            )}
          </div>
        )}
      </section>

      {/* Fail dialog */}
      <FailDialog
        open={!!failTarget}
        onOpenChange={(o) => !o && setFailTarget(null)}
        onSubmit={handleFailSubmit}
        draftPreview={failTarget?.draft_snapshot?.content?.slice(0, 220) || ""}
      />

      {/* Trigger confirm */}
      <AlertDialog
        open={triggerConfirmOpen}
        onOpenChange={(o) => !triggering && setTriggerConfirmOpen(o)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("qualityAudit.trigger.confirmTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("qualityAudit.trigger.confirmBody")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={triggering}>
              {t("qualityAudit.trigger.confirmCancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleTriggerConfirm}
              disabled={triggering}
            >
              {triggering
                ? t("qualityAudit.trigger.submitting")
                : t("qualityAudit.trigger.confirmSubmit")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
