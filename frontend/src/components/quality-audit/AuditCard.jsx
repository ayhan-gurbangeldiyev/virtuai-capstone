/**
 * Phase 43.E.5 — AuditCard
 *
 * Renders a single pending audit: post preview (content + image + video),
 * platform badge, trend topic, scheduled_at relative; bottom action bar
 * with big Pass (emerald) + Fail (rose) buttons. Optimistic state: when
 * the parent flips `pending`, the card fades and disables.
 *
 * Pass is one-tap (no dialog). Fail opens FailDialog in the parent.
 */
import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle, PlayCircle, ExternalLink, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatRelativeTime, formatFullDateTime } from "./lib/time.js";

const PLATFORM_ACCENT = {
  twitter: "border-l-sky-500 bg-sky-500/5",
  x: "border-l-sky-500 bg-sky-500/5",
  instagram: "border-l-pink-500 bg-pink-500/5",
  linkedin: "border-l-blue-600 bg-blue-600/5",
  devto: "border-l-purple-500 bg-purple-500/5",
  youtube: "border-l-red-500 bg-red-500/5",
  tiktok: "border-l-rose-500 bg-rose-500/5",
};

const POSTIZ_DEFAULT_PREVIEW_PREFIX = "DRY_RUN_";

function platformPostUrl(snapshot) {
  if (!snapshot) return null;
  const pid = snapshot.postiz_post_id;
  if (!pid || pid.startsWith(POSTIZ_DEFAULT_PREVIEW_PREFIX)) return null;
  // We can't construct the real X/IG URL without per-platform username
  // mapping; Postiz dashboard link is the safest deep-link target.
  return `https://postiz.com/posts/${pid}`;
}

export default function AuditCard({
  audit,
  pending = false,            // parent toggles when optimistic update fires
  onPass,
  onFailClick,
}) {
  const { t } = useTranslation();
  const snapshot = audit?.draft_snapshot || null;
  const platformKey = String(snapshot?.platform || "").toLowerCase();
  const accent = PLATFORM_ACCENT[platformKey] || "border-l-foreground/30";

  const handlePass = () => {
    if (pending) return;
    onPass?.();
  };
  const handleFail = () => {
    if (pending) return;
    onFailClick?.();
  };

  const fullTime = formatFullDateTime(snapshot?.scheduled_at);
  const relTime = formatRelativeTime(snapshot?.scheduled_at);
  const postUrl = platformPostUrl(snapshot);

  return (
    <article
      className={cn(
        "relative rounded-2xl border bg-card p-5 border-l-4 transition-opacity",
        accent,
        pending && "opacity-60 pointer-events-none"
      )}
    >
      {/* Top bar */}
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="font-medium text-xs">
          {t(
            `qualityAudit.card.platforms.${platformKey}`,
            snapshot?.platform || "—"
          )}
        </Badge>
        {snapshot?.trend_topic && (
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground truncate max-w-[180px]">
            {snapshot.trend_topic}
          </span>
        )}
        {relTime && (
          <span
            className="ml-auto text-[11px] text-muted-foreground"
            title={fullTime || undefined}
          >
            {t("qualityAudit.card.scheduledRelative", { when: relTime })}
          </span>
        )}
      </header>

      {/* Body */}
      {snapshot ? (
        <div className="space-y-3">
          {snapshot.content && (
            <p className="text-sm leading-relaxed whitespace-pre-wrap line-clamp-6">
              {snapshot.content}
            </p>
          )}

          {snapshot.image_url && (
            <img
              src={snapshot.image_url}
              alt=""
              loading="lazy"
              className="w-full rounded-xl border border-border object-cover aspect-square max-h-72"
            />
          )}

          {snapshot.video_url && (
            <a
              href={snapshot.video_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-blue-500 hover:underline"
            >
              <PlayCircle className="h-4 w-4" />
              {t("qualityAudit.card.videoOpen")}
            </a>
          )}

          {postUrl && (
            <a
              href={postUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              {t("qualityAudit.card.postLink")}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      ) : (
        <div className="rounded-md bg-muted/40 p-3 text-xs text-muted-foreground flex items-start gap-2">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{t("qualityAudit.card.missing")}</span>
        </div>
      )}

      {/* Action bar */}
      <footer className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:gap-3">
        <Button
          onClick={handleFail}
          disabled={pending}
          variant="outline"
          className="w-full border-rose-500/40 text-rose-600 hover:bg-rose-500/10 h-11"
        >
          <XCircle className="mr-2 h-4 w-4" />
          {t("qualityAudit.card.failLabel")}
        </Button>
        <Button
          onClick={handlePass}
          disabled={pending}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white h-11"
        >
          <CheckCircle2 className="mr-2 h-4 w-4" />
          {t("qualityAudit.card.passLabel")}
        </Button>
      </footer>
    </article>
  );
}
