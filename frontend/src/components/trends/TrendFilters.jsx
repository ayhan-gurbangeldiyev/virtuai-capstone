import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { CATEGORY_LABELS } from "@/lib/trend-helpers";

export default function TrendFilters({ categories, selectedCategory, onCategoryChange, nicheFilter, onNicheToggle }) {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-2 mb-6 overflow-x-auto no-scrollbar pb-1">
      {/* "T\u00fcm\u00fc" chip */}
      <button
        onClick={() => onCategoryChange("all")}
        className={cn(
          "shrink-0 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors",
          selectedCategory === "all"
            ? "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/25"
            : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
        )}
      >
        {t("trends.allCategories")}
      </button>

      {/* Category chips */}
      {categories.map((cat) => (
        <button
          key={cat.id}
          onClick={() => onCategoryChange(cat.id)}
          className={cn(
            "shrink-0 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap",
            selectedCategory === cat.id
              ? "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/25"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
          )}
        >
          {CATEGORY_LABELS[cat.id] || cat.label}
        </button>
      ))}

      {/* Spacer */}
      <div className="flex-1 min-w-4" />

      {/* \u0130lgi Alanlar\u0131m toggle */}
      <button
        onClick={onNicheToggle}
        className={cn(
          "shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors",
          nicheFilter
            ? "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/25"
            : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
        )}
      >
        <Sparkles className="h-3.5 w-3.5" />
        {t("trends.nicheFilter")}
      </button>
    </div>
  );
}
