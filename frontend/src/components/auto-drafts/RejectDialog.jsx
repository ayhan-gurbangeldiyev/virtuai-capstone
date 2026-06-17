/**
 * RejectDialog — reject flow + optional fix path.
 *
 * Flow:
 *  1. User picks a rejection reason (category) + optional free text.
 *  2. Bottom section optionally expands "Bunu düzeltmek ister misin?" — two
 *     modes:
 *       a. Manuel edit: textarea with char counter.
 *       b. AI ile düzelt: RefinePanel (quick tags + feedback → variants → pick).
 *  3. Submit:
 *       - If no fix → reject path (onReject)
 *       - If user edited / picked a variant → edit path (onEdit) with the new
 *         content; rejection reason becomes feedback so memory still learns.
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Pencil, X as XIcon, Check, Type, Image as ImageIcon, Layers } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import RefinePanel from "./RefinePanel";

const CATEGORIES = [
  "too_long",
  "too_short",
  "tone_too_harsh",
  "tone_too_soft",
  "tone_too_corporate",
  "sounds_like_ai",
  "misread_trend",
  "shallow_insight",
  "weak_hook",
  "inaccurate",
  "already_posted",
  "off_voice",
  "other",
];

// Categories that imply the draft is fixable.
// Non-fixable = the trend itself is wrong / already used / fact-wrong, so the
// right action is reject + generate from a different trend.
const FIXABLE = new Set([
  "too_long",
  "too_short",
  "tone_too_harsh",
  "tone_too_soft",
  "tone_too_corporate",
  "sounds_like_ai",
  "shallow_insight",
  "weak_hook",
  "off_voice",
  "other",
]);

// When the user picks a fixable category, pre-select these RefinePanel
// quick-tags so the AI refine immediately points in the right direction.
const CATEGORY_TO_QUICK_TAGS = {
  too_long: ["shorter"],
  too_short: ["longer"],
  tone_too_harsh: ["softer"],
  tone_too_soft: ["bolder"],
  tone_too_corporate: ["casual"],
  sounds_like_ai: ["casual"],
  shallow_insight: ["informative", "stronger_ending"],
  weak_hook: ["add_hook", "different_opening"],
  off_voice: [],
  other: [],
};

// Phase 28 Fix 3 — image-specific rejection reasons. Each maps to a fix
// signal the Visual Director will see in memory.
const IMAGE_REASONS = [
  { key: "deformed_hand", label: "Bozuk eller / parmaklar" },
  { key: "fake_logo", label: "Sahte marka logosu" },
  { key: "off_brand", label: "Cansu'nun tarzına uymuyor" },
  { key: "identity_drift", label: "Cansu'ya benzemiyor" },
  { key: "ai_obvious", label: "Çok yapay / yağlı cilt" },
  { key: "aesthetic_poor", label: "Kompozisyon / ışık zayıf" },
  { key: "wrong_scene", label: "Yanlış sahne / mekan" },
  { key: "other", label: "Diğer" },
];

export default function RejectDialog({ draft, open, onClose, onReject, onEdit, initialTarget }) {
  const { t } = useTranslation();
  const [target, setTarget] = useState("both");           // Phase 28: 'text' | 'image' | 'both'
  const [category, setCategory] = useState("other");
  const [feedback, setFeedback] = useState("");
  const [fixMode, setFixMode] = useState(null); // null | "manual" | "ai"
  const [editedContent, setEditedContent] = useState("");
  const [imageReason, setImageReason] = useState("other"); // Phase 28: which image issue

  const hasImage = Boolean(draft?.image_url);

  useEffect(() => {
    if (open && draft) {
      setTarget(initialTarget || "both");
      setCategory("other");
      setFeedback("");
      setFixMode(null);
      setEditedContent(draft.content || "");
      setImageReason("other");
    }
  }, [open, draft, initialTarget]);

  if (!draft) return null;

  const charCount = editedContent.length;
  const tooLong = charCount > 4000;
  const editChanged = editedContent.trim() !== (draft.content || "").trim();

  const handleApplyVariant = (newContent) => {
    setEditedContent(newContent);
    setFixMode("manual"); // Switch to manual view so user can polish the variant
  };

  const handleSubmit = () => {
    const trimmed = (editedContent || "").trim();
    const reasonText = feedback.trim();
    // Build a memory-friendly feedback string from the rejection signal.
    const combinedFeedback = reasonText
      ? `[${category}] ${reasonText}`
      : `[${category}]`;

    // Phase 28 — when the user picks "image only" we never edit text; we go
    // straight to reject with the image-specific signal.
    if (target === "image") {
      onReject({
        category: "other",
        feedback: reasonText,
        rejection_target: "image",
        image_rejection_reason: imageReason,
      });
      return;
    }

    if (fixMode && editChanged && trimmed && !tooLong) {
      // Fix path — treat as edit. Rejection signal is preserved in feedback.
      onEdit({ edited_content: trimmed, feedback: combinedFeedback });
    } else {
      onReject({
        category,
        feedback: reasonText,
        rejection_target: target,
        image_rejection_reason: target === "both" ? imageReason : null,
      });
    }
  };

  const submitLabel = fixMode && editChanged && !tooLong
    ? t("autoDrafts.reject.submitWithFix")
    : t("autoDrafts.reject.submit");

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-outfit">{t("autoDrafts.reject.title")}</DialogTitle>
          <DialogDescription>{t("autoDrafts.reject.description")}</DialogDescription>
        </DialogHeader>

        {/* Draft preview — text + image side by side when image exists */}
        <div className="rounded-xl bg-secondary/40 border border-border/50 p-3 my-2 flex gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">
              {draft.trend_topic || "Draft"}
            </p>
            <p className="text-sm text-foreground/80 line-clamp-4 whitespace-pre-wrap">
              {draft.content}
            </p>
          </div>
          {hasImage && (
            <img
              src={draft.image_url}
              alt="Draft görseli"
              className="h-20 w-20 rounded-lg object-cover border border-border/40 shrink-0"
            />
          )}
        </div>

        {/* Phase 28 — Target switcher: which part is the problem? */}
        {hasImage && (
          <div className="space-y-2 mt-1">
            <p className="text-xs font-medium text-muted-foreground">
              {t("autoDrafts.reject.targetLabel", "Hangisi sorunlu?")}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { key: "text",  icon: Type,      label: t("autoDrafts.reject.target.text",  "Sadece metin"),  color: "rose" },
                { key: "image", icon: ImageIcon, label: t("autoDrafts.reject.target.image", "Sadece görsel"), color: "amber" },
                { key: "both",  icon: Layers,    label: t("autoDrafts.reject.target.both",  "İkisi de"),       color: "purple" },
              ].map((opt) => {
                const Icon = opt.icon;
                const active = target === opt.key;
                const colorClasses = {
                  rose:   "bg-rose-500/10 border-rose-500 text-rose-600 dark:text-rose-300",
                  amber:  "bg-amber-500/10 border-amber-500 text-amber-600 dark:text-amber-300",
                  purple: "bg-purple-500/10 border-purple-500 text-purple-600 dark:text-purple-300",
                };
                return (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => setTarget(opt.key)}
                    className={cn(
                      "flex items-center justify-center gap-1.5 text-xs px-2 py-2 rounded-lg border transition-all",
                      active ? `font-medium ${colorClasses[opt.color]}` : "border-border/60 text-foreground/70 hover:border-border"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Image-specific reason — shown when target = image or both */}
        {hasImage && target !== "text" && (
          <div className="space-y-2 mt-2">
            <p className="text-xs font-medium text-muted-foreground">
              {t("autoDrafts.reject.imageReasonLabel", "Görseldeki sorun")}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {IMAGE_REASONS.map((r) => {
                const active = imageReason === r.key;
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => setImageReason(r.key)}
                    className={cn(
                      "text-xs px-3 py-2 rounded-lg border transition-all text-left",
                      "hover:border-amber-500/40 hover:bg-amber-500/5",
                      active
                        ? "bg-amber-500/10 border-amber-500 text-amber-700 dark:text-amber-300 font-medium"
                        : "border-border/60 text-foreground/80"
                    )}
                  >
                    {r.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Text-side rejection — hidden when only image is the problem */}
        {target !== "image" && (
        <>
        {/* Category */}
        <div className="space-y-2 mt-2">
          <p className="text-xs font-medium text-muted-foreground">
            {t("autoDrafts.reject.categoryLabel")}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {CATEGORIES.map((key) => {
              const active = category === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setCategory(key)}
                  className={cn(
                    "text-xs px-3 py-2 rounded-lg border transition-all text-left",
                    "hover:border-purple-500/40 hover:bg-purple-500/5",
                    active
                      ? "bg-purple-500/10 border-purple-500 text-purple-700 dark:text-purple-300 font-medium"
                      : "border-border/60 text-foreground/80"
                  )}
                >
                  {t(`autoDrafts.reject.categories.${key}`)}
                </button>
              );
            })}
          </div>
        </div>

        {/* Fix section */}
        {FIXABLE.has(category) && (
          <div className="rounded-xl border border-border/60 bg-card/40 p-3 mt-2">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium">{t("autoDrafts.reject.fixPrompt")}</p>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setFixMode(fixMode === "manual" ? null : "manual")}
                  className={cn(
                    "inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md border transition-colors",
                    fixMode === "manual"
                      ? "bg-purple-500/15 border-purple-500 text-purple-600 dark:text-purple-300 font-medium"
                      : "border-border/50 text-muted-foreground hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-300"
                  )}
                >
                  <Pencil className="h-3 w-3" />
                  {t("autoDrafts.reject.fixManualCta")}
                </button>
                <button
                  type="button"
                  onClick={() => setFixMode(fixMode === "ai" ? null : "ai")}
                  className={cn(
                    "inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md border transition-colors",
                    fixMode === "ai"
                      ? "bg-purple-500/15 border-purple-500 text-purple-600 dark:text-purple-300 font-medium"
                      : "border-border/50 text-muted-foreground hover:border-purple-500/40 hover:text-purple-600 dark:hover:text-purple-300"
                  )}
                >
                  <Sparkles className="h-3 w-3" />
                  {t("autoDrafts.reject.fixAiCta")}
                </button>
              </div>
            </div>

            <AnimatePresence mode="wait">
              {fixMode === "manual" && (
                <motion.div
                  key="manual"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {t("autoDrafts.edit.contentLabel")}
                    </span>
                    <span
                      className={cn(
                        "text-[10px] font-mono",
                        tooLong ? "text-rose-500" : charCount > 280 ? "text-amber-500" : "text-muted-foreground"
                      )}
                    >
                      {charCount} / 4000
                    </span>
                  </div>
                  <Textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    rows={6}
                    className={cn(
                      "resize-none text-sm leading-relaxed",
                      tooLong && "border-rose-500/60"
                    )}
                  />
                </motion.div>
              )}

              {fixMode === "ai" && (
                <motion.div
                  key="ai"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <RefinePanel
                    draftId={draft.id}
                    currentContent={editedContent || draft.content || ""}
                    onApply={handleApplyVariant}
                    initialQuickTags={CATEGORY_TO_QUICK_TAGS[category] || []}
                    initialFeedback={feedback}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
        </>
        )}

        {/* Free-text feedback (always shown — works for text, image, both) */}
        <div className="space-y-2 mt-2">
          <label className="text-xs font-medium text-muted-foreground">
            {target === "image"
              ? t("autoDrafts.reject.imageFeedbackLabel", "Görsel için ek not (opsiyonel)")
              : t("autoDrafts.reject.feedbackLabel")}
          </label>
          <Textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder={target === "image"
              ? t("autoDrafts.reject.imageFeedbackPlaceholder", "Neyi yanlış buldun? (örn. ışık çok yapay, ortam Cansu'ya uymuyor…)")
              : t("autoDrafts.reject.feedbackPlaceholder")}
            rows={2}
            maxLength={2000}
            className="resize-none text-sm"
          />
        </div>

        <DialogFooter className="gap-2 sm:gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={tooLong}
            className={cn(
              fixMode && editChanged && !tooLong
                ? "bg-purple-600 hover:bg-purple-700 text-white gap-1"
                : "bg-rose-600 hover:bg-rose-700 text-white gap-1"
            )}
          >
            {fixMode && editChanged && !tooLong ? (
              <Check className="h-4 w-4" />
            ) : (
              <XIcon className="h-4 w-4" />
            )}
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
