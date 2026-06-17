import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Copy, Check, RotateCcw, Loader2, MessageCircle, Repeat2,
  ThumbsUp, Swords, HelpCircle, Lightbulb, Laugh,
  Sparkles, ChevronDown,
} from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import api, { API } from "@/lib/api";
import { formatNumber } from "@/lib/feedUtils";

/* ── Animation Variants ── */
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

/* ── Constants ── */
const MODES = [
  { id: "reply", label: "Reply", icon: MessageCircle },
  { id: "quote", label: "Quote", icon: Repeat2 },
];

const REPLY_STYLES = [
  { id: "support", label: "Destek", icon: ThumbsUp },
  { id: "challenge", label: "Karsi", icon: Swords },
  { id: "question", label: "Soru", icon: HelpCircle },
  { id: "expand", label: "Genislet", icon: Lightbulb },
  { id: "joke", label: "Espri", icon: Laugh },
];

const ETKI_OPTIONS = [
  { id: "patlassin", label: "Patlassin", emoji: "\uD83D\uDD25" },
  { id: "konustursun", label: "Konustursun", emoji: "\uD83D\uDCAC" },
  { id: "ogretsin", label: "Ogretsin", emoji: "\uD83E\uDDE0" },
  { id: "iz_biraksin", label: "Iz Biraksin", emoji: "\u2728" },
  { id: "shitpost", label: "Shitpost", emoji: "\uD83D\uDC80" },
];

const KARAKTER_OPTIONS = [
  { id: "uzman", label: "Uzman", emoji: "\uD83C\uDFAF" },
  { id: "otorite", label: "Otorite", emoji: "\uD83C\uDFDB\uFE0F" },
  { id: "iceriden", label: "Iceriden", emoji: "\uD83D\uDD11" },
  { id: "mentalist", label: "Mentalist", emoji: "\uD83E\uDDFF" },
  { id: "haberci", label: "Haberci", emoji: "\uD83D\uDCE1" },
];

const UZUNLUK_OPTIONS = [
  { id: "micro", label: "Micro", emoji: "\u26A1" },
  { id: "punch", label: "Punch", emoji: "\uD83E\uDD4A" },
  { id: "spark", label: "Spark", emoji: "\uD83D\uDCA5" },
];

const SMART_DEFAULTS = {
  patlassin:   { karakter: "uzman",    uzunluk: "punch" },
  konustursun: { karakter: "iceriden", uzunluk: "spark" },
  ogretsin:    { karakter: "otorite",  uzunluk: "punch" },
  iz_biraksin: { karakter: "uzman",    uzunluk: "spark" },
  shitpost:    { karakter: "haberci",  uzunluk: "micro" },
};

/* ── Helper Components ── */
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("Kopyalandi");
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <motion.button
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      onClick={handleCopy}
      className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
    </motion.button>
  );
}

function PillGroup({ label, options, value, onChange }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">{label}</label>
      <div className="flex flex-wrap gap-1.5">
        {options.map(({ id, label: optLabel, emoji }) => (
          <motion.button
            key={id}
            onClick={() => onChange(id)}
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.93 }}
            className={cn(
              "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
              value === id
                ? "bg-purple-500/10 text-purple-400 border-purple-500/25 shadow-[0_0_8px_rgba(139,92,246,0.15)]"
                : "bg-transparent text-muted-foreground border-border/50 hover:border-purple-500/20 hover:text-foreground"
            )}
          >
            {emoji && <span className="text-xs">{emoji}</span>}
            {optLabel}
          </motion.button>
        ))}
      </div>
    </div>
  );
}

/* ── Main Component ── */
export function FeedGeneratePanel({ open, onOpenChange, item }) {
  const [mode, setMode] = useState("reply");
  const [replyMode, setReplyMode] = useState("support");
  const [direction, setDirection] = useState("");
  const [loading, setLoading] = useState(false);
  const [variants, setVariants] = useState([]);

  // V2 settings
  const [etki, setEtki] = useState("konustursun");
  const [karakter, setKarakter] = useState("iceriden");
  const [uzunluk, setUzunluk] = useState("spark");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const resetState = useCallback(() => {
    setMode("reply");
    setReplyMode("support");
    setDirection("");
    setVariants([]);
    setLoading(false);
    setEtki("konustursun");
    setKarakter("iceriden");
    setUzunluk("spark");
    setAdvancedOpen(false);
  }, []);

  const handleOpenChange = (val) => {
    if (!val) resetState();
    onOpenChange(val);
  };

  const handleEtkiChange = (newEtki) => {
    setEtki(newEtki);
    const defaults = SMART_DEFAULTS[newEtki];
    if (defaults) {
      setKarakter(defaults.karakter);
      setUzunluk(defaults.uzunluk);
    }
    setVariants([]);
  };

  const handleGenerate = async () => {
    if (!item) return;
    setLoading(true);
    setVariants([]);

    const endpoint = mode === "quote" ? "/v2/generate/quote" : "/v2/generate/reply";
    const body = {
      tweet_url: item.tweet_url,
      tweet_content: item.content,
      etki,
      karakter,
      yapi: "dogal",
      uzunluk,
      acilis: "otomatik",
      bitis: mode === "reply" ? "soru" : "otomatik",
      derinlik: "standart",
      language: "tr",
      variants: 3,
      ...(direction && { direction }),
      ...(mode === "reply" && { reply_mode: replyMode }),
    };

    try {
      const res = await api.post(`${API}${endpoint}`, body);
      const data = res.data;
      if (data.success === false) {
        toast.error(data.error || "Uretim basarisiz");
      } else {
        const v = data.variants?.map((v) => v.content) || [];
        if (v.length === 0 && (data.content || data.generated_content)) {
          v.push(data.content || data.generated_content);
        }
        setVariants(v);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Bir hata olustu");
    } finally {
      setLoading(false);
    }
  };

  if (!item) return null;

  const activeEtkiLabel = ETKI_OPTIONS.find((e) => e.id === etki);

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent className="w-full sm:max-w-md overflow-y-auto border-l border-border bg-background">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2.5 text-base">
            <motion.div
              animate={{
                boxShadow: [
                  "0 0 8px rgba(139,92,246,0.2)",
                  "0 0 16px rgba(139,92,246,0.4)",
                  "0 0 8px rgba(139,92,246,0.2)",
                ],
              }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/20 to-indigo-500/20 flex items-center justify-center border border-purple-500/20"
            >
              <Zap className="h-3.5 w-3.5 text-purple-400" />
            </motion.div>
            Icerik Uret
          </SheetTitle>
        </SheetHeader>

        <div className="space-y-4 mt-4">
          {/* Tweet Preview */}
          <motion.div
            custom={0} variants={cascadeChild} initial="hidden" animate="visible"
            className="rounded-xl border border-border/60 bg-secondary/20 p-3"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-sm font-semibold text-foreground truncate">{item.display_name}</span>
              <span className="text-xs text-muted-foreground truncate">@{item.username}</span>
              {item.likes > 0 && (
                <span className="ml-auto text-xs text-pink-400 shrink-0">{formatNumber(item.likes)} likes</span>
              )}
            </div>
            <p className="text-sm text-muted-foreground line-clamp-4 leading-relaxed">{item.content}</p>
          </motion.div>

          {/* Mode Toggle */}
          <motion.div
            custom={1} variants={cascadeChild} initial="hidden" animate="visible"
            className="flex gap-1.5 p-1 rounded-xl bg-secondary/40"
          >
            {MODES.map(({ id, label, icon: Icon }) => (
              <motion.button
                key={id}
                onClick={() => { setMode(id); setVariants([]); }}
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.95 }}
                className={cn(
                  "flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-sm font-medium transition-all relative overflow-hidden",
                  mode === id
                    ? "bg-purple-500/15 text-purple-400"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
                {mode === id && (
                  <motion.div
                    layoutId="mode-glow"
                    className="absolute -bottom-0.5 left-3 right-3 h-0.5 rounded-full bg-purple-500"
                    style={{ boxShadow: "0 0 8px rgba(139,92,246,0.5)" }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </motion.button>
            ))}
          </motion.div>

          {/* Reply Mode Chips */}
          {mode === "reply" && (
            <motion.div custom={2} variants={cascadeChild} initial="hidden" animate="visible" className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Yanit tarzi</label>
              <div className="flex flex-wrap gap-1.5">
                {REPLY_STYLES.map(({ id, label, icon: Icon }) => (
                  <motion.button
                    key={id}
                    onClick={() => { setReplyMode(id); setVariants([]); }}
                    whileHover={{ y: -1 }}
                    whileTap={{ scale: 0.93 }}
                    className={cn(
                      "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
                      replyMode === id
                        ? "bg-purple-500/10 text-purple-400 border-purple-500/25"
                        : "bg-transparent text-muted-foreground border-border/50 hover:border-purple-500/20 hover:text-foreground"
                    )}
                  >
                    <Icon className="h-3 w-3" />
                    {label}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}

          {/* Advanced Settings Toggle */}
          <motion.button
            custom={3} variants={cascadeChild} initial="hidden" animate="visible"
            onClick={() => setAdvancedOpen(!advancedOpen)}
            className="flex items-center justify-between w-full text-left group py-1"
          >
            <div className="flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              <span className="text-xs font-medium text-muted-foreground group-hover:text-foreground transition-colors">
                Gelismis ayarlar
              </span>
            </div>
            <div className="flex items-center gap-2">
              {!advancedOpen && activeEtkiLabel && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400/60 border border-purple-500/15">
                  {activeEtkiLabel.emoji} {activeEtkiLabel.label}
                </span>
              )}
              <motion.div animate={{ rotate: advancedOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground/50" />
              </motion.div>
            </div>
          </motion.button>

          <AnimatePresence initial={false}>
            {advancedOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="overflow-hidden"
              >
                <div className="space-y-3 pb-2">
                  <PillGroup label="Etki" options={ETKI_OPTIONS} value={etki} onChange={handleEtkiChange} />
                  <PillGroup label="Karakter" options={KARAKTER_OPTIONS} value={karakter} onChange={(v) => { setKarakter(v); setVariants([]); }} />
                  <PillGroup label="Uzunluk" options={UZUNLUK_OPTIONS} value={uzunluk} onChange={(v) => { setUzunluk(v); setVariants([]); }} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Direction Input */}
          <motion.div custom={4} variants={cascadeChild} initial="hidden" animate="visible" className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Yonlendirme <span className="font-normal text-muted-foreground/50">(opsiyonel)</span>
            </label>
            <input
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              placeholder={mode === "reply" ? "or: buna katilmiyorum cunku..." : "or: kendi deneyimimden bahset"}
              className="w-full rounded-lg border border-border/60 bg-secondary/20 px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-purple-500/40"
            />
          </motion.div>

          {/* Generate Button */}
          <motion.div custom={5} variants={cascadeChild} initial="hidden" animate="visible">
            <motion.button
              onClick={handleGenerate}
              disabled={loading}
              whileHover={!loading ? { scale: 1.01, boxShadow: "0 0 25px rgba(139,92,246,0.3)" } : {}}
              whileTap={!loading ? { scale: 0.98 } : {}}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-medium text-sm shadow-lg shadow-purple-500/10 disabled:opacity-50 relative overflow-hidden"
            >
              <span className="relative flex items-center justify-center gap-2">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                {loading ? "Uretiliyor..." : `${mode === "reply" ? "Reply" : "Quote"} Uret`}
              </span>
            </motion.button>
          </motion.div>

          {/* Loading Skeleton */}
          {loading && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                  className="rounded-xl border border-border/40 p-4 relative overflow-hidden"
                >
                  <div className="space-y-2.5 relative">
                    <div className="h-3 bg-secondary/60 rounded-full w-full" />
                    <div className="h-3 bg-secondary/40 rounded-full w-4/5" />
                    <div className="h-3 bg-secondary/20 rounded-full w-3/5" />
                  </div>
                </motion.div>
              ))}
              <div className="flex items-center justify-center gap-2 pt-1">
                <motion.div
                  animate={{ opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  className="w-1.5 h-1.5 rounded-full bg-purple-400"
                />
                <span className="text-xs text-purple-400/60 font-medium">Uretiliyor...</span>
              </div>
            </div>
          )}

          {/* Results */}
          {variants.length > 0 && !loading && (
            <div className="space-y-2.5">
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">{variants.length} varyant</span>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleGenerate}
                  className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <RotateCcw className="h-3 w-3" />
                  Yeniden uret
                </motion.button>
              </motion.div>

              {variants.map((text, i) => (
                <motion.div
                  key={i}
                  custom={i}
                  variants={resultCard}
                  initial="hidden"
                  animate="visible"
                  className="group/variant rounded-xl border border-border/50 bg-card/50 hover:border-purple-500/20 hover:shadow-[0_0_20px_rgba(139,92,246,0.06)] transition-all duration-300"
                >
                  <div className="flex items-start gap-2 p-3">
                    <p className="flex-1 text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
                    <CopyButton text={text} />
                  </div>
                  <div className="flex items-center gap-3 px-3 pb-2.5 pt-1.5 border-t border-border/30">
                    <span className="text-[11px] text-muted-foreground">{text.length} karakter</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-purple-500/[0.08] text-purple-400/40 font-medium">
                      #{i + 1}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
