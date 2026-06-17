/**
 * @deprecated KULLANILMIYOR (2026-06-14) — route + nav kaldırıldı, sitede erişilemez.
 * Referans için tutuluyor; aktif uygulama akışının parçası DEĞİL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * Phase 43.D / Tier 2 — Autonomy Score dashboard.
 *
 * Surfaces the per-bucket (text / image / video) sample / reject / edit
 * gauges the daily cron at /opt/hype-crew/scripts/check_autonomy_gates.py
 * uses to decide whether `personas.{text,image,video}_autonomy_unlocked`
 * should flip on. Read-only — flipping the flag is the cron's job.
 *
 * Backend:
 *   GET /api/hype/personas          — list workspace personas
 *   GET /api/hype/personas/{id}/autonomy-score — live recompute
 */
import { useEffect, useMemo, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import {
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Lock,
  Clock,
  Type as TypeIcon,
  Image as ImageIcon,
  Video as VideoIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  listPersonas,
  getPersonaAutonomyScore,
} from "@/services/hypeService";
import { formatRelativeTime } from "@/components/quality-audit/lib/time.js";

const BUCKET_ICON = {
  text: TypeIcon,
  image: ImageIcon,
  video: VideoIcon,
};

function pct(n) {
  return Math.round(Number(n || 0) * 100);
}

function BucketCard({ bucketKey, bucket }) {
  const { t } = useTranslation();
  const Icon = BUCKET_ICON[bucketKey] || ShieldCheck;

  const {
    sample_count = 0,
    sample_min = 0,
    reject_count = 0,
    edit_count = 0,
    reject_rate = 0,
    edit_rate = 0,
    passes_sample,
    passes_reject,
    passes_edit,
    currently_unlocked,
    qualifies_for_unlock,
  } = bucket || {};

  const remaining = Math.max(0, sample_min - sample_count);

  // Top-level status banner
  let banner;
  if (currently_unlocked) {
    banner = {
      tone: "emerald",
      icon: CheckCircle2,
      text: t("autonomyScore.bucket.unlocked"),
    };
  } else if (qualifies_for_unlock) {
    banner = {
      tone: "amber",
      icon: Clock,
      text: t("autonomyScore.bucket.qualifies"),
    };
  } else if (!passes_sample) {
    banner = {
      tone: "muted",
      icon: Lock,
      text: t("autonomyScore.bucket.blockedSample"),
    };
  } else if (!passes_reject) {
    banner = {
      tone: "rose",
      icon: Lock,
      text: t("autonomyScore.bucket.blockedReject"),
    };
  } else {
    banner = {
      tone: "rose",
      icon: Lock,
      text: t("autonomyScore.bucket.blockedEdit"),
    };
  }

  const samplePct = sample_min ? Math.min(100, Math.round((sample_count / sample_min) * 100)) : 0;
  const rejPct = pct(reject_rate);
  const editPct = pct(edit_rate);

  const Predicate = ({ ok, label, value }) => (
    <li className="flex items-center justify-between gap-3 text-xs">
      <span className="flex items-center gap-2">
        <span
          className={cn(
            "inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px]",
            ok ? "bg-emerald-500/15 text-emerald-600" : "bg-muted text-muted-foreground"
          )}
        >
          {ok ? "✓" : "·"}
        </span>
        <span className="text-muted-foreground">{label}</span>
      </span>
      <span className="font-mono text-foreground">{value}</span>
    </li>
  );

  return (
    <article className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-foreground/70" />
          <h3 className="text-base font-semibold">
            {t(`autonomyScore.bucket.${bucketKey}`)}
          </h3>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "font-mono text-xs",
            currently_unlocked && "border-emerald-500/40 text-emerald-600",
            !currently_unlocked && qualifies_for_unlock && "border-amber-500/40 text-amber-600",
            !currently_unlocked && !qualifies_for_unlock && "border-border text-muted-foreground"
          )}
        >
          {sample_count}/{sample_min}
        </Badge>
      </header>

      {/* Sample progress */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
          <span>
            {t("autonomyScore.bucket.samples", { n: sample_count, min: sample_min })}
          </span>
          {!passes_sample && (
            <span>{t("autonomyScore.bucket.needSamples", { remaining })}</span>
          )}
        </div>
        <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-[width] duration-300",
              passes_sample ? "bg-emerald-500" : "bg-foreground/30"
            )}
            style={{ width: `${samplePct}%` }}
          />
        </div>
      </div>

      {/* Predicate breakdown */}
      <ul className="space-y-2">
        <Predicate
          ok={passes_sample}
          label={t("autonomyScore.bucket.predicates.sample")}
          value={`${sample_count} / ${sample_min}`}
        />
        <Predicate
          ok={passes_reject}
          label={t("autonomyScore.bucket.predicates.reject")}
          value={`${reject_count} • ${rejPct}%`}
        />
        <Predicate
          ok={passes_edit}
          label={t("autonomyScore.bucket.predicates.edit")}
          value={`${edit_count} • ${editPct}%`}
        />
      </ul>

      {/* Banner */}
      <div
        className={cn(
          "rounded-md px-3 py-2 text-xs flex items-center gap-2 border",
          banner.tone === "emerald" && "bg-emerald-500/5 border-emerald-500/30 text-emerald-700 dark:text-emerald-400",
          banner.tone === "amber" && "bg-amber-500/5 border-amber-500/30 text-amber-700 dark:text-amber-400",
          banner.tone === "rose" && "bg-rose-500/5 border-rose-500/30 text-rose-700 dark:text-rose-400",
          banner.tone === "muted" && "bg-muted/40 border-border text-muted-foreground"
        )}
      >
        <banner.icon className="h-4 w-4 shrink-0" />
        <span>{banner.text}</span>
      </div>
    </article>
  );
}

export default function AutonomyScorePage() {
  const { t } = useTranslation();
  const [personas, setPersonas] = useState([]);
  const [activePersonaId, setActivePersonaId] = useState(null);
  const [score, setScore] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Bootstrap: load persona list + auto-pick first active
  useEffect(() => {
    let cancelled = false;
    listPersonas()
      .then((res) => {
        if (cancelled) return;
        const items = res?.items || [];
        setPersonas(items);
        const firstActive = items.find((p) => p.is_active) || items[0];
        if (firstActive) setActivePersonaId(firstActive.id);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e?.message || "load failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshScore = useCallback(async () => {
    if (!activePersonaId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getPersonaAutonomyScore(activePersonaId);
      setScore(res);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "load failed");
      toast.error(t("autonomyScore.error"));
    } finally {
      setLoading(false);
    }
  }, [activePersonaId, t]);

  useEffect(() => {
    refreshScore();
  }, [refreshScore]);

  const lastCheckText = useMemo(() => {
    if (!score?.last_autonomy_check_at) return t("autonomyScore.lastCheckNever");
    return t("autonomyScore.lastCheck", {
      when: formatRelativeTime(score.last_autonomy_check_at),
    });
  }, [score, t]);

  const sampleMins = useMemo(() => {
    const b = score?.buckets || {};
    return {
      textMin: b.text?.sample_min ?? 30,
      imageMin: b.image?.sample_min ?? 20,
      videoMin: b.video?.sample_min ?? 10,
    };
  }, [score]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-emerald-500" />
            {t("autonomyScore.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {t("autonomyScore.subtitle")}
          </p>
        </div>
        {personas.length > 1 && (
          <select
            value={activePersonaId || ""}
            onChange={(e) => setActivePersonaId(e.target.value)}
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

      {/* Last check */}
      <p className="text-xs text-muted-foreground font-mono">
        {lastCheckText}
      </p>

      {/* Error */}
      {error && !loading && (
        <div
          role="alert"
          className="rounded-md border border-rose-500/40 bg-rose-500/5 p-4 text-sm
                     text-rose-600 dark:text-rose-400 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">{t("autonomyScore.error")}</p>
            <p className="text-xs text-muted-foreground mt-1">{String(error)}</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={refreshScore}>
              {t("autonomyScore.retry")}
            </Button>
          </div>
        </div>
      )}

      {/* Empty: no persona */}
      {!loading && !error && personas.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("autonomyScore.noPersona")}
        </p>
      )}

      {/* Buckets grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-64 rounded-2xl border border-border bg-card animate-pulse"
            />
          ))}
        </div>
      ) : (
        score?.buckets && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <BucketCard bucketKey="text" bucket={score.buckets.text} />
            <BucketCard bucketKey="image" bucket={score.buckets.image} />
            <BucketCard bucketKey="video" bucket={score.buckets.video} />
          </div>
        )
      )}

      {/* Thresholds explainer */}
      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="text-sm font-semibold">{t("autonomyScore.thresholds.title")}</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("autonomyScore.thresholds.body", sampleMins)}
        </p>
      </section>
    </div>
  );
}
