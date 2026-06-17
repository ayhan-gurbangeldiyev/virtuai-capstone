/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
// BlogArchitectModule.jsx - Blog AI İçerik Üretim Modülü (v2)
import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  FileText, Sparkles, Search, Image as ImageIcon, Share2,
  BookOpen, Lightbulb, Clock, AlignLeft, Hash, Type, BarChart3,
  Copy, ArrowRight, Loader2, ChevronDown,
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
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";
import FloatingQueue from "@/components/generation/FloatingQueue";


let jobIdCounter = 0;

/* ─── Inline ChipSelector ─── */
function ChipSelector({ label, options, value, onChange, loading }) {
  if (loading) {
    return (
      <div className="space-y-2">
        {label && <p className="text-sm font-medium text-foreground">{label}</p>}
        <div className="flex gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-9 w-24 rounded-lg bg-secondary animate-pulse" />
          ))}
        </div>
      </div>
    );
  }
  const selected = options.find((o) => o.id === value);
  return (
    <div className="space-y-2">
      {label && <p className="text-sm font-medium text-foreground">{label}</p>}
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-medium transition-all border",
              value === o.id
                ? "bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-500/20"
                : "bg-secondary text-muted-foreground border-border hover:bg-accent hover:text-foreground"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
      {selected?.description && (
        <p className="text-xs text-muted-foreground">{selected.description}</p>
      )}
    </div>
  );
}

/* ─── ReadabilityCard ─── */
function ReadabilityCard({ readability }) {
  if (!readability) return null;
  const avgColor =
    readability.avg_sentence_length < 20
      ? "text-green-400"
      : readability.avg_sentence_length <= 25
      ? "text-yellow-400"
      : "text-red-400";

  const metrics = [
    { icon: Type, label: "Kelime Sayısı", value: readability.word_count },
    { icon: AlignLeft, label: "Cümle Sayısı", value: readability.sentence_count },
    { icon: BarChart3, label: "Ort. Cümle Uzunluğu", value: readability.avg_sentence_length, color: avgColor },
    { icon: BookOpen, label: "Paragraf", value: readability.paragraph_count },
    { icon: Hash, label: "H2 Sayısı", value: readability.h2_count },
    { icon: Clock, label: "Okuma Süresi", value: `${readability.estimated_read_time_min} dk` },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4">
      {metrics.map((m) => (
        <Card key={m.label} className="bg-secondary/50 border-border">
          <CardContent className="p-3 flex items-center gap-3">
            <m.icon className={cn("h-5 w-5 text-indigo-400 shrink-0", m.color)} />
            <div>
              <p className={cn("text-lg font-bold", m.color || "text-foreground")}>{m.value}</p>
              <p className="text-xs text-muted-foreground">{m.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/* ─── SEO Analysis Card ─── */
function SEOAnalysisCard({ seoAnalysis }) {
  if (!seoAnalysis) return null;
  let parsed = seoAnalysis;
  if (typeof seoAnalysis === "string") {
    try { parsed = JSON.parse(seoAnalysis); } catch { return null; }
  }

  const score = parsed.score ?? parsed.seo_score;
  const suggestions = parsed.suggestions || parsed.recommendations || parsed.improvements || [];

  const severityColor = {
    critical: "bg-red-500/20 text-red-400 border-red-500/30",
    warning: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    suggestion: "bg-green-500/20 text-green-400 border-green-500/30",
  };

  return (
    <div className="mt-4 space-y-4">
      {score != null && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">SEO Skoru:</span>
          <span className={cn(
            "text-2xl font-bold",
            score >= 80 ? "text-green-400" : score >= 50 ? "text-yellow-400" : "text-red-400"
          )}>
            {score}/100
          </span>
        </div>
      )}
      {suggestions.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">İyileştirme Önerileri</p>
          {suggestions.map((s, i) => {
            const severity = s.severity || s.type || "suggestion";
            const text = s.message || s.text || s.suggestion || (typeof s === "string" ? s : JSON.stringify(s));
            return (
              <div key={i} className="flex items-start gap-2">
                <Badge variant="outline" className={cn("text-[10px] shrink-0 mt-0.5", severityColor[severity] || severityColor.suggestion)}>
                  {severity === "critical" ? "Kritik" : severity === "warning" ? "Uyarı" : "Öneri"}
                </Badge>
                <span className="text-sm text-muted-foreground">{text}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── JobResults: renders GenerationCard list ─── */
function JobResults({ jobs }) {
  if (!jobs.length) return null;
  return (
    <div className="space-y-4 mt-6">
      {jobs.map((job) => (
        <div key={job.id}>
          <GenerationCard job={job} />
          {job.readability && <ReadabilityCard readability={job.readability} />}
          {job.seoAnalysis && <SEOAnalysisCard seoAnalysis={job.seoAnalysis} />}
          {job.imagePrompts && <ImagePromptsCard prompts={job.imagePrompts} />}
        </div>
      ))}
    </div>
  );
}

/* ─── ImagePromptsCard ─── */
function ImagePromptsCard({ prompts }) {
  if (!prompts) return null;
  const copyText = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopyalandı!");
  };

  return (
    <div className="mt-4 space-y-3">
      {prompts.cover_image && (
        <Card className="bg-indigo-500/10 border-indigo-500/20">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <Badge className="bg-indigo-600">Cover Image</Badge>
              <Button size="sm" variant="ghost" onClick={() => copyText(prompts.cover_image)}>
                <Copy className="h-3.5 w-3.5 mr-1" /> Kopyala
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">{prompts.cover_image}</p>
          </CardContent>
        </Card>
      )}
      {prompts.in_article_images?.map((img, i) => (
        <Card key={i} className="bg-secondary/50 border-border">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <Badge variant="outline">Görsel {i + 1}</Badge>
              <Button size="sm" variant="ghost" onClick={() => copyText(typeof img === "string" ? img : img.prompt || img.description)}>
                <Copy className="h-3.5 w-3.5 mr-1" /> Kopyala
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">{typeof img === "string" ? img : img.prompt || img.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/* ─── Tab 1: Tam Yazı ─── */
function FullTab({ jobs, onAddJob, frameworks, styles, levels, metaLoading, initialTopic, initialOutline, initialTrendContext }) {
  const [topic, setTopic] = useState(initialTopic);
  const [framework, setFramework] = useState("answer_first");
  const [style, setStyle] = useState("informative");
  const [level, setLevel] = useState("standard");
  const [keyword, setKeyword] = useState("");
  const [context, setContext] = useState("");
  const [outline, setOutline] = useState(initialOutline);
  const [contextOpen, setContextOpen] = useState(false);
  const [outlineOpen, setOutlineOpen] = useState(!!initialOutline);
  const hasActive = jobs.some((j) => j.status === "generating");

  useEffect(() => { if (initialOutline) { setOutline(initialOutline); setOutlineOpen(true); } }, [initialOutline]);
  useEffect(() => { if (initialTopic) setTopic(initialTopic); }, [initialTopic]);

  const generate = () => {
    if (!topic.trim()) return toast.error("Konu giriniz");
    onAddJob({
      type: "blog-full",
      endpoint: "/generate/blog/full",
      body: { topic, outline: outline || undefined, style, framework, level, target_keyword: keyword || undefined, language: "tr", additional_context: context || undefined, trend_context: initialTrendContext || undefined },
      topic,
      label: "Tam Yazı",
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm font-medium mb-1.5 block">Konu</label>
        <Textarea placeholder="Blog konusunu detaylı yazın..." value={topic} onChange={(e) => setTopic(e.target.value)} rows={3} />
      </div>
      <ChipSelector label="Framework" options={frameworks} value={framework} onChange={setFramework} loading={metaLoading} />
      <ChipSelector label="Yazı Stili" options={styles} value={style} onChange={setStyle} loading={metaLoading} />
      <ChipSelector label="İçerik Seviyesi" options={levels} value={level} onChange={setLevel} loading={metaLoading} />
      <div>
        <label className="text-sm font-medium mb-1.5 block">Hedef Keyword <span className="text-muted-foreground">(opsiyonel)</span></label>
        <Input placeholder="ana anahtar kelime" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
      </div>
      <Collapsible open={contextOpen} onOpenChange={setContextOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="text-muted-foreground">
            <ChevronDown className={cn("h-4 w-4 mr-1 transition-transform", contextOpen && "rotate-180")} />
            Ek Bağlam
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-2">
          <Textarea placeholder="Ek talimat, hedef kitle, ton vb..." value={context} onChange={(e) => setContext(e.target.value)} rows={3} />
        </CollapsibleContent>
      </Collapsible>
      <Collapsible open={outlineOpen} onOpenChange={setOutlineOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="text-muted-foreground">
            <ChevronDown className={cn("h-4 w-4 mr-1 transition-transform", outlineOpen && "rotate-180")} />
            Taslaktan Yaz
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-2">
          <Textarea placeholder="Hazır taslağı yapıştırın..." value={outline} onChange={(e) => setOutline(e.target.value)} rows={5} />
        </CollapsibleContent>
      </Collapsible>
      <Button onClick={generate} disabled={hasActive} className="w-full bg-indigo-600 hover:bg-indigo-700">
        {hasActive ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
        {hasActive ? "Üretiliyor..." : "Tam Yazı Üret"}
      </Button>
      <JobResults jobs={jobs} />
    </div>
  );
}

/* ─── Tab 2: Taslak ─── */
function OutlineTab({ jobs, onAddJob, frameworks, styles, metaLoading, onUseOutline }) {
  const [topic, setTopic] = useState("");
  const [framework, setFramework] = useState("answer_first");
  const [style, setStyle] = useState("informative");
  const [keyword, setKeyword] = useState("");
  const hasActive = jobs.some((j) => j.status === "generating");

  const generate = () => {
    if (!topic.trim()) return toast.error("Konu giriniz");
    onAddJob({
      type: "blog-outline",
      endpoint: "/generate/blog/outline",
      body: { topic, style, framework, target_keyword: keyword || undefined, language: "tr" },
      topic,
      label: "Taslak",
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm font-medium mb-1.5 block">Konu</label>
        <Textarea placeholder="Blog konusu..." value={topic} onChange={(e) => setTopic(e.target.value)} rows={2} />
      </div>
      <ChipSelector label="Framework" options={frameworks} value={framework} onChange={setFramework} loading={metaLoading} />
      <ChipSelector label="Yazı Stili" options={styles} value={style} onChange={setStyle} loading={metaLoading} />
      <div>
        <label className="text-sm font-medium mb-1.5 block">Hedef Keyword <span className="text-muted-foreground">(opsiyonel)</span></label>
        <Input placeholder="anahtar kelime" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
      </div>
      <Button onClick={generate} disabled={hasActive} className="w-full bg-indigo-600 hover:bg-indigo-700">
        {hasActive ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <BookOpen className="h-4 w-4 mr-2" />}
        {hasActive ? "Üretiliyor..." : "Taslak Üret"}
      </Button>
      {jobs.length > 0 && (
        <div className="space-y-4 mt-6">
          {jobs.map((job) => (
            <div key={job.id}>
              <GenerationCard job={job} />
              {job.status === "done" && job.variants?.[0] && (
                <Button
                  variant="outline"
                  className="mt-3 border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10"
                  onClick={() => onUseOutline(typeof job.variants[0] === "string" ? job.variants[0] : job.variants[0].content, topic)}
                >
                  <ArrowRight className="h-4 w-4 mr-2" /> Bu Taslaktan Tam Yazı Üret
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Tab 3: SEO Analiz ─── */
function SEOTab({ jobs, onAddJob }) {
  const [content, setContent] = useState("");
  const [keyword, setKeyword] = useState("");
  const hasActive = jobs.some((j) => j.status === "generating");

  const analyze = () => {
    if (!content.trim()) return toast.error("Blog içeriğini yapıştırın");
    if (!keyword.trim()) return toast.error("Hedef keyword giriniz");
    onAddJob({
      type: "blog-seo",
      endpoint: "/generate/blog/seo-optimize",
      body: { content, target_keyword: keyword, language: "tr" },
      topic: keyword,
      label: "SEO Analiz",
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm font-medium mb-1.5 block">Blog İçeriği</label>
        <Textarea placeholder="Mevcut blog yazısını buraya yapıştırın..." value={content} onChange={(e) => setContent(e.target.value)} rows={8} />
      </div>
      <div>
        <label className="text-sm font-medium mb-1.5 block">Hedef Keyword</label>
        <Input placeholder="SEO hedef anahtar kelime" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
      </div>
      <Button onClick={analyze} disabled={hasActive} className="w-full bg-indigo-600 hover:bg-indigo-700">
        {hasActive ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Search className="h-4 w-4 mr-2" />}
        {hasActive ? "Analiz Ediliyor..." : "SEO Analiz Et"}
      </Button>
      <JobResults jobs={jobs} />
    </div>
  );
}

/* ─── Tab 4: Görseller ─── */
const imageStyles = [
  { id: "photorealistic", label: "Fotorealistik" },
  { id: "editorial", label: "Editorial" },
  { id: "illustration", label: "İllüstrasyon" },
  { id: "3d", label: "3D" },
];

function ImageTab({ jobs, onAddJob }) {
  const [topic, setTopic] = useState("");
  const [content, setContent] = useState("");
  const [imgStyle, setImgStyle] = useState("photorealistic");
  const [sectionCount, setSectionCount] = useState("3");
  const hasActive = jobs.some((j) => j.status === "generating");

  const generate = () => {
    if (!topic.trim()) return toast.error("Konu giriniz");
    onAddJob({
      type: "blog-image",
      endpoint: "/generate/blog/cover-image",
      body: { topic, content: content || undefined, style: imgStyle, section_count: parseInt(sectionCount) },
      topic,
      label: "Görsel Prompt",
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm font-medium mb-1.5 block">Konu</label>
        <Input placeholder="Blog konusu" value={topic} onChange={(e) => setTopic(e.target.value)} />
      </div>
      <div>
        <label className="text-sm font-medium mb-1.5 block">Blog İçeriği <span className="text-muted-foreground">(opsiyonel)</span></label>
        <Textarea placeholder="İçerik yapıştırın, daha iyi promptlar üretilir" value={content} onChange={(e) => setContent(e.target.value)} rows={4} />
      </div>
      <ChipSelector label="Görsel Stili" options={imageStyles} value={imgStyle} onChange={setImgStyle} />
      <div>
        <label className="text-sm font-medium mb-1.5 block">Makale İçi Görsel Sayısı</label>
        <Select value={sectionCount} onValueChange={setSectionCount}>
          <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
          <SelectContent>
            {[1, 2, 3, 4, 5].map((n) => (
              <SelectItem key={n} value={String(n)}>{n}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button onClick={generate} disabled={hasActive} className="w-full bg-indigo-600 hover:bg-indigo-700">
        {hasActive ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <ImageIcon className="h-4 w-4 mr-2" />}
        {hasActive ? "Üretiliyor..." : "Görsel Promptları Üret"}
      </Button>
      <JobResults jobs={jobs} />
    </div>
  );
}

/* ─── Tab 5: Dağıt (Repurpose) ─── */
const platforms = [
  { id: "twitter", label: "Tweet Thread" },
  { id: "linkedin", label: "LinkedIn Post" },
  { id: "instagram_carousel", label: "Instagram Carousel" },
];

function RepurposeTab({ jobs, onAddJob }) {
  const [content, setContent] = useState("");
  const [platform, setPlatform] = useState("twitter");
  const hasActive = jobs.some((j) => j.status === "generating");

  const generate = () => {
    if (!content.trim()) return toast.error("Blog içeriğini yapıştırın");
    onAddJob({
      type: "blog-repurpose",
      endpoint: "/generate/blog/repurpose",
      body: { blog_content: content, target_platform: platform, language: "tr" },
      topic: platform,
      label: "Dağıtım",
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label className="text-sm font-medium mb-1.5 block">Blog İçeriği</label>
        <Textarea placeholder="Blog yazısını buraya yapıştırın..." value={content} onChange={(e) => setContent(e.target.value)} rows={8} />
      </div>
      <ChipSelector label="Hedef Platform" options={platforms} value={platform} onChange={setPlatform} />
      <Button onClick={generate} disabled={hasActive} className="w-full bg-indigo-600 hover:bg-indigo-700">
        {hasActive ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Share2 className="h-4 w-4 mr-2" />}
        {hasActive ? "Dönüştürülüyor..." : "Dönüştür"}
      </Button>
      {jobs.length > 0 && (
        <div className="space-y-4 mt-6">
          {jobs.map((job) => (
            <div key={job.id}>
              <GenerationCard job={job} />
              {job.status === "done" && job.variants?.[0] && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  onClick={() => { const text = typeof job.variants[0] === "string" ? job.variants[0] : job.variants[0].content; navigator.clipboard.writeText(text); toast.success("Kopyalandı!"); }}
                >
                  <Copy className="h-3.5 w-3.5 mr-1" /> Kopyala
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Main Component ─── */
export default function BlogArchitectModule() {
  const [jobs, setJobs] = useState([]);
  const [activeTab, setActiveTab] = useState("full");
  const [searchParams] = useSearchParams();

  const initialTopic = searchParams.get("topic") || "";
  const initialTrendContext = searchParams.get("trend_context") || "";

  // Meta data from API
  const [frameworks, setFrameworks] = useState([]);
  const [styles, setStyles] = useState([]);
  const [levels, setLevels] = useState([]);
  const [metaLoading, setMetaLoading] = useState(true);

  // Outline → Full tab transfer
  const [outlineForFull, setOutlineForFull] = useState("");
  const [topicForFull, setTopicForFull] = useState("");

  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [fw, st, lv] = await Promise.all([
          api.get(`${API}/meta/blog/frameworks`),
          api.get(`${API}/meta/blog/styles`),
          api.get(`${API}/meta/blog/levels`),
        ]);
        setFrameworks(fw.data || []);
        setStyles(st.data || []);
        setLevels(lv.data || []);
      } catch (e) {
        console.error("Meta fetch error:", e);
        // Fallback
        setFrameworks([
          { id: "answer_first", label: "Answer First" },
          { id: "pas", label: "PAS" },
          { id: "aida", label: "AIDA" },
          { id: "storytelling", label: "Storytelling" },
        ]);
        setStyles([
          { id: "informative", label: "Bilgilendirici" },
          { id: "personal", label: "Kişisel" },
          { id: "technical", label: "Teknik" },
          { id: "opinion", label: "Görüş" },
          { id: "listicle", label: "Listicle" },
          { id: "case_study", label: "Vaka Analizi" },
        ]);
        setLevels([
          { id: "quick", label: "Kısa" },
          { id: "standard", label: "Standart" },
          { id: "deep_dive", label: "Derinlemesine" },
          { id: "ultimate", label: "Ultimate" },
        ]);
      } finally {
        setMetaLoading(false);
      }
    };
    fetchMeta();
  }, []);

  const updateJob = useCallback((jobId, updates) => {
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)));
  }, []);

  const dismissJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  const addJob = useCallback(
    async (params) => {
      const jobId = `blog-${++jobIdCounter}`;
      const newJob = {
        id: jobId,
        type: params.type,
        status: "generating",
        startedAt: Date.now(),
        topic: params.topic,
        label: params.label,
        variantCount: 1,
        variants: null,
        readability: null,
        seoAnalysis: null,
        imagePrompts: null,
      };
      setJobs((prev) => [newJob, ...prev]);

      try {
        const res = await api.post(`${API}${params.endpoint}`, params.body);
        const data = res.data;

        // Backend success: false kontrolü
        if (data.success === false) {
          updateJob(jobId, { status: "error", error: data.error || "Üretim başarısız" });
          toast.error(data.error || "Üretim başarısız");
          return;
        }

        // Backend GenerationResponse: { success, variants: [{content, variant_index, character_count}], metadata }
        let variants = [];
        if (data.variants && Array.isArray(data.variants)) {
          // Obje formatındaysa doğrudan kullan (GenerationCard {content, character_count} bekliyor)
          variants = data.variants.map((v) =>
            typeof v === "string"
              ? { content: v, character_count: v.length, variant_index: 0 }
              : v
          );
        } else {
          // Fallback: düz content/result/outline alanları
          const raw = data.content || data.result || data.outline || data.output || "";
          const arr = Array.isArray(raw) ? raw : [raw];
          variants = arr.map((c, i) => ({
            content: typeof c === "string" ? c : c.content || "",
            character_count: typeof c === "string" ? c.length : c.character_count || 0,
            variant_index: i,
          }));
        }

        updateJob(jobId, {
          status: "done",
          variants,
          readability: data.metadata?.readability || null,
          seoAnalysis: data.metadata?.seo_analysis || null,
          imagePrompts: data.metadata?.image_prompts || null,
        });
        toast.success(`${params.label} tamamlandı!`);
      } catch (e) {
        console.error("Generate error:", e);
        updateJob(jobId, {
          status: "error",
          error: e.response?.data?.detail || e.message || "Bir hata oluştu",
        });
        toast.error("Üretim başarısız oldu");
      }
    },
    [updateJob]
  );

  const handleUseOutline = useCallback((outlineText, topic) => {
    setOutlineForFull(outlineText);
    setTopicForFull(topic);
    setActiveTab("full");
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Hero Header */}
      <div className="text-center mt-4 mb-10">
        <h1 className="font-outfit text-4xl md:text-5xl font-extrabold tracking-tight mb-3">
          Konu yaz, <span className="bg-gradient-to-r from-indigo-400 to-violet-500 bg-clip-text text-transparent">viral bloglar</span> üret
        </h1>
        <p className="text-muted-foreground text-lg">
          AI destekli blog içerik üretimi, SEO analizi ve dağıtım
        </p>
      </div>

      {/* Tabs */}
      <Card className="bg-card border-border/50 rounded-2xl shadow-lg shadow-black/[0.03] dark:shadow-black/20">
        <CardContent className="p-8">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5 h-auto mb-6">
          <TabsTrigger value="full" className="text-xs sm:text-sm py-2">
            <Sparkles className="h-3.5 w-3.5 mr-1 hidden sm:inline" /> Tam Yazı
          </TabsTrigger>
          <TabsTrigger value="outline" className="text-xs sm:text-sm py-2">
            <BookOpen className="h-3.5 w-3.5 mr-1 hidden sm:inline" /> Taslak
          </TabsTrigger>
          <TabsTrigger value="seo" className="text-xs sm:text-sm py-2">
            <Search className="h-3.5 w-3.5 mr-1 hidden sm:inline" /> SEO
          </TabsTrigger>
          <TabsTrigger value="image" className="text-xs sm:text-sm py-2">
            <ImageIcon className="h-3.5 w-3.5 mr-1 hidden sm:inline" /> Görseller
          </TabsTrigger>
          <TabsTrigger value="repurpose" className="text-xs sm:text-sm py-2">
            <Share2 className="h-3.5 w-3.5 mr-1 hidden sm:inline" /> Dağıt
          </TabsTrigger>
        </TabsList>

        <div className="mt-6">
          <TabsContent value="full">
            <FullTab
              jobs={jobs.filter((j) => j.type === "blog-full")}
              onAddJob={addJob}
              frameworks={frameworks}
              styles={styles}
              levels={levels}
              metaLoading={metaLoading}
              initialTopic={topicForFull || initialTopic}
              initialOutline={outlineForFull}
              initialTrendContext={initialTrendContext}
            />
          </TabsContent>
          <TabsContent value="outline">
            <OutlineTab
              jobs={jobs.filter((j) => j.type === "blog-outline")}
              onAddJob={addJob}
              frameworks={frameworks}
              styles={styles}
              metaLoading={metaLoading}
              onUseOutline={handleUseOutline}
            />
          </TabsContent>
          <TabsContent value="seo">
            <SEOTab
              jobs={jobs.filter((j) => j.type === "blog-seo")}
              onAddJob={addJob}
            />
          </TabsContent>
          <TabsContent value="image">
            <ImageTab
              jobs={jobs.filter((j) => j.type === "blog-image")}
              onAddJob={addJob}
            />
          </TabsContent>
          <TabsContent value="repurpose">
            <RepurposeTab
              jobs={jobs.filter((j) => j.type === "blog-repurpose")}
              onAddJob={addJob}
            />
          </TabsContent>
        </div>
      </Tabs>
        </CardContent>
      </Card>

      {/* Floating Queue */}
      <FloatingQueue jobs={jobs} onDismiss={dismissJob} />
    </div>
  );
}
