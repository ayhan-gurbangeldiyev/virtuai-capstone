/**
 * InboxZero — Tüm kartlar bittiğinde tatmin edici empty state.
 * Confetti-style animasyon + motivasyon mesajı.
 */
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

// Rastgele parçacıklar
const PARTICLES = Array.from({ length: 12 }, (_, i) => ({
  id: i,
  x: Math.random() * 200 - 100,
  y: Math.random() * -150 - 50,
  rotate: Math.random() * 360,
  delay: Math.random() * 0.5,
  scale: 0.5 + Math.random() * 0.5,
  emoji: ["✨", "🎉", "⚡", "💜", "🚀", "🎯"][i % 6],
}));

export default function InboxZero() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      className="relative flex flex-col items-center justify-center py-16 px-6"
      style={{ minHeight: 300 }}
    >
      {/* Particle burst */}
      {PARTICLES.map((p) => (
        <motion.span
          key={p.id}
          className="absolute text-lg pointer-events-none select-none"
          initial={{ opacity: 0, x: 0, y: 0, scale: 0, rotate: 0 }}
          animate={{
            opacity: [0, 1, 0],
            x: p.x,
            y: p.y,
            scale: p.scale,
            rotate: p.rotate,
          }}
          transition={{
            duration: 1.2,
            delay: p.delay,
            ease: "easeOut",
          }}
        >
          {p.emoji}
        </motion.span>
      ))}

      {/* Glow */}
      <div className="absolute w-32 h-32 rounded-full bg-purple-500/20 blur-3xl" />

      {/* Icon */}
      <motion.div
        className="relative z-10 w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-2xl mb-6"
        animate={{
          scale: [1, 1.05, 1],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        <Sparkles className="h-8 w-8 text-white" />
      </motion.div>

      {/* Text */}
      <motion.h3
        className="relative z-10 text-xl font-bold text-center mb-2"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        Günün tüm analizlerini inceledin!
      </motion.h3>

      <motion.p
        className="relative z-10 text-sm text-white/40 text-center max-w-xs"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        Şimdi sahne senin. Git ve o viral içeriği yaz! ✨
      </motion.p>
    </motion.div>
  );
}
