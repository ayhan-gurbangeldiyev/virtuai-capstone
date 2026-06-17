/**
 * Phase 28.P — IterationDialog: Stacked Chat refinement loop.
 *
 * Akış:
 *   v1 (orijinal) → reddet/feedback → v2 (LLM) → reddet → v3 ... → onayla
 *   max 10 iterasyon, sonra "manuel düzelt" fallback
 *
 * Bu dialog mevcut RejectDialog'u TAMAMLAR (rakip değil):
 *   - "Hemen reddet" (single-shot, no iteration) → RejectDialog
 *   - "İteratif düzelt" (loop until happy) → IterationDialog (bu dosya)
 *
 * Edge-case korumaları (critic):
 *   - localStorage feedback backup (network fail = data preserved)
 *   - Double-submit guard (multiple iterations on rapid clicks)
 *   - Max attempts UI gate
 *   - Approve marks LATEST pending iteration (server-enforced)
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Check, X, RotateCw, Sparkles, Loader2, AlertTriangle, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { iterateDraft, getDraftIterations, getImageRegenJob } from "@/services/hypeService";
import { timeAgo, REJECT_CATEGORY_LABELS } from "./lib/userNames";

const MAX_ITERATIONS = 10;

// Same category set as RejectDialog (consistent UX)
// Phase 28.R-Lite-V2 Sprint 1 — sounds_like_ai bucket'ı 3 alt kategoriye
// ayrıldı. Critic agent analysis: %70 yanlış sinyal (haber yanlış, yapı
// sorunu, ton steril). Bu ayırım Strategist'in doğru kuralı öğrenmesi için
// kritik. Eski 'sounds_like_ai' geriye uyumluluk için tutuldu.
const CATEGORIES = [
  { key: "too_long", label: "Çok uzun" },
  { key: "too_short", label: "Çok kısa" },
  { key: "tone_too_harsh", label: "Ton sert" },
  { key: "tone_too_corporate", label: "Ton kurumsal" },
  // Granular AI complaints (Sprint 1)
  { key: "haber_yanlis_aktarim", label: "Haber yanlış" },
  { key: "yapi_sorunu_ozet_yorum", label: "Yorum yok, özet" },
  { key: "ton_steril_ai_kelime", label: "AI sözcük" },
  // Legacy bucket (kept for backwards compat in memory + old rows)
  { key: "sounds_like_ai", label: "AI gibi (genel)" },
  { key: "shallow_insight", label: "Yüzeysel" },
  { key: "weak_hook", label: "Kanca zayıf" },
  { key: "off_voice", label: "Ses uyumsuz" },
  { key: "other", label: "Diğer" },
];

const CATEGORY_TO_TAGS = {
  too_long: ["shorter"],
  too_short: ["longer"],
  tone_too_harsh: ["softer"],
  tone_too_corporate: ["casual"],
  haber_yanlis_aktarim: ["accurate_news"],
  yapi_sorunu_ozet_yorum: ["add_commentary", "less_summary"],
  ton_steril_ai_kelime: ["casual"],
  sounds_like_ai: ["casual"],
  shallow_insight: ["informative"],
  weak_hook: ["add_hook", "different_opening"],
};

const THINKING_MESSAGES = [
  "Cansu düşünüyor…",
  "Fikir geliyor…",
  "Son dokunuş…",
];

// Phase 28.Q — Unified scope picker (was a separate "Sadece görsel kötü" button)
const SCOPES = [
  { key: "text", label: "Sadece metin", hint: "Görsel iyi, metin yeniden yazılsın" },
  { key: "image", label: "Sadece görsel", hint: "Metin iyi, görsel yeniden üretilsin" },
  { key: "both", label: "İkisi de", hint: "Hem metin hem görsel" },
];

export default function IterationDialog({ draft, open, onClose, onApprove, onReject, initialScope = "text" }) {
  const { t } = useTranslation();
  const [versions, setVersions] = useState([]); // [{version, content, status, rejection_*, cost_usd, tokens}]
  const [scope, setScope] = useState(initialScope); // Phase 28.Q
  const [category, setCategory] = useState("other");
  const [feedback, setFeedback] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [thinkingMsgIdx, setThinkingMsgIdx] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [imageJob, setImageJob] = useState(null); // Sprint 1B — {id, status, image_url, error}
  // Phase 43.B.4 — anchor-preserve regen UI state. User pastes verbatim
  // text spans (one per line) they want carried byte-for-byte into the
  // next iteration. Backend wraps each in <PRESERVE_VERBATIM> and checks
  // compliance, returning preserve_stats so we can warn on misses.
  const [preserveOpen, setPreserveOpen] = useState(false);
  const [preserveText, setPreserveText] = useState("");
  const [preserveStats, setPreserveStats] = useState(null);
  const scrollRef = useRef(null);

  // ── Hydrate from draft on open ──
  // Phase 28.R-Lite — Two stages:
  //   1. Optimistic hydrate from draft.iterations prop (instant render)
  //   2. Server re-fetch via GET /drafts/{id}/iterations (overwrites with truth)
  // This fixes the "kapatınca değişiklik unutuluyor" bug: when the dialog
  // re-opens after a previous /iterate call, the parent draft card's
  // iterations array is stale (list endpoint was cached at fetch time).
  useEffect(() => {
    if (!open || !draft) return;

    // Stage 1 — optimistic from prop
    if (Array.isArray(draft.iterations) && draft.iterations.length > 0) {
      setVersions(draft.iterations);
    } else {
      setVersions([{
        version: 1,
        content: draft.content,
        status: "pending",
        rejection_category: null,
        rejection_feedback: null,
      }]);
    }
    setCategory("other");
    setScope(initialScope);
    setError(null);

    // Restore unsaved feedback from localStorage (critic recommendation)
    const saved = localStorage.getItem(`iter_fb_${draft.id}`);
    if (saved) {
      try {
        const p = JSON.parse(saved);
        setCategory(p.category || "other");
        setFeedback(p.text || "");
      } catch { /* ignore */ }
    } else {
      setFeedback("");
    }

    // Stage 2 — server-side truth (Phase 28.R-Lite persistence bug fix)
    let cancelled = false;
    getDraftIterations(draft.id)
      .then((res) => {
        if (cancelled) return;
        if (Array.isArray(res?.iterations) && res.iterations.length > 0) {
          setVersions(res.iterations);
        }
      })
      .catch(() => {
        // Network fail = keep optimistic state; user can still iterate.
      });
    return () => { cancelled = true; };
  }, [open, draft, initialScope]);

  // Persist feedback while typing (recovery on network drop)
  useEffect(() => {
    if (!open || !draft) return;
    if (!feedback && category === "other") return;
    localStorage.setItem(
      `iter_fb_${draft.id}`,
      JSON.stringify({ category, text: feedback })
    );
  }, [category, feedback, open, draft]);

  // Auto-scroll to bottom when new version arrives
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [versions.length]);

  // Cycle "Cansu düşünüyor" message during load
  useEffect(() => {
    if (!isLoading) return;
    const interval = setInterval(() => {
      setThinkingMsgIdx((i) => (i + 1) % THINKING_MESSAGES.length);
    }, 1500);
    return () => clearInterval(interval);
  }, [isLoading]);

  // Sprint 1B + V2 backlog #1 — Adaptive polling backoff.
  // Wiro generation is empirically ~90-130s. We poll fast at the start
  // (when completion COULD happen) and back off after each miss to limit
  // request volume when multiple dialogs are open simultaneously. Stops
  // automatically on completed/failed.
  useEffect(() => {
    if (!imageJob?.id) return;
    if (imageJob.status === "completed" || imageJob.status === "failed") return;
    let cancelled = false;
    let timeoutId = null;
    let attempt = 0;
    // 4s, 4s, 6s, 8s, 12s, 16s, 24s, 30s, 30s, ... (cap at 30s)
    const intervalForAttempt = (n) => {
      const ladder = [4000, 4000, 6000, 8000, 12000, 16000, 24000];
      return ladder[Math.min(n, ladder.length - 1)] || 30000;
    };
    const poll = async () => {
      try {
        const job = await getImageRegenJob(imageJob.id);
        if (cancelled) return;
        setImageJob((prev) => prev ? { ...prev, ...job } : job);
        if (job.status === "completed" && job.image_url) {
          setVersions((prev) => prev.map((v) =>
            v.version === imageJob.new_version
              ? { ...v, image_url: job.image_url, image_asset_id: job.image_asset_id }
              : v
          ));
        } else if (job.status !== "completed" && job.status !== "failed") {
          attempt += 1;
          timeoutId = setTimeout(poll, intervalForAttempt(attempt));
        }
      } catch {
        if (!cancelled) timeoutId = setTimeout(poll, 12000); // back off harder on error
      }
    };
    timeoutId = setTimeout(poll, 2000); // initial 2s warmup
    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [imageJob?.id, imageJob?.status, imageJob?.new_version]);

  const latestVersion = versions[versions.length - 1];
  const iterationCount = versions.length;
  const remainingAttempts = MAX_ITERATIONS - iterationCount;
  const maxReached = iterationCount >= MAX_ITERATIONS;
  const hasFeedback = (feedback || "").trim().length > 0 || category !== "other";

  // ── Iterate (LLM call) ─────────────────────────────────────────────
  const handleIterate = useCallback(async () => {
    if (!draft || isLoading || isApproving) return;
    if (!hasFeedback) {
      toast.error("Önce bir kategori seç veya not yaz");
      return;
    }
    if (maxReached) return;

    setIsLoading(true);
    setError(null);
    setPreserveStats(null);
    try {
      const tags = CATEGORY_TO_TAGS[category] || [];
      // Phase 43.B.4 — split textarea by newlines; ignore empties; cap 8.
      const preserved = preserveText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 8);
      const res = await iterateDraft(draft.id, {
        rejection_category: category,
        rejection_feedback: feedback,
        rejection_target: scope, // Phase 28.Q — user-selected scope (text/image/both)
        quick_tags: tags,
        preserve_user_edits: preserved.length > 0,
        preserved_segments: preserved,
      });
      if (res?.preserve_stats && Object.keys(res.preserve_stats).length > 0) {
        setPreserveStats(res.preserve_stats);
      }
      // Server returns full updated iterations array
      if (Array.isArray(res.iterations)) {
        setVersions(res.iterations);
      } else {
        // Fallback: append new version
        setVersions((prev) => [
          ...prev.map((v, idx) => idx === prev.length - 1
            ? { ...v, status: "rejected", rejection_category: category, rejection_feedback: feedback }
            : v),
          { version: res.version, content: res.content, status: "pending", tokens_used: res.tokens_used, cost_usd: res.cost_usd },
        ]);
      }
      // Sprint 1B — kick off image regen polling if a job was queued
      if (res.image_job_id) {
        setImageJob({ id: res.image_job_id, status: "queued", new_version: res.version });
      }
      // Clear feedback form for next iteration
      setCategory("other");
      setFeedback("");
      localStorage.removeItem(`iter_fb_${draft.id}`);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || err.message;
      if (status === 409 && String(detail).startsWith("max_iterations")) {
        setError("max_iterations");
        toast.error("10 deneme tamamlandı. Bu versiyonu onayla ya da manuel düzenle.");
      } else if (status === 409 && detail === "iteration_race") {
        toast.error("Aynı anda başka biri denedi. Lütfen tekrar dene.");
      } else {
        setError(detail || "İterasyon başarısız");
        toast.error(`Hata: ${detail || "bilinmeyen"}`);
      }
    } finally {
      setIsLoading(false);
    }
  }, [draft, isLoading, isApproving, hasFeedback, maxReached, category, feedback, scope]);

  // ── Approve (mark latest version as final) ─────────────────────────
  const handleApprove = useCallback(async () => {
    if (!draft || isLoading || isApproving) return;
    setIsApproving(true);
    try {
      // approve_draft already handles iteration → daily_drafts.content sync
      // (Phase 28.P backend change). Just call the existing onApprove handler.
      await onApprove();
      localStorage.removeItem(`iter_fb_${draft.id}`);
      onClose();
    } catch (err) {
      toast.error(err?.message || "Onay başarısız");
    } finally {
      setIsApproving(false);
    }
  }, [draft, isLoading, isApproving, onApprove, onClose]);

  // Keyboard shortcuts (Cmd/Ctrl+Enter = approve, Enter = iterate when in textarea isn't focused)
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      const inTextarea = document.activeElement?.tagName === "TEXTAREA";
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleApprove();
      } else if (e.key === "Enter" && !inTextarea && !maxReached && hasFeedback) {
        e.preventDefault();
        handleIterate();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, maxReached, hasFeedback, handleIterate, handleApprove]);

  if (!draft) return null;

  // Split versions for stacked layout: always show last 2 in full,
  // collapse older into accordion.
  const visibleTail = versions.slice(-2);
  const collapsedHistory = versions.slice(0, -2);

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-5 py-3 border-b border-border/40 flex-row items-center justify-between space-y-0">
          <DialogTitle className="text-base font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-500" />
            Taslağı Geliştir
          </DialogTitle>
          <span className={cn(
            "text-[11px] font-mono px-2 py-0.5 rounded-md border",
            maxReached
              ? "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30"
              : "bg-secondary/60 text-muted-foreground border-border/40",
          )}
            title={`Bu taslağın ${iterationCount}. deneme versiyonu. En fazla 10 deneme yapılabilir.`}
          >
            v{iterationCount} / {MAX_ITERATIONS}
          </span>
        </DialogHeader>

        <div className="flex-1 px-5 py-4 overflow-y-auto" ref={scrollRef}>
          <div className="space-y-3">
            {/* Collapsed older history */}
            {collapsedHistory.length > 0 && (
              <button
                onClick={() => setHistoryOpen(!historyOpen)}
                className="w-full text-left text-xs text-muted-foreground hover:text-foreground px-3 py-2 border border-dashed border-border/40 rounded-xl bg-secondary/10 transition-colors flex items-center gap-2"
              >
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", historyOpen && "rotate-180")} />
                Önceki {collapsedHistory.length} deneme
              </button>
            )}
            {historyOpen && collapsedHistory.map((v) => (
              <VersionCard key={v.version} version={v} dimmed expanded />
            ))}

            {/* Always-visible recent versions */}
            {visibleTail.map((v, idx) => (
              <VersionCard
                key={v.version}
                version={v}
                dimmed={idx < visibleTail.length - 1}
                isLatest={idx === visibleTail.length - 1}
                imageJob={
                  imageJob && imageJob.new_version === v.version ? imageJob : null
                }
              />
            ))}

            {/* Loading skeleton for next version */}
            {isLoading && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-purple-500/20 bg-card/50 p-4 border-l-4 border-l-purple-400/50"
              >
                <Skeleton className="h-3 w-full mb-2" />
                <Skeleton className="h-3 w-4/5 mb-2" />
                <Skeleton className="h-3 w-3/5" />
                <p className="text-[11px] italic text-purple-500/70 mt-3 flex items-center gap-1.5">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {THINKING_MESSAGES[thinkingMsgIdx]}
                </p>
              </motion.div>
            )}

            {/* Error inline */}
            {error && error !== "max_iterations" && (
              <div className="rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-sm p-3 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">{error}</p>
                  <button onClick={handleIterate} className="text-xs underline mt-1">Tekrar dene</button>
                </div>
              </div>
            )}

            {/* Max reached banner */}
            {maxReached && (
              <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-sm p-3 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <p>
                  10 denemenin tamamı kullanıldı. Bu versiyonu onayla ya da manuel düzenle (yakında).
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Sticky feedback panel */}
        {!maxReached && (
          <div className="border-t border-border/40 bg-background/95 backdrop-blur px-5 py-3 space-y-2.5">
            {/* Phase 28.Q — Scope picker (replaces standalone "Sadece görsel kötü" button) */}
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">
                Ne değişmeli?
              </p>
              <div className="grid grid-cols-3 gap-1.5">
                {SCOPES.map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setScope(s.key)}
                    disabled={isLoading}
                    title={s.hint}
                    className={cn(
                      "px-2 py-1.5 rounded-md text-[11px] border transition-colors text-center",
                      scope === s.key
                        ? "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/50 font-medium"
                        : "bg-secondary/40 text-muted-foreground border-border/40 hover:bg-secondary/60",
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              {/* Phase 28.R-Lite Sprint 1B — image regen aktif. Bilgi mesajı: ~30-60sn sürer */}
              {(scope === "image" || scope === "both") && (
                <div className="mt-2 flex items-start gap-1.5 text-[10px] text-purple-600 dark:text-purple-400 leading-tight">
                  <Sparkles className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>
                    Görsel arka planda yeniden üretiliyor (~30-60sn). Yeni metin hemen
                    gelir, görsel hazır olunca otomatik kartta görünür.
                  </span>
                </div>
              )}
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1.5">
                Sebep
              </p>
              <div className="flex flex-wrap gap-1.5">
                {CATEGORIES.map((c) => (
                  <button
                    key={c.key}
                    onClick={() => setCategory(c.key)}
                    disabled={isLoading}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-[11px] border transition-colors",
                      category === c.key
                        ? "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/40"
                        : "bg-secondary/40 text-muted-foreground border-border/40 hover:bg-secondary/60",
                    )}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            <Textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Bir sonraki deneme için ne değişsin? (opsiyonel)"
              rows={2}
              maxLength={500}
              disabled={isLoading}
              className="text-sm resize-none"
            />

            {/* Phase 43.B.4 — Anchor-preserve regen ("Şu cümleyi koru")
                Only meaningful for text/both scope; image-only ignores it. */}
            {scope !== "image" && (
              <div className="rounded-md border border-border bg-card/50">
                <button
                  type="button"
                  onClick={() => setPreserveOpen((v) => !v)}
                  disabled={isLoading}
                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-[11px] text-muted-foreground hover:text-foreground transition"
                >
                  <span className="inline-flex items-center gap-1.5">
                    🔒 Şu cümleleri koru (opsiyonel)
                    {preserveText.trim() && (
                      <span className="text-emerald-600 dark:text-emerald-400 font-mono">
                        {
                          preserveText
                            .split("\n")
                            .filter((s) => s.trim())
                            .length
                        }
                      </span>
                    )}
                  </span>
                  <ChevronDown
                    className={`h-3.5 w-3.5 transition-transform ${preserveOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {preserveOpen && (
                  <div className="border-t border-border/60 p-3 space-y-1.5">
                    <Textarea
                      value={preserveText}
                      onChange={(e) => setPreserveText(e.target.value)}
                      placeholder={
                        "Her satıra bir cümle / ifade yaz, model bunları aynen koruyacak.\nÖrnek:\nGerçekten akıllanıyor mu?\nHype değil ölçüm konuşur."
                      }
                      rows={3}
                      maxLength={2000}
                      disabled={isLoading}
                      className="text-xs resize-none font-mono"
                    />
                    <p className="text-[10px] text-muted-foreground/70">
                      Maks 8 cümle. Boş bırakırsan koruma kapalı kalır. Modelin
                      ne kadarını koruyabildiği üstte yazar.
                    </p>
                  </div>
                )}
                {preserveStats && (
                  <div
                    className={`border-t border-border/60 px-3 py-2 text-[11px] ${
                      preserveStats.success_rate >= 0.7
                        ? "text-emerald-600 dark:text-emerald-400"
                        : preserveStats.success_rate >= 0.4
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-rose-600 dark:text-rose-400"
                    }`}
                  >
                    {preserveStats.preserved}/{preserveStats.requested} cümle korundu
                    {preserveStats.lost > 0 && preserveStats.miss_samples?.length > 0 && (
                      <span className="ml-1 opacity-70">
                        ({preserveStats.lost} kayboldu)
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            <p className="text-[10px] text-muted-foreground/60">
              Kaldı: <span className="font-mono">{remainingAttempts}</span> deneme
            </p>
          </div>
        )}

        <DialogFooter className="border-t border-border/40 px-5 py-3 flex-row justify-between items-center gap-2">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={isLoading || isApproving}>
              <X className="h-4 w-4 mr-1.5" />
              Vazgeç
            </Button>
            {onReject && (
              <button
                type="button"
                onClick={() => {
                  // Phase 41.A — window.confirm REMOVED. Parent handler (handleIterationReject
                  // in AutoDraftsPage) wraps the call in safeAction → 5sn undo snackbar.
                  // Berkay yanlış tıklarsa "Geri Al" ile kart geri gelir.
                  onReject({
                    category: category !== "other" ? category : "other",
                    feedback: feedback || `${iterationCount} deneme sonrası vazgeçildi`,
                    rejection_target: "text",
                  });
                  localStorage.removeItem(`iter_fb_${draft.id}`);
                  onClose();
                }}
                disabled={isLoading || isApproving}
                className="text-[11px] text-muted-foreground hover:text-rose-600 dark:hover:text-rose-400 underline-offset-2 hover:underline disabled:opacity-40"
                title="Bu taslağı reddet — 5 saniye içinde geri alabilirsin"
              >
                Tamamen sil
              </button>
            )}
          </div>
          <div className="flex gap-2">
            {!maxReached && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleIterate}
                disabled={isLoading || isApproving || !hasFeedback}
                className="border-purple-500/40 hover:bg-purple-500/10 hover:text-purple-700 dark:hover:text-purple-300"
                title={!hasFeedback ? "Önce kategori seç veya not yaz" : "Tekrar dene"}
              >
                {isLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <RotateCw className="h-4 w-4 mr-1.5" />}
                Tekrar dene
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleApprove}
              disabled={isLoading || isApproving}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isApproving ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Check className="h-4 w-4 mr-1.5" />}
              Bu versiyonu onayla
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function VersionCard({ version, dimmed = false, expanded = false, isLatest = false, imageJob = null }) {
  const showFeedback = version.rejection_category || version.rejection_feedback;
  const isImageProcessing = imageJob && (imageJob.status === "queued" || imageJob.status === "processing");
  const imageFailed = imageJob && imageJob.status === "failed";
  // V2 backlog #8 — completed with quality warning. Backend embeds
  // compliance_verdict=FAIL in job.error when LLM judge flagged issues
  // (deformed hand, fake logo, etc). Image is still shown — user may
  // still want to use it — but with a clear warning so they can re-iterate.
  const hasQualityWarning =
    imageJob &&
    imageJob.status === "completed" &&
    imageJob.error &&
    String(imageJob.error).startsWith("compliance_verdict=FAIL");
  const warningText = hasQualityWarning
    ? String(imageJob.error).replace(/^compliance_verdict=FAIL:\s*/, "").slice(0, 180)
    : null;
  return (
    <div>
      <motion.div
        layout
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className={cn(
          "rounded-2xl border p-4 transition-all",
          isLatest
            ? "border-l-4 border-l-emerald-500 border-emerald-500/40 bg-card ring-1 ring-emerald-500/10"
            : "border-l-4 border-l-slate-400/40 border-border/40 bg-card",
        )}
        style={dimmed ? { filter: "saturate(0.3) opacity(0.6)" } : undefined}
      >
        <div className="flex items-center justify-between mb-2">
          <span className={cn(
            "text-[10px] font-mono px-1.5 py-0.5 rounded-md border",
            isLatest
              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"
              : "bg-secondary/60 text-muted-foreground border-border/40",
          )}>
            v{version.version}
          </span>
          {version.cost_usd != null && (
            <span className="text-[10px] font-mono text-muted-foreground/50">
              ${Number(version.cost_usd).toFixed(3)}
            </span>
          )}
        </div>
        {/* Sprint 1B — Image thumbnail (or regen progress placeholder) */}
        {(version.image_url || isImageProcessing || imageFailed) && (
          <div className={cn(
            "mb-3 relative rounded-xl overflow-hidden bg-secondary/40 border",
            hasQualityWarning ? "border-amber-500/40 ring-1 ring-amber-500/10" : "border-border/40"
          )}>
            {version.image_url && !isImageProcessing && (
              <img
                src={version.image_url}
                alt={`v${version.version} visual`}
                className={cn(
                  "w-full h-auto max-h-48 object-cover",
                  hasQualityWarning && "opacity-90"
                )}
                loading="lazy"
              />
            )}
            {/* V2 backlog #8 — compliance warning overlay (image still shown,
                user decides if quality issue is acceptable). */}
            {hasQualityWarning && version.image_url && !isImageProcessing && (
              <div className="absolute top-2 right-2 px-2 py-1 rounded-md bg-amber-500/90 text-white text-[10px] font-medium shadow-md backdrop-blur-sm flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                <span>kalite uyarısı</span>
              </div>
            )}
            {isImageProcessing && (
              <div className="aspect-[4/3] flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-purple-500/5 to-indigo-500/5">
                <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
                <p className="text-[11px] text-purple-700 dark:text-purple-300 font-medium">
                  Görsel üretiliyor…
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  {imageJob.status === "queued" ? "Sıra bekleniyor" : "Wiro + uyum kontrolü"}
                </p>
              </div>
            )}
            {imageFailed && (
              <div className="aspect-[4/3] flex flex-col items-center justify-center gap-2 bg-rose-500/5 border border-rose-500/20">
                <AlertTriangle className="h-5 w-5 text-rose-500" />
                <p className="text-[11px] text-rose-700 dark:text-rose-300 font-medium">
                  Görsel üretilemedi
                </p>
                <p className="text-[10px] text-muted-foreground/60 text-center px-3">
                  {imageJob.error?.slice(0, 80) || "Bilinmeyen hata"}
                </p>
              </div>
            )}
            {/* V2 backlog #8 — full warning detail row below image */}
            {hasQualityWarning && warningText && (
              <div className="px-3 py-2 bg-amber-500/10 border-t border-amber-500/30 flex items-start gap-1.5">
                <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                <p className="text-[10px] text-amber-800 dark:text-amber-200 italic leading-tight">
                  AI kalite kontrolü uyardı: {warningText}
                </p>
              </div>
            )}
          </div>
        )}
        <div className={cn(
          "text-sm whitespace-pre-wrap text-foreground/90",
          !expanded && !isLatest && "line-clamp-3"
        )}>
          {version.content}
        </div>
      </motion.div>

      {/* Feedback bubble — sits between this version and the next */}
      {showFeedback && (
        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex items-start gap-2 pl-3 mt-2"
        >
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border shrink-0 mt-0.5 bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/30">
            ✕ reddedildi
          </span>
          <div className="flex-1 rounded-xl rounded-tl-none bg-secondary/40 border border-border/40 px-3 py-2">
            {version.rejection_category && (
              <span className="inline-flex mr-1.5 mb-1 px-2 py-0.5 rounded-md text-[10px] bg-rose-500/10 text-rose-700 dark:text-rose-300 border border-rose-500/20">
                {REJECT_CATEGORY_LABELS[version.rejection_category] || version.rejection_category}
              </span>
            )}
            {version.rejection_feedback && (
              <p className="text-xs text-foreground/80 mt-1 italic">"{version.rejection_feedback}"</p>
            )}
            {version.rejected_at && (
              <p className="text-[10px] text-muted-foreground/50 mt-1">{timeAgo(version.rejected_at)}</p>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
