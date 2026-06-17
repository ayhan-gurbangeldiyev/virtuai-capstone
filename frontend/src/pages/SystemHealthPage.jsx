/**
 * @deprecated KULLANILMIYOR (2026-06-14) — route + nav kaldırıldı, sitede erişilemez.
 * Referans için tutuluyor; aktif uygulama akışının parçası DEĞİL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * Tier 3 — System Health page.
 *
 * Single dashboard that surfaces three cost-and-quality signals:
 *   1. Cost     — today vs daily_cost_cap_usd + weekly trend + regen +
 *                 video budget. Inline cap editor.
 *   2. Reliability — last 24h success/fail mix, last 5 failures with
 *                    error text, tone banner.
 *   3. Postiz   — credential probe + last published timestamp + key
 *                 rotation guidance.
 *
 * Backend:
 *   GET   /api/hype/system-health
 *   PATCH /api/hype/config/{accountId}        body: { daily_cost_cap_usd }
 *   PATCH /api/hype/personas/{id}/budget      body: { daily_video_budget_usd, video_enabled }
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Wallet,
  Plug,
  RefreshCcw,
  AlertCircle,
  PencilLine,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/AccountContext";
import {
  getSystemHealth,
  updateAccountConfig,
  updatePersonaBudget,
} from "@/services/hypeService";
import {
  formatRelativeTime,
  formatFullDateTime,
} from "@/components/quality-audit/lib/time.js";

const POLL_INTERVAL_MS = 60_000; // 1 min auto refresh

function fmtUsd(n) {
  const v = Number(n || 0);
  return `$${v.toFixed(v < 1 ? 4 : 2)}`;
}

function toneClasses(tone, target = "border") {
  if (tone === "danger") {
    return target === "bg"
      ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/40"
      : "border-rose-500/40 text-rose-600 dark:text-rose-400";
  }
  if (tone === "warn") {
    return target === "bg"
      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/40"
      : "border-amber-500/40 text-amber-600 dark:text-amber-400";
  }
  return target === "bg"
    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
    : "border-emerald-500/40 text-emerald-600 dark:text-emerald-400";
}

function CostSection({ cost, accountId, onCapSaved }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draftCap, setDraftCap] = useState(cost?.today_cap_usd ?? 1);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraftCap(cost?.today_cap_usd ?? 1);
  }, [cost?.today_cap_usd]);

  const pct = Math.min(100, Math.round((cost?.today_pct || 0) * 100));
  const tone = pct >= 100 ? "danger" : pct >= 80 ? "warn" : "ok";

  async function saveCap() {
    if (!accountId) return;
    setSaving(true);
    try {
      const v = Number(draftCap);
      if (!Number.isFinite(v) || v < 0) {
        toast.error(t("systemHealth.cost.capFailed"));
        return;
      }
      await updateAccountConfig(accountId, { daily_cost_cap_usd: v });
      toast.success(t("systemHealth.cost.capSaved", { cap: fmtUsd(v) }));
      setEditing(false);
      onCapSaved?.();
    } catch (e) {
      toast.error(t("systemHealth.cost.capFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="h-5 w-5 text-foreground/70" />
          <h2 className="text-base font-semibold">{t("systemHealth.cost.title")}</h2>
        </div>
        <Badge variant="outline" className={cn("font-mono text-xs", toneClasses(tone))}>
          {fmtUsd(cost?.today_cost_usd)} / {fmtUsd(cost?.today_cap_usd)}
        </Badge>
      </header>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>{t("systemHealth.cost.todayLabel")}</span>
          <span>{t("systemHealth.cost.ofCap", { pct })}</span>
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-300",
              tone === "danger" && "bg-rose-500",
              tone === "warn" && "bg-amber-500",
              tone === "ok" && "bg-emerald-500"
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-[11px] text-muted-foreground font-mono">
          {t("systemHealth.cost.runs", { n: cost?.today_runs ?? 0 })}
        </p>
      </div>

      {/* Cap editor */}
      {accountId && (
        <div className="flex items-center gap-2 text-xs">
          {editing ? (
            <>
              <span className="text-muted-foreground">$</span>
              <input
                type="number"
                step="0.1"
                min="0"
                max="20"
                value={draftCap}
                onChange={(e) => setDraftCap(e.target.value)}
                disabled={saving}
                className="w-24 rounded-md border border-input bg-background px-2 py-1 text-xs font-mono"
              />
              <Button size="sm" onClick={saveCap} disabled={saving}>
                {saving ? t("systemHealth.cost.savingCap") : "✓"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEditing(false);
                  setDraftCap(cost?.today_cap_usd ?? 1);
                }}
                disabled={saving}
              >
                ✕
              </Button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground transition"
            >
              <PencilLine className="h-3 w-3" />
              {t("systemHealth.cost.editCap")}
            </button>
          )}
        </div>
      )}

      {/* Week trend */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-md bg-muted/40 p-3">
          <p className="text-muted-foreground">{t("systemHealth.cost.weekLabel")}</p>
          <p className="font-mono text-foreground mt-1">
            {fmtUsd(cost?.week_cost_usd)}
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {t("systemHealth.cost.weekAvg", {
              avg: fmtUsd(cost?.week_avg_per_day_usd),
            })}
          </p>
        </div>
        <div className="rounded-md bg-muted/40 p-3">
          <p className="text-muted-foreground">{t("systemHealth.cost.regen", {
            n: cost?.regen_today_count ?? 0,
            cost: fmtUsd(cost?.regen_today_cost_usd),
          })}</p>
          <p className="text-[10px] text-muted-foreground mt-1">
            {(cost?.video_today_cost_usd ?? 0) > 0
              ? t("systemHealth.cost.video", {
                  cost: fmtUsd(cost?.video_today_cost_usd),
                  cap: fmtUsd(cost?.video_cap_usd),
                })
              : t("systemHealth.cost.noVideo")}
          </p>
        </div>
      </div>
    </section>
  );
}

function ReliabilitySection({ reliability }) {
  const { t } = useTranslation();
  const tone = reliability?.tone || "ok";
  const fails = reliability?.recent_failures || [];

  return (
    <section className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-foreground/70" />
          <h2 className="text-base font-semibold">
            {t("systemHealth.reliability.title")}
          </h2>
        </div>
        <Badge variant="outline" className={cn("text-xs", toneClasses(tone))}>
          {t(`systemHealth.reliability.tone.${tone}`)}
        </Badge>
      </header>

      {/* Fail rates */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className={cn("rounded-md p-3 border", toneClasses(tone, "bg"))}>
          <p>
            {t("systemHealth.reliability.todayFailRate", {
              pct: reliability?.today_fail_rate_pct ?? 0,
            })}
          </p>
          <p className="font-mono mt-1">
            ✓ {t("systemHealth.reliability.completedToday", {
              n: (reliability?.today_runs ?? 0) - (reliability?.today_failed ?? 0),
            })}
            {"  "}
            ✕ {t("systemHealth.reliability.failedToday", {
              n: reliability?.today_failed ?? 0,
            })}
          </p>
        </div>
        <div className="rounded-md bg-muted/40 p-3 border border-border">
          <p className="text-muted-foreground">
            {t("systemHealth.reliability.weekFailRate", {
              pct: Math.round((reliability?.week_fail_rate || 0) * 1000) / 10,
            })}
          </p>
          {(reliability?.regen_today_count ?? 0) > 0 && (
            <p className="text-[10px] text-muted-foreground mt-1">
              {t("systemHealth.reliability.regenFail", {
                pct: Math.round((reliability?.regen_today_fail_rate || 0) * 1000) / 10,
                failed: reliability?.regen_today_failed ?? 0,
                total: reliability?.regen_today_count ?? 0,
              })}
            </p>
          )}
        </div>
      </div>

      {/* Recent failures */}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">
          {t("systemHealth.reliability.recentFailuresTitle")}
        </p>
        {fails.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            {t("systemHealth.reliability.noFailures")}
          </p>
        ) : (
          <ul className="space-y-1.5">
            {fails.map((f) => (
              <li
                key={f.id}
                className="rounded-md border border-rose-500/20 bg-rose-500/5 p-2 text-xs flex items-start gap-2"
              >
                <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-rose-500" />
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-[10px] text-muted-foreground">
                    {formatRelativeTime(f.started_at)} •{" "}
                    {f.id?.slice(0, 8) || "—"}
                  </p>
                  {f.error && (
                    <p className="mt-0.5 text-rose-700 dark:text-rose-300 line-clamp-2">
                      {f.error}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function PostizSection({ postiz }) {
  const { t } = useTranslation();
  const ok = postiz?.ok;
  return (
    <section
      className={cn(
        "rounded-2xl border bg-card p-5 space-y-4",
        ok ? "border-border" : "border-rose-500/40"
      )}
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Plug className="h-5 w-5 text-foreground/70" />
          <h2 className="text-base font-semibold">
            {t("systemHealth.postiz.title")}
          </h2>
        </div>
        {ok ? (
          <Badge variant="outline" className="border-emerald-500/40 text-emerald-600">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            {t("systemHealth.postiz.connected")}
          </Badge>
        ) : (
          <Badge variant="outline" className="border-rose-500/40 text-rose-600">
            <AlertCircle className="h-3 w-3 mr-1" />
            {t("systemHealth.postiz.broken")}
          </Badge>
        )}
      </header>

      <div className="space-y-2 text-xs">
        <p>
          {t("systemHealth.postiz.integrations", {
            n: postiz?.integrations_count ?? 0,
          })}
        </p>
        <p className="text-muted-foreground">
          {postiz?.last_published_at
            ? t("systemHealth.postiz.lastPublished", {
                when: formatFullDateTime(postiz.last_published_at),
              })
            : t("systemHealth.postiz.noPublishes")}
        </p>
      </div>

      {!ok && (
        <div className="rounded-md bg-rose-500/5 border border-rose-500/30 p-3 text-xs">
          <p className="text-rose-600 dark:text-rose-400 font-mono break-words">
            <span className="font-semibold">{t("systemHealth.postiz.errorPrefix")}</span>{" "}
            {postiz?.error || `HTTP ${postiz?.http_status || "?"}`}
          </p>
          <p className="text-muted-foreground mt-2">
            {t("systemHealth.postiz.rotateHint")}
          </p>
          <a
            href="https://app.postiz.com/settings/api"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex text-rose-500 hover:underline"
          >
            {t("systemHealth.postiz.rotateCta")}
          </a>
        </div>
      )}
    </section>
  );
}

export default function SystemHealthPage() {
  const { t } = useTranslation();
  const { activeAccountId } = useAccount();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true);
      setError(null);
      try {
        const res = await getSystemHealth();
        setData(res);
      } catch (e) {
        setError(e?.response?.data?.detail || e?.message || "load failed");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto refresh every minute when visible
  useEffect(() => {
    const id = setInterval(() => {
      if (!document.hidden) refresh({ silent: true });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const modeLabel = useMemo(() => {
    if (data?.modes?.auto_publish_enabled_anywhere) {
      return t("systemHealth.modes.autoPublish");
    }
    if (data?.modes?.dry_run_mode_anywhere) {
      return t("systemHealth.modes.dry");
    }
    return t("systemHealth.modes.manualOnly");
  }, [data, t]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="h-6 w-6 text-emerald-500" />
            {t("systemHealth.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {t("systemHealth.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2 self-start">
          <Badge variant="outline" className="text-xs">
            {modeLabel}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh()}
            disabled={loading}
          >
            <RefreshCcw className={cn("h-4 w-4 mr-1.5", loading && "animate-spin")} />
            {t("systemHealth.retry")}
          </Button>
        </div>
      </header>

      {data?.as_of && (
        <p className="text-[11px] text-muted-foreground font-mono">
          {t("systemHealth.asOf", { when: formatRelativeTime(data.as_of) })}
        </p>
      )}

      {error && !loading && (
        <div
          role="alert"
          className="rounded-md border border-rose-500/40 bg-rose-500/5 p-4 text-sm
                     text-rose-600 dark:text-rose-400 flex items-start gap-2"
        >
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">{t("systemHealth.error")}</p>
            <p className="text-xs text-muted-foreground mt-1">{String(error)}</p>
          </div>
        </div>
      )}

      {loading && !data ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-72 rounded-2xl border border-border bg-card animate-pulse"
            />
          ))}
        </div>
      ) : data ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <CostSection
            cost={data.cost}
            accountId={activeAccountId}
            onCapSaved={() => refresh({ silent: true })}
          />
          <ReliabilitySection reliability={data.reliability} />
          <PostizSection postiz={data.postiz} />
        </div>
      ) : null}
    </div>
  );
}
