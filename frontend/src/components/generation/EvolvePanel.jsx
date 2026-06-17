import { useState } from "react";
import { useTranslation } from 'react-i18next';
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import EvolveQuickTags from "./EvolveQuickTags";

export default function EvolvePanel({ variant, variants, onEvolve, isLoading, onClose, isMerge }) {
  const { t } = useTranslation();
  const [feedback, setFeedback] = useState("");
  const [quickTags, setQuickTags] = useState([]);
  const [variantCount, setVariantCount] = useState(3);
  const [previewExpanded, setPreviewExpanded] = useState(false);

  const referenceContent = variant?.content || "";

  const handleSubmit = () => {
    onEvolve?.(feedback, quickTags, variantCount);
  };

  return (
    <div
      className="border-t border-dashed border-violet-500/30 bg-violet-500/5 rounded-b-lg p-4 space-y-3 relative"
      style={{ animation: "fadeIn 0.2s ease" }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-3 right-3 text-muted-foreground hover:text-foreground transition-colors"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Title for merge mode */}
      {isMerge && (
        <p className="text-sm font-semibold text-violet-300 mb-1">{t('evolve.mergeTitle')}</p>
      )}

      {/* Reference preview */}
      {isMerge && variants?.length > 0 ? (
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">{t('evolve.reference')} ({variants.length})</p>
          {variants.map((v, i) => (
            <div key={i} className="text-xs text-muted-foreground/70 mb-1 line-clamp-2 border-l-2 border-violet-500/30 pl-2">
              {v.content?.substring(0, 120)}...
            </div>
          ))}
        </div>
      ) : referenceContent ? (
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">{t('evolve.reference')}</p>
          <div
            onClick={() => setPreviewExpanded(!previewExpanded)}
            className={cn(
              "text-xs text-muted-foreground/70 cursor-pointer transition-all",
              !previewExpanded && "line-clamp-2"
            )}
          >
            {referenceContent}
          </div>
        </div>
      ) : null}

      {/* Quick tags */}
      <EvolveQuickTags selectedTags={quickTags} onTagsChange={setQuickTags} />

      {/* Feedback textarea */}
      <textarea
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder={isMerge ? t('evolve.feedbackPlaceholderMerge') : t('evolve.feedbackPlaceholder')}
        className="w-full bg-secondary/50 border border-border rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 placeholder:text-muted-foreground/50 transition-all"
        rows={2}
      />

      {/* Variant count */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{t('evolve.variantCount')}:</span>
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => setVariantCount(n)}
              className={cn(
                "w-8 h-8 rounded-lg text-xs font-medium transition-all border",
                variantCount === n
                  ? "bg-violet-500/20 border-violet-500/50 text-violet-300"
                  : "bg-secondary/50 border-transparent text-muted-foreground hover:bg-secondary/80"
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Generate button */}
      <Button
        onClick={handleSubmit}
        disabled={isLoading}
        className="w-full bg-gradient-to-r from-violet-500 to-fuchsia-500 hover:from-violet-600 hover:to-fuchsia-600 text-white font-medium"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
        ) : null}
        {isLoading ? t('common.loading') : t('evolve.generate')}
      </Button>
    </div>
  );
}
