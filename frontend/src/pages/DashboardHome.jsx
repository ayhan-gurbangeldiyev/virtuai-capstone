import { useState, useEffect, useMemo } from "react";
import { useTranslation } from 'react-i18next';
import { useNavigate, Link } from "react-router-dom";
import {
  Heart, Copy, ArrowRight, Twitter, FileText, PenLine,
  MessageSquare, Quote, Search, Lightbulb, Dna,
  BarChart3, TrendingUp, ExternalLink, Zap, Flame,
  ChevronRight, Target, Compass, Brain, Fingerprint,
  Send,
} from "lucide-react";
import { FaXTwitter, FaYoutube, FaInstagram, FaTiktok, FaLinkedinIn } from "react-icons/fa6";
import { HiDocumentText } from "react-icons/hi2";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import ContentCalendar from "@/components/dashboard/ContentCalendar";
import HypeAutoDraftsBanner from "@/components/dashboard/HypeAutoDraftsBanner";

/* ═══════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════ */

const typeConfigBase = {
  tweet:   { labelKey: "create.contentTypes.tweet",  color: "bg-sky-500/15 text-sky-500",     icon: Twitter },
  quote:   { labelKey: "create.contentTypes.quote", color: "bg-purple-500/15 text-purple-500", icon: Quote },
  reply:   { labelKey: "create.contentTypes.reply",  color: "bg-emerald-500/15 text-emerald-500", icon: MessageSquare },
  article: { labelKey: "create.contentTypes.article", color: "bg-orange-500/15 text-orange-500", icon: FileText },
};

function getGreetingEmoji() {
  const h = new Date().getHours();
  if (h < 6) return "🌙";
  if (h < 12) return "🌅";
  if (h < 18) return "🌞";
  return "🌆";
}

function getGreetingKey() {
  const h = new Date().getHours();
  if (h < 6) return "dashboard.greeting.night";
  if (h < 12) return "dashboard.greeting.morning";
  if (h < 18) return "dashboard.greeting.afternoon";
  return "dashboard.greeting.evening";
}

function getDailyPromptIndex() {
  return Math.floor(Date.now() / 86400000) % 12;
}

/* ═══════════════════════════════════════════════════
   ANIMATED COUNTER
   ═══════════════════════════════════════════════════ */

function AnimatedCounter({ value, duration = 900 }) {
  const [display, setDisplay] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!value) { setDisplay(0); return; }
    setDone(false);
    let start = 0;
    const step = value / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= value) {
        setDisplay(value);
        setDone(true);
        clearInterval(timer);
      } else {
        setDisplay(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [value, duration]);

  return (
    <span className={cn(done && "animate-count-pulse")}>
      {display.toLocaleString()}
    </span>
  );
}

/* ═══════════════════════════════════════════════════
   WEEKLY BARS
   ═══════════════════════════════════════════════════ */

function WeeklyBars({ data = [], days }) {
  const max = Math.max(...data, 1);

  return (
    <div className="flex items-end gap-1.5 h-14">
      {days.map((d, i) => {
        const h = data[i] ? (data[i] / max) * 100 : 8;
        const isToday = i === ((new Date().getDay() + 6) % 7);
        return (
          <div key={i} className="flex flex-col items-center gap-1 flex-1">
            <div className="w-full relative rounded-t-sm overflow-hidden" style={{ height: "40px" }}>
              <div
                className={cn(
                  "absolute bottom-0 w-full rounded-t-sm bar-animate",
                  isToday
                    ? "bg-gradient-to-t from-purple-600 to-purple-400"
                    : data[i] > 0
                      ? "bg-gradient-to-t from-purple-500/40 to-purple-400/30"
                      : "bg-muted/30"
                )}
                style={{ height: `${h}%`, "--bar-i": i }}
              />
            </div>
            <span className={cn(
              "text-[9px] font-medium",
              isToday ? "text-purple-500" : "text-muted-foreground/60"
            )}>
              {d}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════
   TOOL CARD (big, prominent)
   ═══════════════════════════════════════════════════ */

function ToolCardBig({ icon: Icon, label, desc, path, gradient, accentColor, delay, exploreLabel }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(path)}
      className="tool-card bento-card relative overflow-hidden group flex flex-col p-3.5 md:p-5 rounded-xl md:rounded-2xl bg-card/70 backdrop-blur-sm border border-border/40 hover:border-transparent transition-all duration-300 text-left haptic-btn"
      style={{ "--bento-i": delay }}
    >
      {/* Glow orb on hover */}
      <div className={cn(
        "absolute -top-6 -right-6 w-24 h-24 rounded-full blur-2xl opacity-0 group-hover:opacity-30 transition-opacity duration-500",
        gradient.replace("from-", "bg-").split(" ")[0]
      )} />

      <div className={cn(
        "shrink-0 h-9 w-9 md:h-12 md:w-12 rounded-lg md:rounded-xl flex items-center justify-center bg-gradient-to-br mb-3 md:mb-4 group-hover:scale-110 transition-transform duration-300",
        gradient
      )}>
        <Icon className="h-4 w-4 md:h-5 md:w-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs md:text-sm font-bold mb-0.5 md:mb-1 group-hover:text-purple-500 transition-colors">{label}</p>
        <p className="text-[11px] md:text-[12px] text-muted-foreground leading-relaxed line-clamp-2">{desc}</p>
      </div>
      <div className="flex items-center gap-1 mt-2 md:mt-3 text-[10px] md:text-[11px] font-medium text-muted-foreground/50 group-hover:text-purple-500/70 transition-colors">
        <span>{exploreLabel}</span>
        <ArrowRight className="h-3 w-3 group-hover:translate-x-1 transition-transform" />
      </div>
    </button>
  );
}

/* ═══════════════════════════════════════════════════
   PLATFORM PILL (bigger, colorful)
   ═══════════════════════════════════════════════════ */

function PlatformCard({ icon: Icon, label, path, gradient, delay }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(path)}
      className="bento-card group flex flex-col items-center gap-2 md:gap-2.5 p-3 md:p-4 rounded-xl md:rounded-2xl bg-card/50 border border-border/30 hover:border-border/60 hover:bg-card/80 transition-all duration-300 haptic-btn min-h-[72px]"
      style={{ "--bento-i": delay }}
    >
      <div className={cn(
        "h-10 w-10 rounded-xl flex items-center justify-center bg-gradient-to-br group-hover:scale-110 transition-transform duration-300",
        gradient
      )}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <span className="text-xs font-semibold text-muted-foreground group-hover:text-foreground transition-colors">{label}</span>
    </button>
  );
}

/* ═══════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════ */

export default function DashboardHome() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({ generations: 0, tweets: 0, favorites: 0 });
  const [recentGenerations, setRecentGenerations] = useState([]);
  const [styleProfiles, setStyleProfiles] = useState([]);
  const [weeklyData, setWeeklyData] = useState([0, 0, 0, 0, 0, 0, 0]);
  const [topicInput, setTopicInput] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, historyRes, stylesRes, calRes] = await Promise.allSettled([
          api.get(`${API}/user/stats`),
          api.get(`${API}/generations/history?limit=5`),
          api.get(`${API}/styles/list`),
          api.get(`${API}/generations/calendar?year=${new Date().getFullYear()}&month=${new Date().getMonth() + 1}`),
        ]);
        if (statsRes.status === "fulfilled" && statsRes.value.data) setStats(statsRes.value.data);
        if (historyRes.status === "fulfilled" && historyRes.value.data) {
          const data = historyRes.value.data;
          setRecentGenerations(Array.isArray(data) ? data.slice(0, 5) : (data.generations || []).slice(0, 5));
        }
        if (stylesRes.status === "fulfilled" && stylesRes.value.data) {
          const data = stylesRes.value.data;
          setStyleProfiles(Array.isArray(data) ? data : (data.styles || []));
        }
        if (calRes.status === "fulfilled" && calRes.value.data?.days) {
          const days = calRes.value.data.days;
          const now = new Date();
          const weekly = [0, 0, 0, 0, 0, 0, 0];
          for (let i = 6; i >= 0; i--) {
            const d = new Date(now);
            d.setDate(d.getDate() - (6 - i));
            const key = d.toISOString().split("T")[0];
            if (days[key]) weekly[i] = days[key].count || 0;
          }
          setWeeklyData(weekly);
        }
      } catch (e) { /* ignore */ }
    };
    load();

  }, []);

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(t('common.copied'));
  };

  const handleTopicSubmit = () => {
    if (topicInput.trim()) {
      navigate(`/dashboard/create?platform=twitter&topic=${encodeURIComponent(topicInput.trim())}`);
    }
  };

  const firstName = user?.name?.split(" ")[0] || "User";
  const dailyPrompts = t('dashboard.dailyPrompts', { returnObjects: true });
  const dailyPrompt = dailyPrompts[getDailyPromptIndex()];
  const weekDays = t('dashboard.weekDays', { returnObjects: true });

  const typeConfig = useMemo(() => {
    const result = {};
    for (const [key, val] of Object.entries(typeConfigBase)) {
      result[key] = { ...val, label: t(val.labelKey) };
    }
    return result;
  }, [t]);
  const streak = weeklyData.reduceRight((acc, v) => (v > 0 && acc.active ? { count: acc.count + 1, active: true } : { ...acc, active: false }), { count: 0, active: true }).count;
  const weekTotal = weeklyData.reduce((a, b) => a + b, 0);
  const activeProfile = styleProfiles[0];

  const getContent = (gen) => {
    if (gen.variants?.length > 0 && gen.variants[0].content) return gen.variants[0].content;
    return gen.content || gen.text || "";
  };

  /* Tool definitions */
  const tools = [
    { icon: Send,        label: t('dashboard.tools.social', "Sosyal Manager"),       desc: t('dashboard.tools.socialDesc', "Tüm platformlardaki postlarını tek ekrandan yönet"), path: "/dashboard/social",       gradient: "from-sky-500 to-indigo-600" },
    { icon: Dna,         label: t('dashboard.tools.styleLab'),      desc: t('dashboard.tools.styleLabDesc'),   path: "/dashboard/style-lab",        gradient: "from-purple-500 to-indigo-600" },
    { icon: TrendingUp,  label: t('dashboard.tools.trends'),       desc: t('dashboard.tools.trendsDesc'),         path: "/dashboard/trends",           gradient: "from-emerald-500 to-teal-600" },
    { icon: BarChart3,   label: t('dashboard.tools.accountAnalysis'),  desc: t('dashboard.tools.accountAnalysisDesc'),        path: "/dashboard/account-analysis", gradient: "from-sky-500 to-blue-600" },
    { icon: Brain,       label: t('dashboard.tools.aiCoach'),       desc: t('dashboard.tools.aiCoachDesc'),       path: "/dashboard/coach",            gradient: "from-amber-500 to-orange-600" },
  ];

  const platforms = [
    { icon: FaXTwitter,     label: "X",         path: "/dashboard/create?platform=twitter",    gradient: "from-neutral-700 to-neutral-900" },
    { icon: FaYoutube,      label: "YouTube",    path: "/dashboard/create?platform=youtube",    gradient: "from-red-500 to-red-700" },
    { icon: FaInstagram,    label: "Instagram",  path: "/dashboard/create?platform=instagram",  gradient: "from-pink-500 via-purple-500 to-orange-500" },
    { icon: FaTiktok,       label: "TikTok",     path: "/dashboard/create?platform=tiktok",     gradient: "from-cyan-400 to-pink-500" },
    { icon: FaLinkedinIn,   label: "LinkedIn",   path: "/dashboard/create?platform=linkedin",   gradient: "from-blue-600 to-blue-800" },
    { icon: HiDocumentText, label: "Blog",       path: "/dashboard/create?platform=blog",       gradient: "from-orange-500 to-amber-600" },
  ];

  return (
    <div className="max-w-6xl mx-auto px-0 sm:px-1">
      {/* Phase 16.5 — Auto-Drafts pending banner (hides itself when count=0) */}
      <div className="mb-4">
        <HypeAutoDraftsBanner />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 auto-rows-auto">

        {/* ═══════════════════════════════════════
            ROW 1: GREETING (2col) + STATS (1+1)
            ═══════════════════════════════════════ */}

        {/* 1. Greeting + Search */}
        <div
          className="bento-card relative col-span-2 md:col-span-2 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 0 }}
        >
          <div className="bento-orb w-32 h-32 bg-purple-500/15 top-[-20px] right-[-20px]" />
          <div className="bento-orb w-24 h-24 bg-indigo-500/10 bottom-[-10px] left-[-10px]" style={{ animationDelay: "2s" }} />

          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">{getGreetingEmoji()}</span>
              <h1 className="font-outfit text-xl md:text-3xl font-bold tracking-tight">
                {t(getGreetingKey())}, {firstName}
              </h1>
            </div>
            <p className="text-muted-foreground text-sm mb-5">
              {t('dashboard.whatToCreate')}
            </p>

            <div className="flex gap-2.5">
              <div className="flex-1 relative">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                <input
                  type="text"
                  value={topicInput}
                  onChange={(e) => setTopicInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleTopicSubmit()}
                  placeholder={t('dashboard.topicPlaceholder')}
                  className="w-full h-11 pl-10 pr-4 rounded-xl bg-background/80 border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/30 transition-all placeholder:text-muted-foreground/50"
                />
              </div>
              <Button
                onClick={handleTopicSubmit}
                className="h-11 px-5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium shimmer-btn"
              >
                <PenLine className="h-4 w-4 mr-1.5" /> {t('dashboard.generate')}
              </Button>
            </div>
          </div>
        </div>

        {/* 2. Total Generations */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 1 }}
        >
          <div className="bento-orb w-20 h-20 bg-purple-500/10 top-[-10px] right-[-10px]" />
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-2 md:mb-3">
              <div className="h-8 w-8 md:h-10 md:w-10 rounded-xl bg-gradient-to-br from-purple-500/15 to-indigo-500/15 flex items-center justify-center">
                <Zap className="h-4 w-4 md:h-5 md:w-5 text-purple-500" />
              </div>
              <Badge className="text-[9px] md:text-[10px] bg-purple-500/10 text-purple-500 border-0 rounded-lg">{t('common.thisMonth')}</Badge>
            </div>
            <p className="font-outfit text-2xl md:text-3xl font-bold tracking-tight mb-0.5">
              <AnimatedCounter value={stats.generations || 0} />
            </p>
            <p className="text-[11px] md:text-xs text-muted-foreground">{t('common.totalGeneration')}</p>
          </div>
        </div>

        {/* 3. Favorites */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 2 }}
        >
          <div className="bento-orb w-20 h-20 bg-rose-500/10 top-[-10px] right-[-10px]" />
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-2 md:mb-3">
              <div className="h-8 w-8 md:h-10 md:w-10 rounded-xl bg-gradient-to-br from-rose-500/15 to-pink-500/15 flex items-center justify-center">
                <Heart className="h-4 w-4 md:h-5 md:w-5 text-rose-500" />
              </div>
              <Badge className="text-[9px] md:text-[10px] bg-rose-500/10 text-rose-500 border-0 rounded-lg">{t('common.collection')}</Badge>
            </div>
            <p className="font-outfit text-2xl md:text-3xl font-bold tracking-tight mb-0.5">
              <AnimatedCounter value={stats.favorites || 0} />
            </p>
            <p className="text-[11px] md:text-xs text-muted-foreground">{t('common.favoriteContent')}</p>
          </div>
        </div>

        {/* ═══════════════════════════════════════
            ROW 2: ARAÇLAR (full width, prominent!)
            ═══════════════════════════════════════ */}
        <div
          className="bento-card relative col-span-2 md:col-span-4 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 3 }}
        >
          <div className="bento-orb w-40 h-40 bg-purple-500/8 bottom-[-30px] right-[10%]" />
          <div className="bento-orb w-32 h-32 bg-indigo-500/8 top-[-20px] left-[5%]" style={{ animationDelay: "1.5s" }} />

          <div className="relative z-10">
            {/* Header */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
                  <Compass className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-base font-bold">{t('dashboard.toolsAndPlatforms')}</h2>
                  <p className="text-[12px] text-muted-foreground">{t('dashboard.toolsSubtitle')}</p>
                </div>
              </div>
            </div>

            {/* Tool cards - 4 column grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              {tools.map((tool, i) => (
                <ToolCardBig key={tool.label} {...tool} exploreLabel={t('common.explore')} delay={4 + i} />
              ))}
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3 mb-4">
              <div className="h-px flex-1 bg-border/40" />
              <span className="text-[11px] text-muted-foreground/60 font-medium">{t('dashboard.contentPlatforms')}</span>
              <div className="h-px flex-1 bg-border/40" />
            </div>

            {/* Platform cards - 6 column grid */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {platforms.map((p, i) => (
                <PlatformCard key={p.label} {...p} delay={8 + i} />
              ))}
            </div>
          </div>
        </div>

        {/* ═══════════════════════════════════════
            ROW 3: CALENDAR (2col, 2row) + STREAK + STYLE + RECENT + ILHAM
            ═══════════════════════════════════════ */}

        {/* 4. Content Calendar (embedded, no double Card) */}
        <div
          className="bento-card relative col-span-2 md:col-span-2 md:row-span-2 rounded-2xl md:rounded-3xl overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 9 }}
        >
          {/* Gradient top accent */}
          <div className="h-[2px] bg-gradient-to-r from-purple-500 via-pink-500 to-indigo-500" />
          <ContentCalendar embedded />
        </div>

        {/* 5. Streak & Weekly */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 10 }}
        >
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Flame className={cn(
                  "h-5 w-5",
                  streak > 0 ? "text-orange-500 animate-streak-fire" : "text-muted-foreground/40"
                )} />
                <span className="text-sm font-semibold">{t('dashboard.streak')}</span>
              </div>
              <span className="font-outfit text-2xl font-bold">
                {streak > 0 ? (
                  <span className="bg-gradient-to-r from-orange-500 to-amber-500 bg-clip-text text-transparent">{streak}</span>
                ) : (
                  <span className="text-muted-foreground/40">0</span>
                )}
              </span>
            </div>

            <div className="mt-1 mb-1">
              <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1.5">
                <span>{t('dashboard.thisWeek')}</span>
                <span className="font-medium">{t('dashboard.nGenerations', { count: weekTotal })}</span>
              </div>
              <WeeklyBars data={weeklyData} days={weekDays} />
            </div>
          </div>
        </div>

        {/* 6. Style Profile */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 11 }}
        >
          <div className="bento-orb w-20 h-20 bg-indigo-500/10 bottom-[-10px] right-[-10px]" style={{ animationDelay: "1s" }} />
          <div className="relative z-10">
            {activeProfile ? (
              <>
                <div className="flex items-center gap-3 mb-3">
                  <div className="relative">
                    <div className="h-11 w-11 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white font-bold text-sm animate-ring-pulse">
                      {(activeProfile.name || "S").charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-sm truncate">{activeProfile.name || activeProfile.screen_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {activeProfile.style_summary?.tweet_count || activeProfile.tweet_count || 0} {t('dashboard.tweetAnalyzed')}
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={() => navigate(`/dashboard/create?platform=twitter&style=${activeProfile.id}`)}
                  className="w-full h-9 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white text-xs font-medium"
                >
                  {t('dashboard.generateWithStyle')} <ArrowRight className="h-3 w-3 ml-1" />
                </Button>
              </>
            ) : (
              <div className="text-center py-2">
                <div className="mx-auto w-12 h-12 rounded-full bg-gradient-to-br from-purple-500/15 to-indigo-500/15 flex items-center justify-center mb-2">
                  <Dna className="h-5 w-5 text-purple-500/50 animate-float" />
                </div>
                <p className="text-xs text-muted-foreground mb-3">{t('dashboard.noStyleProfile')}</p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate("/dashboard/style-lab")}
                  className="w-full h-8 rounded-xl text-xs"
                >
                  Style Lab <ArrowRight className="h-3 w-3 ml-1" />
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* 7. Recent Generation Preview */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-5 overflow-hidden bg-card/80 backdrop-blur-sm border border-border/40"
          style={{ "--bento-i": 12 }}
        >
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold">{t('dashboard.recentGenerations')}</span>
              <Link to="/dashboard/history" className="text-[10px] text-purple-500 hover:text-purple-400 flex items-center gap-0.5 transition-colors">
                {t('dashboard.viewAll')} <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {recentGenerations.length > 0 ? (
              <div className="space-y-2">
                {recentGenerations.slice(0, 3).map((gen, i) => {
                  const type = typeConfig[gen.type] || typeConfig.tweet;
                  const content = getContent(gen);
                  return (
                    <button
                      key={gen.id || i}
                      onClick={() => handleCopy(content)}
                      className="group w-full text-left flex items-start gap-2.5 p-2 rounded-xl hover:bg-secondary/50 transition-colors"
                    >
                      <div className={cn("shrink-0 mt-0.5 h-2 w-2 rounded-full", type.color.split(" ")[0])} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs leading-relaxed line-clamp-2 text-foreground/80">
                          {content.slice(0, 80)}{content.length > 80 ? "..." : ""}
                        </p>
                        <p className="text-[9px] text-muted-foreground/60 mt-0.5">
                          {gen.created_at ? new Date(gen.created_at).toLocaleDateString("tr-TR") : ""}
                        </p>
                      </div>
                      <Copy className="shrink-0 h-3 w-3 text-muted-foreground/30 group-hover:text-purple-500 transition-colors mt-1" />
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-4">
                <PenLine className="h-6 w-6 text-muted-foreground/20 mx-auto mb-2" />
                <p className="text-xs text-muted-foreground/60">{t('dashboard.noGenerationsYet')}</p>
              </div>
            )}
          </div>
        </div>

        {/* 8. Bugünün İlhamı */}
        <div
          className="bento-card relative col-span-1 rounded-2xl md:rounded-3xl p-4 md:p-6 overflow-hidden bg-gradient-to-br from-amber-500/[0.08] to-orange-500/[0.05] border border-amber-500/10"
          style={{ "--bento-i": 13 }}
        >
          <div className="bento-orb w-24 h-24 bg-amber-500/10 top-[-15px] left-[-15px]" style={{ animationDelay: "3s" }} />
          <div className="relative z-10">
            <div className="flex items-center gap-2 mb-3">
              <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 flex items-center justify-center">
                <Lightbulb className="h-[18px] w-[18px] text-amber-500" />
              </div>
              <span className="text-sm font-semibold">{t('dashboard.todaysInspiration')}</span>
            </div>
            <p className="text-xs text-foreground/70 leading-relaxed mb-4 line-clamp-3">
              {dailyPrompt}
            </p>
            <Button
              size="sm"
              onClick={() => navigate(`/dashboard/create?platform=twitter?topic=${encodeURIComponent(dailyPrompt)}`)}
              className="w-full h-9 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white text-xs font-medium"
            >
              <PenLine className="h-3.5 w-3.5 mr-1" /> {t('dashboard.generateOnTopic')}
            </Button>
          </div>
        </div>

      </div>
    </div>
  );
}
