import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Check, Pencil, Trash2, Video, Image as ImageIcon, ExternalLink, Clock, ChevronDown, Lightbulb, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent } from "@/components/ui/dialog";

/**
 * Phase 40 (Berkay 1 Haz 2026) — Thread-grouped draft card.
 *
 * Bir content_thread_id altındaki 4-5 platform draft'ını TEK kart olarak
 * gösterir. Üstte trend topic + hero media (video varsa video, yoksa image)
 * + tab'larla platform versiyonları + tek "Onayla" butonu.
 *
 * "Onayla" → parent component'in `onApproveThread(threadId)` callback'ini
 * çağırır → backend POST /api/hype/threads/{id}/approve → tüm platforma birden
 * Postiz schedule.
 *
 * Tek bir platform kötü ise: "Bu platformu reddet" linki o platformun
 * draft'ını sıradan reject endpoint'iyle reddeder, thread kalan platformlarla
 * approve edilebilir.
 */
const PLATFORM_LABELS = {
  twitter: "X",
  linkedin: "LinkedIn",
  devto: "Dev.to",
  instagram: "Instagram",
  youtube: "YouTube",
};

const PLATFORM_ICONS = {
  twitter: "𝕏",
  linkedin: "in",
  devto: "dev",  // Phase 41.A — "</>" was a mystery icon (Critic audit)
  instagram: "IG",
  youtube: "YT",
};

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
  return `${diffDay} gün önce`;
}

export default function ThreadCard({ thread, isTopForKeyboard = false, onApproveThread, onRejectDraft, onRefineDraft }) {
  // thread: { thread_id, trend_topic, drafts: [draftRow, ...], created_at }
  const drafts = thread.drafts || [];
  const platforms = drafts.map((d) => d.platform);
  const hasVideo = drafts.some((d) => d.video_url);
  const heroVideo = useMemo(() => drafts.find((d) => d.video_url) || null, [drafts]);
  const heroImage = useMemo(() => drafts.find((d) => d.image_url) || null, [drafts]);

  // Default active tab = first platform (alphabetical preference: twitter > linkedin > devto > instagram > youtube)
  const platformOrder = ["twitter", "linkedin", "devto", "instagram", "youtube"];
  const firstPlat = platformOrder.find((p) => platforms.includes(p)) || platforms[0];
  const [activeTab, setActiveTab] = useState(firstPlat);
  const [approving, setApproving] = useState(false);
  const [videoOpen, setVideoOpen] = useState(false);

  const activeDraft = drafts.find((d) => d.platform === activeTab) || drafts[0];

  async function handleApprove() {
    if (approving) return;
    setApproving(true);
    try {
      await onApproveThread(thread.thread_id);
    } finally {
      setApproving(false);
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, x: -32 }}
      className={`rounded-2xl border bg-card overflow-hidden transition-all ${
        isTopForKeyboard
          ? "border-purple-500/60 ring-2 ring-purple-500/30 ring-offset-2 ring-offset-background"
          : "border-border"
      }`}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-secondary/20">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-foreground line-clamp-2">
              {thread.trend_topic || "(no trend topic)"}
            </h3>
            {thread.created_at && (
              <p className="text-[11px] text-muted-foreground mt-1 inline-flex items-center gap-1">
                <Clock className="h-3 w-3" /> {formatRelativeTime(thread.created_at)} üretildi
              </p>
            )}
          </div>
          {hasVideo && (
            <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-300 border-purple-500/40">
              <Video className="h-3 w-3 mr-1" /> Video hazır
            </Badge>
          )}
        </div>

        {/* Platform tabs */}
        <div className="flex items-center gap-1 mt-2 flex-wrap">
          {drafts.map((d) => {
            const isActive = d.platform === activeTab;
            const hasOwnVideo = Boolean(d.video_url);
            return (
              <button
                key={d.id}
                onClick={() => setActiveTab(d.platform)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors inline-flex items-center gap-1.5 ${
                  isActive
                    ? "bg-purple-500/15 text-purple-700 dark:text-purple-200 border-purple-500/50 font-medium"
                    : "bg-card border-border/60 text-muted-foreground hover:text-foreground hover:border-purple-500/30"
                }`}
                title={PLATFORM_LABELS[d.platform] || d.platform}
              >
                <span className="font-mono">{PLATFORM_ICONS[d.platform] || d.platform}</span>
                <span>{PLATFORM_LABELS[d.platform] || d.platform}</span>
                {hasOwnVideo && <Video className="h-3 w-3 text-purple-500" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Body — active platform content */}
      <div className="p-4 grid grid-cols-1 sm:grid-cols-[160px_1fr] gap-4">
        {/* Hero media */}
        <div className="space-y-2">
          {activeDraft?.video_url ? (
            // Phase 43 hotfix: inline <video> (autoplay+muted+loop) replaces
            // the Dialog-modal flow that Chrome left stuck at 0:00. The
            // "↗ Tam ekran" link opens the mp4 in a new browser tab when
            // the user wants sound / full screen.
            <div className="relative w-full aspect-[9/16] rounded-lg overflow-hidden bg-black/60">
              <video
                key={activeDraft.id}
                src={activeDraft.video_url}
                poster={activeDraft.video_thumbnail_url || undefined}
                controls
                autoPlay
                muted
                loop
                playsInline
                preload="metadata"
                onError={(e) => {
                  // eslint-disable-next-line no-console
                  console.error("[ThreadCard] video failed", {
                    src: activeDraft.video_url,
                    code: e.currentTarget.error?.code,
                    message: e.currentTarget.error?.message,
                  });
                }}
                className="absolute inset-0 w-full h-full object-cover"
              />
              <a
                href={activeDraft.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[9px] font-medium bg-black/70 text-white hover:bg-black z-10"
                title="Tam ekran / sesli aç"
              >
                ↗
              </a>
              <div className="absolute bottom-0 left-0 right-0 p-1 bg-gradient-to-t from-black/80 to-transparent pointer-events-none">
                <p className="text-[10px] text-white/90 text-center">
                  {Math.round(activeDraft.video_duration_sec || 0)}sn
                </p>
              </div>
            </div>
          ) : (activeDraft?.image_url || heroImage?.image_url) ? (
            <a
              href={activeDraft?.image_url || heroImage.image_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full"
            >
              <img
                src={activeDraft?.image_url || heroImage.image_url}
                alt={thread.trend_topic || ""}
                className="w-full aspect-[9/16] rounded-lg object-cover hover:opacity-90 transition-opacity"
              />
            </a>
          ) : (
            <div className="w-full aspect-[9/16] rounded-lg bg-secondary/40 flex items-center justify-center text-muted-foreground/60">
              <ImageIcon className="h-8 w-8" />
            </div>
          )}
        </div>

        {/* Active platform content */}
        <div className="flex flex-col">
          <div className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1">
            {PLATFORM_LABELS[activeTab] || activeTab}
            {activeDraft?.video_url && (
              <span className="ml-2 text-purple-600 dark:text-purple-400 normal-case">
                · {activeTab === "youtube" ? "Shorts" : activeTab === "instagram" ? "Reels" : "video"}
              </span>
            )}
          </div>
          <p className="text-sm text-foreground/90 whitespace-pre-wrap break-words leading-relaxed flex-1">
            {activeDraft?.content}
          </p>
          <div className="mt-3 flex items-center gap-2 text-[11px]">
            <button
              onClick={() => onRefineDraft && onRefineDraft(activeDraft)}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
            >
              <Pencil className="h-3 w-3" /> Bu platformu düzelt
            </button>
            <span className="text-muted-foreground/40">·</span>
            <button
              onClick={() => onRejectDraft && onRejectDraft(activeDraft)}
              className="text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 inline-flex items-center gap-1 transition-colors"
            >
              <Trash2 className="h-3 w-3" /> Bu platformu reddet
            </button>
          </div>
        </div>
      </div>

      {/* Phase 43.F — Agent reasoning + source panel.
          Backend already returns source_meta (trend origin) + image_meta
          (Visual Director's LLM verdict). Surface both so the user can see
          *why* this draft exists and *why* the visual was chosen, without
          leaving the card. */}
      <ThreadDetailsPanel drafts={drafts} activeDraft={activeDraft} />

      {/* Footer — single Approve button for all platforms */}
      <div className="px-4 py-3 border-t border-border bg-secondary/10 flex items-center justify-between gap-3">
        <p className="text-[11px] text-muted-foreground">
          Onaylarsan <span className="font-semibold text-foreground/80">{drafts.length} platforma</span> birden Postiz'e gönderilir,
          ~2 saat sonra yayına çıkar.
        </p>
        <Button
          onClick={handleApprove}
          disabled={approving}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          <Check className="h-4 w-4 mr-1.5" />
          {approving ? "Gönderiliyor..." : `Onayla (${drafts.length} platform)`}
        </Button>
      </div>

      {/* Video modal */}
      {hasVideo && heroVideo && (
        <Dialog open={videoOpen} onOpenChange={setVideoOpen}>
          <DialogContent className="max-w-md p-2">
            <video
              src={heroVideo.video_url}
              controls
              autoPlay
              poster={heroVideo.video_thumbnail_url || undefined}
              className="w-full rounded-lg"
            />
            {heroVideo.youtube_video_id && (
              <a
                href={`https://www.youtube.com/shorts/${heroVideo.youtube_video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-purple-600 hover:underline inline-flex items-center gap-1 mt-2"
              >
                YouTube'da aç <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </DialogContent>
        </Dialog>
      )}
    </motion.div>
  );
}


function ThreadDetailsPanel({ drafts, activeDraft }) {
  const [open, setOpen] = useState(false);
  // Source meta + insight are identical across the platform-variants of the
  // same thread, so use the first available one.
  const sourceMeta = drafts.find((d) => d.source_meta?.url || d.source_meta?.snippet)?.source_meta || null;
  const insight = drafts.find((d) => d.insight)?.insight || null;
  // Image meta = Visual Director's reasoning. Prefer the active platform's
  // image when it has one (different platforms can share or have distinct
  // visuals).
  const imageMeta = activeDraft?.image_meta
    || drafts.find((d) => d.image_meta)?.image_meta
    || null;
  const contentType = activeDraft?.content_type || drafts.find((d) => d.content_type)?.content_type || null;
  const voiceMode = activeDraft?.voice_mode || drafts.find((d) => d.voice_mode)?.voice_mode || null;
  const trendTopic = drafts[0]?.trend_topic || null;
  const hasAny = sourceMeta || insight || imageMeta || contentType || voiceMode;
  if (!hasAny) return null;
  return (
    <div className="border-t border-border bg-secondary/5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2 flex items-center justify-between text-[11px] text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="inline-flex items-center gap-1.5">
          <Lightbulb className="h-3 w-3" />
          {open ? "Detayları gizle" : "Haber kaynağı + agent'ların kararları"}
        </span>
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-3 text-xs">
          {/* Strategist — content_type + voice mode */}
          {(contentType || voiceMode) && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                🧭 Strategist
              </p>
              <div className="flex flex-wrap gap-1.5">
                {contentType && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/20">
                    content_type: {contentType}
                  </span>
                )}
                {voiceMode && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-500/20">
                    voice: {voiceMode}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* TrendScout — source + snippet */}
          {(sourceMeta || trendTopic) && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                📡 TrendScout — haber kaynağı
              </p>
              {trendTopic && (
                <p className="text-foreground/90 font-medium leading-snug">{trendTopic}</p>
              )}
              {sourceMeta?.snippet && (
                <p className="text-muted-foreground italic leading-relaxed border-l-2 border-purple-500/30 pl-2">
                  "{sourceMeta.snippet}"
                </p>
              )}
              {sourceMeta?.url && (
                <a
                  href={sourceMeta.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-purple-600 dark:text-purple-400 hover:underline text-[11px]"
                >
                  <ExternalLink className="h-3 w-3" />
                  {sourceMeta.type && (
                    <span className="font-mono text-muted-foreground">[{sourceMeta.type}]</span>
                  )}
                  <span>{sourceMeta.name || "Kaynağı aç"}</span>
                </a>
              )}
            </div>
          )}

          {/* Writer — insight */}
          {insight && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                ✍️ Writer — temel argüman
              </p>
              <p className="text-foreground/90 italic leading-relaxed border-l-2 border-amber-500/40 pl-2">
                {insight}
              </p>
            </div>
          )}

          {/* Visual Director — image LLM verdict */}
          {imageMeta && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                🎨 Visual Director — görsel kararı
              </p>
              <div className="flex flex-wrap gap-1.5">
                {imageMeta.model && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-secondary/60 border border-border/40">
                    model: {imageMeta.model.split("/").pop()}
                  </span>
                )}
                {imageMeta.llm_verdict && (
                  <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono border ${
                    imageMeta.llm_verdict === "pass"
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"
                      : imageMeta.llm_verdict === "fail"
                      ? "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30"
                      : "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30"
                  }`}>
                    verdict: {imageMeta.llm_verdict}
                  </span>
                )}
                {imageMeta.clip_similarity != null && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-secondary/60 border border-border/40">
                    clip: {Number(imageMeta.clip_similarity).toFixed(2)}
                  </span>
                )}
                {imageMeta.aesthetic_score != null && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-secondary/60 border border-border/40">
                    aesthetic: {Number(imageMeta.aesthetic_score).toFixed(2)}
                  </span>
                )}
                {imageMeta.cost_usd != null && (
                  <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono bg-secondary/60 border border-border/40">
                    ${Number(imageMeta.cost_usd).toFixed(3)}
                  </span>
                )}
              </div>
              {imageMeta.llm_reasoning && (
                <p className="text-muted-foreground italic leading-relaxed border-l-2 border-rose-500/30 pl-2 mt-1">
                  {imageMeta.llm_reasoning}
                </p>
              )}
            </div>
          )}

          {/* Compliance — confidence score */}
          {activeDraft?.confidence_score != null && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                <ShieldCheck className="inline h-3 w-3 mr-0.5" />
                Compliance — güven skoru
              </p>
              <p className="text-foreground/90 font-mono">
                {Number(activeDraft.confidence_score).toFixed(2)}
                <span className="text-muted-foreground ml-2 text-[10px]">
                  (son 30 günde bu content_type için ortalama)
                </span>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
