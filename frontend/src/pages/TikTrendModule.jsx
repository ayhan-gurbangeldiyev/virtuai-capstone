/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
// TikTrendModule.jsx - TikTok AI İçerik Üretim Modülü
import { useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Music2,
  Sparkles,
  RefreshCw,
  Settings2,
  ChevronDown,
  ChevronUp,
  Plus,
  Minus,
  Lightbulb,
  Film,
  Type,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";
import FloatingQueue from "@/components/generation/FloatingQueue";


const tiktokDurations = [
  { id: "15s", label: "15 saniye" },
  { id: "30s", label: "30 saniye" },
  { id: "60s", label: "60 saniye" },
];

const tiktokFormats = [
  { id: "tutorial", label: "Tutorial", desc: "Adım adım öğretici" },
  { id: "skit", label: "Skit", desc: "Komedi/senaryo" },
  { id: "storytime", label: "Storytime", desc: "Hikaye anlatımı" },
  { id: "pov", label: "POV", desc: "Bakış açısı formatı" },
  { id: "duet", label: "Duet", desc: "Duet/yanıt formatı" },
];

const tiktokTones = [
  { id: "eglenceli", label: "Eğlenceli", desc: "Komik ve enerjik" },
  { id: "egitici", label: "Eğitici", desc: "Bilgi paylaşımı" },
  { id: "ilham_verici", label: "İlham Verici", desc: "Motivasyonel" },
  { id: "trend", label: "Trend", desc: "Güncel akım tarzı" },
  { id: "samimi", label: "Samimi", desc: "Doğal ve yakın" },
];

function ChipSelector({ options, value, onChange }) {
  const selected = options.find((o) => o.id === value);
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button key={option.id} type="button" onClick={() => onChange(option.id)}
            className={cn("chip", value === option.id && "active")} data-testid={`chip-${option.id}`}>
            {option.label}
          </button>
        ))}
      </div>
      {selected?.desc && <p className="text-xs text-muted-foreground">{selected.desc}</p>}
    </div>
  );
}

function VariantCounter({ value, onChange, max = 5 }) {
  return (
    <div className="flex items-center gap-4">
      <Button variant="outline" size="icon" onClick={() => onChange(Math.max(1, value - 1))} disabled={value <= 1}><Minus className="h-4 w-4" /></Button>
      <span className="text-xl font-semibold w-8 text-center">{value}</span>
      <Button variant="outline" size="icon" onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}><Plus className="h-4 w-4" /></Button>
    </div>
  );
}

// Script Tab
function ScriptTab({ jobs, onAddJob, onDismissJob, initialTopic }) {
  const [topic, setTopic] = useState(initialTopic || "");
  const [duration, setDuration] = useState("30s");
  const [format, setFormat] = useState("tutorial");
  const [variants, setVariants] = useState(2);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "tiktok_script",
      topic, duration, format, variants,
      personaLabel: "Script",
      toneLabel: tiktokFormats.find((f) => f.id === format)?.label,
      lengthLabel: duration,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
        <Film className="h-5 w-5 text-cyan-400" />
        <p className="text-sm text-cyan-200">Hook → Content → CTA + Overlay text önerileri ile tam script.</p>
      </div>

      <Textarea placeholder="TikTok video konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-cyan-500/30 focus:border-cyan-500"
        data-testid="tiktok-script-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Süre</label>
        <div className="flex gap-2">
          {tiktokDurations.map((d) => (
            <button key={d.id} type="button" onClick={() => setDuration(d.id)}
              className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all border",
                duration === d.id ? "bg-cyan-500 text-white border-cyan-500" : "bg-secondary text-muted-foreground border-transparent hover:bg-secondary/80")}
              data-testid={`tiktok-duration-${d.id}`}>{d.label}</button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Format</label>
        <ChipSelector options={tiktokFormats} value={format} onChange={setFormat} />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Varyant Sayısı</label>
        <VariantCounter value={variants} onChange={setVariants} max={3} />
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-cyan-500 hover:bg-cyan-600 text-black" data-testid="tiktok-script-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Sparkles className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Script Üret"}
      </Button>

      {jobs.length > 0 && (
        <div className="space-y-4 mt-6">
          <h3 className="font-outfit text-lg font-semibold">Üretilen İçerik</h3>
          {jobs.map((job) => <GenerationCard key={job.id} job={job} />)}
        </div>
      )}
      <FloatingQueue jobs={jobs} onDismiss={onDismissJob} />
    </div>
  );
}

// Caption Tab
function CaptionTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [tone, setTone] = useState("eglenceli");
  const [variants, setVariants] = useState(3);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "tiktok_caption",
      topic, tone, variants,
      personaLabel: "Caption",
      toneLabel: tiktokTones.find((t) => t.id === tone)?.label,
      lengthLabel: "Hook + Hashtag",
    });
  };

  return (
    <div className="space-y-6">
      <Textarea placeholder="Video konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-cyan-500/30 focus:border-cyan-500"
        data-testid="tiktok-caption-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Varyant Sayısı</label>
        <VariantCounter value={variants} onChange={setVariants} />
      </div>

      <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <CollapsibleTrigger asChild>
          <button type="button" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full">
            <Settings2 className="h-4 w-4" /><span>Gelişmiş Ayarlar</span>
            {advancedOpen ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-4 pt-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Ton</label>
            <ChipSelector options={tiktokTones} value={tone} onChange={setTone} />
          </div>
        </CollapsibleContent>
      </Collapsible>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-cyan-500 hover:bg-cyan-600 text-black" data-testid="tiktok-caption-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Type className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Caption Üret"}
      </Button>

      {jobs.length > 0 && (
        <div className="space-y-4 mt-6">
          <h3 className="font-outfit text-lg font-semibold">Üretilen İçerik</h3>
          {jobs.map((job) => <GenerationCard key={job.id} job={job} />)}
        </div>
      )}
      <FloatingQueue jobs={jobs} onDismiss={onDismissJob} />
    </div>
  );
}

// Trend Fikir Tab
function TrendFikirTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [variants, setVariants] = useState(1);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir niche girin"); return; }
    onAddJob({
      type: "tiktok_trend",
      topic, variants,
      personaLabel: "Trend",
      toneLabel: "Trend Analiz",
      lengthLabel: "Fikir + Adaptasyon",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
        <TrendingUp className="h-5 w-5 text-cyan-400" />
        <p className="text-sm text-cyan-200">Niche'inize uygun trending format önerileri ve adaptasyon fikirleri.</p>
      </div>

      <Input placeholder="Niche girin (örn: fitness, yazılım, yemek, moda)..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="border-cyan-500/30 focus:border-cyan-500"
        data-testid="tiktok-trend-input" />

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-cyan-500 hover:bg-cyan-600 text-black" data-testid="tiktok-trend-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <TrendingUp className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Trend Fikir Üret"}
      </Button>

      {jobs.length > 0 && (
        <div className="space-y-4 mt-6">
          <h3 className="font-outfit text-lg font-semibold">Üretilen İçerik</h3>
          {jobs.map((job) => <GenerationCard key={job.id} job={job} />)}
        </div>
      )}
      <FloatingQueue jobs={jobs} onDismiss={onDismissJob} />
    </div>
  );
}

let jobIdCounter = 0;

export default function TikTrendModule() {
  const [searchParams] = useSearchParams();
  const initialTopic = searchParams.get("topic") || "";
  const [jobs, setJobs] = useState([]);
  const updateJob = useCallback((jobId, updates) => {
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)));
  }, []);

  const dismissJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  const addJob = useCallback(async (params) => {
    const jobId = `tiktok-${++jobIdCounter}`;
    const newJob = {
      id: jobId, type: params.type, status: "generating", startedAt: Date.now(),
      topic: params.topic, personaLabel: params.personaLabel,
      toneLabel: params.toneLabel, lengthLabel: params.lengthLabel,
      variantCount: params.variants, variants: null,
    };
    setJobs((prev) => [newJob, ...prev]);

    try {
      let endpoint, body;

      if (params.type === "tiktok_script") {
        endpoint = `${API}/generate/tiktok/script`;
        body = { topic: params.topic, duration: params.duration, format: params.format, variants: params.variants };
      } else if (params.type === "tiktok_caption") {
        endpoint = `${API}/generate/tiktok/caption`;
        body = { topic: params.topic, tone: params.tone, variants: params.variants };
      } else if (params.type === "tiktok_trend") {
        endpoint = `${API}/generate/tiktok/script`;
        body = { topic: params.topic, type: "trend_ideas" };
      }

      const response = await api.post(endpoint, body);

      if (response.data.success) {
        updateJob(jobId, { status: "completed", variants: response.data.variants });
        toast.success("TikTok içerik başarıyla üretildi!");
      } else {
        updateJob(jobId, { status: "error" });
        toast.error(response.data.error || "Üretim başarısız");
      }
    } catch (error) {
      updateJob(jobId, { status: "error" });
      toast.error(error.response?.data?.detail || "Bir hata oluştu");
    }
  }, [updateJob]);

  return (
    <div className="max-w-4xl mx-auto" data-testid="tiktrend-module">
      <div className="mt-4 mb-10 text-center">
        <h1 className="font-outfit text-4xl md:text-5xl font-extrabold tracking-tight mb-3">
          Konu yaz, <span className="bg-gradient-to-r from-cyan-400 to-pink-500 bg-clip-text text-transparent">viral videolar</span> üret
        </h1>
        <p className="text-muted-foreground text-lg">
          Gen Z'nin hızına yetişin, trendleri yakalayın
        </p>
      </div>

      <Card className="bg-card border-border/50 rounded-2xl shadow-lg shadow-black/[0.03] dark:shadow-black/20 mb-8">
        <CardContent className="p-6">
          <Tabs defaultValue="script" className="w-full">
            <TabsList className="grid w-full grid-cols-3 mb-6" data-testid="tiktok-tabs">
              <TabsTrigger value="script" data-testid="tab-tiktok-script">Script</TabsTrigger>
              <TabsTrigger value="caption" data-testid="tab-tiktok-caption">Caption</TabsTrigger>
              <TabsTrigger value="trend" data-testid="tab-tiktok-trend">Trend Fikir</TabsTrigger>
            </TabsList>

            <TabsContent value="script">
              <ScriptTab jobs={jobs.filter((j) => j.type === "tiktok_script")} onAddJob={addJob} onDismissJob={dismissJob} initialTopic={initialTopic} />
            </TabsContent>
            <TabsContent value="caption">
              <CaptionTab jobs={jobs.filter((j) => j.type === "tiktok_caption")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
            <TabsContent value="trend">
              <TrendFikirTab jobs={jobs.filter((j) => j.type === "tiktok_trend")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

    </div>
  );
}
