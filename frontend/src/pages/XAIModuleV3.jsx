/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * XAIModuleV3 — Orriso-Style Spatial Canvas Workspace
 *
 * Premium glassmorphic UI over warm gray-beige canvas.
 * Floating panels, rainbow prompt bar, persona cards, dark-pill toolbars.
 * All business logic preserved from XAIModuleV2.
 *
 * Design skills applied: shadcn-ui, react-expert, superdesign
 */
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Sparkles,
  Zap,
  Plus,
  Minus,
  RefreshCw,
  Image as ImageIcon,
  X,
  Copy,
  Heart,
  ChevronDown,
  Paperclip,
  Settings2,
  Type,
  ArrowRight,
  Check,
  Loader2,
  Clock,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useProfile } from "@/contexts/ProfileContext";

/* ═══════════════════════════════════════════════════════════
   CONFIGURATION
   ═══════════════════════════════════════════════════════════ */

const PERSONAS = [
  { id: "saf", label: "Saf", bg: "#E88B9C", emoji: "💗" },
  { id: "otorite", label: "Otorite", bg: "#D4A854", emoji: "👔" },
  { id: "insider", label: "Insider", bg: "#5B8A5E", emoji: "🤫" },
  { id: "mentalist", label: "Mentalist", bg: "#7B6BAA", emoji: "🔮" },
  { id: "haber", label: "Haber", bg: "#C45A4A", emoji: "📢" },
];

const TONES = [
  { id: "natural", label: "Natural" },
  { id: "raw", label: "Raw" },
  { id: "polished", label: "Polished" },
  { id: "unhinged", label: "Unhinged" },
];

const LENGTHS = [
  { id: "micro", label: "Micro", range: "50-100" },
  { id: "punch", label: "Punch", range: "140-280" },
  { id: "spark", label: "Spark", range: "400-600" },
  { id: "storm", label: "Storm", range: "700-1K" },
  { id: "thread", label: "Thread", range: "3-7 tweet" },
];

const CONTENT_TYPES = [
  { id: "tweet", label: "Tweet" },
  { id: "quote", label: "Alıntı" },
  { id: "reply", label: "Yanıt" },
  { id: "article", label: "Makale" },
];

const KNOWLEDGE_OPTIONS = [
  { id: null, label: "Yok" },
  { id: "insider", label: "Insider" },
  { id: "contrarian", label: "Contrarian" },
  { id: "hidden", label: "Hidden" },
  { id: "expert", label: "Expert" },
];

const LANGUAGE_OPTIONS = [
  { id: "auto", label: "Oto" },
  { id: "tr", label: "TR" },
  { id: "en", label: "EN" },
];

/* ═══════════════════════════════════════════════════════════
   INLINE KEYFRAMES — injected once for stagger + shimmer
   ═══════════════════════════════════════════════════════════ */

const KEYFRAMES_ID = "xai-v3-keyframes";

function useKeyframes() {
  useEffect(() => {
    if (document.getElementById(KEYFRAMES_ID)) return;
    const style = document.createElement("style");
    style.id = KEYFRAMES_ID;
    style.textContent = `
      @keyframes xv3-fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }
      @keyframes xv3-shimmer {
        0%   { background-position: -200% 0; }
        100% { background-position: 200% 0; }
      }
      @keyframes xv3-pulseGlow {
        0%, 100% { opacity: 0.4; }
        50%      { opacity: 0.8; }
      }
      @keyframes xv3-float {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-6px); }
      }
      .xv3-stagger-enter {
        animation: xv3-fadeInUp 400ms ease-out both;
      }
      .xv3-scroll-hidden::-webkit-scrollbar { display: none; }
      .xv3-scroll-hidden { scrollbar-width: none; }
    `;
    document.head.appendChild(style);
    return () => {
      const el = document.getElementById(KEYFRAMES_ID);
      if (el) el.remove();
    };
  }, []);
}

/* ═══════════════════════════════════════════════════════════
   STYLE HELPERS
   ═══════════════════════════════════════════════════════════ */

/** Standard glassmorphic panel style — layered shadows for depth */
const glass = {
  background: "rgba(255, 255, 255, 0.12)",
  backdropFilter: "blur(40px)",
  WebkitBackdropFilter: "blur(40px)",
  border: "1px solid rgba(255, 255, 255, 0.18)",
  borderRadius: "24px",
  boxShadow: [
    "0 8px 32px rgba(0, 0, 0, 0.25)",
    "0 2px 8px rgba(0, 0, 0, 0.12)",
    "inset 0 1px 0 rgba(255, 255, 255, 0.12)",
    "inset 0 -1px 0 rgba(0, 0, 0, 0.05)",
  ].join(", "),
};

/** Dark charcoal pill (Orriso toolbar style) */
const pill = {
  background: "#3A3A3A",
  borderRadius: "50px",
  border: "1px solid rgba(255, 255, 255, 0.10)",
  boxShadow: [
    "0 4px 24px rgba(0, 0, 0, 0.20)",
    "0 1px 4px rgba(0, 0, 0, 0.10)",
    "inset 0 1px 0 rgba(255, 255, 255, 0.06)",
  ].join(", "),
};

/** Prompt bar glass — slightly different tint */
const promptGlass = {
  background: "rgba(255, 255, 255, 0.10)",
  backdropFilter: "blur(48px)",
  WebkitBackdropFilter: "blur(48px)",
  border: "1px solid rgba(255, 255, 255, 0.16)",
  borderRadius: "24px",
  boxShadow: [
    "0 12px 48px rgba(0, 0, 0, 0.30)",
    "0 4px 12px rgba(0, 0, 0, 0.15)",
    "inset 0 1px 0 rgba(255, 255, 255, 0.14)",
  ].join(", "),
};

/* Rainbow gradient string (used in prompt bar bottom border) */
const RAINBOW =
  "linear-gradient(90deg, #4CAF50, #8BC34A, #FFEB3B, #FF9800, #F44336, #E91E63, #9C27B0, #2196F3, #00BCD4)";

/* ═══════════════════════════════════════════════════════════
   SUB-COMPONENTS
   ═══════════════════════════════════════════════════════════ */

/* ── Dark Charcoal Pill Selector ───────────────────────── */
function DarkPillSelector({ options, value, onChange, className = "", ariaLabel }) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn("inline-flex items-center p-1 gap-0.5", className)}
      style={pill}
    >
      {options.map((opt) => (
        <button
          key={opt.id}
          role="radio"
          aria-checked={value === opt.id}
          onClick={() => onChange(opt.id)}
          className={cn(
            "px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap",
            "transition-all duration-300 ease-out",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30 focus-visible:ring-offset-1 focus-visible:ring-offset-transparent",
            value === opt.id
              ? "bg-white text-black shadow-[0_2px_8px_rgba(0,0,0,0.15)]"
              : "text-white/60 hover:text-white/90 hover:bg-white/[0.06]"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/* ── Persona Card ──────────────────────────────────────── */
function PersonaCard({ persona, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`Karakter: ${persona.label}`}
      className={cn(
        "flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs font-bold whitespace-nowrap",
        "transition-all duration-300 ease-out",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent",
        selected
          ? "scale-105 text-white"
          : "opacity-55 hover:opacity-85 text-white/90 hover:scale-[1.02]"
      )}
      style={{
        backgroundColor: persona.bg,
        boxShadow: selected
          ? `0 6px 20px ${persona.bg}88, 0 2px 6px ${persona.bg}44, inset 0 1px 0 rgba(255,255,255,0.25)`
          : `0 2px 8px rgba(0,0,0,0.15)`,
      }}
    >
      <span className="text-sm leading-none">{persona.emoji}</span>
      {persona.label}
    </button>
  );
}

/* ── Result Card ───────────────────────────────────────── */
function ResultCard({ content, index, onCopy, onFavorite, isFavorited, staggerDelay }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    onCopy();
    setCopied(true);
    const t = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(t);
  }, [onCopy]);

  return (
    <article
      className="xv3-stagger-enter p-5 group transition-all duration-300 ease-out hover:scale-[1.015] hover:translate-y-[-2px]"
      style={{
        ...glass,
        borderRadius: "20px",
        animationDelay: `${staggerDelay}ms`,
        /* elevate shadow on hover via CSS custom property trick */
      }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2.5 mb-3">
            <div
              className="h-7 w-7 rounded-full flex items-center justify-center shrink-0"
              style={{ background: "linear-gradient(135deg, #8B5CF6, #D946EF)" }}
            >
              <span className="text-[10px] font-bold text-white select-none">
                #{index + 1}
              </span>
            </div>
            <span className="text-xs text-white/35 font-medium">{content.length} karakter</span>
          </div>

          {/* Body */}
          <p className="text-[15px] leading-[1.7] text-white/90 whitespace-pre-wrap selection:bg-violet-500/30">
            {content}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-white/[0.08]">
        <button
          onClick={handleCopy}
          aria-label={copied ? "Kopyalandı" : "Kopyala"}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium",
            "transition-all duration-300 ease-out",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
            copied
              ? "text-green-400 bg-green-500/10"
              : "text-white/45 hover:text-white hover:bg-white/[0.08]"
          )}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Kopyalandı" : "Kopyala"}
        </button>
        <button
          onClick={onFavorite}
          aria-label={isFavorited ? "Favorilerden kaldır" : "Favorilere ekle"}
          aria-pressed={isFavorited}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium",
            "transition-all duration-300 ease-out",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pink-400/40",
            isFavorited
              ? "text-pink-400 bg-pink-500/12"
              : "text-white/45 hover:text-pink-400 hover:bg-white/[0.08]"
          )}
        >
          <Heart className={cn("h-3.5 w-3.5", isFavorited && "fill-current")} />
          Favori
        </button>
      </div>
    </article>
  );
}

/* ── Empty State ───────────────────────────────────────── */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center select-none">
      {/* Glowing orb */}
      <div className="relative mb-8">
        {/* Outer glow */}
        <div
          className="absolute inset-[-16px] rounded-full"
          style={{
            background: "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)",
            animation: "xv3-pulseGlow 3s ease-in-out infinite",
          }}
        />
        <div
          className="relative h-28 w-28 rounded-full flex items-center justify-center"
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(255, 255, 255, 0.10)",
            boxShadow: "0 4px 24px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255,255,255,0.08)",
          }}
        >
          <Sparkles className="h-12 w-12 text-violet-400/80" />
        </div>
        {/* Floating zap badge */}
        <div
          className="absolute -top-1 -right-1 h-8 w-8 rounded-full flex items-center justify-center"
          style={{
            background: "linear-gradient(135deg, #FBBF24, #F97316)",
            boxShadow: "0 4px 12px rgba(251, 191, 36, 0.35)",
            animation: "xv3-float 2.5s ease-in-out infinite",
          }}
        >
          <Zap className="h-3.5 w-3.5 text-white" />
        </div>
      </div>
      <h3 className="text-xl font-semibold text-white/75 mb-2 tracking-[-0.01em]">
        İçerik üretmeye hazır
      </h3>
      <p className="text-sm text-white/35 max-w-[280px] leading-relaxed">
        Aşağıdaki alana konunu yaz, karakterini seç ve üret butonuna bas.
      </p>
    </div>
  );
}

/* ── Loading State ─────────────────────────────────────── */
function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center h-full select-none">
      <div className="relative">
        <div
          className="h-16 w-16 rounded-full animate-spin"
          style={{
            border: "2px solid rgba(255,255,255,0.08)",
            borderTopColor: "#8B5CF6",
          }}
        />
        <Sparkles className="h-6 w-6 text-violet-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
      </div>
      <p className="text-sm text-white/35 mt-5 font-medium">İçerik üretiliyor…</p>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function XAIModuleV3() {
  useKeyframes();

  const [searchParams] = useSearchParams();
  const { activeProfileId, activeProfile } = useProfile();
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const lengthMenuRef = useRef(null);

  /* ─── State ─── */
  const [contentType, setContentType] = useState("tweet");
  const [mode, setMode] = useState("classic");
  const [topic, setTopic] = useState(searchParams.get("topic") || "");
  const [length, setLength] = useState("punch");
  const [variants, setVariants] = useState(3);
  const [persona, setPersona] = useState("otorite");
  const [tone, setTone] = useState("natural");
  const [knowledge, setKnowledge] = useState(null);
  const [language, setLanguage] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [favoritedIds, setFavoritedIds] = useState(new Set());
  const [generationId, setGenerationId] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [recentGenerations, setRecentGenerations] = useState([]);
  const [showLengthMenu, setShowLengthMenu] = useState(false);

  /* ─── Derived ─── */
  const currentLength = useMemo(
    () => LENGTHS.find((l) => l.id === length) || LENGTHS[1],
    [length]
  );

  /* ─── Auto-resize textarea ─── */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [topic]);

  /* ─── Close length dropdown on outside click ─── */
  useEffect(() => {
    if (!showLengthMenu) return;
    function handleClick(e) {
      if (lengthMenuRef.current && !lengthMenuRef.current.contains(e.target)) {
        setShowLengthMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showLengthMenu]);

  /* ─── Clean up image preview URL on unmount ─── */
  useEffect(() => {
    return () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview);
    };
  }, [imagePreview]);

  /* ─── Generate ─── */
  const handleGenerate = useCallback(async () => {
    if (!topic.trim()) {
      toast.error("Konu girin");
      return;
    }
    setLoading(true);
    setResults([]);
    setFavoritedIds(new Set());
    try {
      const endpoint =
        contentType === "article"
          ? "/generate/article"
          : contentType === "quote"
          ? "/generate/quote"
          : contentType === "reply"
          ? "/generate/reply"
          : "/generate/tweet";

      const body = {
        topic,
        mode: mode === "apex" ? "apex" : "classic",
        length,
        variants,
        persona,
        tone,
        knowledge,
        language,
        style_profile_id: activeProfileId || undefined,
      };

      if (contentType === "reply" || contentType === "quote") {
        body.tweet_url = topic;
      }

      const res = await api.post(`${API}${endpoint}`, body);
      const data = res.data;

      if (data.success) {
        const items = data.variants?.map((v) => v.content) || [];
        setResults(items);
        setGenerationId(data.generation_id);
        toast.success(`${items.length} varyant üretildi!`);
        setRecentGenerations((prev) => [
          {
            topic: topic.slice(0, 50),
            count: items.length,
            type: contentType,
            time: Date.now(),
          },
          ...prev.slice(0, 4),
        ]);
      } else {
        toast.error(data.error || "Üretim başarısız");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Bir hata oluştu");
    } finally {
      setLoading(false);
    }
  }, [topic, contentType, mode, length, variants, persona, tone, knowledge, language, activeProfileId]);

  const handleCopy = useCallback((text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopyalandı!");
  }, []);

  const handleFavorite = useCallback(
    async (text, variantIndex) => {
      try {
        const res = await api.post(`${API}/favorites/toggle`, {
          content: text,
          type: contentType,
          generation_id: generationId,
          variant_index: variantIndex,
        });
        setFavoritedIds((prev) => {
          const next = new Set(prev);
          if (res.data.action === "added") next.add(variantIndex);
          else next.delete(variantIndex);
          return next;
        });
        toast.success(
          res.data.action === "added" ? "Favorilere eklendi!" : "Favorilerden kaldırıldı"
        );
      } catch {
        toast.error("Favori işlemi başarısız");
      }
    },
    [contentType, generationId]
  );

  const handleImageSelect = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        toast.error("Max 5MB");
        return;
      }
      if (imagePreview) URL.revokeObjectURL(imagePreview);
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
    },
    [imagePreview]
  );

  const clearImage = useCallback(() => {
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(null);
    setImagePreview(null);
  }, [imagePreview]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleGenerate();
      }
    },
    [handleGenerate]
  );

  const placeholder = useMemo(() => {
    switch (contentType) {
      case "quote":
        return "Tweet linki yapıştır…";
      case "reply":
        return "Yanıtlamak istediğin tweet linki…";
      case "article":
        return "Makale konusunu yaz…";
      default:
        return "Konu yaz, link yapıştır veya fikir paylaş…";
    }
  }, [contentType]);

  const canGenerate = topic.trim().length > 0 && !loading;

  /* ═══════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════ */

  return (
    <div
      className="relative w-full overflow-hidden"
      style={{ background: "#B5ADA6", height: "calc(100vh - 64px)" }}
    >
      {/* ─── Subtle warm-gradient canvas texture ─── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div
          className="absolute top-[-15%] left-[-10%] w-[55%] h-[55%] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(181,173,166,0.6) 0%, transparent 70%)" }}
        />
        <div
          className="absolute bottom-[-10%] right-[-8%] w-[45%] h-[45%] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(160,152,144,0.4) 0%, transparent 70%)" }}
        />
      </div>

      {/* ══════════════════════════════════════════════════════
          FLOATING TOOLBARS — Top Center (z-30)
          ══════════════════════════════════════════════════════ */}
      <nav
        className="absolute top-5 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center gap-3"
        aria-label="İçerik araçları"
      >
        {/* Row 1: Content type */}
        <DarkPillSelector
          options={CONTENT_TYPES}
          value={contentType}
          onChange={setContentType}
          ariaLabel="İçerik türü seç"
        />

        {/* Row 2: Mode + Length + Variants + Settings */}
        <div className="flex items-center gap-3 flex-wrap justify-center">
          <DarkPillSelector
            options={[
              { id: "classic", label: "Klasik" },
              { id: "apex", label: "⚡ APEX" },
            ]}
            value={mode}
            onChange={setMode}
            ariaLabel="Mod seç"
          />

          {/* Length dropdown */}
          <div className="relative" ref={lengthMenuRef}>
            <button
              onClick={() => setShowLengthMenu((v) => !v)}
              aria-haspopup="listbox"
              aria-expanded={showLengthMenu}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white/70",
                "transition-all duration-300 ease-out",
                "hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
              )}
              style={pill}
            >
              <Type className="h-3.5 w-3.5" />
              {currentLength.label}
              <ChevronDown
                className={cn(
                  "h-3 w-3 transition-transform duration-300",
                  showLengthMenu && "rotate-180"
                )}
              />
            </button>
            {showLengthMenu && (
              <div
                role="listbox"
                aria-label="Uzunluk seç"
                className="absolute top-full left-0 mt-2 w-52 z-50 p-1.5 xv3-stagger-enter"
                style={{
                  ...glass,
                  borderRadius: "16px",
                  background: "rgba(35, 35, 35, 0.96)",
                  backdropFilter: "blur(24px)",
                }}
              >
                {LENGTHS.map((l) => (
                  <button
                    key={l.id}
                    role="option"
                    aria-selected={length === l.id}
                    onClick={() => {
                      setLength(l.id);
                      setShowLengthMenu(false);
                    }}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm",
                      "transition-all duration-200 ease-out",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20",
                      length === l.id
                        ? "bg-white/15 text-white font-medium"
                        : "text-white/55 hover:bg-white/[0.08] hover:text-white"
                    )}
                  >
                    <span>{l.label}</span>
                    <span className="text-[11px] text-white/25 font-mono">{l.range}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Variants stepper */}
          <div className="flex items-center gap-1 px-3 py-1" style={pill}>
            <button
              onClick={() => setVariants(Math.max(1, variants - 1))}
              aria-label="Varyant azalt"
              className={cn(
                "p-1.5 rounded-full transition-all duration-200",
                "text-white/50 hover:text-white hover:bg-white/10",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
              )}
            >
              <Minus className="h-3 w-3" />
            </button>
            <span className="text-sm font-bold text-white/85 w-5 text-center tabular-nums select-none">
              {variants}
            </span>
            <button
              onClick={() => setVariants(Math.min(5, variants + 1))}
              aria-label="Varyant arttır"
              className={cn(
                "p-1.5 rounded-full transition-all duration-200",
                "text-white/50 hover:text-white hover:bg-white/10",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
              )}
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>

          {/* Settings toggle */}
          <button
            onClick={() => setShowSettings((v) => !v)}
            aria-label="Ayarları aç/kapat"
            aria-expanded={showSettings}
            className={cn(
              "p-2.5 transition-all duration-300 ease-out",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
              showSettings ? "text-violet-300" : "text-white/50 hover:text-white/80"
            )}
            style={{
              ...pill,
              ...(showSettings
                ? { background: "#4A3A6A", border: "1px solid rgba(139,92,246,0.4)" }
                : {}),
            }}
          >
            <Settings2 className="h-4 w-4" />
          </button>
        </div>

        {/* Row 3: Tone selector */}
        <DarkPillSelector
          options={TONES}
          value={tone}
          onChange={setTone}
          ariaLabel="Ton seç"
        />
      </nav>

      {/* ══════════════════════════════════════════════════════
          SETTINGS PANEL — Floating below toolbars (z-30)
          ══════════════════════════════════════════════════════ */}
      {showSettings && (
        <div
          className="absolute top-[175px] left-1/2 -translate-x-1/2 z-30 w-[460px] max-w-[92vw] p-5 xv3-stagger-enter"
          style={glass}
          role="region"
          aria-label="Gelişmiş ayarlar"
        >
          <div className="grid grid-cols-2 gap-5">
            {/* Knowledge */}
            <div className="space-y-2.5">
              <label className="text-[11px] font-bold text-white/45 uppercase tracking-widest">
                Knowledge
              </label>
              <div className="flex flex-wrap gap-1.5">
                {KNOWLEDGE_OPTIONS.map((k) => (
                  <button
                    key={k.id || "none"}
                    onClick={() => setKnowledge(k.id)}
                    className={cn(
                      "px-2.5 py-1.5 rounded-lg text-xs font-medium",
                      "transition-all duration-200 ease-out",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
                      knowledge === k.id
                        ? "bg-white/15 text-white border border-white/20"
                        : "text-white/40 hover:text-white/70 hover:bg-white/[0.06]"
                    )}
                  >
                    {k.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Language */}
            <div className="space-y-2.5">
              <label className="text-[11px] font-bold text-white/45 uppercase tracking-widest">
                Dil
              </label>
              <div className="flex gap-1.5">
                {LANGUAGE_OPTIONS.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => setLanguage(l.id)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-medium",
                      "transition-all duration-200 ease-out",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
                      language === l.id
                        ? "bg-white/15 text-white border border-white/20"
                        : "text-white/40 hover:text-white/70 hover:bg-white/[0.06]"
                    )}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════
          PERSONA CARDS — Bottom-Left Panel (z-20)
          ══════════════════════════════════════════════════════ */}
      <aside
        className="absolute bottom-28 left-8 z-20 p-4 w-[260px] hidden lg:block transition-all duration-300 ease-out hover:scale-[1.015] hover:translate-y-[-2px]"
        style={glass}
        aria-label="Karakter seçimi"
      >
        <h4 className="text-[13px] font-bold text-white/90 mb-3 tracking-[-0.01em]">Karakter</h4>
        <div className="grid grid-cols-2 gap-2">
          {PERSONAS.map((p) => (
            <PersonaCard
              key={p.id}
              persona={p}
              selected={persona === p.id}
              onClick={() => setPersona(p.id)}
            />
          ))}
        </div>
      </aside>

      {/* ══════════════════════════════════════════════════════
          RIGHT PANEL — Style Profile (z-20)
          ══════════════════════════════════════════════════════ */}
      <aside
        className="absolute top-1/2 -translate-y-1/2 right-8 z-20 p-4 w-[200px] hidden xl:block transition-all duration-300 ease-out hover:scale-[1.015] hover:translate-y-[calc(-50%-2px)]"
        style={glass}
        aria-label="Stil profili"
      >
        <h4 className="text-[11px] font-bold text-white/45 uppercase tracking-widest mb-3">
          Stil Profili
        </h4>
        {activeProfile ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <div
                className="h-10 w-10 rounded-full flex items-center justify-center shrink-0"
                style={{
                  background: "linear-gradient(135deg, #8B5CF6, #D946EF)",
                  boxShadow: "0 4px 12px rgba(139, 92, 246, 0.3)",
                }}
              >
                <span className="text-sm font-bold text-white">
                  {activeProfile.name?.charAt(0)?.toUpperCase()}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white truncate">{activeProfile.name}</p>
                <p className="text-[11px] text-white/35">Aktif profil</p>
              </div>
            </div>
            {activeProfile.source_username && (
              <p className="text-xs text-white/25 truncate">@{activeProfile.source_username}</p>
            )}
          </div>
        ) : (
          <div className="text-center py-4">
            <User className="h-8 w-8 text-white/15 mx-auto mb-2" />
            <p className="text-xs text-white/25">Profil seçilmedi</p>
          </div>
        )}
      </aside>

      {/* ══════════════════════════════════════════════════════
          BOTTOM-RIGHT — Son Üretimler (z-20)
          ══════════════════════════════════════════════════════ */}
      {recentGenerations.length > 0 && (
        <aside
          className="absolute bottom-28 right-8 z-20 p-4 w-[260px] hidden lg:block transition-all duration-300 ease-out hover:scale-[1.015] hover:translate-y-[-2px]"
          style={glass}
          aria-label="Son üretimler"
        >
          <h4 className="text-[11px] font-bold text-white/45 uppercase tracking-widest mb-3">
            Son Üretimler
          </h4>
          <div className="space-y-2">
            {recentGenerations.slice(0, 3).map((gen, i) => (
              <div
                key={gen.time}
                className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl bg-white/[0.05] transition-all duration-200 ease-out hover:bg-white/[0.10]"
              >
                <Clock className="h-3.5 w-3.5 text-white/25 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-white/65 truncate font-medium">{gen.topic}</p>
                  <p className="text-[10px] text-white/25">
                    {gen.count} varyant · {gen.type}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </aside>
      )}

      {/* ══════════════════════════════════════════════════════
          CENTRAL CANVAS — Results Area (z-10)
          ══════════════════════════════════════════════════════ */}
      <main className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
        <div
          className="w-full max-w-2xl mx-auto pointer-events-auto overflow-y-auto px-4 xv3-scroll-hidden"
          style={{
            maxHeight: "calc(100vh - 300px)",
            marginTop: "150px",
          }}
        >
          {loading ? (
            <LoadingState />
          ) : results.length > 0 ? (
            <div className="space-y-4 pb-6">
              {/* Results header */}
              <div className="flex items-center justify-between px-1 xv3-stagger-enter">
                <h3 className="text-sm font-semibold text-white/65">
                  {results.length} Varyant Üretildi
                </h3>
                <button
                  onClick={handleGenerate}
                  className={cn(
                    "flex items-center gap-1.5 text-xs text-white/35 font-medium",
                    "px-3 py-1.5 rounded-full",
                    "transition-all duration-300 ease-out",
                    "hover:text-white/70 hover:bg-white/[0.08]",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
                  )}
                >
                  <RefreshCw className="h-3 w-3" /> Tekrar Üret
                </button>
              </div>

              {/* Result cards with stagger */}
              {results.map((text, i) => (
                <ResultCard
                  key={`${generationId}-${i}`}
                  content={text}
                  index={i}
                  onCopy={() => handleCopy(text)}
                  onFavorite={() => handleFavorite(text, i)}
                  isFavorited={favoritedIds.has(i)}
                  staggerDelay={i * 100}
                />
              ))}
            </div>
          ) : (
            <EmptyState />
          )}
        </div>
      </main>

      {/* ══════════════════════════════════════════════════════
          MOBILE: Persona row (visible on <lg)
          ══════════════════════════════════════════════════════ */}
      <div
        className="absolute bottom-[148px] left-4 right-4 z-20 flex items-center gap-2 overflow-x-auto lg:hidden pb-1 xv3-scroll-hidden"
        aria-label="Karakter seçimi"
      >
        <span className="text-[10px] text-white/35 shrink-0 font-bold uppercase tracking-wider mr-1">
          Karakter
        </span>
        {PERSONAS.map((p) => (
          <PersonaCard
            key={p.id}
            persona={p}
            selected={persona === p.id}
            onClick={() => setPersona(p.id)}
          />
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════
          PROMPT BAR — Bottom Center, Hero Component (z-40)
          ══════════════════════════════════════════════════════ */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 w-[92%] sm:w-[70%] lg:w-[50%] min-w-[320px] max-w-[600px]">
        <div className="relative overflow-hidden" style={promptGlass}>
          {/* ── Rainbow gradient bottom border (KEY design element) ── */}
          <div
            className="absolute bottom-0 left-0 right-0 h-[3px] z-10"
            style={{
              background: RAINBOW,
              borderRadius: "0 0 24px 24px",
            }}
          />
          {/* Subtle shimmer animation on the rainbow */}
          <div
            className="absolute bottom-0 left-0 right-0 h-[3px] z-11 pointer-events-none"
            style={{
              background:
                "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.25) 50%, transparent 100%)",
              backgroundSize: "200% 100%",
              animation: "xv3-shimmer 3s linear infinite",
              borderRadius: "0 0 24px 24px",
            }}
            aria-hidden="true"
          />

          {/* Image preview */}
          {imagePreview && (
            <div className="flex items-center gap-2 pt-3 px-4">
              <div className="relative group">
                <img
                  src={imagePreview}
                  alt="Eklenmiş görsel"
                  className="h-14 w-14 rounded-xl object-cover ring-1 ring-white/10"
                />
                <button
                  onClick={clearImage}
                  aria-label="Görseli kaldır"
                  className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-red-500/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                >
                  <X className="h-2.5 w-2.5 text-white" />
                </button>
              </div>
            </div>
          )}

          {/* Textarea */}
          <div className="px-4 pt-3 pb-1">
            <textarea
              ref={textareaRef}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={1}
              aria-label="Konu veya link gir"
              className={cn(
                "w-full bg-transparent text-[15px] text-white placeholder:text-white/25 resize-none leading-relaxed max-h-[160px]",
                "focus:outline-none",
                "selection:bg-violet-500/30"
              )}
            />
          </div>

          {/* Bottom action row */}
          <div className="flex items-center justify-between px-3 pb-3">
            <div className="flex items-center gap-0.5">
              {/* Attachment */}
              <button
                onClick={() => fileInputRef.current?.click()}
                aria-label="Dosya ekle"
                className={cn(
                  "p-2.5 rounded-xl text-white/35",
                  "transition-all duration-300 ease-out",
                  "hover:text-white/70 hover:bg-white/[0.06]",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/25"
                )}
              >
                <Paperclip className="h-[18px] w-[18px]" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
                aria-hidden="true"
              />

              {/* APEX toggle */}
              <button
                onClick={() => setMode(mode === "apex" ? "classic" : "apex")}
                aria-label={mode === "apex" ? "APEX modu kapat" : "APEX modu aç"}
                aria-pressed={mode === "apex"}
                className={cn(
                  "p-2.5 rounded-xl transition-all duration-300 ease-out",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40",
                  mode === "apex"
                    ? "text-amber-400 bg-amber-500/12"
                    : "text-white/35 hover:text-white/70 hover:bg-white/[0.06]"
                )}
              >
                <Zap className="h-[18px] w-[18px]" />
              </button>

              {/* Image button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                aria-label="Görsel ekle"
                className={cn(
                  "p-2.5 rounded-xl text-white/35",
                  "transition-all duration-300 ease-out",
                  "hover:text-white/70 hover:bg-white/[0.06]",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/25"
                )}
              >
                <ImageIcon className="h-[18px] w-[18px]" />
              </button>
            </div>

            {/* Send button — circular, violet gradient */}
            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              aria-label="Üret"
              className={cn(
                "h-10 w-10 rounded-full flex items-center justify-center shrink-0",
                "transition-all duration-300 ease-out",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent",
                canGenerate
                  ? "hover:scale-110 active:scale-95"
                  : "opacity-25 cursor-not-allowed"
              )}
              style={{
                background: canGenerate
                  ? "linear-gradient(135deg, #8B5CF6, #D946EF)"
                  : "rgba(255,255,255,0.08)",
                boxShadow: canGenerate
                  ? "0 4px 16px rgba(139, 92, 246, 0.45), 0 2px 6px rgba(217, 70, 239, 0.2)"
                  : "none",
              }}
            >
              {loading ? (
                <Loader2 className="h-[18px] w-[18px] text-white animate-spin" />
              ) : (
                <ArrowRight className="h-[18px] w-[18px] text-white" />
              )}
            </button>
          </div>

          {/* Info bar */}
          <div className="flex items-center justify-between px-4 pb-2.5 -mt-0.5">
            <div className="flex items-center gap-2 text-[11px] text-white/20 font-medium">
              <span className="tabular-nums">{topic.length}/280</span>
              <span className="text-white/10">·</span>
              <span>
                {currentLength.label} · {variants} varyant
              </span>
              {activeProfile && (
                <>
                  <span className="text-white/10">·</span>
                  <span className="text-violet-400/40">🎨 {activeProfile.name}</span>
                </>
              )}
            </div>
            <span className="text-[10px] text-white/15 font-medium hidden sm:inline">
              Enter üret · Shift+Enter satır
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
