import { useTranslation } from 'react-i18next';
import { cn } from "@/lib/utils";
import {
  Minus, Plus, Equal,
  Flame, Feather, Briefcase, Coffee, Zap, BookOpen,
  Sparkles, Target, Anchor, Scissors,
  RotateCcw,
} from "lucide-react";

// ─── Conflict map: selecting one disables the other ───
const TONE_CONFLICTS = {
  bolder: "softer",
  softer: "bolder",
  professional: "casual",
  casual: "professional",
  provocative: "softer",
};

const TONE_ICONS = {
  bolder: Flame,
  softer: Feather,
  professional: Briefcase,
  casual: Coffee,
  provocative: Zap,
  informative: BookOpen,
};

const STRUCTURE_ICONS = {
  different_opening: Sparkles,
  stronger_ending: Target,
  add_hook: Anchor,
  simplify: Scissors,
};

const LENGTH_OPTIONS = [
  { id: "shorter", labelKey: "evolve.tags.shorter", icon: Minus },
  { id: "original", label: "Orijinal", icon: Equal },
  { id: "longer", labelKey: "evolve.tags.longer", icon: Plus },
];

const TONE_TAGS = [
  { id: "bolder", labelKey: "evolve.tags.bolder" },
  { id: "softer", labelKey: "evolve.tags.softer" },
  { id: "professional", labelKey: "evolve.tags.professional" },
  { id: "casual", labelKey: "evolve.tags.casual" },
  { id: "provocative", labelKey: "evolve.tags.provocative" },
  { id: "informative", labelKey: "evolve.tags.informative" },
];

const STRUCTURE_TAGS = [
  { id: "different_opening", labelKey: "evolve.tags.differentOpening" },
  { id: "stronger_ending", labelKey: "evolve.tags.strongerEnding" },
  { id: "add_hook", labelKey: "evolve.tags.addHook" },
  { id: "simplify", labelKey: "evolve.tags.simplify" },
];

export default function EvolveQuickTags({ selectedTags = [], onTagsChange }) {
  const { t } = useTranslation();

  // ─── Length: single select (radio) ───
  const selectedLength = selectedTags.find(id => ["shorter", "longer"].includes(id)) || "original";

  const handleLength = (id) => {
    const withoutLength = selectedTags.filter(t => !["shorter", "longer"].includes(t));
    if (id === "original") {
      onTagsChange(withoutLength);
    } else {
      onTagsChange([...withoutLength, id]);
    }
  };

  // ─── Tone: max 2, conflict-aware ───
  const selectedTones = selectedTags.filter(id => TONE_TAGS.some(t => t.id === id));

  const isToneDisabled = (tagId) => {
    if (selectedTones.includes(tagId)) return false;
    // Conflict check
    const conflictId = TONE_CONFLICTS[tagId];
    if (conflictId && selectedTones.includes(conflictId)) return true;
    // Reverse conflict
    for (const selected of selectedTones) {
      if (TONE_CONFLICTS[selected] === tagId) return true;
    }
    // Max 2
    if (selectedTones.length >= 2) return true;
    return false;
  };

  const toggleTone = (tagId) => {
    if (selectedTones.includes(tagId)) {
      onTagsChange(selectedTags.filter(id => id !== tagId));
    } else if (!isToneDisabled(tagId)) {
      onTagsChange([...selectedTags, tagId]);
    }
  };

  // ─── Structure: free multi-select ───
  const selectedStructure = selectedTags.filter(id => STRUCTURE_TAGS.some(t => t.id === id));

  const toggleStructure = (tagId) => {
    if (selectedStructure.includes(tagId)) {
      onTagsChange(selectedTags.filter(id => id !== tagId));
    } else {
      onTagsChange([...selectedTags, tagId]);
    }
  };

  const totalSelected = selectedTags.length + (selectedLength !== "original" ? 0 : 0);
  const hasAnySelection = selectedTags.length > 0;

  return (
    <div className="space-y-3">
      {/* ─── Length: Segmented Control ─── */}
      <div>
        <p className="text-[11px] text-muted-foreground mb-1.5">{t("evolve.tagCategories.length")}</p>
        <div className="inline-flex rounded-lg border border-border/50 bg-secondary/30 p-0.5">
          {LENGTH_OPTIONS.map((opt) => {
            const isActive = selectedLength === opt.id;
            const Icon = opt.icon;
            return (
              <button
                key={opt.id}
                onClick={() => handleLength(opt.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all",
                  isActive
                    ? "bg-violet-500/20 text-violet-300 shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-3 w-3" />
                {opt.labelKey ? t(opt.labelKey) : opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Tone: Limited multi (max 2, conflicts) ─── */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[11px] text-muted-foreground">{t("evolve.tagCategories.tone")}</p>
          {selectedTones.length > 0 && (
            <span className="text-[10px] text-violet-400/60">{selectedTones.length}/2</span>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {TONE_TAGS.map((tag) => {
            const isSelected = selectedTones.includes(tag.id);
            const disabled = isToneDisabled(tag.id);
            const Icon = TONE_ICONS[tag.id];
            return (
              <button
                key={tag.id}
                onClick={() => toggleTone(tag.id)}
                disabled={disabled}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border",
                  isSelected
                    ? "bg-violet-500/15 border-violet-500/50 text-violet-300"
                    : disabled
                      ? "opacity-30 cursor-not-allowed border-transparent text-muted-foreground"
                      : "bg-secondary/40 border-transparent text-muted-foreground hover:bg-secondary/70 hover:text-foreground hover:border-border/50"
                )}
              >
                {Icon && <Icon className="h-3 w-3" />}
                {t(tag.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Structure: free multi ─── */}
      <div>
        <p className="text-[11px] text-muted-foreground mb-1.5">{t("evolve.tagCategories.structure")}</p>
        <div className="flex flex-wrap gap-1.5">
          {STRUCTURE_TAGS.map((tag) => {
            const isSelected = selectedStructure.includes(tag.id);
            const Icon = STRUCTURE_ICONS[tag.id];
            return (
              <button
                key={tag.id}
                onClick={() => toggleStructure(tag.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border",
                  isSelected
                    ? "bg-violet-500/15 border-violet-500/50 text-violet-300"
                    : "bg-secondary/40 border-transparent text-muted-foreground hover:bg-secondary/70 hover:text-foreground hover:border-border/50"
                )}
              >
                {Icon && <Icon className="h-3 w-3" />}
                {t(tag.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      {/* ─── Reset + info ─── */}
      {hasAnySelection && (
        <div className="flex items-center justify-between pt-0.5">
          <button
            onClick={() => onTagsChange([])}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-violet-400 transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Seçimleri Temizle
          </button>
        </div>
      )}
    </div>
  );
}
