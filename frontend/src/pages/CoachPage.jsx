/**
 * AI Coach v3.1 — Premium UI
 * Üst: AI Orb + Card Stack (dar, odaklı)
 * Alt: Geniş Bento layout (plan + heatmap + stats)
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Calendar, BarChart3, Clock, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";

import AIOrb from "@/components/coach/AIOrb";
import CardStack from "@/components/coach/CardStack";
import MiniStats from "@/components/coach/MiniStats";
import WeeklyPlanSection from "@/components/coach/WeeklyPlanSection";

// ── Greeting ──
function getGreeting(t) {
  const hour = new Date().getHours();
  if (hour < 12) return t("coach.greeting.morning");
  if (hour < 18) return t("coach.greeting.afternoon");
  return t("coach.greeting.evening");
}

// ── Posting Heatmap ──
function getHeatmapColor(score) {
  if (score >= 0.85) return "bg-emerald-400";
  if (score >= 0.7) return "bg-emerald-700";
  if (score >= 0.5) return "bg-emerald-900";
  if (score >= 0.3) return "bg-zinc-700";
  return "bg-zinc-800";
}

function PostingHeatmap({ postingData, bestNow, postingLoading }) {
  const { t } = useTranslation();
  const SHORT_DAYS = t("coach.shortDays", { returnObjects: true });

  if (postingLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!postingData) return null;

  const { heatmap, days, best_slots, timezone } = postingData;
  const evenHours = Array.from({ length: 12 }, (_, i) => i * 2);

  return (
    <div className="space-y-4">
      {bestNow && (
        <div className="flex items-center justify-between p-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
          <div>
            <p className="font-medium text-sm flex items-center gap-2">
              ⏰ {t("coach.postNow")}
            </p>
            <p className="text-base font-bold mt-0.5">{bestNow.verdict}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">
              {t("coach.score", { score: Math.round((bestNow.current_score || 0) * 100) })}
            </p>
            {bestNow.next_best && (
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {t("coach.nextBest", {
                  day: bestNow.next_best.day,
                  time: bestNow.next_best.time,
                  hours: bestNow.next_best.hours_away,
                })}
              </p>
            )}
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <div className="inline-block">
          <div className="flex ml-10">
            {evenHours.map((h) => (
              <div key={h} className="w-7 text-center text-[10px] text-muted-foreground">{h}</div>
            ))}
          </div>
          {heatmap.map((row, dayIdx) => (
            <div key={dayIdx} className="flex items-center gap-1 mb-0.5">
              <span className="w-8 text-[11px] text-muted-foreground text-right mr-1">
                {SHORT_DAYS[dayIdx]}
              </span>
              {row.map((score, hourIdx) => (
                <div
                  key={hourIdx}
                  className={cn(
                    "w-[11px] h-[11px] rounded-sm cursor-pointer transition-colors hover:ring-1 hover:ring-white/50",
                    getHeatmapColor(score)
                  )}
                  title={`${days?.[dayIdx] || SHORT_DAYS[dayIdx]} ${String(hourIdx).padStart(2, "0")}:00 — ${(score * 100).toFixed(0)}%`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {timezone && <p className="text-[11px] text-muted-foreground">{timezone}</p>}

      {best_slots?.length > 0 && (
        <div>
          <p className="text-xs font-medium mb-1.5">{t("coach.top5Slots")}</p>
          <div className="flex flex-wrap gap-1.5">
            {best_slots.slice(0, 5).map((slot, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">
                {slot.day} {slot.time} — {Math.round(slot.score * 100)}%
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stat Bar ──
function StatBar({ label, data, colorMap }) {
  if (!data || Object.keys(data).length === 0) return null;
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  const colors = ["bg-sky-500", "bg-purple-500", "bg-pink-500", "bg-green-500", "bg-yellow-500", "bg-orange-500"];
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex rounded-full overflow-hidden h-2.5 bg-secondary">
        {Object.entries(data).map(([key, count], i) => (
          <div
            key={key}
            className={cn(colorMap?.[key] || colors[i % colors.length], "transition-all")}
            style={{ width: `${(count / total) * 100}%` }}
            title={`${key}: ${count} (${Math.round((count / total) * 100)}%)`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(data).map(([key, count], i) => (
          <span key={key} className="text-[11px] text-muted-foreground">
            <span className={cn("inline-block w-2 h-2 rounded-full mr-1", colorMap?.[key] || colors[i % colors.length])} />
            {key}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════

export default function CoachPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [cards, setCards] = useState([]);
  const [feedLoading, setFeedLoading] = useState(true);
  const [activeCardType, setActiveCardType] = useState(null);

  const [weeklyPlan, setWeeklyPlan] = useState(null);
  const [weeklyGoal, setWeeklyGoal] = useState("");
  const [planCached, setPlanCached] = useState(false);
  const [planCreatedAt, setPlanCreatedAt] = useState(null);
  const [planGenerating, setPlanGenerating] = useState(false);

  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(true);

  const [postingData, setPostingData] = useState(null);
  const [bestNow, setBestNow] = useState(null);
  const [postingLoading, setPostingLoading] = useState(true);

  const [showDetails, setShowDetails] = useState(false);

  // ── Fetch ──
  useEffect(() => {
    api.get(`${API}/coach/feed`)
      .then((res) => {
        const c = res.data.cards || [];
        setCards(c);
        if (c.length > 0) setActiveCardType(c[0].type);
      })
      .catch(() => {})
      .finally(() => setFeedLoading(false));

    api.get(`${API}/coach/weekly-plan`)
      .then((res) => {
        if (res.data.plan) {
          setWeeklyPlan(res.data.plan);
          setWeeklyGoal(res.data.weekly_goal || "");
          setPlanCached(res.data.cached || false);
          setPlanCreatedAt(res.data.created_at);
        }
      })
      .catch(() => {});

    api.get(`${API}/coach/insights`)
      .then((res) => setInsights(res.data))
      .catch(() => {})
      .finally(() => setInsightsLoading(false));

    Promise.all([
      api.get(`${API}/posting-times/heatmap`).catch(() => ({ data: null })),
      api.get(`${API}/posting-times/best-now`).catch(() => ({ data: null })),
    ]).then(([hRes, bRes]) => {
      setPostingData(hRes.data);
      setBestNow(bRes.data);
    }).finally(() => setPostingLoading(false));
  }, []);

  // ── Handlers ──
  const handleDismiss = useCallback(async (cardKey) => {
    setCards((prev) => {
      const next = prev.filter((c) => c.key !== cardKey);
      setActiveCardType(next.length > 0 ? next[0].type : null);
      return next;
    });
    try { await api.post(`${API}/coach/dismiss`, { card_key: cardKey }); } catch {}
  }, []);

  const handleAction = useCallback((action) => {
    if (action.route) { navigate(action.route); return; }
    const params = new URLSearchParams();
    params.set("platform", action.platform || "twitter");
    if (action.topic) params.set("topic", action.topic);
    if (action.persona) params.set("persona", action.persona);
    if (action.tone) params.set("tone", action.tone);
    if (action.hook) params.set("hook", action.hook);
    if (action.length) params.set("length", action.length);
    navigate(`/dashboard/create?${params.toString()}`);
  }, [navigate]);

  const handleGeneratePlan = useCallback(async () => {
    setPlanGenerating(true);
    try {
      const res = await api.post(`${API}/coach/weekly-plan`, { niche: "tech" });
      setWeeklyPlan(res.data.plan);
      setWeeklyGoal(res.data.weekly_goal || "");
      setPlanCached(false);
      setPlanCreatedAt(res.data.created_at);
      toast.success(t("coach.plan.created") || "Plan oluşturuldu! 🎉");
    } catch {
      toast.error(t("coach.weeklyPlanError"));
    } finally {
      setPlanGenerating(false);
    }
  }, [t]);

  const handleWriteFromPlan = useCallback((day) => {
    const params = new URLSearchParams();
    params.set("platform", "twitter");
    if (day.topic_suggestion) params.set("topic", day.topic_suggestion);
    if (day.persona) params.set("persona", day.persona);
    if (day.tone) params.set("tone", day.tone);
    navigate(`/dashboard/create?${params.toString()}`);
  }, [navigate]);

  const miniStats = useMemo(() => {
    const s = insights?.stats || {};
    return {
      current_streak: s.current_streak || 0,
      this_week: s.last_7_days ?? s.this_week ?? 0,
      favorite_ratio: s.favorite_ratio || 0,
    };
  }, [insights]);

  const greeting = getGreeting(t);
  const subtitle = cards.length > 0
    ? t("coach.cardCount", { count: cards.length })
    : t("coach.subtitle");
  const stats = insights?.stats || {};

  return (
    <div className="pb-12" data-testid="coach-page">
      {/* ══════════════════════════════════════
          ÜST BÖLÜM: Orb + Stack (dar, odaklı)
          ══════════════════════════════════════ */}
      <div className="max-w-lg mx-auto">
        {/* Kartlar varken: normal orb + stack */}
        {/* Kartlar bitince: orb expanded + inbox zero text (tek orb, sahne ortası) */}
        {!feedLoading && cards.length === 0 ? (
          /* Inbox Zero: Orb sahneye iniyor */
          <div className="flex flex-col items-center">
            <AIOrb
              activeCardType={null}
              greeting="Günün tüm analizlerini inceledin!"
              subtitle="Şimdi sahne senin. Git ve o viral içeriği yaz! ✨"
              expanded
            />
          </div>
        ) : (
          <>
            <AIOrb
              activeCardType={activeCardType}
              greeting={greeting}
              subtitle={subtitle}
            />

            <div className="px-2 mb-6">
              {feedLoading ? (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-purple-400 mb-4" />
                  <p className="text-sm text-white/30">Kartların hazırlanıyor...</p>
                </div>
              ) : (
                <CardStack
                  cards={cards}
                  onDismiss={handleDismiss}
                  onAction={handleAction}
                  onActiveChange={setActiveCardType}
                />
              )}
            </div>
          </>
        )}

        {/* Mini Stats */}
        {!insightsLoading && (
          <div className="px-2 mb-8">
            <MiniStats stats={miniStats} />
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════
          ALT BÖLÜM: Geniş Bento (plan + heatmap + stats)
          ══════════════════════════════════════════════ */}
      <div className="max-w-4xl mx-auto px-4">
        {/* Bento Grid: Plan (sol, geniş) + Heatmap (sağ) */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Haftalık Plan: 3/5 genişlik */}
          <div className="lg:col-span-3">
            <WeeklyPlanSection
              plan={weeklyPlan}
              weeklyGoal={weeklyGoal}
              cached={planCached}
              createdAt={planCreatedAt}
              onGenerate={handleGeneratePlan}
              onWrite={handleWriteFromPlan}
              generating={planGenerating}
            />
          </div>

          {/* Heatmap: 2/5 genişlik */}
          <div className="lg:col-span-2">
            <div className="mb-4">
              <h2 className="font-outfit text-lg font-bold mb-4 flex items-center gap-2">
                <Clock className="h-5 w-5 text-emerald-400" />
                {t("coach.optimalPostingTimes")}
              </h2>
              <div className="rounded-xl border border-white/[0.06] bg-[#0A0A0A] p-4">
                <PostingHeatmap postingData={postingData} bestNow={bestNow} postingLoading={postingLoading} />
              </div>
            </div>
          </div>
        </div>

        {/* Detay İstatistikler (toggle) */}
        {!insightsLoading && stats.total > 0 && (
          <div className="mt-6">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-2 text-xs text-white/30 hover:text-white/50 transition-colors"
            >
              {showDetails ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              <span>{showDetails ? "Daha az göster" : "Detaylı İstatistikler"}</span>
            </button>

            <AnimatePresence>
              {showDetails && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="mt-4"
                >
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="rounded-xl border border-white/[0.06] bg-[#0A0A0A] p-4">
                      <StatBar label={t("coach.personaDistribution")} data={stats.personas} />
                    </div>
                    <div className="rounded-xl border border-white/[0.06] bg-[#0A0A0A] p-4">
                      <StatBar label={t("coach.toneDistribution")} data={stats.tones} />
                    </div>
                    <div className="rounded-xl border border-white/[0.06] bg-[#0A0A0A] p-4">
                      <StatBar label={t("coach.lengthDistribution")} data={stats.lengths} />
                    </div>
                    <div className="rounded-xl border border-white/[0.06] bg-[#0A0A0A] p-4">
                      <StatBar label={t("coach.contentType")} data={stats.types} />
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
