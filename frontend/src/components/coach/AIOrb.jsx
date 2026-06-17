/**
 * AIOrb — Dinamik AI küre. Aktif kartın tipine göre renk ve nabız değişir.
 * CSS-only, lightweight. WebGL yok.
 */
import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

// Kart tipine göre orb renk paleti ve nabız hızı
const ORB_MOODS = {
  opportunity: {
    core: "from-amber-400 via-orange-500 to-red-500",
    glow: "bg-orange-500/20",
    pulse: 1.8, // saniye — hızlı, acil
    label: "🔥",
  },
  roast: {
    core: "from-pink-500 via-rose-500 to-red-500",
    glow: "bg-pink-500/20",
    pulse: 2.0,
    label: "💀",
  },
  toast: {
    core: "from-emerald-400 via-green-400 to-teal-500",
    glow: "bg-emerald-500/20",
    pulse: 3.5, // yavaş, sakin
    label: "🎉",
  },
  daily_goal: {
    core: "from-blue-400 via-indigo-500 to-violet-500",
    glow: "bg-indigo-500/20",
    pulse: 3.0,
    label: "🎯",
  },
  daily_complete: {
    core: "from-emerald-400 via-cyan-400 to-green-500",
    glow: "bg-emerald-500/20",
    pulse: 4.0,
    label: "✅",
  },
  repurpose: {
    core: "from-purple-500 via-fuchsia-500 to-pink-500",
    glow: "bg-purple-500/20",
    pulse: 3.0,
    label: "♻️",
  },
  progress: {
    core: "from-emerald-400 via-teal-500 to-cyan-500",
    glow: "bg-teal-500/20",
    pulse: 3.5,
    label: "📈",
  },
  progress_down: {
    core: "from-yellow-400 via-amber-500 to-orange-500",
    glow: "bg-amber-500/20",
    pulse: 2.2,
    label: "⚡",
  },
  streak: {
    core: "from-amber-400 via-orange-500 to-red-400",
    glow: "bg-amber-500/20",
    pulse: 2.5,
    label: "🔥",
  },
  onboarding: {
    core: "from-violet-400 via-purple-500 to-indigo-500",
    glow: "bg-violet-500/20",
    pulse: 3.0,
    label: "👋",
  },
  // Default / idle (kart yokken)
  idle: {
    core: "from-violet-500 via-purple-600 to-indigo-600",
    glow: "bg-purple-500/15",
    pulse: 4.0,
    label: "✨",
  },
};

export default function AIOrb({ activeCardType, greeting, subtitle, expanded = false }) {
  const mood = useMemo(
    () => ORB_MOODS[activeCardType] || ORB_MOODS.idle,
    [activeCardType]
  );

  // Expanded: orb büyür, sahnenin ortasına iner
  const orbSize = expanded ? "w-28 h-28" : "w-20 h-20";
  const emojiSize = expanded ? "text-4xl" : "text-2xl";
  const glowSize = expanded ? "w-56 h-56" : "w-40 h-40";
  const pulseSize = expanded ? "w-28 h-28" : "w-20 h-20";
  const padding = expanded ? "pt-12 pb-8" : "pt-6 pb-4";

  return (
    <motion.div
      className={cn("relative flex flex-col items-center", padding)}
      layout
      transition={{ type: "spring", stiffness: 200, damping: 25 }}
    >
      {/* Glow */}
      <motion.div
        key={activeCardType || "idle"}
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6 }}
        className={cn(
          "absolute top-2 rounded-full blur-3xl pointer-events-none",
          glowSize,
          mood.glow
        )}
      />

      {/* Pulse rings */}
      <motion.div
        className={cn("absolute rounded-full border border-white/10", expanded ? "top-12" : "top-6", pulseSize)}
        animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0, 0.3] }}
        transition={{ duration: mood.pulse, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className={cn("absolute rounded-full border border-white/5", expanded ? "top-12" : "top-6", pulseSize)}
        animate={{ scale: [1, 1.8, 1], opacity: [0.15, 0, 0.15] }}
        transition={{ duration: mood.pulse, repeat: Infinity, ease: "easeInOut", delay: mood.pulse * 0.3 }}
      />

      {/* Core orb */}
      <motion.div
        className="relative z-10"
        layout
        transition={{ type: "spring", stiffness: 200, damping: 25 }}
      >
        <motion.div
          className={cn(
            "rounded-full bg-gradient-to-br shadow-2xl flex items-center justify-center",
            orbSize,
            mood.core
          )}
          layout
          transition={{ type: "spring", stiffness: 200, damping: 25 }}
        >
          <AnimatePresence mode="wait">
            <motion.span
              key={mood.label}
              initial={{ scale: 0, rotate: -20 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0, rotate: 20 }}
              transition={{ type: "spring", stiffness: 300, damping: 15 }}
              className={cn("select-none", emojiSize)}
            >
              {mood.label}
            </motion.span>
          </AnimatePresence>
        </motion.div>
      </motion.div>

      {/* Text */}
      <motion.div
        className="relative z-10 mt-4 text-center"
        layout
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <h1 className={cn(
          "font-outfit font-bold tracking-tight",
          expanded ? "text-3xl" : "text-2xl"
        )}>
          {greeting}
        </h1>
        {subtitle && (
          <p className={cn(
            "text-muted-foreground mt-1",
            expanded ? "text-base" : "text-sm"
          )}>
            {subtitle}
          </p>
        )}
      </motion.div>
    </motion.div>
  );
}
