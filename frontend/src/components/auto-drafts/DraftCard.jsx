/**
 * DraftCard — premium card for a Hype Crew auto-draft.
 *
 * Visual:
 *  - left border accent colored by trend category (AI=purple, Tech=blue, etc.)
 *  - top row: category badge + voice score pill + cost badge + status dot
 *  - body: trend topic uppercase tracker + content with preserved line-breaks
 *  - countdown strip (mono font, color shifts by proximity)
 *  - collapsible "how Hype Crew thought" with stage details
 *  - bottom action bar: Approve / Reject / Edit
 */
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ChevronDown, Clock, Sparkles, ExternalLink, Image as ImageIcon, RotateCw, Trash2, ShieldCheck } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import StageDetails from "./StageDetails";
import {
  resolveCollaborator,
  timeAgo,
  ACTION_LABELS,
  REJECT_CATEGORY_LABELS,
  IMAGE_REJECTION_LABELS,
} from "./lib/userNames";

const CATEGORY_ACCENTS = {
  ai: { border: "border-l-purple-500", chip: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/30", label: "AI" },
  tech: { border: "border-l-blue-500", chip: "bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/30", label: "Tech" },
  crypto: { border: "border-l-amber-500", chip: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30", label: "Crypto" },
  business: { border: "border-l-emerald-500", chip: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30", label: "Business" },
  default: { border: "border-l-slate-500", chip: "bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/30", label: "Trend" },
};

function getAccent(draft) {
  const cat = (draft?.trend_topic || "").toLowerCase();
  if (cat.includes("ai") || cat.includes("agent") || cat.includes("gpt") || cat.includes("llm")) return CATEGORY_ACCENTS.ai;
  if (cat.includes("crypto") || cat.includes("btc") || cat.includes("eth")) return CATEGORY_ACCENTS.crypto;
  if (cat.includes("startup") || cat.includes("yc") || cat.includes("founder")) return CATEGORY_ACCENTS.business;
  if (cat.includes("apple") || cat.includes("google") || cat.includes("dev") || cat.includes("tech")) return CATEGORY_ACCENTS.tech;
  return CATEGORY_ACCENTS.default;
}

function formatScheduledIn(scheduledAt) {
  if (!scheduledAt) return null;
  const target = new Date(scheduledAt).getTime();
  const now = Date.now();
  const diffSec = Math.floor((target - now) / 1000);
  const abs = Math.abs(diffSec);
  // Phase 39.9 — Past or far-future timestamps now read as human-friendly
  // relative time ("3 saat önce yayınlandı") instead of the live HH:MM:SS
  // countdown, which only made sense within a 24h window. Live countdown
  // is kept ONLY for posts scheduled in the next 24h.
  if (diffSec <= 0 || abs >= 86400) {
    return {
      isFuture: diffSec > 0,
      text: formatRelativeTime(scheduledAt),
      diffSec,
      humanized: true,
    };
  }
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;
  return {
    isFuture: true,
    text: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
    diffSec,
    humanized: false,
  };
}

function voiceScoreColor(score) {
  if (score == null) return "text-muted-foreground border-border";
  if (score >= 70) return "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (score >= 40) return "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/30";
}

// Phase 43.B.5 — composite confidence score (sample-weighted 30d reject
// rate). 0.75+ = system has been happy with similar drafts; 0.5-0.75 =
// mixed; <0.5 = the same content_type has been rejected often, treat
// this draft with extra suspicion.
function confidenceColor(score) {
  if (score == null) return "text-muted-foreground border-border";
  if (score >= 0.75) return "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (score >= 0.5)  return "text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/30";
}

// Phase 32.2 — Relative time: "az önce" / "5 dk önce" / "3 saat önce" / "9 gün önce"
function formatRelativeTime(date) {
  if (!date) return null;
  const diffMs = Date.now() - new Date(date).getTime();
  if (diffMs < 0) return "az önce";
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "az önce";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} dk önce`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} saat önce`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} gün önce`;
  const diffWeek = Math.floor(diffDay / 7);
  if (diffWeek < 4) return `${diffWeek} hafta önce`;
  const diffMonth = Math.floor(diffDay / 30);
  return `${diffMonth} ay önce`;
}

function formatFullDateTime(date) {
  if (!date) return null;
  try {
    return new Date(date).toLocaleString("tr-TR", {
      timeZone: "Europe/Istanbul",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return new Date(date).toISOString();
  }
}

export default function DraftCard({ draft, index = 0, isTopForKeyboard = false, onApprove, onRefine, onReject, onCancelApproval }) {
  const { t } = useTranslation();
  // Phase 41.A — Accordion default CLOSED. Critic audit (1 Haz 2026) showed
  // auto-expand cost ~250px/card vertical space, making it impossible to
  // see 2-3 cards above the fold. Reviewer can tap "🧠 Hype Crew nasıl
  // düşündü?" to inspect pipeline if needed.
  const [expanded, setExpanded] = useState(false);
  const [imageModalOpen, setImageModalOpen] = useState(false);

  const accent = useMemo(() => getAccent(draft), [draft]);
  const sched = useMemo(() => formatScheduledIn(draft?.scheduled_at), [draft?.scheduled_at]);
  // Phase 28.C: 'pending_review' is the new "user hasn't reviewed yet, NOT yet
  // on Postiz" state. We treat it the same as 'pending' for action visibility.
  const isPending = draft?.status === "pending" || draft?.status === "pending_review";
  // Phase 28.R-Lite-V2: approved drafts that haven't published yet can be
  // cancelled (Postiz schedule recall). Published drafts (scheduled_at in
  // the past) need manual platform-side delete.
  const isApproved = draft?.status === "approved" || draft?.status === "auto_approved";
  const isScheduled = draft?.status === "auto_scheduled";
  const scheduledAtMs = draft?.scheduled_at ? new Date(draft.scheduled_at).getTime() : null;
  const isLikelyPublished = scheduledAtMs != null && scheduledAtMs < Date.now();
  const canCancelApproval = (isApproved || isScheduled) && !isLikelyPublished && Boolean(onCancelApproval);
  const hasImage = Boolean(draft?.image_url);
  const imageMeta = draft?.image_meta;
  // Phase 35.2 — video preview support (HeyGen Avatar V + MiniMax)
  const hasVideo = Boolean(draft?.video_url);
  const videoDurationSec = draft?.video_duration_sec || null;
  const youtubeVideoId = draft?.youtube_video_id || null;
  const [videoModalOpen, setVideoModalOpen] = useState(false);

  // Phase 43.B.5 — confidence_score lives directly on daily_drafts (filled
  // by flow.py at insert time using a sample-weighted 30d reject rate).
  // Null on legacy rows or when no persona resolved at insert.
  const confidenceScore = draft?.confidence_score ?? null;

  // Derive cost + voice score from metadata when present (forward-compat with backend)
  const cost = draft?.cost_usd ?? draft?.metadata?.cost_usd ?? null;
  const voiceScore = draft?.voice_score ?? draft?.metadata?.voice_score ?? null;
  const insight = draft?.insight || draft?.metadata?.insight || null;

  return (
    <motion.div
      data-draft-idx={index}
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, x: -32 }}
      transition={{ duration: 0.15, ease: "easeOut" }}
      whileHover={{ y: -2 }}
      className={cn(
        "group relative rounded-2xl border bg-card",
        isTopForKeyboard
          ? "border-purple-500/60 ring-2 ring-purple-500/30 ring-offset-2 ring-offset-background"
          : "border-border/60",
        "border-l-[3px]", accent.border,
        "shadow-sm hover:shadow-lg hover:shadow-purple-500/5 transition-shadow",
        "p-5 sm:p-6"
      )}
    >
      {/* Top row — Phase 41.A: category chip removed (left border accent zaten kategori
          rengini taşıyor), cost badge accordion'a taşındı (accounting değer, review değil),
          status dot pending tab'da gizlendi (redundant — sekme zaten Bekleyen). */}
      <div className="flex items-center gap-2 flex-wrap mb-3">
        {/* Platform badge (Phase 20 multi-platform) */}
        {draft.platform && (
          <PlatformBadge platform={draft.platform} />
        )}

        {voiceScore != null && (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono border cursor-help",
                    voiceScoreColor(voiceScore)
                  )}
                >
                  <Sparkles className="h-3 w-3" />
                  {voiceScore}
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs text-xs">
                {t("autoDrafts.card.voiceScoreHint", { score: voiceScore })}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* Phase 43.B.5 — confidence_score pill. Tooltip explains the math
            (composite of 30d reject rate × sample-weight) so Berkay knows
            what the number actually means. */}
        {confidenceScore != null && (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono border cursor-help",
                    confidenceColor(confidenceScore)
                  )}
                >
                  <ShieldCheck className="h-3 w-3" />
                  {confidenceScore.toFixed(2)}
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs text-xs">
                {t("autoDrafts.card.confidenceHint", {
                  score: confidenceScore.toFixed(2),
                  defaultValue:
                    "Bu içerik türü için son 30 günde sistemin güveni " +
                    "({{score}}). 0.75+ iyi, 0.50-0.75 karışık, altı dikkat.",
                })}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        <div className="flex-1" />

        {/* StatusDot only when NOT pending — pending tab'da redundant signal */}
        {!isPending && <StatusDot status={draft.status} />}
      </div>

      {/* Phase 35.3 — Promoted trend headline + source snippet
          (Berkay 30 May 2026: "ne haber geldiğini göreyim, basitçe görebileyim") */}
      {draft.trend_topic && (
        <h3 className="text-base font-semibold leading-snug text-foreground mb-1.5">
          {draft.trend_topic}
        </h3>
      )}
      {draft.source_meta?.snippet && (
        <p className="text-[12.5px] leading-relaxed text-muted-foreground/95 line-clamp-2 italic mb-2 border-l-2 border-purple-500/30 pl-2.5">
          "{draft.source_meta.snippet}"
        </p>
      )}

      {/* Phase 32.2 — Üretilme zamanı + "Yeni" badge (son 1 saat) */}
      {draft.created_at && (
        <div className="flex items-center gap-2 mb-2">
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground/80 cursor-help">
                  <Clock className="h-3 w-3" />
                  {formatRelativeTime(draft.created_at)} üretildi
                </span>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs font-mono">
                {formatFullDateTime(draft.created_at)}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {/* Phase 41.A — "Yeni" amber pill kaldırıldı (Critic audit): pending
              kuyruğundaki her şey zaten yeni, redundant signal her kartta ping ediyor. */}
        </div>
      )}

      {/* Source link (Phase 17.3) */}
      {draft.source_meta?.url && (
        <a
          href={draft.source_meta.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-purple-500 mb-3 transition-colors group/source"
        >
          <ExternalLink className="h-3 w-3 group-hover/source:scale-110 transition-transform" />
          {draft.source_meta.type === "twitter" && draft.source_meta.name ? (
            <span className="font-mono">@{draft.source_meta.name}</span>
          ) : (
            <span className="font-mono">{draft.source_meta.name || "Kaynak"}</span>
          )}
          <span className="text-muted-foreground/50">·</span>
          <span className="truncate max-w-[280px]">
            {draft.source_meta.url.replace(/^https?:\/\//, "").replace(/\/$/, "")}
          </span>
        </a>
      )}

      {/* Video preview (Phase 35.2 — HeyGen Avatar V).
          Phase 43 hotfix: inline <video> inside a Radix Dialog was rendering
          the controls bar but never decoding past frame 0 in Chrome. The
          combination of focus trap + late `preload="metadata"` left the
          element in a permanent "loading" state. Switched to a native
          <video> element rendered inline on the card itself (no Dialog) —
          autoplays muted, loops as a silent preview, and a "Tam ekran aç"
          link opens the full-resolution mp4 in a new tab. */}
      {hasVideo && (
        <div className="relative w-full mb-3 rounded-xl overflow-hidden bg-secondary/40 border border-border/40">
          <video
            src={draft.video_url}
            poster={draft.video_thumbnail_url || draft.image_url || undefined}
            controls
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
            onError={(e) => {
              // eslint-disable-next-line no-console
              console.error("[DraftCard] video failed", {
                src: draft.video_url,
                code: e.currentTarget.error?.code,
                message: e.currentTarget.error?.message,
              });
            }}
            className="w-full h-auto max-h-80 bg-black"
          />
          <div className="absolute top-2 right-2 flex items-center gap-1.5">
            {youtubeVideoId && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-rose-600/90 text-white">
                YT
              </span>
            )}
            <a
              href={draft.video_url}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2 py-0.5 rounded text-[10px] font-medium bg-black/70 text-white hover:bg-black"
              title="Videoyu yeni sekmede aç"
            >
              ↗ Tam ekran
            </a>
          </div>
          {videoDurationSec && (
            <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-[10px] font-mono bg-black/70 text-white pointer-events-none">
              {Math.round(videoDurationSec)}sn
            </span>
          )}
        </div>
      )}

      {/* Legacy thumbnail button — kept for reference, no longer rendered.
          The native <video> above replaced the click-to-open Dialog flow. */}
      {false && hasVideo && (
        <button
          type="button"
          onClick={() => setVideoModalOpen(true)}
          className="group/vid relative block w-full mb-3 rounded-xl overflow-hidden bg-secondary/40 border border-border/40 hover:border-purple-500/40 transition-colors"
        >
          <img
            src={draft.video_thumbnail_url || draft.image_url || "data:image/svg+xml,%3Csvg/%3E"}
            alt={draft.trend_topic || "Generated video"}
            className="w-full h-auto max-h-72 object-cover"
            loading="lazy"
          />
          {/* Play overlay */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-14 h-14 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center group-hover/vid:bg-black/80 transition">
              <svg viewBox="0 0 24 24" fill="white" className="w-7 h-7 ml-1">
                <polygon points="6,4 20,12 6,20" />
              </svg>
            </div>
          </div>
          {/* Duration badge */}
          {videoDurationSec && (
            <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-[10px] font-mono bg-black/70 text-white">
              {Math.round(videoDurationSec)}sn
            </span>
          )}
          {/* YouTube linked badge */}
          {youtubeVideoId && (
            <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-rose-600/90 text-white">
              YT
            </span>
          )}
        </button>
      )}

      {/* Image thumbnail (Phase 21).
          Phase 43 hotfix: clicking opens the full-resolution image in a new
          tab (same pattern as video). The Dialog modal underneath has been
          retired — browser image viewer handles zoom/pan + save far better
          than our cramped modal could. */}
      {hasImage && !hasVideo && (
        <a
          href={draft.image_url}
          target="_blank"
          rel="noopener noreferrer"
          className="group/img relative block w-full mb-3 rounded-xl overflow-hidden bg-secondary/40 border border-border/40 hover:border-purple-500/40 transition-colors"
        >
          <img
            src={draft.image_url}
            alt={draft.trend_topic || "Generated visual"}
            className="w-full h-auto max-h-72 object-cover"
            loading="lazy"
          />
          <div className="absolute top-2 right-2 flex items-center gap-1 flex-wrap">
            {imageMeta?.model && (
              <span className="px-1.5 py-0.5 rounded-md text-[9px] font-mono bg-black/60 text-white border border-white/20 backdrop-blur-sm">
                {imageMeta.model.split("/").pop()}
              </span>
            )}
            {imageMeta?.compliance_passed === false && (
              <span className="px-1.5 py-0.5 rounded-md text-[9px] font-semibold bg-amber-500/90 text-white">
                review
              </span>
            )}
            {imageMeta?.compliance_passed === true && (
              <span className="px-1.5 py-0.5 rounded-md text-[9px] font-semibold bg-emerald-500/90 text-white">
                ✓
              </span>
            )}
            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-black/70 text-white opacity-0 group-hover/img:opacity-100 transition-opacity">
              ↗ Tam ekran
            </span>
          </div>
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 group-hover/img:opacity-100 transition-opacity flex items-end justify-start p-3">
            <span className="text-xs text-white inline-flex items-center gap-1.5">
              <ImageIcon className="h-3.5 w-3.5" />
              {t("autoDrafts.card.viewImage", "Görseli aç")}
            </span>
          </div>
        </a>
      )}

      {/* Content */}
      <div className="text-[15px] leading-relaxed whitespace-pre-wrap mb-4 text-foreground/95">
        {draft.content}
      </div>

      {/* Insight */}
      {insight && (
        <p className="text-xs italic text-muted-foreground mb-3 border-l-2 border-border pl-3">
          {insight}
        </p>
      )}

      {/* Countdown */}
      {sched && (
        <div className="flex items-center gap-2 mb-3 text-xs">
          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
          <span className={cn(
            "font-mono",
            !sched.isFuture ? "text-muted-foreground" :
            sched.diffSec < 600 ? "text-amber-600 dark:text-amber-400" :
            "text-emerald-600 dark:text-emerald-400"
          )}>
            {sched.humanized
              ? (sched.isFuture
                  ? `${sched.text} sonra yayında`
                  : `${sched.text} yayınlandı`)
              : (sched.isFuture
                  ? t("autoDrafts.card.scheduledIn", { time: sched.text })
                  : t("autoDrafts.card.publishedAgo", { time: sched.text }))}
          </span>
        </div>
      )}

      {/* Phase 28.H — Feedback timeline (who did what on this draft) */}
      {Array.isArray(draft.feedback_events) && draft.feedback_events.length > 0 && (
        <FeedbackTimeline events={draft.feedback_events} />
      )}

      {/* Pipeline accordion — Phase 35.3 clearer trigger label */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
      >
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")}
        />
        <span className="font-medium">🧠 Hype Crew nasıl düşündü?</span>
        <span className="text-[10px] text-muted-foreground/70 hidden sm:inline">
          Scout · Strateji · Yazım · Kontrol
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <StageDetails draft={draft} expanded={expanded} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Image full-size modal */}
      {hasImage && (
        <Dialog open={imageModalOpen} onOpenChange={setImageModalOpen}>
          <DialogContent className="max-w-4xl p-2 sm:p-4 gap-2">
            <DialogTitle className="sr-only">
              {draft.trend_topic || "Generated visual"}
            </DialogTitle>
            <img
              src={draft.image_url}
              alt={draft.trend_topic || "Generated visual"}
              className="w-full h-auto rounded-lg"
            />
            {/* Stage 3 (B.5): internal scoring + cost metrics moved
                behind a collapsed disclosure so the approval surface
                reads as editorial review, not infra telemetry. */}
            {(imageMeta || imageMeta?.llm_reasoning) && (
              <details className="px-1 pb-1 text-xs text-muted-foreground">
                <summary className="cursor-pointer select-none text-[11px] tracking-wide hover:text-foreground">
                  Detaylar (teknik)
                </summary>
                {imageMeta && (
                  <div className="flex items-center flex-wrap gap-2 mt-2 font-mono text-[11px]">
                    {imageMeta.model && <span>model: {imageMeta.model}</span>}
                    {imageMeta.clip_similarity != null && (
                      <span>clip: {Number(imageMeta.clip_similarity).toFixed(3)}</span>
                    )}
                    {imageMeta.aesthetic_score != null && (
                      <span>aesthetic: {Number(imageMeta.aesthetic_score).toFixed(3)}</span>
                    )}
                    {imageMeta.llm_verdict && (
                      <span>llm: {imageMeta.llm_verdict}</span>
                    )}
                    {imageMeta.cost_usd != null && (
                      <span>cost: ${Number(imageMeta.cost_usd).toFixed(3)}</span>
                    )}
                  </div>
                )}
                {imageMeta?.llm_reasoning && (
                  <p className="italic mt-2">{imageMeta.llm_reasoning}</p>
                )}
              </details>
            )}
          </DialogContent>
        </Dialog>
      )}

      {/* Video full-size modal (Phase 35.2) */}
      {hasVideo && (
        <Dialog open={videoModalOpen} onOpenChange={setVideoModalOpen}>
          <DialogContent className="max-w-3xl p-2 sm:p-4 gap-2">
            <DialogTitle className="sr-only">
              {draft.trend_topic || "Generated video"}
            </DialogTitle>
            <video
              src={draft.video_url}
              poster={draft.video_thumbnail_url || draft.image_url || undefined}
              controls
              autoPlay
              muted
              playsInline
              preload="metadata"
              onError={(e) => {
                // Surface failures so the modal isn't a silent black box.
                // eslint-disable-next-line no-console
                console.error("[DraftCard] video failed to load", {
                  src: draft.video_url,
                  code: e.currentTarget.error?.code,
                  message: e.currentTarget.error?.message,
                });
              }}
              className="w-full h-auto max-h-[80vh] rounded-lg bg-black"
            />
            {/* Fallback link in case the inline player can't decode */}
            <a
              href={draft.video_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-muted-foreground hover:text-purple-500 underline underline-offset-2 px-1"
            >
              Yeni sekmede aç ↗
            </a>
            <div className="flex items-center flex-wrap gap-2 text-[11px] text-muted-foreground font-mono px-1">
              {videoDurationSec && <span>duration: {Math.round(videoDurationSec)}sn</span>}
              {draft.heygen_video_id && (
                <span title="HeyGen video id">heygen: {draft.heygen_video_id.slice(0, 8)}</span>
              )}
              {youtubeVideoId && (
                <a
                  href={`https://youtube.com/shorts/${youtubeVideoId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-rose-500 hover:underline"
                >
                  YouTube'da aç ↗
                </a>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Phase 28.R-Lite-V2: Approved drafts can be cancelled before publish.
          Published drafts (scheduled_at < now) need manual platform delete. */}
      {!isPending && canCancelApproval && (
        <div className="mt-4 space-y-2">
          <Button
            onClick={() => {
              if (window.confirm("Bu yayını iptal et? Zamanlama kaldırılıyor, hiçbir platformda gözükmeyecek.")) {
                onCancelApproval();
              }
            }}
            size="sm"
            variant="outline"
            className="w-full h-10 gap-1.5 border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-700 dark:hover:text-rose-300"
            title="Yayına alınmadan önce zamanlamadan çek"
          >
            <Trash2 className="h-4 w-4" />
            {t("autoDrafts.actions.cancelApproval", "Yayını iptal et")}
          </Button>
        </div>
      )}
      {!isPending && !canCancelApproval && isLikelyPublished && (
        <div className="mt-4 rounded-lg bg-amber-500/10 border border-amber-500/30 p-3 text-[11px] text-amber-700 dark:text-amber-300 flex items-start gap-1.5">
          <Clock className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>
            {t("autoDrafts.actions.alreadyPublished",
              "Yayın zamanı geçti, post canlı olabilir. Silmek istiyorsan ilgili platformdan manuel kaldır.")}
          </span>
        </div>
      )}

      {/* Actions — Phase 28.Q: 2 primary buttons + 1 ghost link
          (consolidated from 4 buttons after sub-agent UX analysis).
          Onayla → Postiz schedule
          Düzelt → IterationDialog (scope picker: metin/görsel/ikisi inside)
          Sil → 1-click confirm + hard reject (no dialog, fast escape) */}
      {isPending && (
        <div className="mt-4 space-y-2">
          <div className="flex flex-col sm:flex-row gap-2">
            <Button
              onClick={onApprove}
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 text-white flex-1 h-10 gap-1.5"
              title="A — Onayla, yayın programına al"
            >
              <Check className="h-4 w-4" />
              {t("autoDrafts.actions.approve")}
            </Button>
            {onRefine && (
              <Button
                onClick={onRefine}
                size="sm"
                variant="outline"
                className="flex-1 h-10 gap-1.5 border-purple-500/30 hover:bg-purple-500/10 hover:text-purple-700 dark:hover:text-purple-300"
                title={t("autoDrafts.actions.refineHint", "D — AI ile yeniden yaz, beğenene kadar (max 10)")}
              >
                <RotateCw className="h-4 w-4" />
                {t("autoDrafts.actions.refine", "Düzelt")}
              </Button>
            )}
          </div>
          {onReject && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm("Bu taslağı tamamen sil? Geri alınamaz.")) {
                  onReject({ category: "other", feedback: "manually deleted", rejection_target: "both" });
                }
              }}
              className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 transition-colors mx-auto"
              title="Backspace — Bu taslağı tamamen sil"
            >
              <Trash2 className="h-3 w-3" />
              <span className="underline-offset-2 hover:underline">{t("autoDrafts.actions.deleteForever", "Tamamen sil")}</span>
            </button>
          )}
        </div>
      )}
    </motion.div>
  );
}

function StatusDot({ status }) {
  const map = {
    pending: { color: "bg-amber-400", label: "Bekliyor" },
    pending_review: { color: "bg-amber-400", label: "Bekliyor" },  // Phase 41.A — map yoktu, raw "pending_review" string gözüküyordu
    auto_scheduled: { color: "bg-blue-500", label: "Planlandı" },
    auto_approved: { color: "bg-emerald-500", label: "Onaylandı" },
    approved: { color: "bg-emerald-500", label: "Onaylandı" },
    auto_rejected: { color: "bg-rose-500", label: "Reddedildi" },
    rejected: { color: "bg-rose-500", label: "Reddedildi" },
    edited: { color: "bg-violet-500", label: "Düzenlendi" },
    published: { color: "bg-emerald-600", label: "Yayında" },
    cancelled: { color: "bg-slate-500", label: "İptal edildi" },
  };
  const s = map[status] || { color: "bg-slate-400", label: status };
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", s.color)} />
      <span>{s.label}</span>
    </span>
  );
}

const PLATFORM_BADGE_STYLE = {
  twitter: { label: "X", classes: "bg-black/85 text-white border-black/40 dark:bg-white/10 dark:text-white" },
  x: { label: "X", classes: "bg-black/85 text-white border-black/40 dark:bg-white/10 dark:text-white" },
  linkedin: { label: "LinkedIn", classes: "bg-[#0a66c2]/15 text-[#0a66c2] border-[#0a66c2]/30 dark:text-[#3a9bff]" },
  devto: { label: "dev.to", classes: "bg-slate-900/90 text-white border-slate-900/40 dark:bg-slate-100 dark:text-slate-900" },
  instagram: { label: "IG", classes: "bg-gradient-to-r from-pink-500/15 to-violet-500/15 text-pink-700 dark:text-pink-300 border-pink-500/30" },
  youtube: { label: "YT", classes: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30" },
  medium: { label: "Medium", classes: "bg-emerald-900/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30" },
};

/**
 * Phase 28.H — Per-draft feedback timeline.
 * Shows "[avatar] {name} {action} · {time}" + optional rejection cat / image reason / free text.
 * Events come back ASC from backend; render newest-first for readability.
 */
function FeedbackTimeline({ events }) {
  const ordered = [...events].reverse(); // newest first
  return (
    <div className="mb-4 space-y-2 rounded-xl bg-secondary/30 border border-border/40 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Ekip aktivitesi
      </p>
      {ordered.map((ev, i) => {
        const persona = resolveCollaborator(ev.user_email);
        const verb = ACTION_LABELS[ev.action] || ev.action || "—";
        return (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span
              className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border shrink-0",
                persona.classes,
              )}
              title={ev.user_email}
            >
              <span>{persona.avatar}</span>
              <span>{persona.name}</span>
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-foreground/90">
                <span className="text-muted-foreground">{verb}</span>
                <span className="text-muted-foreground/60"> · {timeAgo(ev.created_at)}</span>
              </p>
              {ev.action === "rejected" && (
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {ev.rejection_target === "image" && (
                    <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 text-[10px]">
                      sadece görsel
                    </span>
                  )}
                  {ev.rejection_target === "text" && (
                    <span className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-700 dark:text-rose-300 text-[10px]">
                      sadece metin
                    </span>
                  )}
                  {ev.image_rejection_reason && (
                    <span className="mr-1.5">
                      {IMAGE_REJECTION_LABELS[ev.image_rejection_reason] || ev.image_rejection_reason}
                    </span>
                  )}
                  {ev.rejection_category && (
                    <span>
                      {REJECT_CATEGORY_LABELS[ev.rejection_category] || ev.rejection_category}
                    </span>
                  )}
                </p>
              )}
              {ev.free_text_feedback && (
                <p className="mt-1 text-[12px] italic text-foreground/80 border-l-2 border-border/60 pl-2">
                  "{ev.free_text_feedback}"
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PlatformBadge({ platform }) {
  const key = (platform || "").toLowerCase();
  const cfg = PLATFORM_BADGE_STYLE[key] || {
    label: platform,
    classes: "bg-secondary/60 text-muted-foreground border-border/50",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border",
        cfg.classes,
      )}
    >
      {cfg.label}
    </span>
  );
}

