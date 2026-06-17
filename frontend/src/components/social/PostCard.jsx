import { useState } from "react";
import { motion } from "framer-motion";
import { Clock, ExternalLink, Pencil, Trash2, AlertTriangle, CheckCircle2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import PlatformIcon, { platformLabel } from "./PlatformIcon";
import { cancelPost } from "@/services/postizService";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogAction, AlertDialogCancel,
} from "@/components/ui/alert-dialog";

// Phase 36 — Premium glassmorphism post card.
// Premium dark mode + sky-500/indigo-600 accent identity for the Social page.

function StatusBadge({ status }) {
  const map = {
    scheduled:  { Icon: Clock,         className: "bg-amber-500/15 text-amber-400 border-amber-500/25",    label: "Planlı" },
    draft:      { Icon: Pencil,        className: "bg-zinc-500/15 text-zinc-300 border-zinc-500/25",       label: "Taslak" },
    published:  { Icon: CheckCircle2,  className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25", label: "Yayında" },
    failed:     { Icon: AlertTriangle, className: "bg-rose-500/15 text-rose-400 border-rose-500/25",       label: "Hata" },
    processing: { Icon: Sparkles,      className: "bg-sky-500/15 text-sky-400 border-sky-500/25",          label: "İşleniyor" },
  };
  const spec = map[status] || map.draft;
  const { Icon, className, label } = spec;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10.5px] font-semibold uppercase tracking-wider border ${className}`}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

function formatWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = Date.now();
  const diffMs = d.getTime() - now;
  const absMin = Math.round(Math.abs(diffMs) / 60000);
  const future = diffMs > 0;
  if (absMin < 1)  return future ? "şimdi" : "az önce";
  if (absMin < 60) return future ? `${absMin} dk sonra` : `${absMin} dk önce`;
  const h = Math.round(absMin / 60);
  if (h < 24)      return future ? `${h} saat sonra` : `${h} saat önce`;
  const day = Math.round(h / 24);
  if (day < 7)     return future ? `${day} gün sonra` : `${day} gün önce`;
  return d.toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}

function fullDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("tr-TR", {
    dateStyle: "long",
    timeStyle: "short",
    hour12: false,
  });
}

export default function PostCard({ post, onEdit, onCancelled }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const integrationName = post.integration?.name || platformLabel(post.platform);
  const integrationPic = post.integration?.picture;
  // Media detection — Postiz returns media in `media`, `image`, or as
  // nested objects under value[0].image. Walk multiple shapes; tolerate
  // both arrays and single-objects. (Audit 6 Haz 2026: video drafts
  // returned nothing because the UI only checked `media` array shape.)
  const mediaArray = (() => {
    if (Array.isArray(post.media) && post.media.length) return post.media;
    if (Array.isArray(post.image) && post.image.length) return post.image;
    // Sometimes Postiz returns post.value = [{image:[{path}]}]
    const v = Array.isArray(post.value) ? post.value[0] : null;
    if (v && Array.isArray(v.image) && v.image.length) return v.image;
    if (v && Array.isArray(v.media) && v.media.length) return v.media;
    return [];
  })();
  const firstMediaUrl = mediaArray[0]?.path || mediaArray[0]?.url || null;
  const isVideo = (() => {
    if (!firstMediaUrl) return false;
    const url = String(firstMediaUrl).toLowerCase().split("?")[0];
    return url.endsWith(".mp4") || url.endsWith(".mov") || url.endsWith(".webm")
            || url.endsWith(".m4v");
  })();
  const isEditable = post.status === "scheduled" || post.status === "draft";

  async function handleCancel() {
    setBusy(true);
    try {
      await cancelPost(post.id);
      toast.success("Post iptal edildi");
      setConfirmOpen(false);
      onCancelled?.(post.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "İptal edilemedi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      className="relative rounded-2xl border border-border/50 bg-card/90 backdrop-blur-xl p-5 hover:border-sky-500/40 transition-colors"
    >
      {/* Top bar */}
      <div className="flex items-center gap-2.5 mb-3">
        <div className="relative">
          {integrationPic ? (
            <img
              src={integrationPic}
              alt={integrationName}
              className="h-9 w-9 rounded-xl object-cover ring-1 ring-border/60"
            />
          ) : (
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-sky-500/30 to-indigo-500/30 flex items-center justify-center">
              <PlatformIcon identifier={post.platform} className="h-4 w-4" />
            </div>
          )}
          <div className="absolute -bottom-0.5 -right-0.5 rounded-full bg-card border border-border p-0.5">
            <PlatformIcon identifier={post.platform} className="h-3 w-3" />
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold leading-none truncate">{integrationName}</p>
            <StatusBadge status={post.status} />
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground" title={fullDateTime(post.scheduled_at)}>
            <Clock className="h-3 w-3" />
            <span>{formatWhen(post.scheduled_at)}</span>
            <span className="text-muted-foreground/50">·</span>
            <span className="font-mono">{fullDateTime(post.scheduled_at)}</span>
          </div>
        </div>
      </div>

      {/* Content */}
      {post.content && (
        <p className="text-[13.5px] leading-relaxed text-foreground/90 whitespace-pre-wrap break-words mb-3 max-h-40 overflow-hidden relative">
          {post.content}
          {post.content.length > 280 && (
            <span className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-card/95 to-transparent pointer-events-none" />
          )}
        </p>
      )}

      {/* Media — video uses <video controls>, image uses <img> */}
      {firstMediaUrl && (
        <div className="mb-3 rounded-xl overflow-hidden border border-border/40 bg-secondary/20">
          {isVideo ? (
            <video
              src={firstMediaUrl}
              controls
              preload="metadata"
              className="w-full max-h-56 object-contain bg-black"
            />
          ) : (
            <img
              src={firstMediaUrl}
              alt=""
              className="w-full max-h-56 object-cover"
              onError={(e) => { e.currentTarget.style.display = "none"; }}
            />
          )}
        </div>
      )}

      {/* Error */}
      {post.status === "failed" && post.error && (
        <div className="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300 flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span className="truncate">{post.error}</span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        {post.release_url && (
          <a
            href={post.release_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-secondary/40 hover:bg-secondary/60 border border-border/40 transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            Aç
          </a>
        )}
        {isEditable && (
          <>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs gap-1.5 border-sky-500/30 text-sky-300 hover:bg-sky-500/10"
              onClick={() => onEdit?.(post)}
            >
              <Pencil className="h-3 w-3" />
              Düzenle
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs gap-1.5 border-rose-500/30 text-rose-300 hover:bg-rose-500/10"
              onClick={() => setConfirmOpen(true)}
            >
              <Trash2 className="h-3 w-3" />
              İptal et
            </Button>
          </>
        )}
      </div>

      {/* Cancel confirm */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Postu iptal et?</AlertDialogTitle>
            <AlertDialogDescription>
              {post.status === "scheduled"
                ? "Bu post planlanan zamanda yayınlanmayacak. Bu işlem geri alınamaz."
                : "Bu taslak post silinecek. Bu işlem geri alınamaz."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Vazgeç</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleCancel();
              }}
              disabled={busy}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {busy ? "İptal ediliyor..." : "İptal et"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </motion.div>
  );
}
