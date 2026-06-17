/**
 * EvolveSlideOver — Premium "Refine Studio" panel
 *
 * Persona Lab kalitesinde animasyonlar:
 *   - Spring bounce açılış
 *   - Staggered cascade children
 *   - Neon glow active states
 *   - Shimmer loading skeleton
 *   - Micro-interactions (hover lift, press scale)
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  X, Copy, Send, Dna, ChevronDown, ChevronUp,
  Loader2, RotateCcw, ArrowRight, Check, Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import EvolveQuickTags from "./EvolveQuickTags";

// ─── Animation variants ───
const cascadeChild = {
  hidden: { opacity: 0, y: 20, filter: "blur(4px)" },
  visible: (i) => ({
    opacity: 1, y: 0, filter: "blur(0px)",
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  }),
};

const resultCard = {
  hidden: { opacity: 0, y: 24, scale: 0.97 },
  visible: (i) => ({
    opacity: 1, y: 0, scale: 1,
    transition: { delay: 0.1 + i * 0.07, duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  }),
};

export default function EvolveSlideOver({
  open, onClose, originalContent, variantIndex,
  parentGenerationId, onEvolve, onApply,
  mergeVariantIndices,  // number[] — merge mode when multiple variants selected
}) {
  const { t } = useTranslation();
  const panelRef = useRef(null);
  const resultsRef = useRef(null);
  const textareaRef = useRef(null);

  const [quickTags, setQuickTags] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [variantCount, setVariantCount] = useState(3);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [settingsCollapsed, setSettingsCollapsed] = useState(false);
  const [hasUnsavedResults, setHasUnsavedResults] = useState(false);

  // Reset on open
  useEffect(() => {
    if (open) {
      setQuickTags([]); setFeedback(""); setVariantCount(3);
      setLoading(false); setResults(null);
      setSettingsCollapsed(false); setHasUnsavedResults(false);
    }
  }, [open]);

  // Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === "Escape") handleClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, hasUnsavedResults]);

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  // Auto-scroll to results
  useEffect(() => {
    if (results && resultsRef.current) {
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);
    }
  }, [results]);

  const handleGenerate = async () => {
    setLoading(true);
    setSettingsCollapsed(true);
    setResults(null);
    try {
      const result = await onEvolve?.({
        parentGenerationId,
        selectedVariantIndices: mergeVariantIndices || [variantIndex],
        feedback, quickTags, variantCount,
      });
      if (result?.variants) {
        setResults({
          variants: result.variants.map((v, i) => ({
            ...v, character_count: v.character_count || v.content?.length || 0, variant_index: i,
          })),
          quickTags: [...quickTags],
        });
        setHasUnsavedResults(true);
      }
    } catch (e) {
      toast.error(t("evolve.error"));
      setSettingsCollapsed(false);
    } finally { setLoading(false); }
  };

  const handleApply = () => {
    if (results) { onApply?.(results.variants, results.quickTags); setHasUnsavedResults(false); onClose(); }
  };

  const handleRetry = () => { setResults(null); setSettingsCollapsed(false); setHasUnsavedResults(false); };

  const handleCopy = (content) => { navigator.clipboard.writeText(content); toast.success("Kopyalandı ✓"); };
  const handleTweet = (content) => { window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(content)}`, "_blank"); };

  const handleFeedbackChange = (e) => {
    setFeedback(e.target.value);
    if (textareaRef.current) { textareaRef.current.style.height = "auto"; textareaRef.current.style.height = textareaRef.current.scrollHeight + "px"; }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* ─── BACKDROP ─── */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-xl z-50"
            onClick={handleClose}
          />

          {/* ─── PANEL ─── */}
          <motion.div
            ref={panelRef}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className={cn(
              "fixed z-50 bg-[#0A0A0A] flex flex-col overflow-hidden",
              // Desktop
              "sm:right-0 sm:top-0 sm:bottom-0 sm:w-[460px] sm:border-l sm:border-white/[0.08]",
              // Mobile: bottom sheet
              "max-sm:inset-x-0 max-sm:bottom-0 max-sm:top-10 max-sm:rounded-t-2xl max-sm:border-t max-sm:border-white/[0.08]",
            )}
            style={{ boxShadow: "0 0 80px rgba(139, 92, 246, 0.08), -20px 0 60px rgba(0,0,0,0.5)" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* ═══ STICKY HEADER ═══ */}
            <div className="shrink-0 border-b border-white/[0.06] bg-[#0A0A0A]/90 backdrop-blur-md z-10">
              {/* Mobile drag handle */}
              <div className="sm:hidden flex justify-center pt-2 pb-1">
                <div className="w-8 h-1 rounded-full bg-white/15" />
              </div>

              {/* Title */}
              <motion.div
                custom={0} variants={cascadeChild} initial="hidden" animate="visible"
                className="flex items-center justify-between px-5 py-3"
              >
                <div className="flex items-center gap-3">
                  <motion.div
                    animate={{ boxShadow: ["0 0 15px rgba(139,92,246,0.2)", "0 0 25px rgba(139,92,246,0.4)", "0 0 15px rgba(139,92,246,0.2)"] }}
                    transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500/25 to-fuchsia-500/25 flex items-center justify-center border border-violet-500/20"
                  >
                    <Dna className="h-4 w-4 text-violet-400" />
                  </motion.div>
                  <div>
                    <h3 className="text-sm font-bold text-white tracking-tight">Geliştirme Stüdyosu</h3>
                    <p className="text-[11px] text-white/30">
                      {mergeVariantIndices?.length > 1
                        ? `${mergeVariantIndices.length} varyant birleştiriliyor`
                        : "İnce ayar yap, karşılaştır, uygula"}
                    </p>
                  </div>
                </div>
                <motion.button
                  whileHover={{ scale: 1.1, backgroundColor: "rgba(255,255,255,0.1)" }}
                  whileTap={{ scale: 0.9 }}
                  onClick={handleClose}
                  className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center transition-colors"
                >
                  <X className="h-4 w-4 text-white/50" />
                </motion.button>
              </motion.div>

              {/* Original text */}
              <motion.div custom={1} variants={cascadeChild} initial="hidden" animate="visible" className="px-5 pb-3">
                <p className="text-[10px] uppercase tracking-widest text-violet-400/40 mb-1.5 font-medium">Orijinal Metin</p>
                <div className="px-3.5 py-2.5 rounded-xl bg-white/[0.025] border border-white/[0.05] relative overflow-hidden">
                  <p className="text-xs text-white/45 leading-relaxed line-clamp-3">{originalContent}</p>
                  {/* Subtle gradient fade at bottom */}
                  <div className="absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-[#0A0A0A]/80 to-transparent pointer-events-none" />
                </div>
              </motion.div>
            </div>

            {/* ═══ SCROLLABLE BODY ═══ */}
            <div className="flex-1 overflow-y-auto scrollbar-hide">
              {/* ─── SETTINGS ─── */}
              <div className="border-b border-white/[0.04]">
                <motion.button
                  custom={2} variants={cascadeChild} initial="hidden" animate="visible"
                  onClick={() => setSettingsCollapsed(!settingsCollapsed)}
                  className="flex items-center justify-between w-full px-5 py-3 text-left group"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-3.5 w-3.5 text-violet-400" />
                    <span className="text-xs font-medium text-white/60 group-hover:text-white/80 transition-colors">
                      {settingsCollapsed ? "Ayarlar" : "Nasıl geliştireyim?"}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {settingsCollapsed && quickTags.length > 0 && (
                      <div className="flex items-center gap-1">
                        {quickTags.slice(0, 3).map((tag, i) => (
                          <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400/50 border border-violet-500/15">
                            {t(`evolve.tags.${tag}`, tag)}
                          </span>
                        ))}
                        {quickTags.length > 3 && <span className="text-[10px] text-white/25">+{quickTags.length - 3}</span>}
                      </div>
                    )}
                    <motion.div animate={{ rotate: settingsCollapsed ? 0 : 180 }} transition={{ duration: 0.2 }}>
                      <ChevronDown className="h-3.5 w-3.5 text-white/25" />
                    </motion.div>
                  </div>
                </motion.button>

                <AnimatePresence initial={false}>
                  {!settingsCollapsed && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                      className="overflow-hidden"
                    >
                      <div className="px-5 pb-4 space-y-4">
                        <motion.div custom={3} variants={cascadeChild} initial="hidden" animate="visible">
                          <EvolveQuickTags selectedTags={quickTags} onTagsChange={setQuickTags} />
                        </motion.div>

                        {/* Textarea */}
                        <motion.div custom={4} variants={cascadeChild} initial="hidden" animate="visible">
                          <p className="text-[11px] text-white/30 mb-1.5">Ek yönerge (opsiyonel)</p>
                          <textarea
                            ref={textareaRef}
                            value={feedback}
                            onChange={handleFeedbackChange}
                            placeholder="Neyi değiştirmemi istersin?"
                            className="w-full bg-white/[0.025] border border-white/[0.06] rounded-xl p-3 text-sm text-white/80 resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/30 focus:shadow-[0_0_20px_rgba(139,92,246,0.15)] placeholder:text-white/15 transition-all min-h-[44px] max-h-[120px]"
                            rows={1}
                          />
                        </motion.div>

                        {/* Variant count */}
                        <motion.div custom={5} variants={cascadeChild} initial="hidden" animate="visible" className="flex items-center gap-2.5">
                          <span className="text-[11px] text-white/30">Varyant:</span>
                          <div className="flex gap-1.5">
                            {[1, 2, 3, 4, 5].map((n) => (
                              <motion.button
                                key={n}
                                whileHover={{ y: -2 }}
                                whileTap={{ scale: 0.9 }}
                                onClick={() => setVariantCount(n)}
                                className={cn(
                                  "w-8 h-8 rounded-lg text-xs font-semibold transition-all duration-200",
                                  variantCount === n
                                    ? "bg-violet-500/20 text-violet-300 ring-1 ring-violet-500/40 shadow-[0_0_12px_rgba(139,92,246,0.25)]"
                                    : "text-white/30 hover:text-white/60 hover:bg-white/5"
                                )}
                              >
                                {n}
                              </motion.button>
                            ))}
                          </div>
                        </motion.div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* ─── SHIMMER LOADING ─── */}
              {loading && (
                <div className="px-5 py-6 space-y-3">
                  {Array.from({ length: variantCount }).map((_, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.08 }}
                      className="rounded-xl border border-white/[0.04] p-4 relative overflow-hidden"
                    >
                      {/* Shimmer sweep */}
                      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite]"
                        style={{
                          background: "linear-gradient(90deg, transparent 0%, rgba(139,92,246,0.06) 50%, transparent 100%)",
                        }}
                      />
                      <div className="space-y-2.5 relative">
                        <div className="h-3 bg-white/[0.04] rounded-full w-full" />
                        <div className="h-3 bg-white/[0.03] rounded-full w-4/5" />
                        <div className="h-3 bg-white/[0.02] rounded-full w-3/5" />
                      </div>
                    </motion.div>
                  ))}

                  {/* Animated connector line */}
                  <div className="flex flex-col items-center gap-2 pt-2">
                    <div className="relative w-px h-8">
                      <div className="absolute inset-0 bg-gradient-to-b from-violet-500/40 to-transparent" />
                      <motion.div
                        animate={{ y: [0, 32, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
                        className="absolute top-0 w-1.5 h-1.5 -left-[2px] rounded-full bg-violet-400 shadow-[0_0_8px_rgba(139,92,246,0.6)]"
                      />
                    </div>
                    <span className="text-xs text-violet-400/60 font-medium">Üretiliyor...</span>
                  </div>
                </div>
              )}

              {/* ─── RESULTS ─── */}
              {results && !loading && (
                <div ref={resultsRef} className="px-5 py-4 space-y-3">
                  <motion.div
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
                    className="flex items-center justify-between"
                  >
                    <p className="text-[10px] uppercase tracking-widest text-violet-400/40 font-medium">
                      Sonuçlar ({results.variants.length})
                    </p>
                    {results.quickTags?.length > 0 && (
                      <div className="flex items-center gap-1">
                        {results.quickTags.map((tag, i) => (
                          <span key={i} className="text-[9px] px-1.5 py-0.5 rounded-full bg-violet-500/8 text-violet-400/40 border border-violet-500/10">
                            {t(`evolve.tags.${tag}`, tag)}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>

                  {results.variants.map((variant, index) => (
                    <motion.div
                      key={index}
                      custom={index}
                      variants={resultCard}
                      initial="hidden"
                      animate="visible"
                      className="group rounded-xl border border-white/[0.05] bg-white/[0.012] hover:border-violet-500/20 hover:bg-violet-500/[0.015] hover:shadow-[0_0_30px_rgba(139,92,246,0.06)] transition-all duration-300"
                    >
                      <div className="px-4 py-3.5">
                        <p className="text-[13px] text-white/85 leading-[1.7] whitespace-pre-wrap">{variant.content}</p>
                      </div>
                      <div className="flex items-center justify-between px-4 py-2.5 border-t border-white/[0.03]">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-white/20 tabular-nums">{variant.content?.length || 0} karakter</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-violet-500/8 text-violet-400/40 font-medium">#{index + 1}</span>
                        </div>
                        <div className="flex items-center gap-0.5 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-200">
                          <motion.button
                            whileHover={{ y: -1 }} whileTap={{ scale: 0.95 }}
                            onClick={() => handleCopy(variant.content)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] text-white/40 hover:text-white hover:bg-white/5 transition-all"
                          >
                            <Copy className="h-3 w-3" /> Kopyala
                          </motion.button>
                          <motion.button
                            whileHover={{ y: -1 }} whileTap={{ scale: 0.95 }}
                            onClick={() => handleTweet(variant.content)}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] text-sky-400/60 hover:text-sky-400 hover:bg-sky-500/8 transition-all"
                          >
                            <Send className="h-3 w-3" /> Tweetle
                          </motion.button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* ═══ STICKY FOOTER ═══ */}
            <div className="shrink-0 border-t border-white/[0.06] px-5 py-3.5 bg-[#0A0A0A]/95 backdrop-blur-md">
              {results && !loading ? (
                <div className="flex items-center gap-2.5">
                  <motion.button
                    whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={handleRetry}
                    className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-medium text-white/50 hover:text-white/80 bg-white/[0.04] hover:bg-white/[0.07] border border-white/[0.06] transition-all"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Tekrar Dne
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => { setHasUnsavedResults(false); onClose(); }}
                    className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold text-white bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.08] transition-all"
                  >
                    <X className="h-4 w-4" /> Kapat
                  </motion.button>
                </div>
              ) : (
                <div className="flex items-center gap-2.5">
                  {quickTags.length > 0 && !loading && (
                    <motion.button
                      whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                      onClick={() => { setQuickTags([]); setFeedback(""); }}
                      className="flex items-center gap-1 px-3 py-2.5 rounded-xl text-[11px] text-white/35 hover:text-white/60 bg-white/[0.03] hover:bg-white/[0.05] border border-white/[0.04] transition-all"
                    >
                      <RotateCcw className="h-3 w-3" /> Temizle
                    </motion.button>
                  )}
                  <motion.button
                    whileHover={!loading ? { scale: 1.01, boxShadow: "0 0 30px rgba(139,92,246,0.3)" } : {}}
                    whileTap={!loading ? { scale: 0.98 } : {}}
                    onClick={handleGenerate}
                    disabled={loading}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all",
                      loading
                        ? "bg-violet-500/15 text-violet-400/40 cursor-not-allowed"
                        : "text-white bg-gradient-to-r from-violet-600 to-fuchsia-500 hover:from-violet-500 hover:to-fuchsia-400 shadow-lg shadow-violet-500/25"
                    )}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                    {loading ? "Üretiliyor..." : "Geliştir"}
                  </motion.button>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
