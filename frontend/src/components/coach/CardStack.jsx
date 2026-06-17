/**
 * CardStack — Apple Wallet card stack + Tinder action buttons + wiggle hint.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform } from "framer-motion";
import { X, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import StackCard from "./StackCard";

const MAX_VISIBLE = 3;
const SWIPE_THRESHOLD = 80;
const SWIPE_VELOCITY = 300;

const DEPTH = [
  { scale: 1,    y: 0,  opacity: 1,    z: 30 },
  { scale: 0.95, y: 16, opacity: 0.55, z: 20 },
  { scale: 0.90, y: 30, opacity: 0.30, z: 10 },
];

function triggerHaptic() {
  if (navigator.vibrate) navigator.vibrate(12);
}

export default function CardStack({ cards, onDismiss, onAction, onActiveChange }) {
  const [exitDirection, setExitDirection] = useState(0);
  const [cardHeight, setCardHeight] = useState(280);
  const [hasInteracted, setHasInteracted] = useState(false);

  const handleSwipe = useCallback((cardKey, direction) => {
    triggerHaptic();
    setHasInteracted(true);
    setExitDirection(direction);
    onDismiss(cardKey);
  }, [onDismiss]);

  // Butonla dismiss: aktif kartı belirli yöne uçur
  const handleButtonDismiss = useCallback((direction) => {
    if (cards.length === 0) return;
    const activeCard = cards[0];
    triggerHaptic();
    setHasInteracted(true);
    setExitDirection(direction);
    onDismiss(activeCard.key);
  }, [cards, onDismiss]);

  // Butonla action: aktif kartın CTA'sını tetikle
  const handleButtonAction = useCallback(() => {
    if (cards.length === 0) return;
    const activeCard = cards[0];
    if (activeCard.action) {
      onAction(activeCard.action);
    } else {
      // CTA yoksa sağa dismiss
      handleButtonDismiss(1);
    }
  }, [cards, onAction, handleButtonDismiss]);

  const peekTotal = cards.length >= 3 ? DEPTH[2].y : cards.length >= 2 ? DEPTH[1].y : 0;
  const stackHeight = cardHeight + peekTotal + 8;

  return (
    <div className="relative w-full">
      {/* Kart alanı */}
      <div className="relative" style={{ minHeight: Math.max(stackHeight, 200) }}>
        <AnimatePresence mode="popLayout" initial={false}>
          {cards.slice(0, MAX_VISIBLE).map((card, index) => (
            <StackCardWrapper
              key={card.key}
              card={card}
              index={index}
              isActive={index === 0}
              exitDirection={exitDirection}
              onSwipe={handleSwipe}
              onAction={onAction}
              onMeasure={index === 0 ? (h) => setCardHeight(h) : undefined}
              shouldWiggle={index === 0 && !hasInteracted}
              onInteract={() => setHasInteracted(true)}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Dot indicator + Action buttons */}
      {cards.length > 0 && (
        <div className="mt-5 space-y-4">
          {/* Tinder-style action buttons */}
          <div className="flex items-center justify-center gap-6">
            {/* ✕ Geç */}
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => handleButtonDismiss(-1)}
              className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                "border border-white/10 bg-white/[0.03]",
                "text-white/40 hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-500/5",
                "transition-colors"
              )}
            >
              <X className="w-5 h-5" />
            </motion.button>

            {/* Dot indicator (ortada) */}
            <div className="flex items-center gap-1.5">
              {cards.slice(0, Math.min(cards.length, 7)).map((card, i) => (
                <motion.div
                  key={card.key}
                  className={cn(
                    "rounded-full transition-all duration-300",
                    i === 0 ? "w-6 h-1.5 bg-white/50" : "w-1.5 h-1.5 bg-white/15"
                  )}
                  layout
                />
              ))}
              {cards.length > 7 && (
                <span className="text-[9px] text-white/20 ml-0.5">+{cards.length - 7}</span>
              )}
            </div>

            {/* ✓ Yap */}
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={handleButtonAction}
              className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                "border border-emerald-500/20 bg-emerald-500/10",
                "text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/30",
                "transition-colors"
              )}
            >
              <Check className="w-5 h-5" />
            </motion.button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tek kart wrapper ──

function StackCardWrapper({ card, index, isActive, exitDirection, onSwipe, onAction, onMeasure, shouldWiggle, onInteract }) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-250, 0, 250], [-12, 0, 12]);
  const leftIndicator = useTransform(x, [-120, -40, 0], [1, 0, 0]);
  const rightIndicator = useTransform(x, [0, 40, 120], [0, 0, 1]);
  const cardRef = useRef(null);

  useEffect(() => {
    if (isActive && cardRef.current && onMeasure) {
      requestAnimationFrame(() => {
        const h = cardRef.current?.getBoundingClientRect().height;
        if (h > 0) onMeasure(h);
      });
    }
  }, [isActive, onMeasure, card.key]);

  const depth = DEPTH[index] || DEPTH[2];

  const handleDragEnd = useCallback((_, info) => {
    const { offset, velocity } = info;
    if (Math.abs(offset.x) > SWIPE_THRESHOLD || Math.abs(velocity.x) > SWIPE_VELOCITY) {
      onSwipe(card.key, offset.x > 0 ? 1 : -1);
    }
  }, [card.key, onSwipe]);

  // Wiggle: ilk kart, kullanıcı henüz etkileşmemişse 1.5s sonra salla
  const wiggleAnimation = shouldWiggle
    ? {
        scale: depth.scale,
        y: depth.y,
        opacity: depth.opacity,
        x: [0, -15, 12, -8, 5, 0],
      }
    : {
        scale: depth.scale,
        y: depth.y,
        opacity: depth.opacity,
      };

  const wiggleTransition = shouldWiggle
    ? {
        x: { delay: 1.2, duration: 0.8, ease: "easeInOut" },
        default: { type: "spring", stiffness: 300, damping: 22 },
      }
    : { type: "spring", stiffness: 300, damping: 22 };

  return (
    <motion.div
      ref={cardRef}
      className={cn(
        "absolute inset-x-0 top-0",
        isActive ? "z-30 cursor-grab active:cursor-grabbing" : "pointer-events-none"
      )}
      style={{
        x: isActive ? x : 0,
        rotate: isActive ? rotate : 0,
        zIndex: depth.z,
      }}
      initial={{
        scale: (DEPTH[index + 1] || DEPTH[2]).scale,
        y: (DEPTH[index + 1] || DEPTH[2]).y,
        opacity: 0,
      }}
      animate={wiggleAnimation}
      exit={{
        x: exitDirection > 0 ? 500 : -500,
        opacity: 0,
        scale: 0.85,
        rotate: exitDirection > 0 ? 20 : -20,
        transition: { type: "spring", stiffness: 250, damping: 25 },
      }}
      transition={wiggleTransition}
      drag={isActive ? "x" : false}
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.85}
      onDragStart={isActive ? onInteract : undefined}
      onDragEnd={isActive ? handleDragEnd : undefined}
    >
      {/* Swipe indicator'lar */}
      {isActive && (
        <>
          <motion.div
            className="absolute -left-2 top-1/2 -translate-y-1/2 z-40
                       text-xs font-semibold text-rose-400 bg-rose-500/10
                       backdrop-blur-sm px-3 py-1.5 rounded-full border border-rose-500/20"
            style={{ opacity: leftIndicator }}
          >
            ← Geç
          </motion.div>
          <motion.div
            className="absolute -right-2 top-1/2 -translate-y-1/2 z-40
                       text-xs font-semibold text-emerald-400 bg-emerald-500/10
                       backdrop-blur-sm px-3 py-1.5 rounded-full border border-emerald-500/20"
            style={{ opacity: rightIndicator }}
          >
            Yap →
          </motion.div>
        </>
      )}

      <StackCard card={card} isActive={isActive} onAction={onAction} stackIndex={index} />
    </motion.div>
  );
}
