/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
// YouTubeModule.jsx - YouTube AI İçerik Üretim Modülü
import { useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Youtube,
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
  Image,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";
import FloatingQueue from "@/components/generation/FloatingQueue";


const scriptDurations = [
  { id: "5", label: "5 dk" },
  { id: "10", label: "10 dk" },
  { id: "15", label: "15 dk" },
  { id: "20", label: "20 dk" },
];

function VariantCounter({ value, onChange, max = 5 }) {
  return (
    <div className="flex items-center gap-4">
      <Button variant="outline" size="icon" onClick={() => onChange(Math.max(1, value - 1))} disabled={value <= 1}><Minus className="h-4 w-4" /></Button>
      <span className="text-xl font-semibold w-8 text-center">{value}</span>
      <Button variant="outline" size="icon" onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max}><Plus className="h-4 w-4" /></Button>
    </div>
  );
}

// Fikir Tab
function FikirTab({ jobs, onAddJob, onDismissJob, initialTopic }) {
  const [topic, setTopic] = useState(initialTopic || "");
  const [ideaCount, setIdeaCount] = useState(5);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir niche/konu girin"); return; }
    onAddJob({
      type: "youtube_idea",
      topic, ideaCount, variants: 1,
      personaLabel: "Fikir",
      toneLabel: `${ideaCount} fikir`,
      lengthLabel: "Fikir Listesi",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
        <Lightbulb className="h-5 w-5 text-red-400" />
        <p className="text-sm text-red-200">Her fikir title + hook + kısa outline içerecek.</p>
      </div>

      <Textarea placeholder="Niche veya konu yazın (örn: kişisel finans, yazılım, yemek)..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-red-500/30 focus:border-red-500"
        data-testid="yt-idea-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Fikir Sayısı: {ideaCount}</label>
        <input type="range" min={3} max={10} value={ideaCount} onChange={(e) => setIdeaCount(Number(e.target.value))}
          className="w-full accent-red-500" data-testid="yt-idea-count" />
        <div className="flex justify-between text-xs text-muted-foreground"><span>3</span><span>10</span></div>
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-red-600 hover:bg-red-700" data-testid="yt-idea-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Lightbulb className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Fikir Üret"}
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

// Script Tab
function ScriptTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState("10");
  const [additionalContext, setAdditionalContext] = useState("");
  const [showContext, setShowContext] = useState(false);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "youtube_script",
      topic, duration, variants: 1,
      additionalContext: showContext ? additionalContext : null,
      personaLabel: "Script",
      toneLabel: `${duration} dk`,
      lengthLabel: "Tam Script",
    });
  };

  return (
    <div className="space-y-6">
      <Textarea placeholder="Video konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-red-500/30 focus:border-red-500"
        data-testid="yt-script-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Video Süresi</label>
        <div className="flex gap-2">
          {scriptDurations.map((d) => (
            <button key={d.id} type="button" onClick={() => setDuration(d.id)}
              className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all border",
                duration === d.id ? "bg-red-600 text-white border-red-600" : "bg-secondary text-muted-foreground border-transparent hover:bg-secondary/80")}
              data-testid={`yt-duration-${d.id}`}>{d.label}</button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={showContext} onChange={(e) => setShowContext(e.target.checked)} className="rounded border-border" />
          <span className="text-sm font-medium">Ek Bağlam (Opsiyonel)</span>
        </label>
        {showContext && (
          <Textarea placeholder="Hedef kitle, ton, özel notlar..." value={additionalContext} onChange={(e) => setAdditionalContext(e.target.value)}
            className="min-h-[80px] resize-none" data-testid="yt-script-context" />
        )}
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-red-600 hover:bg-red-700" data-testid="yt-script-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Film className="h-5 w-5 mr-2" />}
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

// Başlık & Açıklama Tab
function TitleDescTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [titleCount, setTitleCount] = useState(5);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen video konusu girin"); return; }
    onAddJob({
      type: "youtube_title",
      topic, titleCount, variants: 1,
      personaLabel: "Başlık",
      toneLabel: `${titleCount} varyant`,
      lengthLabel: "Title + SEO Desc",
    });
  };

  return (
    <div className="space-y-6">
      <Textarea placeholder="Video konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-red-500/30 focus:border-red-500"
        data-testid="yt-title-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Başlık Varyantı: {titleCount}</label>
        <input type="range" min={3} max={10} value={titleCount} onChange={(e) => setTitleCount(Number(e.target.value))}
          className="w-full accent-red-500" data-testid="yt-title-count" />
        <div className="flex justify-between text-xs text-muted-foreground"><span>3</span><span>10</span></div>
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-red-600 hover:bg-red-700" data-testid="yt-title-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Type className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Başlık & Açıklama Üret"}
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

// Thumbnail Tab
function ThumbnailTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [variants, setVariants] = useState(3);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen video konusu girin"); return; }
    onAddJob({
      type: "youtube_thumbnail",
      topic, variants,
      personaLabel: "Thumbnail",
      toneLabel: "Konsept",
      lengthLabel: `${variants} konsept`,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
        <Image className="h-5 w-5 text-red-400" />
        <p className="text-sm text-red-200">Her konseptte metin, renk paleti ve layout önerisi bulunur.</p>
      </div>

      <Textarea placeholder="Video konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-red-500/30 focus:border-red-500"
        data-testid="yt-thumb-input" />

      <div className="space-y-2">
        <label className="text-sm font-medium">Konsept Sayısı</label>
        <VariantCounter value={variants} onChange={setVariants} max={5} />
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-red-600 hover:bg-red-700" data-testid="yt-thumb-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Image className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Thumbnail Konsept Üret"}
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

export default function YouTubeModule() {
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
    const jobId = `yt-${++jobIdCounter}`;
    const newJob = {
      id: jobId, type: params.type, status: "generating", startedAt: Date.now(),
      topic: params.topic, personaLabel: params.personaLabel,
      toneLabel: params.toneLabel, lengthLabel: params.lengthLabel,
      variantCount: params.variants, variants: null,
    };
    setJobs((prev) => [newJob, ...prev]);

    try {
      let endpoint, body;

      if (params.type === "youtube_idea") {
        endpoint = `${API}/generate/youtube/idea`;
        body = { topic: params.topic, idea_count: params.ideaCount };
      } else if (params.type === "youtube_script") {
        endpoint = `${API}/generate/youtube/script`;
        body = { topic: params.topic, duration: params.duration, additional_context: params.additionalContext };
      } else if (params.type === "youtube_title") {
        endpoint = `${API}/generate/youtube/title`;
        body = { topic: params.topic, title_count: params.titleCount };
      } else if (params.type === "youtube_thumbnail") {
        endpoint = `${API}/generate/youtube/description`;
        body = { topic: params.topic, variants: params.variants };
      }

      const response = await api.post(endpoint, body);

      if (response.data.success) {
        updateJob(jobId, { status: "completed", variants: response.data.variants });
        toast.success("YouTube içerik başarıyla üretildi!");
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
    <div className="max-w-4xl mx-auto" data-testid="youtube-module">
      <div className="mt-4 mb-10 text-center">
        <h1 className="font-outfit text-4xl md:text-5xl font-extrabold tracking-tight mb-3">
          Konu yaz, <span className="bg-gradient-to-r from-red-500 to-orange-500 bg-clip-text text-transparent">viral videolar</span> planla
        </h1>
        <p className="text-muted-foreground text-lg">
          Video fikirlerinden scriptlere, başlıklardan thumbnail'lara
        </p>
      </div>

      <Card className="bg-card border-border/50 rounded-2xl shadow-lg shadow-black/[0.03] dark:shadow-black/20 mb-8">
        <CardContent className="p-6">
          <Tabs defaultValue="fikir" className="w-full">
            <TabsList className="grid w-full grid-cols-4 mb-6" data-testid="youtube-tabs">
              <TabsTrigger value="fikir" data-testid="tab-yt-fikir">Fikir</TabsTrigger>
              <TabsTrigger value="script" data-testid="tab-yt-script">Script</TabsTrigger>
              <TabsTrigger value="title" data-testid="tab-yt-title">Başlık & Açıklama</TabsTrigger>
              <TabsTrigger value="thumbnail" data-testid="tab-yt-thumb">Thumbnail</TabsTrigger>
            </TabsList>

            <TabsContent value="fikir">
              <FikirTab jobs={jobs.filter((j) => j.type === "youtube_idea")} onAddJob={addJob} onDismissJob={dismissJob} initialTopic={initialTopic} />
            </TabsContent>
            <TabsContent value="script">
              <ScriptTab jobs={jobs.filter((j) => j.type === "youtube_script")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
            <TabsContent value="title">
              <TitleDescTab jobs={jobs.filter((j) => j.type === "youtube_title")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
            <TabsContent value="thumbnail">
              <ThumbnailTab jobs={jobs.filter((j) => j.type === "youtube_thumbnail")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

    </div>
  );
}
