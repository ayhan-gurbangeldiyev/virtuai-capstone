/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * XAIModuleV2 — Orriso-style AI Workspace Design
 * Glassmorphism + floating pills + chat-style prompt bar + persona cards
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Sparkles, Zap, Plus, Minus, RefreshCw, Image, X, Copy, Heart,
  Send, ChevronDown, Paperclip, Settings2, Globe, Type, Wand2,
  ArrowRight, Check, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useProfile } from "@/contexts/ProfileContext";

/* ─── Config ─── */
const personas = [
  { id: "saf", label: "Saf", color: "from-pink-400 to-rose-400", emoji: "💗" },
  { id: "otorite", label: "Otorite", color: "from-amber-400 to-yellow-500", emoji: "👔" },
  { id: "insider", label: "Insider", color: "from-emerald-400 to-green-500", emoji: "🤫" },
  { id: "mentalist", label: "Mentalist", color: "from-violet-400 to-purple-500", emoji: "🔮" },
  { id: "haber", label: "Haber", color: "from-red-400 to-orange-500", emoji: "📢" },
];

const tones = [
  { id: "natural", label: "Natural" },
  { id: "raw", label: "Raw" },
  { id: "polished", label: "Polished" },
  { id: "unhinged", label: "Unhinged" },
];

const lengths = [
  { id: "micro", label: "Micro", range: "50-100" },
  { id: "punch", label: "Punch", range: "140-280" },
  { id: "spark", label: "Spark", range: "400-600" },
  { id: "storm", label: "Storm", range: "700-1K" },
  { id: "thread", label: "Thread", range: "3-7 tweet" },
];

const contentTypes = [
  { id: "tweet", label: "Tweet" },
  { id: "quote", label: "Alıntı" },
  { id: "reply", label: "Yanıt" },
  { id: "article", label: "Makale" },
];

/* ─── Glass Card ─── */
function GlassCard({ children, className = "", hover = false }) {
  return (
    <div className={cn(
      "rounded-2xl border border-white/[0.08] bg-white/[0.04] backdrop-blur-xl shadow-2xl",
      hover && "hover:bg-white/[0.07] hover:border-white/[0.12] transition-all duration-300",
      className
    )}>
      {children}
    </div>
  );
}

/* ─── Floating Pill Selector ─── */
function PillSelector({ options, value, onChange, className = "" }) {
  return (
    <div className={cn("inline-flex items-center rounded-full p-1 bg-white/[0.06] backdrop-blur-md border border-white/[0.08]", className)}>
      {options.map((opt) => (
        <button
          key={opt.id}
          onClick={() => onChange(opt.id)}
          className={cn(
            "px-4 py-1.5 rounded-full text-sm font-medium transition-all duration-200",
            value === opt.id
              ? "bg-white text-black shadow-lg"
              : "text-white/60 hover:text-white/90"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/* ─── Persona Card ─── */
function PersonaCard({ persona, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative px-4 py-3 rounded-xl text-sm font-medium transition-all duration-300 overflow-hidden group",
        selected
          ? `bg-gradient-to-br ${persona.color} text-white shadow-lg shadow-black/20 scale-105`
          : "bg-white/[0.06] text-white/70 hover:bg-white/[0.10] border border-white/[0.06]"
      )}
    >
      <span className="relative z-10 flex items-center gap-1.5">
        <span className="text-base">{persona.emoji}</span>
        {persona.label}
      </span>
      {selected && (
        <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </button>
  );
}

/* ─── Result Card ─── */
function ResultCard({ content, index, onCopy, onFavorite, isFavorited }) {
  return (
    <GlassCard className="p-5 group" hover>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-3">
            <div className="h-6 w-6 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center">
              <span className="text-[10px] font-bold text-white">#{index + 1}</span>
            </div>
            <span className="text-xs text-white/40">{content.length} karakter</span>
          </div>
          <p className="text-[15px] leading-relaxed text-white/90 whitespace-pre-wrap">{content}</p>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-white/[0.06]">
        <button
          onClick={onCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-white/50 hover:text-white hover:bg-white/[0.06] transition-all"
        >
          <Copy className="h-3.5 w-3.5" /> Kopyala
        </button>
        <button
          onClick={onFavorite}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all",
            isFavorited
              ? "text-pink-400 bg-pink-500/10"
              : "text-white/50 hover:text-pink-400 hover:bg-white/[0.06]"
          )}
        >
          <Heart className={cn("h-3.5 w-3.5", isFavorited && "fill-current")} /> Favori
        </button>
      </div>
    </GlassCard>
  );
}

/* ─── Empty State ─── */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="relative mb-6">
        <div className="h-24 w-24 rounded-full bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 flex items-center justify-center backdrop-blur-sm border border-white/[0.08]">
          <Sparkles className="h-10 w-10 text-violet-400" />
        </div>
        <div className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center animate-bounce">
          <Zap className="h-3 w-3 text-white" />
        </div>
      </div>
      <h3 className="text-xl font-semibold text-white/80 mb-2">İçerik üretmeye hazır</h3>
      <p className="text-sm text-white/40 max-w-xs">
        Aşağıdaki alana konunu yaz, karakterini seç ve üret butonuna bas.
      </p>
    </div>
  );
}

/* ═══════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════ */
export default function XAIModuleV2() {
  const [searchParams] = useSearchParams();
  const { activeProfileId, activeProfile } = useProfile();
  const textareaRef = useRef(null);

  // State
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
  const fileInputRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, [topic]);

  // Generate
  const handleGenerate = async () => {
    if (!topic.trim()) {
      toast.error("Konu girin");
      return;
    }
    setLoading(true);
    setResults([]);
    try {
      const endpoint = contentType === "article" ? "/generate/article"
        : contentType === "quote" ? "/generate/quote"
        : contentType === "reply" ? "/generate/reply"
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
        setResults(data.variants?.map(v => v.content) || []);
        setGenerationId(data.generation_id);
        toast.success(`${data.variants?.length || 0} varyant üretildi!`);
      } else {
        toast.error(data.error || "Üretim başarısız");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Bir hata oluştu");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopyalandı!");
  };

  const handleFavorite = async (text, variantIndex) => {
    try {
      const res = await api.post(`${API}/favorites/toggle`, {
        content: text,
        type: contentType,
        generation_id: generationId,
        variant_index: variantIndex,
      });
      setFavoritedIds(prev => {
        const next = new Set(prev);
        if (res.data.action === "added") next.add(variantIndex);
        else next.delete(variantIndex);
        return next;
      });
      toast.success(res.data.action === "added" ? "Favorilere eklendi!" : "Favorilerden kaldırıldı");
    } catch {
      toast.error("Favori işlemi başarısız");
    }
  };

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Max 5MB");
      return;
    }
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden">

      {/* ─── Warm Gradient Background ─── */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-[#0c0a14]" />
        <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full bg-violet-600/8 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-fuchsia-600/6 blur-[100px]" />
        <div className="absolute top-[40%] right-[20%] w-[30%] h-[30%] rounded-full bg-indigo-600/5 blur-[80px]" />
      </div>

      {/* ─── Main Content Area ─── */}
      <div className="max-w-4xl mx-auto px-4 pt-6 pb-40">

        {/* ─── Top: Content Type Tabs (Floating Pill) ─── */}
        <div className="flex justify-center mb-6">
          <PillSelector
            options={contentTypes}
            value={contentType}
            onChange={setContentType}
          />
        </div>

        {/* ─── Mode + Settings Row ─── */}
        <div className="flex items-center justify-between mb-6 px-2">
          {/* Mode Toggle */}
          <div className="flex items-center gap-2">
            <PillSelector
              options={[
                { id: "classic", label: "Klasik" },
                { id: "apex", label: "⚡ APEX" },
              ]}
              value={mode}
              onChange={setMode}
            />
          </div>

          {/* Right side: Length + Variants + Settings */}
          <div className="flex items-center gap-3">
            {/* Length dropdown */}
            <div className="relative group">
              <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm text-white/60 bg-white/[0.06] border border-white/[0.08] hover:bg-white/[0.10] transition-all">
                <Type className="h-3.5 w-3.5" />
                {lengths.find(l => l.id === length)?.label}
                <ChevronDown className="h-3 w-3" />
              </button>
              <div className="absolute top-full right-0 mt-2 w-48 rounded-xl bg-[#1a1625]/95 backdrop-blur-xl border border-white/[0.08] shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 p-1.5">
                {lengths.map(l => (
                  <button
                    key={l.id}
                    onClick={() => setLength(l.id)}
                    className={cn(
                      "w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors",
                      length === l.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/[0.06] hover:text-white"
                    )}
                  >
                    <span>{l.label}</span>
                    <span className="text-xs text-white/30">{l.range}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Variants */}
            <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-white/[0.06] border border-white/[0.08]">
              <button onClick={() => setVariants(Math.max(1, variants - 1))} className="p-1 rounded-full hover:bg-white/10 text-white/50 transition-colors">
                <Minus className="h-3 w-3" />
              </button>
              <span className="text-sm font-medium text-white/80 w-5 text-center">{variants}</span>
              <button onClick={() => setVariants(Math.min(5, variants + 1))} className="p-1 rounded-full hover:bg-white/10 text-white/50 transition-colors">
                <Plus className="h-3 w-3" />
              </button>
            </div>

            {/* Settings toggle */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={cn(
                "p-2 rounded-full transition-all",
                showSettings
                  ? "bg-violet-500/20 text-violet-400 border border-violet-500/30"
                  : "bg-white/[0.06] text-white/50 border border-white/[0.08] hover:bg-white/[0.10]"
              )}
            >
              <Settings2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* ─── Advanced Settings Panel (Collapsible) ─── */}
        {showSettings && (
          <GlassCard className="p-5 mb-6 animate-in slide-in-from-top-2 duration-200">
            <div className="grid grid-cols-2 gap-6">
              {/* Tone */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Ton</label>
                <div className="flex flex-wrap gap-2">
                  {tones.map(t => (
                    <button
                      key={t.id}
                      onClick={() => setTone(t.id)}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-sm transition-all",
                        tone === t.id
                          ? "bg-white/15 text-white border border-white/20"
                          : "text-white/40 hover:text-white/70 hover:bg-white/[0.06]"
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Knowledge */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Knowledge</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: null, label: "Yok" },
                    { id: "insider", label: "Insider" },
                    { id: "contrarian", label: "Contrarian" },
                    { id: "hidden", label: "Hidden" },
                    { id: "expert", label: "Expert" },
                  ].map(k => (
                    <button
                      key={k.id || "none"}
                      onClick={() => setKnowledge(k.id)}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-sm transition-all",
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
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Dil</label>
                <div className="flex gap-2">
                  {[
                    { id: "auto", label: "Otomatik" },
                    { id: "tr", label: "Türkçe" },
                    { id: "en", label: "English" },
                  ].map(l => (
                    <button
                      key={l.id}
                      onClick={() => setLanguage(l.id)}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-sm transition-all",
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

              {/* Style Profile */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/50 uppercase tracking-wider">Stil Profili</label>
                <div className="flex items-center gap-2">
                  {activeProfile ? (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/20 text-sm text-violet-300">
                      <div className="h-5 w-5 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center">
                        <span className="text-[8px] font-bold text-white">{activeProfile.name?.charAt(0)}</span>
                      </div>
                      {activeProfile.name}
                    </div>
                  ) : (
                    <span className="text-sm text-white/30">Profil seçilmedi</span>
                  )}
                </div>
              </div>
            </div>
          </GlassCard>
        )}

        {/* ─── Persona Cards ─── */}
        <div className="flex items-center gap-2 mb-8 px-2 overflow-x-auto scrollbar-hide">
          <span className="text-xs text-white/30 mr-1 shrink-0">Karakter</span>
          {personas.map(p => (
            <PersonaCard
              key={p.id}
              persona={p}
              selected={persona === p.id}
              onClick={() => setPersona(p.id)}
            />
          ))}
        </div>

        {/* ─── Results Area ─── */}
        <div className="min-h-[300px]">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-2 border-white/10 border-t-violet-500 animate-spin" />
                <Sparkles className="h-6 w-6 text-violet-400 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              </div>
              <p className="text-sm text-white/40 mt-4">İçerik üretiliyor...</p>
            </div>
          ) : results.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between px-2">
                <h3 className="text-sm font-medium text-white/50">
                  {results.length} Varyant Üretildi
                </h3>
                <button
                  onClick={handleGenerate}
                  className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/70 transition-colors"
                >
                  <RefreshCw className="h-3 w-3" /> Tekrar Üret
                </button>
              </div>
              {results.map((text, i) => (
                <ResultCard
                  key={i}
                  content={text}
                  index={i}
                  onCopy={() => handleCopy(text)}
                  onFavorite={() => handleFavorite(text, i)}
                  isFavorited={favoritedIds.has(i)}
                />
              ))}
            </div>
          ) : (
            <EmptyState />
          )}
        </div>
      </div>

      {/* ─── Bottom Prompt Bar (Fixed) ─── */}
      <div className="fixed bottom-0 left-0 right-0 z-50 pb-6 px-4">
        <div className="max-w-4xl mx-auto">
          <GlassCard className="p-3 border-white/[0.12] bg-[#1a1625]/80 backdrop-blur-2xl shadow-[0_-8px_32px_rgba(0,0,0,0.4)]">
            {/* Image preview */}
            {imagePreview && (
              <div className="flex items-center gap-2 mb-2 px-2">
                <div className="relative">
                  <img src={imagePreview} alt="" className="h-12 w-12 rounded-lg object-cover" />
                  <button
                    onClick={() => { setImageFile(null); setImagePreview(null); }}
                    className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-red-500 flex items-center justify-center"
                  >
                    <X className="h-2.5 w-2.5 text-white" />
                  </button>
                </div>
              </div>
            )}

            <div className="flex items-end gap-2">
              {/* Attachment button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="p-2.5 rounded-xl text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-all shrink-0"
              >
                <Paperclip className="h-5 w-5" />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
              />

              {/* Text Input */}
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    contentType === "quote" ? "Tweet linki yapıştır..."
                    : contentType === "reply" ? "Yanıtlamak istediğin tweet linki..."
                    : contentType === "article" ? "Makale konusunu yaz..."
                    : "Konu yaz, link yapıştır veya fikir paylaş..."
                  }
                  rows={1}
                  className="w-full bg-transparent text-white/90 placeholder:text-white/25 text-[15px] resize-none focus:outline-none py-2.5 px-1 max-h-[200px] leading-relaxed"
                />
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={!topic.trim() || loading}
                className={cn(
                  "p-2.5 rounded-xl transition-all shrink-0",
                  topic.trim() && !loading
                    ? "bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-500/25 hover:shadow-violet-500/40 hover:scale-105"
                    : "bg-white/[0.06] text-white/20 cursor-not-allowed"
                )}
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <ArrowRight className="h-5 w-5" />
                )}
              </button>
            </div>

            {/* Bottom info bar */}
            <div className="flex items-center justify-between mt-2 px-2">
              <div className="flex items-center gap-3 text-[11px] text-white/25">
                <span>{topic.length}/280</span>
                <span>•</span>
                <span>{lengths.find(l => l.id === length)?.label} · {variants} varyant</span>
                {activeProfile && (
                  <>
                    <span>•</span>
                    <span className="text-violet-400/50">🎨 {activeProfile.name}</span>
                  </>
                )}
              </div>
              <span className="text-[11px] text-white/20">Enter ile üret · Shift+Enter satır</span>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
