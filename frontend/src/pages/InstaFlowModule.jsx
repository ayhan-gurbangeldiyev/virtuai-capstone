/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
// InstaFlowModule.jsx - Instagram AI İçerik Üretim Modülü
import { useState, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Instagram,
  Sparkles,
  RefreshCw,
  Settings2,
  ChevronDown,
  ChevronUp,
  Plus,
  Minus,
  Lightbulb,
  Hash,
  Film,
  Type,
  Calendar,
  Upload,
  X,
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


const captionLengths = [
  { id: "kisa", label: "Kısa", desc: "1-2 satır hook" },
  { id: "orta", label: "Orta", desc: "3-5 satır detaylı" },
  { id: "uzun", label: "Uzun", desc: "Hikaye tarzı uzun caption" },
];

const instaTones = [
  { id: "eglenceli", label: "Eğlenceli", desc: "Emoji dolu, rahat" },
  { id: "ilham_verici", label: "İlham Verici", desc: "Motivasyonel" },
  { id: "egitici", label: "Eğitici", desc: "Bilgi paylaşımı" },
  { id: "samimi", label: "Samimi", desc: "Arkadaşça sohbet" },
  { id: "profesyonel", label: "Profesyonel", desc: "Kurumsal ve ciddi" },
];

const reelDurations = [
  { id: "15s", label: "15 saniye" },
  { id: "30s", label: "30 saniye" },
  { id: "60s", label: "60 saniye" },
];

const reelFormats = [
  { id: "egitici", label: "Eğitici", desc: "Bilgi paylaşımı" },
  { id: "eglenceli", label: "Eğlenceli", desc: "Komedi ve trend" },
  { id: "tanitim", label: "Tanıtım", desc: "Ürün/hizmet tanıtımı" },
];

function ChipSelector({ options, value, onChange }) {
  const selected = options.find((o) => o.id === value);
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => onChange(option.id)}
            className={cn("chip", value === option.id && "active")}
            data-testid={`chip-${option.id}`}
          >
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

function ImageUpload({ imageUrl, onImageChange, onImageRemove }) {
  const fileInputRef = useRef(null);
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { toast.error("Görsel 5MB'dan küçük olmalı"); return; }
      onImageChange(URL.createObjectURL(file));
    }
  };
  return (
    <div className="relative border-2 border-dashed border-border rounded-lg p-4 hover:border-pink-500/50 transition-colors cursor-pointer" onClick={() => !imageUrl && fileInputRef.current?.click()}>
      <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFileChange} className="hidden" />
      {imageUrl ? (
        <div className="relative">
          <img src={imageUrl} alt="Uploaded" className="max-h-32 rounded-lg mx-auto" />
          <button type="button" onClick={(e) => { e.stopPropagation(); onImageRemove(); }} className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full p-1"><X className="h-4 w-4" /></button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Upload className="h-8 w-8" />
          <p className="text-sm font-medium">Görsel ekle (opsiyonel)</p>
          <p className="text-xs">Max 5MB - JPG, PNG, WebP</p>
        </div>
      )}
    </div>
  );
}

// Caption Tab
function CaptionTab({ jobs, onAddJob, onDismissJob, initialTopic }) {
  const [topic, setTopic] = useState(initialTopic || "");
  const [captionLength, setCaptionLength] = useState("orta");
  const [tone, setTone] = useState("eglenceli");
  const [variants, setVariants] = useState(3);
  const [imageUrl, setImageUrl] = useState(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "instagram_caption",
      topic, captionLength, tone, variants, imageUrl,
      personaLabel: "Caption",
      toneLabel: instaTones.find((t) => t.id === tone)?.label,
      lengthLabel: captionLengths.find((l) => l.id === captionLength)?.label,
    });
  };

  return (
    <div className="space-y-6">
      <Textarea
        placeholder="Caption konusu yazın (ürün, anı, konu)..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-pink-500/30 focus:border-pink-500"
        data-testid="insta-caption-input"
      />
      <ImageUpload imageUrl={imageUrl} onImageChange={setImageUrl} onImageRemove={() => setImageUrl(null)} />

      <div className="space-y-2">
        <label className="text-sm font-medium">Caption Uzunluğu</label>
        <ChipSelector options={captionLengths} value={captionLength} onChange={setCaptionLength} />
      </div>

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
            <ChipSelector options={instaTones} value={tone} onChange={setTone} />
          </div>
        </CollapsibleContent>
      </Collapsible>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-gradient-to-r from-purple-600 via-pink-500 to-orange-500 hover:from-purple-700 hover:via-pink-600 hover:to-orange-600" data-testid="insta-caption-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Sparkles className="h-5 w-5 mr-2" />}
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

// Reel Script Tab
function ReelScriptTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [duration, setDuration] = useState("30s");
  const [format, setFormat] = useState("egitici");
  const [variants, setVariants] = useState(2);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "instagram_reel",
      topic, duration, format, variants,
      personaLabel: "Reel",
      toneLabel: reelFormats.find((f) => f.id === format)?.label,
      lengthLabel: duration,
    });
  };

  return (
    <div className="space-y-6">
      <Textarea
        placeholder="Reel konusu yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[120px] text-base resize-none border-pink-500/30 focus:border-pink-500"
        data-testid="insta-reel-input"
      />

      <div className="space-y-2">
        <label className="text-sm font-medium">Süre</label>
        <div className="flex gap-2">
          {reelDurations.map((d) => (
            <button key={d.id} type="button" onClick={() => setDuration(d.id)}
              className={cn("px-4 py-2 rounded-lg text-sm font-medium transition-all border", duration === d.id ? "bg-pink-500 text-white border-pink-500" : "bg-secondary text-muted-foreground border-transparent hover:bg-secondary/80")}
              data-testid={`reel-duration-${d.id}`}>{d.label}</button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Format</label>
        <ChipSelector options={reelFormats} value={format} onChange={setFormat} />
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Varyant Sayısı</label>
        <VariantCounter value={variants} onChange={setVariants} max={3} />
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-gradient-to-r from-purple-600 via-pink-500 to-orange-500 hover:from-purple-700 hover:via-pink-600 hover:to-orange-600" data-testid="insta-reel-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Film className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Reel Script Üret"}
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

// Hashtag Tab
function HashtagTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [variants, setVariants] = useState(2);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "instagram_hashtags",
      topic, variants,
      personaLabel: "Hashtag",
      toneLabel: "Niche+Trending Mix",
      lengthLabel: "20-30 hashtag",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 p-4 rounded-lg bg-pink-500/10 border border-pink-500/20">
        <Hash className="h-5 w-5 text-pink-400" />
        <p className="text-sm text-pink-200">Niche, trending ve branded hashtag mix'i üretilir (20-30 hashtag).</p>
      </div>

      <Input
        placeholder="Konu veya niche girin (örn: dijital pazarlama, fitness)..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="border-pink-500/30 focus:border-pink-500"
        data-testid="insta-hashtag-input"
      />

      <div className="space-y-2">
        <label className="text-sm font-medium">Set Sayısı</label>
        <VariantCounter value={variants} onChange={setVariants} max={3} />
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-gradient-to-r from-purple-600 via-pink-500 to-orange-500 hover:from-purple-700 hover:via-pink-600 hover:to-orange-600" data-testid="insta-hashtag-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Hash className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Hashtag Üret"}
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

// Story Ideas Tab
function StoryIdeasTab({ jobs, onAddJob, onDismissJob }) {
  const [topic, setTopic] = useState("");
  const [dayCount, setDayCount] = useState(7);
  const [variants, setVariants] = useState(1);

  const hasActiveJob = jobs.some((j) => j.status === "generating");

  const handleGenerate = () => {
    if (!topic.trim()) { toast.error("Lütfen bir konu girin"); return; }
    onAddJob({
      type: "instagram_story_ideas",
      topic, dayCount, variants,
      personaLabel: "Story Plan",
      toneLabel: `${dayCount} gün`,
      lengthLabel: "Story Ideas",
    });
  };

  return (
    <div className="space-y-6">
      <Textarea
        placeholder="Story planı için konu veya marka/niche yazın..."
        value={topic} onChange={(e) => setTopic(e.target.value)}
        className="min-h-[100px] text-base resize-none border-pink-500/30 focus:border-pink-500"
        data-testid="insta-story-ideas-input"
      />

      <div className="space-y-2">
        <label className="text-sm font-medium">Gün Sayısı: {dayCount}</label>
        <input type="range" min={3} max={14} value={dayCount} onChange={(e) => setDayCount(Number(e.target.value))} className="w-full accent-pink-500" data-testid="insta-day-range" />
        <div className="flex justify-between text-xs text-muted-foreground"><span>3</span><span>14</span></div>
      </div>

      <Button onClick={handleGenerate} disabled={!topic.trim()} className="w-full h-12 text-base font-medium bg-gradient-to-r from-purple-600 via-pink-500 to-orange-500 hover:from-purple-700 hover:via-pink-600 hover:to-orange-600" data-testid="insta-story-ideas-generate-btn">
        {hasActiveJob ? <RefreshCw className="h-5 w-5 animate-spin mr-2" /> : <Calendar className="h-5 w-5 mr-2" />}
        {hasActiveJob ? "Sıraya Ekle" : "Story Planı Üret"}
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

export default function InstaFlowModule() {
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
    const jobId = `insta-${++jobIdCounter}`;
    const newJob = {
      id: jobId, type: params.type, status: "generating", startedAt: Date.now(),
      topic: params.topic, personaLabel: params.personaLabel,
      toneLabel: params.toneLabel, lengthLabel: params.lengthLabel,
      variantCount: params.variants, variants: null,
    };
    setJobs((prev) => [newJob, ...prev]);

    try {
      let endpoint = `${API}/generate/instagram/caption`;
      let body = { topic: params.topic, variants: params.variants };

      if (params.type === "instagram_caption") {
        endpoint = `${API}/generate/instagram/caption`;
        body = { ...body, caption_length: params.captionLength, tone: params.tone, image_url: params.imageUrl };
      } else if (params.type === "instagram_reel") {
        endpoint = `${API}/generate/instagram/reel-script`;
        body = { ...body, duration: params.duration, format: params.format };
      } else if (params.type === "instagram_hashtags") {
        endpoint = `${API}/generate/instagram/hashtags`;
      } else if (params.type === "instagram_story_ideas") {
        endpoint = `${API}/generate/instagram/story-ideas`;
        body = { ...body, day_count: params.dayCount };
      }

      const response = await api.post(endpoint, body);

      if (response.data.success) {
        updateJob(jobId, { status: "completed", variants: response.data.variants });
        toast.success("Instagram içerik başarıyla üretildi!");
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
    <div className="max-w-4xl mx-auto" data-testid="instaflow-module">
      <div className="mt-4 mb-10 text-center">
        <h1 className="font-outfit text-4xl md:text-5xl font-extrabold tracking-tight mb-3">
          Konu yaz, <span className="bg-gradient-to-r from-purple-500 via-pink-500 to-orange-500 bg-clip-text text-transparent">viral reeller</span> üret
        </h1>
        <p className="text-muted-foreground text-lg">
          Instagram algoritmasını lehinize çeviren içerikler üretin
        </p>
      </div>

      <Card className="bg-card border-border/50 rounded-2xl shadow-lg shadow-black/[0.03] dark:shadow-black/20 mb-8">
        <CardContent className="p-6">
          <Tabs defaultValue="caption" className="w-full">
            <TabsList className="grid w-full grid-cols-4 mb-6" data-testid="insta-tabs">
              <TabsTrigger value="caption" data-testid="tab-insta-caption">Caption</TabsTrigger>
              <TabsTrigger value="reel" data-testid="tab-insta-reel">Reel Script</TabsTrigger>
              <TabsTrigger value="hashtag" data-testid="tab-insta-hashtag">Hashtag</TabsTrigger>
              <TabsTrigger value="story-ideas" data-testid="tab-insta-story">Story Ideas</TabsTrigger>
            </TabsList>

            <TabsContent value="caption">
              <CaptionTab jobs={jobs.filter((j) => j.type === "instagram_caption")} onAddJob={addJob} onDismissJob={dismissJob} initialTopic={initialTopic} />
            </TabsContent>
            <TabsContent value="reel">
              <ReelScriptTab jobs={jobs.filter((j) => j.type === "instagram_reel")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
            <TabsContent value="hashtag">
              <HashtagTab jobs={jobs.filter((j) => j.type === "instagram_hashtags")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
            <TabsContent value="story-ideas">
              <StoryIdeasTab jobs={jobs.filter((j) => j.type === "instagram_story_ideas")} onAddJob={addJob} onDismissJob={dismissJob} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

    </div>
  );
}
