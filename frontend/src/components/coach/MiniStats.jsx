/**
 * MiniStats — Alt kısımdaki 3 küçük stat widget.
 * Streak, tempo, favori oranı.
 * Sabit, scroll etmez. Devasa rakamlar + neon glow.
 */
import { motion } from "framer-motion";
import { Flame, Zap, Heart } from "lucide-react";
import { cn } from "@/lib/utils";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.3 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  show: { opacity: 1, y: 0, scale: 1 },
};

export default function MiniStats({ stats }) {
  const streak = stats?.current_streak || 0;
  const thisWeek = stats?.this_week || 0;
  const favoriteRatio = stats?.favorite_ratio || 0;

  const widgets = [
    {
      icon: Flame,
      value: streak,
      suffix: streak === 1 ? "gün" : "gün",
      label: "Streak",
      color: streak > 0 ? "text-amber-400" : "text-white/20",
      iconColor: streak > 0 ? "text-amber-400" : "text-white/10",
      glow: streak > 0 ? "shadow-[0_0_30px_rgba(245,158,11,0.1)]" : "",
      border: streak > 0 ? "border-amber-500/15" : "border-white/[0.04]",
    },
    {
      icon: Zap,
      value: thisWeek,
      suffix: "",
      label: "Son 7 Gün",
      color: thisWeek > 0 ? "text-blue-400" : "text-white/20",
      iconColor: thisWeek > 0 ? "text-blue-400" : "text-white/10",
      glow: thisWeek > 0 ? "shadow-[0_0_30px_rgba(59,130,246,0.1)]" : "",
      border: thisWeek > 0 ? "border-blue-500/15" : "border-white/[0.04]",
    },
    {
      icon: Heart,
      value: `${favoriteRatio}%`,
      suffix: "",
      label: "Favori Oranı",
      color: favoriteRatio > 0 ? "text-pink-400" : "text-white/20",
      iconColor: favoriteRatio > 0 ? "text-pink-400" : "text-white/10",
      glow: favoriteRatio > 0 ? "shadow-[0_0_30px_rgba(236,72,153,0.1)]" : "",
      border: favoriteRatio > 0 ? "border-pink-500/15" : "border-white/[0.04]",
    },
  ];

  return (
    <motion.div
      className="grid grid-cols-3 gap-3"
      variants={container}
      initial="hidden"
      animate="show"
    >
      {widgets.map((w) => (
        <motion.div
          key={w.label}
          variants={item}
          className={cn(
            "relative rounded-xl bg-[#0A0A0A] border p-4 text-center overflow-hidden",
            w.border,
            w.glow,
          )}
        >
          {/* Icon */}
          <w.icon className={cn("h-4 w-4 mx-auto mb-2", w.iconColor)} />

          {/* Value */}
          <p className={cn("text-2xl font-black tracking-tight", w.color)}>
            {w.value}
            {w.suffix && <span className="text-xs font-normal text-white/30 ml-1">{w.suffix}</span>}
          </p>

          {/* Label */}
          <p className="text-[10px] text-white/30 mt-1 font-medium uppercase tracking-wider">
            {w.label}
          </p>
        </motion.div>
      ))}
    </motion.div>
  );
}
