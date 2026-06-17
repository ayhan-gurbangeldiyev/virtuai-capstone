/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Share2, Sparkles, Lightbulb, BarChart3, Image as ImageIcon,
  MessageSquare, Copy, ArrowRight, Loader2, ChevronDown, ChevronUp,
  Users, BookOpen, TrendingUp, Heart,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import GenerationCard from "@/components/generation/GenerationCard";
import FloatingQueue from "@/components/generation/FloatingQueue";


let jobIdCounter = 0;

/* ── Inline Components ─────────────────────────────────── */

function ChipSelector({ options, value, onChange, labelKey = "label", idKey = "id" }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt[idKey]}
          type="button"
          onClick={() => onChange(opt[idKey])}
          className={cn(
            "px-3 py-1.5 rounded-lg text-sm font-medium transition-all border",
            value === opt[idKey]
              ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-transparent shadow-md"
              : "bg-card border-border text-muted-foreground hover:border-blue-500/50 hover:text-foreground"
          )}
        >
          {opt[labelKey]}
        </button>
      ))}
    </div>
  );
}

function ScoreCard({ score, label, large }) {
  const color =
    score >= 7
      ? "bg-green-500/10 text-green-400 border-green-500/20"
      : score >= 4
      ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20"
      : "bg-red-500/10 text-red-400 border-red-500/20";
  return (
    <div
      className={cn(
        "rounded-xl border p-3 text-center",
        color,
        large && "col-span-2 row-span-1"
      )}
    >
      <p className={cn("font-bold", large ? "text-3xl" : "text-2xl")}>{score}</p>
      <p className="text-xs mt-1 opacity-80">{label}</p>
    </div>
  );
}

function StatCard({ value, label, icon: Icon }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3 text-center">
      {Icon && <Icon className="h-4 w-4 mx-auto mb-1 text-blue-400" />}
      <p className="text-xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/* ── Post Tab ──────────────────────────────────────────── */

function PostTab({ personas, formats, initialTopic, initialTrendContext, hookOverride, setHookOverride, jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState(initialTopic || "");
  const [persona, setPersona] = useState(personas[0]?.id || "thought_leader");
  const [format, setFormat] = useState(formats[0]?.id || "standard");
  const [variants, setVariants] = useState(1);
  const [additionalContext, setAdditionalContext] = useState(initialTrendContext || "");
  const [ctxOpen, setCtxOpen] = useState(!!initialTrendContext);
  const [hookOpen, setHookOpen] = useState(!!hookOverride);
  const [loading, setLoading] = useState(false);

  // sync initialTopic
  useEffect(() => { if (initialTopic) setTopic(initialTopic); }, [initialTopic]);
  useEffect(() => { if (hookOverride) setHookOpen(true); }, [hookOverride]);

  const generate = async () => {
    if (!topic.trim()) return toast.error("Konu gerekli");
    setLoading(true);
    await onAddJob({
      type: "linkedin",
      endpoint: "/generate/linkedin",
      body: {
        topic: topic.trim(),
        format,
        persona,
        language: "tr",
        additional_context: additionalContext || undefined,
        variants,
        hook: hookOverride || undefined,
      },
      meta: { topic: topic.trim(), persona, variantCount: variants },
    });
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="LinkedIn postunuzun konusu..."
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        className="min-h-[80px] bg-card"
      />

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Persona</p>
        <ChipSelector options={personas} value={persona} onChange={setPersona} />
      </div>

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Format</p>
        <ChipSelector options={formats} value={format} onChange={setFormat} />
      </div>

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Varyant</p>
        <div className="flex gap-2">
          {[1, 2, 3].map((n) => (
            <button
              key={n}
              onClick={() => setVariants(n)}
              className={cn(
                "w-9 h-9 rounded-lg text-sm font-semibold border transition-all",
                variants === n
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-transparent"
                  : "bg-card border-border text-muted-foreground hover:border-blue-500/50"
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <Collapsible open={ctxOpen} onOpenChange={setCtxOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="text-muted-foreground gap-1">
            {ctxOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Ek Bağlam
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Textarea
            placeholder="Ek bağlam, notlar..."
            value={additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            className="mt-2 min-h-[60px] bg-card"
          />
        </CollapsibleContent>
      </Collapsible>

      <Collapsible open={hookOpen} onOpenChange={setHookOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="text-muted-foreground gap-1">
            {hookOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Hook Override
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Input
            placeholder="Hook Lab'dan seçilen hook..."
            value={hookOverride || ""}
            onChange={(e) => setHookOverride(e.target.value)}
            className="mt-2 bg-card"
          />
        </CollapsibleContent>
      </Collapsible>

      <Button
        onClick={generate}
        disabled={loading || !topic.trim()}
        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
        Üret
      </Button>

      {/* Results */}
      <div className="space-y-3">
        {jobs.map((job) => (
          <GenerationCard key={job.id} job={job} />
        ))}
      </div>

      <FloatingQueue jobs={jobs.filter((j) => j.status === "generating")} onDismiss={onDismissJob} />
    </div>
  );
}

/* ── Carousel Tab ──────────────────────────────────────── */

function CarouselTab({ personas, jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [persona, setPersona] = useState(personas[0]?.id || "thought_leader");
  const [slideCount, setSlideCount] = useState("8");
  const [loading, setLoading] = useState(false);
  const [slides, setSlides] = useState([]);

  const generate = async () => {
    if (!topic.trim()) return toast.error("Konu gerekli");
    setLoading(true);
    try {
      const res = await api.post(`${API}/generate/linkedin/carousel`, {
        topic: topic.trim(),
        slide_count: parseInt(slideCount),
        persona,
        language: "tr",
      });
      const data = res.data;
      // slides might be in variants[0].slides or variants[0].content parsed
      const v = data.variants?.[0];
      if (v?.slides) {
        setSlides(v.slides);
      } else if (v?.content) {
        // try parse numbered slides from content
        const parsed = v.content.split(/\n(?=Slide \d|📌)/).filter(Boolean);
        setSlides(parsed.map((s, i) => ({ number: i + 1, content: s.trim() })));
      }
      toast.success("Carousel üretildi!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Carousel üretilemedi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="Carousel konusu..."
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        className="min-h-[80px] bg-card"
      />

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Persona</p>
        <ChipSelector options={personas} value={persona} onChange={setPersona} />
      </div>

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Slide Sayısı</p>
        <Select value={slideCount} onValueChange={setSlideCount}>
          <SelectTrigger className="w-32 bg-card">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Array.from({ length: 8 }, (_, i) => i + 5).map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} slide
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        onClick={generate}
        disabled={loading || !topic.trim()}
        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <BookOpen className="h-4 w-4 mr-2" />}
        Carousel Üret
      </Button>

      {slides.length > 0 && (
        <div className="space-y-3">
          {slides.map((slide, i) => (
            <Card key={i} className="bg-card border-blue-500/20">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Badge className="bg-blue-600 text-white shrink-0">
                    {slide.number || i + 1}
                  </Badge>
                  <div className="flex-1">
                    <p className="text-sm whitespace-pre-wrap">
                      {typeof slide === "string" ? slide : slide.content || slide.text || JSON.stringify(slide)}
                    </p>
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="shrink-0"
                    onClick={() => {
                      const text = typeof slide === "string" ? slide : slide.content || slide.text;
                      navigator.clipboard.writeText(text);
                      toast.success("Kopyalandı");
                    }}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Hook Lab Tab ──────────────────────────────────────── */

function HookLabTab({ personas, formats, onUseHook }) {
  const [topic, setTopic] = useState("");
  const [persona, setPersona] = useState(personas[0]?.id || "thought_leader");
  const [format, setFormat] = useState(formats[0]?.id || "standard");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [hooks, setHooks] = useState([]);

  const generate = async () => {
    if (!topic.trim()) return toast.error("Konu gerekli");
    setLoading(true);
    try {
      const res = await api.post(`${API}/generate/linkedin/hooks`, {
        topic: topic.trim(),
        persona,
        format,
        count,
        language: "tr",
      });
      const content = res.data.variants?.[0]?.content || "";
      // Parse numbered hooks
      const parsed = content
        .split(/\n/)
        .map((line) => line.replace(/^\d+[\.\)]\s*/, "").trim())
        .filter((line) => line.length > 10);
      setHooks(parsed);
      toast.success(`${parsed.length} hook üretildi!`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Hook üretilemedi");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="Hook konusu..."
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        className="min-h-[80px] bg-card"
      />

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Persona</p>
        <ChipSelector options={personas} value={persona} onChange={setPersona} />
      </div>

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Format</p>
        <ChipSelector options={formats} value={format} onChange={setFormat} />
      </div>

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Hook Sayısı</p>
        <div className="flex gap-2">
          {[3, 4, 5, 6, 7].map((n) => (
            <button
              key={n}
              onClick={() => setCount(n)}
              className={cn(
                "w-9 h-9 rounded-lg text-sm font-semibold border transition-all",
                count === n
                  ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white border-transparent"
                  : "bg-card border-border text-muted-foreground hover:border-blue-500/50"
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <Button
        onClick={generate}
        disabled={loading || !topic.trim()}
        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Lightbulb className="h-4 w-4 mr-2" />}
        Hook Üret
      </Button>

      {hooks.length > 0 && (
        <div className="space-y-3">
          {hooks.map((hook, i) => (
            <Card key={i} className="bg-card border-indigo-500/20">
              <CardContent className="p-4">
                <p className="text-sm mb-3">{hook}</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      navigator.clipboard.writeText(hook);
                      toast.success("Kopyalandı");
                    }}
                  >
                    <Copy className="h-3.5 w-3.5 mr-1" /> Kopyala
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-blue-500/50 text-blue-400 hover:bg-blue-500/10"
                    onClick={() => onUseHook(hook, topic)}
                  >
                    <ArrowRight className="h-3.5 w-3.5 mr-1" /> Bu Hook ile Post Üret
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Anket Tab ─────────────────────────────────────────── */

function AnketTab({ personas, jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [persona, setPersona] = useState(personas[0]?.id || "thought_leader");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    if (!topic.trim()) return toast.error("Konu gerekli");
    setLoading(true);
    await onAddJob({
      type: "linkedin",
      endpoint: "/generate/linkedin",
      body: {
        topic: topic.trim(),
        format: "poll",
        persona,
        language: "tr",
        variants: 1,
      },
      meta: { topic: topic.trim(), persona, variantCount: 1 },
    });
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="Anket konusu..."
        value={topic}
        onChange={(e) => setTopic(e.target.value)}
        className="min-h-[80px] bg-card"
      />

      <div>
        <p className="text-sm font-medium mb-2 text-muted-foreground">Persona</p>
        <ChipSelector options={personas} value={persona} onChange={setPersona} />
      </div>

      <Button
        onClick={generate}
        disabled={loading || !topic.trim()}
        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <MessageSquare className="h-4 w-4 mr-2" />}
        Anket Üret
      </Button>

      <div className="space-y-3">
        {jobs.map((job) => (
          <GenerationCard key={job.id} job={job} />
        ))}
      </div>

      <FloatingQueue jobs={jobs.filter((j) => j.status === "generating")} onDismiss={onDismissJob} />
    </div>
  );
}

/* ── Analiz Tab ────────────────────────────────────────── */

function AnalizTab() {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const analyze = async () => {
    if (!content.trim()) return toast.error("İçerik yapıştırın");
    setLoading(true);
    try {
      const res = await api.post(`${API}/generate/linkedin/analyze`, {
        content: content.trim(),
        language: "tr",
      });
      setResult(res.data.metadata);
      toast.success("Analiz tamamlandı!");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Analiz başarısız");
    } finally {
      setLoading(false);
    }
  };

  const analysis = result?.analysis || {};
  const stats = result?.stats || {};

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="LinkedIn postunuzu buraya yapıştırın..."
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="min-h-[160px] bg-card"
      />

      <Button
        onClick={analyze}
        disabled={loading || !content.trim()}
        className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <BarChart3 className="h-4 w-4 mr-2" />}
        Analiz Et
      </Button>

      {result && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-4 gap-3">
            <StatCard value={stats.character_count || 0} label="Karakter" />
            <StatCard value={stats.word_count || 0} label="Kelime" />
            <StatCard value={stats.line_count || 0} label="Satır" />
            <StatCard value={stats.hashtag_count || 0} label="Hashtag" />
          </div>

          {/* Scores */}
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            <ScoreCard score={analysis.overall_score || 0} label="Genel" large />
            <ScoreCard score={analysis.hook_score || 0} label="Hook" />
            <ScoreCard score={analysis.structure_score || 0} label="Yapı" />
            <ScoreCard score={analysis.persona_score || 0} label="Persona" />
            <ScoreCard score={analysis.engagement_score || 0} label="Engagement" />
            <ScoreCard score={analysis.cta_score || 0} label="CTA" />
          </div>

          {/* Strengths */}
          {analysis.strengths?.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Güçlü Yönler</p>
              <div className="flex flex-wrap gap-2">
                {analysis.strengths.map((s, i) => (
                  <Badge key={i} className="bg-green-500/10 text-green-400 border-green-500/20">
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Weaknesses */}
          {analysis.weaknesses?.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Zayıf Yönler</p>
              <div className="flex flex-wrap gap-2">
                {analysis.weaknesses.map((w, i) => (
                  <Badge key={i} className="bg-red-500/10 text-red-400 border-red-500/20">
                    {w}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Improvements */}
          {analysis.improvements?.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium mb-2">İyileştirmeler</p>
              {analysis.improvements.map((imp, i) => {
                const level = imp.level || imp.type || "suggestion";
                const colors = {
                  critical: "border-red-500/30 bg-red-500/5",
                  warning: "border-yellow-500/30 bg-yellow-500/5",
                  suggestion: "border-blue-500/30 bg-blue-500/5",
                };
                return (
                  <Card key={i} className={cn("border", colors[level] || colors.suggestion)}>
                    <CardContent className="p-3">
                      <div className="flex items-start gap-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            "shrink-0 text-xs",
                            level === "critical" && "border-red-500 text-red-400",
                            level === "warning" && "border-yellow-500 text-yellow-400",
                            level === "suggestion" && "border-blue-500 text-blue-400"
                          )}
                        >
                          {level === "critical" ? "Kritik" : level === "warning" ? "Uyarı" : "Öneri"}
                        </Badge>
                        <p className="text-sm">{typeof imp === "string" ? imp : imp.text || imp.message}</p>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Hashtags */}
          {analysis.suggested_hashtags?.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Önerilen Hashtag'ler</p>
              <div className="flex flex-wrap gap-2">
                {analysis.suggested_hashtags.map((h, i) => (
                  <Badge
                    key={i}
                    className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20 cursor-pointer"
                    onClick={() => {
                      navigator.clipboard.writeText(h.startsWith("#") ? h : `#${h}`);
                      toast.success("Kopyalandı");
                    }}
                  >
                    {h.startsWith("#") ? h : `#${h}`}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Alternative Hooks */}
          {analysis.alternative_hooks?.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Alternatif Hook Önerileri</p>
              <div className="space-y-2">
                {analysis.alternative_hooks.map((hook, i) => (
                  <Card key={i} className="bg-card border-blue-500/20">
                    <CardContent className="p-3 flex items-center justify-between gap-3">
                      <p className="text-sm flex-1">{hook}</p>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="shrink-0"
                        onClick={() => {
                          navigator.clipboard.writeText(hook);
                          toast.success("Kopyalandı");
                        }}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Image Prompt Dialog ───────────────────────────────── */

function ImagePromptDialog({ open, onOpenChange, topic, content }) {
  const [style, setStyle] = useState("professional");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const generate = async () => {
    setLoading(true);
    try {
      const res = await api.post(`${API}/generate/linkedin/image-prompt`, {
        topic,
        content,
        style,
      });
      setResult(res.data.metadata?.image_prompt);
    } catch (err) {
      toast.error("Görsel promptu üretilemedi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      setResult(null);
      generate();
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5 text-blue-400" />
            Görsel Promptu
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
          </div>
        ) : result ? (
          <div className="space-y-3">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Prompt</p>
              <p className="text-sm bg-muted/50 rounded-lg p-3">{result.prompt}</p>
            </div>
            {result.negative_prompt && (
              <div>
                <p className="text-xs text-muted-foreground mb-1">Negative Prompt</p>
                <p className="text-sm bg-muted/50 rounded-lg p-3">{result.negative_prompt}</p>
              </div>
            )}
            <div className="flex gap-4 text-xs text-muted-foreground">
              {result.style_preset && <span>Stil: {result.style_preset}</span>}
              {result.aspect_ratio && <span>Oran: {result.aspect_ratio}</span>}
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(result.prompt);
                toast.success("Prompt kopyalandı");
              }}
            >
              <Copy className="h-3.5 w-3.5 mr-1" /> Promptu Kopyala
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

/* ── Main Module ───────────────────────────────────────── */

export default function LinkShareModule() {
  const [searchParams] = useSearchParams();
  const initialTopic = searchParams.get("topic") || "";
  const initialTrendContext = searchParams.get("trend_context") || "";

  const [activeTab, setActiveTab] = useState("post");
  const [hookOverride, setHookOverride] = useState("");
  const [personas, setPersonas] = useState([]);
  const [formats, setFormats] = useState([]);
  const [jobs, setJobs] = useState([]);

  // Fetch meta
  useEffect(() => {
    api
      .get(`${API}/meta/linkedin/personas`)
      .then((r) => setPersonas(r.data))
      .catch(() =>
        setPersonas([
          { id: "thought_leader", label: "Thought Leader" },
          { id: "storyteller", label: "Storyteller" },
          { id: "data_driven", label: "Data Driven" },
          { id: "motivator", label: "Motivator" },
        ])
      );
    api
      .get(`${API}/meta/linkedin/formats`)
      .then((r) => setFormats(r.data))
      .catch(() =>
        setFormats([
          { id: "standard", label: "Standard" },
          { id: "listicle", label: "Listicle" },
          { id: "story", label: "Story" },
          { id: "carousel_text", label: "Carousel Text" },
          { id: "poll", label: "Poll" },
          { id: "micro", label: "Micro" },
        ])
      );
  }, []);

  const addJob = useCallback(async ({ endpoint, body, meta }) => {
    const jobId = `linkedin-${++jobIdCounter}`;
    const newJob = {
      id: jobId,
      type: "linkedin",
      status: "generating",
      startedAt: Date.now(),
      topic: meta.topic,
      persona: meta.persona,
      personaLabel: meta.persona,
      toneLabel: "LinkedIn",
      lengthLabel: "",
      variantCount: meta.variantCount || 1,
      variants: null,
    };

    setJobs((prev) => [newJob, ...prev]);

    try {
      const res = await api.post(`${API}${endpoint}`, body);
      const variants = res.data.variants || [];
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId ? { ...j, status: "done", variants } : j
        )
      );
    } catch (err) {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId
            ? { ...j, status: "error", error: err.response?.data?.detail || "Hata" }
            : j
        )
      );
      toast.error(err.response?.data?.detail || "Üretim başarısız");
    }
  }, []);

  const dismissJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  const handleUseHook = useCallback((hook, topic) => {
    setHookOverride(hook);
    setActiveTab("post");
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="text-center mt-4 mb-10">
        <h1 className="font-outfit text-4xl md:text-5xl font-extrabold tracking-tight mb-3">
          Konu yaz, <span className="bg-gradient-to-r from-blue-500 to-indigo-600 bg-clip-text text-transparent">viral postlar</span> üret
        </h1>
        <p className="text-muted-foreground text-lg">
          Post, carousel, hook ve analiz araçları
        </p>
      </div>

      {/* Tabs */}
      <Card className="bg-card border-border/50 rounded-2xl shadow-lg shadow-black/[0.03] dark:shadow-black/20">
        <CardContent className="p-8">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-5 w-full mb-6">
          <TabsTrigger value="post" className="text-xs sm:text-sm">📝 Post</TabsTrigger>
          <TabsTrigger value="carousel" className="text-xs sm:text-sm">📑 Carousel</TabsTrigger>
          <TabsTrigger value="hooklab" className="text-xs sm:text-sm">💡 Hook Lab</TabsTrigger>
          <TabsTrigger value="anket" className="text-xs sm:text-sm">🗳️ Anket</TabsTrigger>
          <TabsTrigger value="analiz" className="text-xs sm:text-sm">🔍 Analiz</TabsTrigger>
        </TabsList>

        <TabsContent value="post" className="mt-4">
          <PostTab
            personas={personas}
            formats={formats}
            initialTopic={initialTopic}
            initialTrendContext={initialTrendContext}
            hookOverride={hookOverride}
            setHookOverride={setHookOverride}
            jobs={jobs.filter((j) => j.type === "linkedin" && !j._tab || j._tab === "post")}
            onAddJob={(p) => addJob({ ...p, _tab: "post" })}
            onDismissJob={dismissJob}
          />
        </TabsContent>

        <TabsContent value="carousel" className="mt-4">
          <CarouselTab
            personas={personas}
            jobs={jobs.filter((j) => j._tab === "carousel")}
            onAddJob={(p) => addJob({ ...p, _tab: "carousel" })}
            onDismissJob={dismissJob}
          />
        </TabsContent>

        <TabsContent value="hooklab" className="mt-4">
          <HookLabTab
            personas={personas}
            formats={formats}
            onUseHook={handleUseHook}
          />
        </TabsContent>

        <TabsContent value="anket" className="mt-4">
          <AnketTab
            personas={personas}
            jobs={jobs.filter((j) => j._tab === "anket")}
            onAddJob={(p) => addJob({ ...p, _tab: "anket" })}
            onDismissJob={dismissJob}
          />
        </TabsContent>

        <TabsContent value="analiz" className="mt-4">
          <AnalizTab />
        </TabsContent>
      </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
