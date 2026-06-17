import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle, Flame, PartyPopper, Target, CheckCircle,
  RefreshCw, TrendingUp, TrendingDown, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const CARD_CONFIG = {
  opportunity: {
    icon: AlertTriangle,
    iconColor: "text-red-400",
    border: "border-red-500/30",
    bg: "bg-gradient-to-r from-red-500/10 to-orange-500/10",
    glow: "shadow-[0_4px_20px_rgba(239,68,68,0.12)]",
  },
  roast: {
    icon: Flame,
    iconColor: "text-pink-400",
    border: "border-pink-500/30",
    bg: "bg-gradient-to-r from-pink-500/10 to-red-500/10",
    glow: "shadow-[0_4px_20px_rgba(236,72,153,0.12)]",
  },
  toast: {
    icon: PartyPopper,
    iconColor: "text-emerald-400",
    border: "border-emerald-500/30",
    bg: "bg-gradient-to-r from-emerald-500/10 to-green-500/10",
    glow: "shadow-[0_4px_20px_rgba(16,185,129,0.12)]",
  },
  daily_goal: {
    icon: Target,
    iconColor: "text-blue-400",
    border: "border-blue-500/30",
    bg: "bg-gradient-to-r from-blue-500/10 to-cyan-500/10",
    glow: "shadow-[0_4px_20px_rgba(59,130,246,0.12)]",
  },
  daily_complete: {
    icon: CheckCircle,
    iconColor: "text-emerald-400",
    border: "border-emerald-500/30",
    bg: "bg-emerald-500/5",
    glow: "shadow-[0_4px_20px_rgba(16,185,129,0.12)]",
  },
  repurpose: {
    icon: RefreshCw,
    iconColor: "text-purple-400",
    border: "border-purple-500/30",
    bg: "bg-gradient-to-r from-purple-500/10 to-fuchsia-500/10",
    glow: "shadow-[0_4px_20px_rgba(168,85,247,0.12)]",
  },
  progress: {
    icon: TrendingUp,
    iconColor: "text-emerald-400",
    border: "border-emerald-500/30",
    bg: "bg-emerald-500/5",
    glow: "shadow-[0_4px_20px_rgba(16,185,129,0.12)]",
  },
  progress_down: {
    icon: TrendingDown,
    iconColor: "text-yellow-400",
    border: "border-yellow-500/30",
    bg: "bg-yellow-500/5",
    glow: "shadow-[0_4px_20px_rgba(234,179,8,0.12)]",
  },
  streak: {
    icon: Flame,
    iconColor: "text-amber-400",
    border: "border-amber-500/30",
    bg: "bg-gradient-to-r from-amber-500/10 to-orange-500/10",
    glow: "shadow-[0_4px_20px_rgba(245,158,11,0.12)]",
  },
  onboarding: {
    icon: Target,
    iconColor: "text-violet-400",
    border: "border-violet-500/30",
    bg: "bg-gradient-to-r from-violet-500/10 to-indigo-500/10",
    glow: "shadow-[0_4px_20px_rgba(139,92,246,0.12)]",
  },
};

export default function CoachCard({ card, onDismiss, onAction }) {
  const { t } = useTranslation();
  const config = CARD_CONFIG[card.type] || CARD_CONFIG.daily_goal;
  const Icon = config.icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: -300, scale: 0.95, transition: { duration: 0.3 } }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.1}
      onDragEnd={(_, info) => {
        if (info.offset.x < -100) onDismiss(card.key);
      }}
      className={cn(
        "rounded-xl border p-4 cursor-grab active:cursor-grabbing",
        "transition-all",
        config.border,
        config.bg,
        config.glow,
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={cn("mt-0.5 shrink-0", config.iconColor)}>
          <Icon className="h-5 w-5" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-semibold leading-tight">{card.title}</h4>
            <button
              onClick={(e) => { e.stopPropagation(); onDismiss(card.key); }}
              className="shrink-0 p-1 rounded-md text-white/20 hover:text-white/60 hover:bg-white/5 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
            {card.description}
          </p>

          {/* Original content (repurpose) */}
          {card.original_content && (
            <div className="mt-2 px-3 py-2 rounded-lg bg-white/5 border border-white/5">
              <p className="text-xs text-white/50 italic line-clamp-2">
                "{card.original_content.slice(0, 140)}{card.original_content.length > 140 ? '...' : ''}"
              </p>
            </div>
          )}

          {/* Meta badges */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {card.trend_score && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                ⚡ {card.trend_score}
              </Badge>
            )}
            {card.freshness && (
              <span className="text-[10px] text-muted-foreground">{card.freshness}</span>
            )}
          </div>

          {/* Action button */}
          {card.action && card.action.label && (
            <div className="mt-3">
              <Button
                size="sm"
                onClick={(e) => { e.stopPropagation(); onAction(card.action); }}
                className="h-8 text-xs rounded-lg bg-white/10 hover:bg-white/20 text-white border-0"
              >
                {card.action.label}
              </Button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
