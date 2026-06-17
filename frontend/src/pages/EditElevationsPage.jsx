/**
 * @deprecated KULLANILMIYOR (2026-06-14) — route + nav kaldırıldı, sitede erişilemez.
 * Referans için tutuluyor; aktif uygulama akışının parçası DEĞİL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * Phase 43.D / Tier 2 — Edit Elevation dashboard.
 *
 * scripts/scan_edit_elevations.py runs daily and surfaces edit_fields
 * patterns Berkay applied 3+ times on the same content_type. Each row
 * is a "make this the default?" suggestion. Accept promotes the matching
 * editor_diffs rows' scope_tag from 'draft_only' → 'trend_type' (or
 * 'global' on opt-in). Reject hides the suggestion until the signature
 * changes.
 *
 * Backend:
 *   GET  /api/hype/personas
 *   GET  /api/hype/personas/{id}/edit-elevations?status=pending|accepted|rejected
 *   POST /api/hype/elevations/{id}/accept   body: { scope, notes? }
 *   POST /api/hype/elevations/{id}/reject   body: { notes? }
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  Lightbulb,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Calendar,
  Layers as LayersIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  listPersonas,
  listEditElevations,
  acceptEditElevation,
  rejectEditElevation,
} from "@/services/hypeService";
import { formatRelativeTime } from "@/components/quality-audit/lib/time.js";

const TABS = ["pending", "accepted", "rejected"];

function PatternPreview({ pattern }) {
  if (!pattern || typeof pattern !== "object") {
    return <p className="text-xs text-muted-foreground">—</p>;
  }
  const entries = Object.entries(pattern);
  if (entries.length === 0) return null;
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
      {entries.slice(0, 8).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground font-mono uppercase tracking-wide">{k}</dt>
          <dd className="text-foreground/90 font-mono break-words line-clamp-2">
            {typeof v === "string"
              ? v
              : Array.isArray(v)
              ? v.slice(0, 3).join(" · ")
              : typeof v === "object"
              ? JSON.stringify(v).slice(0, 120)
              : String(v)}
          </dd>
        </div>
      ))}
      {entries.length > 8 && (
        <div className="col-span-2 text-[10px] text-muted-foreground">
          +{entries.length - 8} alan daha
        </div>
      )}
    </dl>
  );
}

function ElevationCard({ candidate, onAccept, onReject, busy }) {
  const { t } = useTranslation();
  const [scope, setScope] = useState("trend_type");
  const isPending = candidate.status === "pending";

  return (
    <article
      className={cn(
        "rounded-2xl border bg-card p-5 space-y-4 transition-opacity",
        busy && "opacity-60 pointer-events-none",
        !isPending && "border-dashed"
      )}
    >
      {/* Header */}
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-amber-500" />
            <span className="text-sm font-semibold">
              {candidate.content_type
                ? candidate.content_type.replace(/_/g, " ")
                : t("editElevations.card.contentType")}
            </span>
            <Badge variant="outline" className="text-[11px]">
              {t("editElevations.card.sampleCount", { n: candidate.sample_count })}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground font-mono">
            sig {String(candidate.edit_signature || "").slice(0, 10)}…
          </p>
        </div>
        {!isPending && (
          <Badge
            variant="outline"
            className={cn(
              candidate.status === "accepted" &&
                "border-emerald-500/40 text-emerald-600",
              candidate.status === "rejected" &&
                "border-rose-500/40 text-rose-600"
            )}
          >
            {candidate.status === "accepted" ? (
              <CheckCircle2 className="h-3 w-3 mr-1" />
            ) : (
              <XCircle className="h-3 w-3 mr-1" />
            )}
            {t(`editElevations.tabs.${candidate.status}`)}
          </Badge>
        )}
      </header>

      {/* Pattern */}
      <section className="rounded-md bg-muted/40 p-3">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">
          {t("editElevations.card.pattern")}
        </p>
        <PatternPreview pattern={candidate.edit_pattern} />
      </section>

      {/* Timeline + sample drafts */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        {candidate.first_seen && (
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {t("editElevations.card.firstSeen", {
              when: formatRelativeTime(candidate.first_seen),
            })}
          </span>
        )}
        {candidate.last_seen && (
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {t("editElevations.card.lastSeen", {
              when: formatRelativeTime(candidate.last_seen),
            })}
          </span>
        )}
        {Array.isArray(candidate.example_draft_ids) &&
          candidate.example_draft_ids.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <LayersIcon className="h-3 w-3" />
              {t("editElevations.card.exampleDrafts", {
                n: candidate.example_draft_ids.length,
              })}
            </span>
          )}
      </div>

      {/* Action */}
      {isPending ? (
        <footer className="space-y-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1.5">
              {t("editElevations.actions.scopeLabel")}
            </label>
            <div className="flex gap-2">
              {["trend_type", "global"].map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setScope(opt)}
                  className={cn(
                    "flex-1 rounded-md border px-3 py-2 text-xs transition",
                    scope === opt
                      ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "border-border bg-background text-muted-foreground"
                  )}
                >
                  {t(`editElevations.card.scopeOptions.${opt}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2 flex-col-reverse sm:flex-row">
            <Button
              variant="outline"
              className="w-full border-rose-500/40 text-rose-600 hover:bg-rose-500/10"
              onClick={() => onReject(candidate)}
              disabled={busy}
            >
              <XCircle className="mr-2 h-4 w-4" />
              {t("editElevations.actions.reject")}
            </Button>
            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={() => onAccept(candidate, scope)}
              disabled={busy}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {t("editElevations.actions.accept")}
            </Button>
          </div>
        </footer>
      ) : (
        candidate.promoted_scope && (
          <footer className="text-[11px] text-muted-foreground">
            {t("editElevations.card.promotedScope", {
              scope: t(
                `editElevations.card.scopeOptions.${candidate.promoted_scope}`
              ),
            })}
          </footer>
        )
      )}
    </article>
  );
}

export default function EditElevationsPage() {
  const { t } = useTranslation();
  const [personas, setPersonas] = useState([]);
  const [personaId, setPersonaId] = useState(null);
  const [tab, setTab] = useState("pending");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyIds, setBusyIds] = useState(new Set());

  // Persona bootstrap
  useEffect(() => {
    let cancelled = false;
    listPersonas()
      .then((res) => {
        if (cancelled) return;
        const ps = res?.items || [];
        setPersonas(ps);
        const first = ps.find((p) => p.is_active) || ps[0];
        if (first) setPersonaId(first.id);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "load failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!personaId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await listEditElevations(personaId, { status: tab, limit: 100 });
      setItems(res?.items || []);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "load failed");
    } finally {
      setLoading(false);
    }
  }, [personaId, tab]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setBusy = (id, on) =>
    setBusyIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  const handleAccept = async (candidate, scope) => {
    setBusy(candidate.id, true);
    try {
      const res = await acceptEditElevation(candidate.id, { scope });
      toast.success(
        t("editElevations.toast.accepted", {
          n: res?.editor_diffs_promoted ?? "?",
        })
      );
      setItems((prev) => prev.filter((c) => c.id !== candidate.id));
    } catch (e) {
      toast.error(t("editElevations.toast.failed"));
      setBusy(candidate.id, false);
      return;
    }
    setBusy(candidate.id, false);
  };

  const handleReject = async (candidate) => {
    setBusy(candidate.id, true);
    try {
      await rejectEditElevation(candidate.id);
      toast.success(t("editElevations.toast.rejected"));
      setItems((prev) => prev.filter((c) => c.id !== candidate.id));
    } catch (e) {
      toast.error(t("editElevations.toast.failed"));
      setBusy(candidate.id, false);
      return;
    }
    setBusy(candidate.id, false);
  };

  const tabCounts = useMemo(() => {
    // For pending tab the count IS items.length; other tabs we trust the
    // server result (it's already filtered).
    return { current: items.length };
  }, [items]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Lightbulb className="h-6 w-6 text-amber-500" />
            {t("editElevations.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {t("editElevations.subtitle")}
          </p>
        </div>
        {personas.length > 1 && (
          <select
            value={personaId || ""}
            onChange={(e) => setPersonaId(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm"
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.display_name || p.slug || p.id.slice(0, 8)}
              </option>
            ))}
          </select>
        )}
      </header>

      {/* Tabs */}
      <div className="inline-flex rounded-lg border border-border p-1 bg-card">
        {TABS.map((tk) => (
          <button
            key={tk}
            type="button"
            onClick={() => setTab(tk)}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm transition",
              tab === tk
                ? "bg-background shadow-sm font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`editElevations.tabs.${tk}`)}
            {tab === tk && tabCounts.current > 0 && (
              <Badge
                variant="outline"
                className="ml-2 px-1 py-0 text-[10px] font-mono"
              >
                {tabCounts.current}
              </Badge>
            )}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && !loading && (
        <div
          role="alert"
          className="rounded-md border border-rose-500/40 bg-rose-500/5 p-4 text-sm
                     text-rose-600 dark:text-rose-400 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">{t("editElevations.error")}</p>
            <p className="text-xs text-muted-foreground mt-1">{String(error)}</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={refresh}>
              {t("editElevations.retry")}
            </Button>
          </div>
        </div>
      )}

      {/* No persona */}
      {!loading && !error && personas.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("editElevations.noPersona")}
        </p>
      )}

      {/* List */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-72 rounded-2xl border border-border bg-card animate-pulse"
            />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-12">
          {t("editElevations.empty")}
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((c) => (
            <ElevationCard
              key={c.id}
              candidate={c}
              busy={busyIds.has(c.id)}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}
