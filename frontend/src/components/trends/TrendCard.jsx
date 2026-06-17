import { useTranslation } from "react-i18next";
import { ExternalLink, Wand2, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { timeAgo, CATEGORY_LABELS } from "@/lib/trend-helpers";

export default function TrendCard({ trend, onGenerate }) {
  const { t } = useTranslation();
  const isHot = (trend.score || 0) >= 85;
  const catLabel = CATEGORY_LABELS[trend.category] || trend.category;

  return (
    <div className={cn(
      "relative rounded-xl border border-border/40 bg-card/80",
      "p-4 flex flex-col h-full",
      "transition-all duration-200",
      "hover:border-border/60 hover:shadow-md hover:shadow-purple-500/5",
      isHot && "border-l-[3px] border-l-emerald-500/70",
    )}>
      {/* Meta row */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground/70">{catLabel}</span>
        {trend.published_at && (
          <span className="text-xs text-muted-foreground/50">{timeAgo(trend.published_at)}</span>
        )}
      </div>

      {/* Title */}
      <h3 className="font-semibold text-[15px] leading-snug text-foreground line-clamp-2 mt-2">
        {trend.topic}
      </h3>

      {/* Summary */}
      <p className="text-sm text-muted-foreground/70 line-clamp-2 leading-relaxed mt-1.5 flex-1">
        {trend.summary}
      </p>

      {/* Actions */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
        <div className="flex items-center gap-3">
          {trend.url && (
            <a
              href={trend.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground/50 hover:text-foreground transition-colors flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" />
              {t("trends.source")}
            </a>
          )}
          {trend.source_count >= 2 && (
            <span className="text-xs text-emerald-400/70 flex items-center gap-1">
              <CheckCircle className="h-3 w-3" />
              {trend.source_count} {t("trends.sourceLabel")}
            </span>
          )}
        </div>
        <Button
          size="sm"
          onClick={() => onGenerate(trend)}
          className="h-8 px-3.5 rounded-lg text-xs font-medium bg-purple-600 hover:bg-purple-700 text-white"
        >
          <Wand2 className="h-3.5 w-3.5 mr-1.5" />
          {t("trends.generate")}
        </Button>
      </div>
    </div>
  );
}
