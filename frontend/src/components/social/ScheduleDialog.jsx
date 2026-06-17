import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { tr } from "date-fns/locale";
import { Calendar as CalIcon, Send, Loader2, Image as ImageIcon, X, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { schedulePost, updatePost, cancelPost, listIntegrations, uploadFromUrl } from "@/services/postizService";
import PlatformIcon, { platformLabel } from "./PlatformIcon";

// Phase 36 — Premium schedule/edit dialog.
//
// Tek dialog hem yeni post yaratmak hem mevcut post'u düzenlemek için.
// `mode === "edit"` ise group_id + integration_id + content prefill edilir.

const DEFAULT_DELAY_MIN = 60;

function buildDefaultDate() {
  const d = new Date();
  d.setMinutes(d.getMinutes() + DEFAULT_DELAY_MIN);
  d.setSeconds(0, 0);
  return d;
}

export default function ScheduleDialog({ open, onClose, mode = "create", initialPost = null, onSuccess }) {
  const [integrations, setIntegrations] = useState([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [selectedIntegration, setSelectedIntegration] = useState(null);
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(buildDefaultDate());
  const [time, setTime] = useState(() => format(buildDefaultDate(), "HH:mm"));
  const [mediaUrl, setMediaUrl] = useState("");
  const [mediaRef, setMediaRef] = useState(null);
  const [publishNow, setPublishNow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const isEdit = mode === "edit" && initialPost;

  // Hydrate when opened
  useEffect(() => {
    if (!open) return;
    setSubmitting(false);
    setUploading(false);
    setPublishNow(false);
    setMediaUrl("");
    if (isEdit) {
      setContent(initialPost.content || "");
      setTitle(initialPost.title || "");
      const initDate = initialPost.scheduled_at ? new Date(initialPost.scheduled_at) : buildDefaultDate();
      setDate(initDate);
      setTime(format(initDate, "HH:mm"));
      // Hydrate existing media from the post so the user can SEE it in
      // the detail dialog (6 Haz 2026 audit: previously the detail
      // dialog reset mediaRef to null even on edit, so video/image
      // attached to the schedule was invisible).
      const existingMedia = (() => {
        if (Array.isArray(initialPost.media) && initialPost.media.length) return initialPost.media[0];
        if (Array.isArray(initialPost.image) && initialPost.image.length) return initialPost.image[0];
        const v = Array.isArray(initialPost.value) ? initialPost.value[0] : null;
        if (v && Array.isArray(v.image) && v.image.length) return v.image[0];
        if (v && Array.isArray(v.media) && v.media.length) return v.media[0];
        return null;
      })();
      setMediaRef(existingMedia && (existingMedia.id || existingMedia.path) ? {
        id: existingMedia.id || "(existing)",
        path: existingMedia.path || existingMedia.url || "",
      } : null);
    } else {
      setMediaRef(null);
      setContent("");
      setTitle("");
      const d = buildDefaultDate();
      setDate(d);
      setTime(format(d, "HH:mm"));
    }
    let cancelled = false;
    setIntegrationsLoading(true);
    listIntegrations()
      .then((res) => {
        if (cancelled) return;
        const items = res?.items || [];
        setIntegrations(items);
        if (isEdit && initialPost.integration?.id) {
          const match = items.find((i) => i.id === initialPost.integration.id);
          setSelectedIntegration(match || items[0] || null);
        } else if (items.length) {
          setSelectedIntegration(items[0]);
        }
      })
      .catch(() => toast.error("Platformlar yüklenemedi"))
      .finally(() => { if (!cancelled) setIntegrationsLoading(false); });
    return () => { cancelled = true; };
  }, [open, isEdit, initialPost]);

  const platformIdentifier = selectedIntegration?.identifier || "x";
  const charLimit = useMemo(() => {
    const map = { x: 280, "linkedin-page": 3000, linkedin: 3000, instagram: 2200, devto: 50000, youtube: 5000 };
    return map[platformIdentifier] || 5000;
  }, [platformIdentifier]);
  const needsTitle = ["devto", "medium", "youtube"].includes(platformIdentifier);

  const scheduledAtIso = useMemo(() => {
    const [hh, mm] = (time || "00:00").split(":").map((s) => Number(s));
    const d = new Date(date);
    d.setHours(isNaN(hh) ? 0 : hh, isNaN(mm) ? 0 : mm, 0, 0);
    return d.toISOString();
  }, [date, time]);

  async function handleUploadMedia() {
    if (!mediaUrl) return;
    setUploading(true);
    try {
      const ref = await uploadFromUrl(mediaUrl);
      if (!ref?.id) throw new Error("upload yanıtı boş");
      setMediaRef(ref);
      toast.success("Görsel yüklendi");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Görsel yüklenemedi");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit() {
    if (!selectedIntegration) {
      toast.error("Platform seç");
      return;
    }
    if (!content.trim()) {
      toast.error("İçerik gerekli");
      return;
    }
    if (needsTitle && !title.trim()) {
      toast.error("Bu platform için başlık gerekli");
      return;
    }
    setSubmitting(true);
    const platformPost = {
      integration_id: selectedIntegration.id,
      provider: platformIdentifier,
      content: content.trim(),
      ...(title.trim() ? { title: title.trim() } : {}),
      ...(mediaRef ? { media: [{ id: mediaRef.id, path: mediaRef.path || "" }] } : {}),
    };
    try {
      if (isEdit) {
        if (!initialPost.group_id) throw new Error("Düzenlenecek postun group_id'si bulunamadı");
        await updatePost(initialPost.id, {
          group_id: initialPost.group_id,
          scheduled_at: scheduledAtIso,
          posts: [platformPost],
        });
        toast.success("Post güncellendi");
      } else {
        await schedulePost({
          scheduled_at: scheduledAtIso,
          posts: [platformPost],
          publish_now: publishNow,
        });
        toast.success(publishNow ? "Post yayınlandı" : "Post planlandı");
      }
      onSuccess?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (isEdit ? "Güncellenemedi" : "Planlanamadı"));
    } finally {
      setSubmitting(false);
    }
  }

  // Delete/cancel an existing scheduled post (calendar had no delete before).
  async function handleDelete() {
    if (!initialPost?.id) return;
    if (!window.confirm("Bu planlanmış post silinsin mi? Bu işlem geri alınamaz.")) return;
    setDeleting(true);
    try {
      await cancelPost(initialPost.id);
      toast.success("Post silindi");
      onSuccess?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Silinemedi");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !submitting && onClose?.()}>
      <DialogContent className="max-w-lg p-0 overflow-hidden bg-card/95 backdrop-blur-2xl border-border/60">
        <div className="p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-4 w-4 text-sky-400" />
              {isEdit ? "Postu Düzenle" : "Yeni Post"}
            </DialogTitle>
            <DialogDescription>
              {isEdit ? "İçeriği ve zamanı güncelleyebilirsin." : "Tüm sosyal medya hesaplarına aynı arayüzden post planla."}
            </DialogDescription>
          </DialogHeader>

          {/* Platform picker */}
          <div className="mt-5">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 block">
              Platform
            </label>
            {integrationsLoading ? (
              <div className="text-xs text-muted-foreground">Yükleniyor...</div>
            ) : integrations.length === 0 ? (
              <div className="text-xs text-muted-foreground">Bağlı platform yok</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {integrations.map((i) => {
                  const active = selectedIntegration?.id === i.id;
                  return (
                    <button
                      key={i.id}
                      type="button"
                      onClick={() => setSelectedIntegration(i)}
                      className={[
                        "inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-colors text-xs",
                        active
                          ? "border-sky-500/60 bg-sky-500/10 text-sky-200"
                          : "border-border/50 bg-secondary/30 hover:bg-secondary/50 text-foreground/80",
                      ].join(" ")}
                    >
                      <PlatformIcon identifier={i.identifier} className="h-3.5 w-3.5" />
                      <span className="font-medium">{i.name || platformLabel(i.identifier)}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Title (devto/medium/youtube) */}
          {needsTitle && (
            <div className="mt-4">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 block">
                Başlık
              </label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Post başlığı"
                className="bg-secondary/30 border-border/50"
                disabled={submitting}
              />
            </div>
          )}

          {/* Content */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                İçerik
              </label>
              <span className={`text-[11px] font-mono ${content.length > charLimit ? "text-rose-400" : "text-muted-foreground"}`}>
                {content.length} / {charLimit}
              </span>
            </div>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Ne paylaşmak istersin?"
              className="min-h-[160px] bg-secondary/30 border-border/50 font-medium"
              disabled={submitting}
            />
          </div>

          {/* Media URL */}
          <div className="mt-4">
            <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 block flex items-center gap-1">
              <ImageIcon className="h-3 w-3" />
              Görsel (URL ile)
            </label>
            <div className="flex gap-2">
              <Input
                value={mediaUrl}
                onChange={(e) => setMediaUrl(e.target.value)}
                placeholder="https://..."
                className="bg-secondary/30 border-border/50 flex-1"
                disabled={submitting || uploading}
              />
              <Button type="button" variant="outline" size="sm" onClick={handleUploadMedia} disabled={!mediaUrl || uploading || submitting} className="h-9">
                {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Yükle"}
              </Button>
            </div>
            {mediaRef && (
              <div className="mt-2">
                <div className="flex items-center gap-2 text-[11px] text-emerald-300 mb-2">
                  <ImageIcon className="h-3 w-3" />
                  <span className="truncate flex-1">Hazır: {mediaRef.id}</span>
                  <button type="button" onClick={() => setMediaRef(null)} className="hover:text-rose-300">
                    <X className="h-3 w-3" />
                  </button>
                </div>
                {mediaRef.path && (() => {
                  const url = String(mediaRef.path).toLowerCase().split("?")[0];
                  const isVid = url.endsWith(".mp4") || url.endsWith(".mov")
                                 || url.endsWith(".webm") || url.endsWith(".m4v");
                  return (
                    <div className="rounded-lg overflow-hidden border border-border/40 bg-black/60">
                      {isVid ? (
                        <video src={mediaRef.path} controls preload="metadata"
                                className="w-full max-h-48 object-contain bg-black" />
                      ) : (
                        <img src={mediaRef.path} alt=""
                              className="w-full max-h-48 object-cover"
                              onError={(e) => { e.currentTarget.style.display = "none"; }} />
                      )}
                    </div>
                  );
                })()}
              </div>
            )}
          </div>

          {/* Date + Time */}
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 block">
                Tarih
              </label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal bg-secondary/30 border-border/50 h-9" disabled={submitting || publishNow}>
                    <CalIcon className="h-3.5 w-3.5 mr-2" />
                    {format(date, "d MMMM yyyy", { locale: tr })}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0 bg-card border-border/60">
                  <Calendar mode="single" selected={date} onSelect={(d) => d && setDate(d)} locale={tr} initialFocus />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 block">
                Saat ({Intl.DateTimeFormat().resolvedOptions().timeZone || "yerel"})
              </label>
              <Input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="bg-secondary/30 border-border/50 font-mono"
                disabled={submitting || publishNow}
              />
            </div>
          </div>

          {/* Phase 39.9 — confirm parsed datetime back to the user so the
              UTC offset can't bite. Shows "Yayın: 31 May 2026, 18:50" in TR. */}
          {!publishNow && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Yayın: <span className="font-mono text-foreground/80">
                {format(new Date(scheduledAtIso), "d MMM yyyy, HH:mm", { locale: tr })}
              </span>
              <span className="ml-1 opacity-70">
                ({Intl.DateTimeFormat().resolvedOptions().timeZone || "yerel"})
              </span>
            </p>
          )}

          {/* Publish now */}
          {!isEdit && (
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-border/40 bg-secondary/20 p-3">
              <Switch
                checked={publishNow}
                onCheckedChange={setPublishNow}
                disabled={submitting}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">Şimdi yayınla</p>
                <p className="text-[11px] text-muted-foreground">
                  Açık olursa post planlanmaz, anında gönderilir.
                </p>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="bg-secondary/10 border-t border-border/40 px-6 py-4">
          {initialPost?.id && (
            <Button
              variant="ghost"
              onClick={handleDelete}
              disabled={submitting || deleting}
              className="mr-auto text-red-500 hover:text-red-400 hover:bg-red-500/10"
            >
              {deleting ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Sil
            </Button>
          )}
          <Button variant="outline" onClick={onClose} disabled={submitting || deleting}>
            Vazgeç
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || deleting || !selectedIntegration || !content.trim() || content.length > charLimit}
            className="bg-gradient-to-br from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white border-0 shadow-lg shadow-sky-500/20"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Send className="h-4 w-4 mr-2" />
            )}
            {isEdit ? "Güncelle" : publishNow ? "Yayınla" : "Planla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
