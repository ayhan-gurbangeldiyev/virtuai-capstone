/**
 * RefinePanel — AI refinement section embedded inside EditDialog.
 *
 * Mirrors the XAIModule EvolveSlideOver pattern: quick tag chips + free
 * text + variant count → POST /api/hype/drafts/:id/refine → user picks
 * one of N variants and the parent EditDialog's textarea is updated.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles, Loader2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { refineDraft } from "@/services/hypeService";
import { cn } from "@/lib/utils";

const QUICK_TAGS = [
  // Length
  { key: "shorter", group: "length" },
  { key: "longer", group: "length" },
  // Tone
  { key: "bolder", group: "tone" },
  { key: "softer", group: "tone" },
  { key: "professional", group: "tone" },
  { key: "casual", group: "tone" },
  { key: "provocative", group: "tone" },
  { key: "informative", group: "tone" },
  // Structure
  { key: "different_opening", group: "structure" },
  { key: "stronger_ending", group: "structure" },
  { key: "add_hook", group: "structure" },
  { key: "simplify", group: "structure" },
];

// Mutually-exclusive groups: only one of each can be active
const GROUPS = ["length", "tone", "structure"];

export default function RefinePanel({ draftId, currentContent, onApply, initialQuickTags = [], initialFeedback = "" }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState(initialQuickTags);
  const [feedback, setFeedback] = useState(initialFeedback);
  const [variantCount, setVariantCount] = useState(3);
  const [loading, setLoading] = useState(false);
  const [variants, setVariants] = useState([]);
  const [pickedIdx, setPickedIdx] = useState(null);

  const toggleTag = (key, group) => {
    setSelected((prev) => {
      const isOn = prev.includes(key);
      if (isOn) return prev.filter((t) => t !== key);
      // Drop other tags in the same group (mutually exclusive)
      const sameGroup = QUICK_TAGS.filter((q) => q.group === group).map((q) => q.key);
      const cleaned = prev.filter((t) => !sameGroup.includes(t));
      return [...cleaned, key];
    });
  };

  const handleGenerate = async () => {
    if (!draftId) return;
    setLoading(true);
    setVariants([]);
    setPickedIdx(null);
    try {
      const res = await refineDraft(draftId, {
        feedback: feedback.trim(),
        quick_tags: selected,
        variant_count: variantCount,
      });
      const list = res?.variants || [];
      setVariants(list);
      if (list.length === 0) toast.error(t("autoDrafts.refine.error"));
    } catch (e) {
      toast.error(t("autoDrafts.refine.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (pickedIdx == null) return;
    const picked = variants[pickedIdx];
    if (picked && typeof picked.content === "string") {
      onApply(picked.content);
      toast.success(t("autoDrafts.refine.applied"));
    }
  };

  return (
    <div className="space-y-4 rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-500/5 to-indigo-500/5 p-4">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
          <Sparkles className="h-3.5 w-3.5 text-white" />
        </div>
        <div>
          <h4 className="text-sm font-semibold">{t("autoDrafts.refine.title")}</h4>
          <p className="text-[11px] text-muted-foreground">{t("autoDrafts.refine.description")}</p>
        </div>
      </div>

      {/* Quick tag chips, grouped */}
      <div className="space-y-2">
        <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">
          {t("autoDrafts.refine.tagsLabel")}
        </p>
        {GROUPS.map((g) => (
          <div key={g} className="flex flex-wrap gap-1.5">
            {QUICK_TAGS.filter((tag) => tag.group === g).map((tag) => {
              const active = selected.includes(tag.key);
              return (
                <button
                  key={tag.key}
                  type="button"
                  onClick={() => toggleTag(tag.key, tag.group)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] border transition-all",
                    active
                      ? "bg-purple-500/15 border-purple-500 text-purple-600 dark:text-purple-300 font-medium"
                      : "border-border/50 text-muted-foreground hover:border-purple-500/40 hover:bg-purple-500/5"
                  )}
                >
                  {t(`autoDrafts.refine.tags.${tag.key}`)}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Free-text feedback */}
      <div className="space-y-2">
        <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">
          {t("autoDrafts.refine.feedbackLabel")}
        </p>
        <Textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder={t("autoDrafts.refine.feedbackPlaceholder")}
          rows={2}
          maxLength={1000}
          className="resize-none text-sm"
        />
      </div>

      {/* Variant count */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">
            {t("autoDrafts.refine.variantCountLabel")}
          </p>
          <span className="text-xs font-mono text-purple-600 dark:text-purple-400">
            {variantCount}
          </span>
        </div>
        <Slider
          value={[variantCount]}
          onValueChange={([v]) => setVariantCount(v)}
          min={1}
          max={5}
          step={1}
        />
      </div>

      <Button
        onClick={handleGenerate}
        disabled={loading || (selected.length === 0 && !feedback.trim())}
        className="w-full bg-purple-600 hover:bg-purple-700 text-white gap-2"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {t("autoDrafts.refine.generating")}
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" />
            {t("autoDrafts.refine.generateCta")}
          </>
        )}
      </Button>

      {/* Variants */}
      <AnimatePresence>
        {variants.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2 overflow-hidden"
          >
            <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground">
              {t("autoDrafts.refine.variantsTitle")}
            </p>
            {variants.map((v, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setPickedIdx(i)}
                className={cn(
                  "w-full text-left rounded-lg border p-3 transition-all",
                  pickedIdx === i
                    ? "border-purple-500 bg-purple-500/10"
                    : "border-border/60 bg-card hover:border-purple-500/40"
                )}
              >
                <div className="flex items-start gap-2">
                  <span className="text-[10px] font-mono shrink-0 px-1.5 py-0.5 rounded bg-secondary/60 text-muted-foreground">
                    #{i + 1}
                  </span>
                  <p className="text-xs leading-relaxed whitespace-pre-wrap flex-1">
                    {v.content}
                  </p>
                </div>
                <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground font-mono">
                  <span>{(v.content || "").length} ch</span>
                  {pickedIdx === i && (
                    <span className="text-purple-600 dark:text-purple-400">seçildi</span>
                  )}
                </div>
              </button>
            ))}
            <Button
              onClick={handleApply}
              disabled={pickedIdx == null}
              size="sm"
              variant="outline"
              className="w-full gap-2 border-purple-500/40 hover:bg-purple-500/10"
            >
              <ArrowRight className="h-3.5 w-3.5" />
              {t("autoDrafts.refine.applyCta")}
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
