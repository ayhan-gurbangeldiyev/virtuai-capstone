/**
 * StackCard — Devasa, glassmorphism, premium kart.
 * Her kart tipinin kendine özgü renk glow'u ve ikon alanı var.
 * Tipografi hiyerarşisi: rakamlar devasa, açıklama küçük.
 */
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle, Flame, PartyPopper, Target, CheckCircle,
  RefreshCw, TrendingUp, TrendingDown, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const CARD_STYLES = {
  opportunity: {
    icon: AlertTriangle,
    gradient: "from-orange-500/10 via-red-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-orange-500 to-red-500",
    glowColor: "shadow-[0_0_80px_rgba(249,115,22,0.15)]",
    accentText: "text-orange-400",
    accentBorder: "border-orange-500/20",
    ctaClass: "bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600",
  },
  roast: {
    icon: Flame,
    gradient: "from-pink-500/10 via-rose-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-pink-500 to-rose-500",
    glowColor: "shadow-[0_0_80px_rgba(236,72,153,0.15)]",
    accentText: "text-pink-400",
    accentBorder: "border-pink-500/20",
    ctaClass: "bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600",
  },
  toast: {
    icon: PartyPopper,
    gradient: "from-emerald-500/10 via-green-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-emerald-500 to-green-500",
    glowColor: "shadow-[0_0_80px_rgba(16,185,129,0.15)]",
    accentText: "text-emerald-400",
    accentBorder: "border-emerald-500/20",
    ctaClass: "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600",
  },
  daily_goal: {
    icon: Target,
    gradient: "from-blue-500/10 via-indigo-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-blue-500 to-indigo-500",
    glowColor: "shadow-[0_0_80px_rgba(99,102,241,0.15)]",
    accentText: "text-blue-400",
    accentBorder: "border-blue-500/20",
    ctaClass: "bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600",
  },
  daily_complete: {
    icon: CheckCircle,
    gradient: "from-emerald-500/10 via-cyan-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-emerald-400 to-cyan-500",
    glowColor: "shadow-[0_0_80px_rgba(16,185,129,0.15)]",
    accentText: "text-emerald-400",
    accentBorder: "border-emerald-500/20",
    ctaClass: "bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600",
  },
  repurpose: {
    icon: RefreshCw,
    gradient: "from-purple-500/10 via-fuchsia-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-purple-500 to-fuchsia-500",
    glowColor: "shadow-[0_0_80px_rgba(168,85,247,0.15)]",
    accentText: "text-purple-400",
    accentBorder: "border-purple-500/20",
    ctaClass: "bg-gradient-to-r from-purple-500 to-fuchsia-500 hover:from-purple-600 hover:to-fuchsia-600",
  },
  progress: {
    icon: TrendingUp,
    gradient: "from-emerald-500/10 via-teal-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-emerald-400 to-teal-500",
    glowColor: "shadow-[0_0_80px_rgba(20,184,166,0.15)]",
    accentText: "text-emerald-400",
    accentBorder: "border-emerald-500/20",
    ctaClass: "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600",
  },
  progress_down: {
    icon: TrendingDown,
    gradient: "from-yellow-500/10 via-amber-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-yellow-500 to-amber-500",
    glowColor: "shadow-[0_0_80px_rgba(234,179,8,0.15)]",
    accentText: "text-yellow-400",
    accentBorder: "border-yellow-500/20",
    ctaClass: "bg-gradient-to-r from-yellow-500 to-amber-500 hover:from-yellow-600 hover:to-amber-600",
  },
  streak: {
    icon: Flame,
    gradient: "from-amber-500/10 via-orange-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-amber-500 to-orange-500",
    glowColor: "shadow-[0_0_80px_rgba(245,158,11,0.15)]",
    accentText: "text-amber-400",
    accentBorder: "border-amber-500/20",
    ctaClass: "bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600",
  },
  onboarding: {
    icon: Sparkles,
    gradient: "from-violet-500/10 via-indigo-500/5 to-transparent",
    iconBg: "bg-gradient-to-br from-violet-500 to-indigo-500",
    glowColor: "shadow-[0_0_80px_rgba(139,92,246,0.15)]",
    accentText: "text-violet-400",
    accentBorder: "border-violet-500/20",
    ctaClass: "bg-gradient-to-r from-violet-500 to-indigo-500 hover:from-violet-600 hover:to-indigo-600",
  },
};

export default function StackCard({ card, isActive, onAction, stackIndex = 0 }) {
  const { t } = useTranslation();
  const style = CARD_STYLES[card.type] || CARD_STYLES.daily_goal;
  const Icon = style.icon;

  // Büyük rakam çıkarma (varsa)
  const bigNumber = card.big_number || card.trend_score || null;

  return (
    <div
      className={cn(
        "relative rounded-2xl overflow-hidden select-none backdrop-blur-xl",
        // Derinlik bazlı arka plan: arkadaki kartlar daha açık (ışık yakalama)
        stackIndex === 0 && "bg-[#0A0A0A]",
        stackIndex === 1 && "bg-[#181818]",
        stackIndex >= 2 && "bg-[#222222]",
        // Border: aktif kart ince, arkadakiler üst kenar highlight
        isActive
          ? cn("border border-white/[0.08]", style.glowColor)
          : cn(
              "border border-white/[0.06]",
              // Dark mode ışık yakalama: üst kenara parlak border
              stackIndex === 1 && "border-t-white/30",
              stackIndex >= 2 && "border-t-white/15",
            ),
      )}
    >
      {/* Background gradient */}
      <div className={cn(
        "absolute inset-0 bg-gradient-to-br pointer-events-none",
        style.gradient,
      )} />

      {/* Content */}
      <div className="relative z-10 p-6 flex flex-col h-full" style={{ minHeight: 240 }}>
        {/* Top row: icon + type badge */}
        <div className="flex items-center justify-between mb-4">
          <div className={cn(
            "w-11 h-11 rounded-xl flex items-center justify-center shadow-lg",
            style.iconBg,
          )}>
            <Icon className="h-5 w-5 text-white" />
          </div>

          <div className="flex items-center gap-2">
            {card.freshness && (
              <span className="text-[10px] text-white/30">{card.freshness}</span>
            )}
            {card.trend_score && (
              <Badge
                className={cn(
                  "text-[10px] px-2 py-0.5 h-5 border",
                  style.accentBorder,
                  "bg-transparent",
                  style.accentText,
                )}
              >
                ⚡ {card.trend_score}
              </Badge>
            )}
          </div>
        </div>

        {/* Big number (eğer varsa) */}
        {bigNumber && (
          <div className="mb-2">
            <span className={cn("text-5xl font-black tracking-tight", style.accentText)}>
              {bigNumber}
            </span>
          </div>
        )}

        {/* Title */}
        <h3 className="text-lg font-bold leading-snug mb-2 text-white/95">
          {card.title}
        </h3>

        {/* Description */}
        <p className="text-sm text-white/50 leading-relaxed flex-1">
          {card.description}
        </p>

        {/* Original content (repurpose) */}
        {card.original_content && (
          <div className="mt-3 px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.05]">
            <p className="text-xs text-white/40 italic line-clamp-2">
              "{card.original_content.slice(0, 160)}{card.original_content.length > 160 ? "..." : ""}"
            </p>
          </div>
        )}

        {/* CTA */}
        {card.action?.label && (
          <div className="mt-4">
            <Button
              onClick={(e) => { e.stopPropagation(); onAction(card.action); }}
              className={cn(
                "h-11 px-6 text-sm font-semibold rounded-xl text-white border-0",
                "shadow-lg transition-all",
                style.ctaClass,
              )}
            >
              {card.action.label}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
