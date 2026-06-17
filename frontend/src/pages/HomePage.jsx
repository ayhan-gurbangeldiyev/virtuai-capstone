/**
 * HomePage — operator-facing editorial briefing at /control.
 *
 * Source of truth: projects/post-capstone/product-structure.md and
 * projects/post-capstone/home-v1-implementation-plan.md.
 *
 * v1.1 redesign (2026-06-04 evening): comparison-first hero. The decision
 * (covered vs skipped) is the visual centerpiece; the prose reason becomes
 * supporting context. Previous version presented the explanation before
 * the comparison, which read as a wireframe paragraph instead of an
 * editorial choice.
 *
 * Hard rules (do not violate during future edits):
 *   - No internal system names anywhere (Persona Gate, TrendScout, Visual
 *     Director, Compliance, Postiz, Wiro, HeyGen, Nano Banana).
 *   - No cards, tiles, KPI boxes, charts, or skeleton shimmer.
 *   - No personality copy not anchored in an external fact.
 *   - The hero sentence is server-composed; never assemble it client-side
 *     by interpolating fields.
 *   - Comparison comes BEFORE explanation; the decision is the product.
 */
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { useAccount } from "@/contexts/AccountContext";
import { Button } from "@/components/ui/button";
import { fetchHomeSummary, setPauseState } from "@/services/hypeService";
import { HomePendingCTA } from "@/components/ControlChrome";

export default function HomePage() {
  const { effectiveAccountId } = useAccount();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pausing, setPausing] = useState(false);

  const load = useCallback(async () => {
    if (!effectiveAccountId) return;
    setError(null);
    try {
      const data = await fetchHomeSummary(effectiveAccountId);
      setSummary(data);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [effectiveAccountId]);

  useEffect(() => {
    load();
  }, [load]);

  const handlePauseToggle = async () => {
    if (!effectiveAccountId || !summary?.pause) return;
    setPausing(true);
    try {
      const next = !summary.pause.is_paused;
      const newPause = await setPauseState(effectiveAccountId, next);
      setSummary((s) => (s ? { ...s, pause: newPause } : s));
    } catch (e) {
      setError(e);
    } finally {
      setPausing(false);
    }
  };

  if (loading) {
    return (
      <ControlShell>
        <p className="text-neutral-500 text-sm">Bugünün seçimleri yükleniyor…</p>
      </ControlShell>
    );
  }

  if (error || !summary) {
    // Clean error state: no internal references (runbook / system / infra).
    // One sentence, one retry. If the operator wants the technical reason
    // they can open devtools; this surface is for the editorial loop, not
    // for explaining outages.
    return (
      <ControlShell>
        <div className="space-y-4">
          <p className="text-neutral-700">
            Bugünün özeti şu an yüklenemiyor.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setError(null);
              load();
            }}
            className="border-neutral-400 text-neutral-900 hover:bg-neutral-100"
          >
            Yeniden dene
          </Button>
        </div>
      </ControlShell>
    );
  }

  const { as_of, hero, latest_published, pause, liveness } = summary;

  return (
    <ControlShell>
      <Wordmark as_of={as_of} />

      {hero.kind === "decision_pair" && (
        <DecisionPairBlock covered={hero.covered} skipped={hero.skipped} />
      )}
      {hero.kind === "closest_call" && (
        <ClosestCallBlock skipped={hero.skipped} />
      )}
      {hero.kind === "decision_covered_only" && (
        <CoveredOnlyBlock covered={hero.covered} sentence={hero.sentence} />
      )}
      {hero.kind === "status_only" && (
        <StatusOnlyBlock sentence={hero.sentence} />
      )}

      {/* Composer reason (only present when HOME_COMPOSER_ENABLED + validation passed) */}
      {hero.reason && hero.kind !== "status_only" && (
        <ReasonBlock sentence={hero.sentence} reason={hero.reason} />
      )}

      {/* Latest-published anchor — shown only when distinct from the covered slot
          (i.e. on quiet days, or when latest publish is from a prior day). */}
      {latest_published && !sameTrendAsCovered(hero, latest_published) && (
        <LatestPublishedAnchor lp={latest_published} />
      )}

      {/* CTA into the approval queue — only shows when pending > 0 so
          quiet days stay quiet. */}
      <HomePendingCTA />

      {pause?.is_paused && (
        <p className="text-sm text-amber-700 mt-6">
          Cansu şu anda duraklatılmış durumda.
        </p>
      )}

      <KillSwitch
        pausing={pausing}
        paused={!!pause?.is_paused}
        canPause={!!pause?.can_pause}
        onToggle={handlePauseToggle}
      />

      <LivenessFooter liveness={liveness} />
    </ControlShell>
  );
}

/* ── Shell ────────────────────────────────────────────────────────── */

function ControlShell({ children }) {
  // Top-anchored layout. Background + min-height come from <ControlChrome />
  // wrapper now; this shell only handles the inner column.
  return (
    <main>
      <div className="px-6 md:px-12 pt-8 md:pt-12 pb-24">
        <div className="mx-auto w-full max-w-3xl">{children}</div>
      </div>
    </main>
  );
}

/* ── Wordmark + timestamp ─────────────────────────────────────────── */

function Wordmark({ as_of }) {
  return (
    <header className="mb-10">
      <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500">
        Cansu · bugün
      </p>
      <p className="text-xs text-neutral-400 mt-1">{formatAsOf(as_of)}</p>
    </header>
  );
}

/* ── Decision pair: the comparison IS the page ──────────────────── */

function DecisionPairBlock({ covered, skipped }) {
  return (
    <section aria-label="Bugünün editöryel kararı">
      <DecisionRow
        label="Yazdı"
        labelTone="accent"
        title={covered?.title}
        meta={
          covered
            ? `${covered.platform || ""}${
                covered.platform && covered.published_at ? " · " : ""
              }${formatRelativeShort(covered.published_at)}`
            : null
        }
        // C3 (2026-06-07): the title now opens the LIFECYCLE page when
        // we have a draft_id. The release_url stays available as a
        // secondary "↗ Yayında" link beneath the meta line.
        lifecycleHref={covered?.draft_id ? `/control/lifecycle/${covered.draft_id}` : null}
        externalHref={covered?.release_url}
        emphasized
      />

      <Separator />

      <DecisionRow
        label="Yazmadı"
        labelTone="muted"
        title={skipped?.title}
        meta={null}
        lifecycleHref={null}
        externalHref={null}
        emphasized={false}
      />
    </section>
  );
}

function DecisionRow({ label, labelTone, title, meta, lifecycleHref, externalHref, emphasized }) {
  const labelClass =
    labelTone === "accent"
      ? "text-emerald-700"
      : "text-neutral-400";
  // Emphasized titles are the page's centerpiece — large, bold, link-as-headline.
  // Non-emphasized titles (the "Yazmadı" side) stay smaller and muted so the
  // covered side dominates visually.
  const titleClass = emphasized
    ? "text-3xl md:text-5xl leading-[1.1] text-neutral-900 font-semibold tracking-tight"
    : "text-xl md:text-2xl leading-snug text-neutral-500 font-medium";
  return (
    <div className={emphasized ? "py-2" : "py-4"}>
      <p className={`text-[10px] font-bold tracking-[0.22em] uppercase mb-3 ${labelClass}`}>
        {label}
      </p>
      {lifecycleHref ? (
        <RouterLink
          to={lifecycleHref}
          className={`${titleClass} block hover:underline underline-offset-4 decoration-2`}
        >
          {title || "—"}
        </RouterLink>
      ) : externalHref ? (
        <a
          href={externalHref}
          target="_blank"
          rel="noopener noreferrer"
          className={`${titleClass} block hover:underline underline-offset-4 decoration-2`}
        >
          {title || "—"}
        </a>
      ) : (
        <p className={titleClass}>{title || "—"}</p>
      )}
      {meta && (
        <p className={`mt-3 ${emphasized ? "text-sm text-neutral-600" : "text-xs text-neutral-500"}`}>
          {meta}
        </p>
      )}
      {emphasized && externalHref && (
        <p className="mt-1 text-xs text-neutral-500">
          <a
            href={externalHref}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-neutral-900"
          >
            ↗ Yayında
          </a>
        </p>
      )}
    </div>
  );
}

function Separator() {
  return (
    <div className="my-2 flex items-center gap-3">
      <div className="flex-1 h-px bg-neutral-200" />
      <span className="text-[10px] tracking-[0.22em] uppercase text-neutral-400 font-semibold">
        vs
      </span>
      <div className="flex-1 h-px bg-neutral-200" />
    </div>
  );
}

/* ── Closest call: quiet day with a near-miss ───────────────────── */

function ClosestCallBlock({ skipped }) {
  return (
    <section aria-label="Bugünün en yakın editöryel adayı">
      <p className="text-[10px] font-bold tracking-[0.22em] uppercase mb-2 text-neutral-400">
        Bugün yazmadı
      </p>
      <p className="text-xs text-neutral-500 mb-3">En yakın aday:</p>
      <p className="text-2xl md:text-3xl leading-tight text-neutral-900 font-semibold">
        {skipped?.title || "—"}
      </p>
    </section>
  );
}

/* ── Covered only: fresh pick today, no grounded skip to pair with ── */

function CoveredOnlyBlock({ covered, sentence }) {
  return (
    <section aria-label="Bugünün editöryel seçimi" className="mb-6">
      <DecisionRow
        label="Yazdı"
        labelTone="accent"
        title={covered?.title}
        meta={
          covered
            ? `${covered.platform || ""}${
                covered.platform && covered.published_at ? " · " : ""
              }${formatRelativeShort(covered.published_at)}`
            : null
        }
        link={covered?.release_url}
        emphasized
      />
      {sentence && (
        <p className="mt-6 text-base md:text-lg leading-relaxed text-neutral-700 max-w-2xl">
          {sentence}
        </p>
      )}
    </section>
  );
}

/* ── Status only: deterministic system-state sentence ───────────── */

function StatusOnlyBlock({ sentence }) {
  return (
    <section>
      <p className="text-xl md:text-2xl leading-snug text-neutral-700">
        {sentence}
      </p>
    </section>
  );
}

/* ── Reason: supporting context below the decision ──────────────── */

function ReasonBlock({ sentence, reason }) {
  // Composer wrote a full sentence. The comparison block above already shows
  // the verbatim titles, so we show the sentence as the explanation
  // paragraph below the visual comparison. (Reason field used for analytics
  // / debug, not displayed verbatim here — operator reads the prose.)
  return (
    <section className="mt-8 pt-6 border-t border-neutral-200">
      <p className="text-sm md:text-base leading-relaxed text-neutral-700">
        {sentence}
      </p>
    </section>
  );
}

/* ── Latest published anchor ────────────────────────────────────── */

function LatestPublishedAnchor({ lp }) {
  return (
    <section className="mt-8">
      <p className="text-[10px] font-bold tracking-[0.22em] uppercase mb-2 text-neutral-400">
        En son yazısı
      </p>
      <p className="text-sm text-neutral-700">
        {lp.release_url ? (
          <a
            href={lp.release_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-neutral-900"
          >
            {lp.title}
          </a>
        ) : (
          <span>{lp.title}</span>
        )}
        {lp.platform ? ` · ${lp.platform}` : ""}
        {lp.relative_time ? ` · ${lp.relative_time}` : ""}
        {lp.release_url ? " ↗" : ""}
      </p>
    </section>
  );
}

/* ── Kill switch: visible, neutral, single-click ────────────────── */

function KillSwitch({ pausing, paused, canPause, onToggle }) {
  return (
    <section className="mt-10">
      <Button
        variant="outline"
        size="sm"
        onClick={onToggle}
        disabled={pausing || !canPause}
        className="border-neutral-400 text-neutral-900 hover:bg-neutral-100 hover:border-neutral-600"
      >
        {paused ? "Cansu'yu devam ettir" : "Cansu'yu duraklat"}
      </Button>
    </section>
  );
}

/* ── Liveness footer ────────────────────────────────────────────── */

function LivenessFooter({ liveness }) {
  const dotColor = {
    green: "bg-emerald-500",
    yellow: "bg-amber-500",
    red: "bg-red-500",
  }[liveness.status] || "bg-neutral-300";

  const cronLine = liveness.cron_relative
    ? `Son kontrol: ${liveness.cron_relative}.`
    : "Henüz bir değerlendirme yapılmadı.";

  const issueCopy = {
    no_recent_evaluation: "Cansu henüz bugün için bir değerlendirme yapmadı.",
    system_quiet_longer_than_usual: "Cansu olağandan uzun süredir sessiz.",
    system_dark: "Cansu son bir saattir aktif değil.",
  };

  return (
    <footer className="pt-10 mt-12 border-t border-neutral-200 space-y-1">
      <p className="text-xs text-neutral-500 flex items-center gap-2">
        <span className={`inline-block w-2 h-2 rounded-full ${dotColor}`} />
        {cronLine}
      </p>
      {liveness.issues.map((code) => (
        <p key={code} className="text-xs text-neutral-500">
          {issueCopy[code] || code}
        </p>
      ))}
    </footer>
  );
}

/* ── Utilities ──────────────────────────────────────────────────── */

function sameTrendAsCovered(hero, latest_published) {
  if (hero?.kind !== "decision_pair" && hero?.kind !== "decision_covered_only") return false;
  const coveredUrl = hero?.covered?.release_url;
  const lpUrl = latest_published?.release_url;
  return !!coveredUrl && coveredUrl === lpUrl;
}

function formatAsOf(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return `${d.toLocaleDateString("tr-TR", {
      day: "numeric",
      month: "long",
    })}, ${d.toLocaleTimeString("tr-TR", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  } catch {
    return "";
  }
}

function formatRelativeShort(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const mins = Math.floor((Date.now() - d.getTime()) / 60000);
    if (mins < 1) return "az önce";
    if (mins < 60) return `${mins} dakika önce`;
    if (mins < 60 * 24) return `${Math.floor(mins / 60)} saat önce`;
    return `${Math.floor(mins / (60 * 24))} gün önce`;
  } catch {
    return "";
  }
}
