import { useState, useEffect, useCallback } from "react";
import { useTranslation } from 'react-i18next';
import { User, Search, BarChart3, TrendingUp, ThumbsUp, ThumbsDown, Lightbulb, Clock, MoreVertical, Trash2, RefreshCw, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import api, { API } from "@/lib/api";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip
} from "recharts";

/* ── Analysis Progress Steps ── */
const ANALYSIS_STEPS = [
  { labelKey: "account.loadingSteps.finding", pct: 10 },
  { labelKey: "account.loadingSteps.scanning", pct: 25 },
  { labelKey: "account.loadingSteps.hookAnalysis", pct: 45 },
  { labelKey: "account.loadingSteps.formatAnalysis", pct: 60 },
  { labelKey: "account.loadingSteps.emotionAnalysis", pct: 78 },
  { labelKey: "account.loadingSteps.preparing", pct: 95 },
];

/* ── Analysis Progress Overlay (Persona Lab style) ── */
function AnalysisProgressOverlay({ username, currentStep, onCancel }) {
  const { t } = useTranslation();
  const step = ANALYSIS_STEPS[Math.min(currentStep, ANALYSIS_STEPS.length - 1)];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.8)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div style={{ width: "100%", maxWidth: "420px", padding: "32px", textAlign: "center" }}>
        {/* Avatar with pulse rings */}
        <div style={{ position: "relative", display: "inline-block", marginBottom: "24px" }}>
          <div
            style={{
              width: "80px",
              height: "80px",
              borderRadius: "50%",
              overflow: "hidden",
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto",
            }}
          >
            <img
              src={`https://unavatar.io/x/${username}`}
              alt=""
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
              onError={(e) => {
                e.target.style.display = "none";
                e.target.parentElement.innerHTML = `<span style="color:white;font-size:28px;font-weight:700">@</span>`;
              }}
            />
          </div>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{ scale: [1, 1.8], opacity: [0.4, 0] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.6, ease: "easeOut" }}
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                border: "2px solid rgba(139, 92, 246, 0.4)",
              }}
            />
          ))}
        </div>

        <h3 style={{ fontSize: "18px", fontWeight: "700", color: "white", marginBottom: "4px" }}>
          @{username}
        </h3>
        <p style={{ fontSize: "13px", color: "rgba(255,255,255,0.5)", marginBottom: "28px" }}>
          {t('account.analyzing')}
        </p>

        {/* Progress bar */}
        <div
          style={{
            width: "100%",
            height: "4px",
            borderRadius: "4px",
            background: "rgba(255,255,255,0.08)",
            marginBottom: "16px",
            overflow: "hidden",
          }}
        >
          <motion.div
            animate={{ width: `${step.pct}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{
              height: "100%",
              borderRadius: "4px",
              background: "linear-gradient(90deg, #7c3aed, #a855f7, #c084fc)",
            }}
          />
        </div>

        {/* Step label with animation */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
          >
            <div style={{ fontSize: "14px", fontWeight: "600", color: "#a78bfa", marginBottom: "4px" }}>
              {t(step.labelKey, { username })}
            </div>
          </motion.div>
        </AnimatePresence>

        <p style={{ fontSize: "12px", color: "rgba(255,255,255,0.3)", marginTop: "12px" }}>
          {t('account.processingTime')}
        </p>

        {/* Cancel */}
        <button
          onClick={onCancel}
          style={{
            marginTop: "20px",
            padding: "8px 20px",
            borderRadius: "8px",
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "rgba(255,255,255,0.4)",
            fontSize: "12px",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.1)";
            e.currentTarget.style.color = "rgba(255,255,255,0.7)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.06)";
            e.currentTarget.style.color = "rgba(255,255,255,0.4)";
          }}
        >
          {t('common.cancel') || 'İptal'}
        </button>
      </div>
    </motion.div>
  );
}


function DimensionRadar({ dimensions, dimensionDetails }) {
  const { t } = useTranslation();
  if (!dimensions) return null;
  const data = [
    { subject: t('account.dimensions.hookPower'), value: dimensions.hook_power || 0, key: 'hook_power' },
    { subject: t('account.dimensions.engagement'), value: dimensions.engagement_potential || 0, key: 'engagement_potential' },
    { subject: t('account.dimensions.formatDiversity'), value: dimensions.format_diversity || 0, key: 'format_diversity' },
    { subject: t('account.dimensions.emotionalRange'), value: dimensions.emotional_range || 0, key: 'emotional_range' },
    { subject: t('account.dimensions.visualUsage'), value: dimensions.visual_usage || 0, key: 'visual_usage' },
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    const detail = dimensionDetails?.[d.key];
    return (
      <div className="bg-[#1A1A1A] border border-white/10 rounded-xl px-4 py-3 max-w-[280px] shadow-2xl">
        <p className="text-sm font-semibold text-white">{d.subject}</p>
        <p className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-fuchsia-400 bg-clip-text text-transparent">{d.value}/100</p>
        {detail && <p className="text-xs text-white/60 mt-1 leading-relaxed">{detail}</p>}
      </div>
    );
  };

  return (
    <div className="h-[320px] w-full" style={{ filter: "drop-shadow(0 0 8px rgba(168,85,247,0.15))" }}>
      <ResponsiveContainer>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="75%">
          <PolarGrid stroke="rgba(255,255,255,0.08)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: "rgba(255,255,255,0.6)", fontSize: 11, fontWeight: 500 }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 10 }}
            axisLine={false}
          />
          <Radar
            name="Skor"
            dataKey="value"
            stroke="#a855f7"
            fill="url(#radarGradient)"
            fillOpacity={0.3}
            strokeWidth={2.5}
            dot={{ r: 4, fill: "#a855f7", strokeWidth: 0 }}
          />
          <Tooltip content={<CustomTooltip />} />
          <defs>
            <linearGradient id="radarGradient" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#a855f7" />
              <stop offset="100%" stopColor="#d946ef" />
            </linearGradient>
          </defs>
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function PostingHeatmap({ heatmap }) {
  const { t } = useTranslation();
  if (!heatmap || !Array.isArray(heatmap)) return null;
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const days = t('coach.shortDays', { returnObjects: true });

  // Normalize
  let max = 0;
  heatmap.forEach(day => {
    if (day.hours) {
      Object.values(day.hours).forEach(v => { if (v > max) max = v; });
    }
  });

  return (
    <div className="overflow-x-auto">
      <div className="grid gap-0.5" style={{ gridTemplateColumns: `60px repeat(24, 1fr)` }}>
        <div />
        {hours.map(h => (
          <div key={h} className="text-[10px] text-muted-foreground text-center">{h}</div>
        ))}
        {heatmap.slice(0, 7).map((day, di) => (
          <>
            <div key={`label-${di}`} className="text-xs text-muted-foreground flex items-center">
              {days[di] || day.day?.substring(0, 3)}
            </div>
            {hours.map(h => {
              const count = day.hours?.[String(h)] || 0;
              const intensity = max > 0 ? count / max : 0;
              return (
                <div
                  key={`${di}-${h}`}
                  className="aspect-square rounded-sm"
                  style={{
                    backgroundColor: intensity > 0
                      ? `rgba(59, 130, 246, ${0.15 + intensity * 0.85})`
                      : "hsl(var(--secondary))",
                  }}
                  title={`${days[di] || day.day} ${h}:00 - ${count} tweet`}
                />
              );
            })}
          </>
        ))}
      </div>
    </div>
  );
}

function InfoCard({ title, items, icon: Icon, color }) {
  const colorMap = {
    green: "border-green-500/30 bg-green-500/5",
    red: "border-red-500/30 bg-red-500/5",
    blue: "border-blue-500/30 bg-blue-500/5",
  };

  const titleColor = {
    green: "text-green-400",
    red: "text-red-400",
    blue: "text-blue-400",
  };

  return (
    <div className={cn("rounded-xl border p-4", colorMap[color])}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className={cn("h-5 w-5", titleColor[color])} />
        <h4 className={cn("font-semibold", titleColor[color])}>{title}</h4>
      </div>
      <div className="space-y-2">
        {items?.map((item, i) => (
          <div key={i}>
            <p className="text-sm font-medium">{item.title}</p>
            <p className="text-xs text-muted-foreground">{item.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopTweet({ tweet, index }) {
  return (
    <div className="p-3 rounded-lg bg-secondary/50 border border-border">
      <div className="flex items-start gap-2">
        <span className="text-xs font-bold text-muted-foreground">#{index + 1}</span>
        <div className="flex-1">
          <p className="text-sm">{tweet.content?.substring(0, 200)}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
            <span>❤️ {tweet.likes || 0}</span>
            <span>🔁 {tweet.retweets || 0}</span>
            <span>💬 {tweet.replies || 0}</span>
          </div>
          {tweet.why_good && (
            <p className="text-xs text-blue-400 mt-1">💡 {tweet.why_good}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AccountAnalysisPage() {
  const { t } = useTranslation();
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [analysisUsername, setAnalysisUsername] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [openMenuId, setOpenMenuId] = useState(null);

  const fetchHistory = useCallback(async (append = false) => {
    if (!append) setHistoryLoading(true);
    setHistoryError(false);
    try {
      const offset = append ? history.length : 0;
      const res = await api.get(`${API}/analyze/history`, { params: { limit: 20, offset } });
      const data = res.data.analyses || [];
      setHistory(prev => append ? [...prev, ...data] : data);
      setHasMore(res.data.has_more || false);
    } catch (err) {
      setHistoryError(true);
    } finally {
      setHistoryLoading(false);
    }
  }, [history.length]);

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = async (id) => {
    if (!window.confirm("Bu analizi geçmişten silmek istediğine emin misin?")) return;
    try {
      await api.delete(`${API}/analyze/history/${id}`);
      setHistory(prev => prev.filter(h => h.id !== id));
      toast.success("Silindi");
    } catch {
      toast.error("Silinemedi");
    }
  };

  const handleViewDetail = async (item) => {
    try {
      const res = await api.get(`${API}/analyze/history/${item.id}`);
      setResult({
        success: true,
        username: res.data.twitter_username,
        display_name: res.data.display_name,
        followers: res.data.followers_count,
        bio: res.data.bio,
        tweets_analyzed: res.data.tweet_count,
        tweet_count_analyzed: res.data.tweet_count,
        analysis: res.data.analysis,
      });
      setUsername(res.data.twitter_username);
    } catch {
      toast.error("Rapor yüklenemedi");
    }
  };

  const handleAnalyze = async () => {
    if (!username.trim()) {
      toast.error(t('account.emptyUsername'));
      return;
    }
    setLoading(true);
    setResult(null);
    setAnalysisStep(0);
    setAnalysisUsername(username.replace("@", ""));

    try {
      const stepTimers = [
        setTimeout(() => setAnalysisStep(1), 5000),
        setTimeout(() => setAnalysisStep(2), 10000),
        setTimeout(() => setAnalysisStep(3), 15000),
        setTimeout(() => setAnalysisStep(4), 20000),
        setTimeout(() => setAnalysisStep(5), 25000),
      ];

      const res = await api.post(`${API}/analyze/account`, {
        twitter_username: username.replace("@", ""),
      });

      stepTimers.forEach(clearTimeout);
      if (res.data.success) {
        setResult(res.data);
        toast.success(t('account.analysisComplete'));
        fetchHistory();
      } else {
        toast.error(res.data.error || t('account.analysisError'));
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || t('account.analysisError'));
    } finally {
      setLoading(false);
      setAnalysisStep(0);
    }
  };

  const analysis = result?.analysis;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20">
          <BarChart3 className="h-6 w-6 text-blue-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            {t('account.title')}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('account.subtitle')}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="flex gap-3 mb-8">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder={t('account.placeholder')}
            className="w-full pl-10 pr-4 py-3 rounded-xl border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
        </div>
        <Button
          onClick={handleAnalyze}
          disabled={loading}
          className="px-6 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white"
        >
          {loading ? t('account.analyzing') : t('account.analyze')}
        </Button>
      </div>

      {/* Loading Overlay (Persona Lab style) */}
      <AnimatePresence>
        {loading && analysisUsername && (
          <AnalysisProgressOverlay
            username={analysisUsername}
            currentStep={analysisStep}
            onCancel={() => setLoading(false)}
          />
        )}
      </AnimatePresence>

      {/* Results */}
      {!loading && analysis && (
        <div className="space-y-6 pb-16">
          {/* Back to history */}
          <button
            onClick={() => setResult(null)}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            <span>←</span> {t('account.previousAnalyses')}
          </button>

          {/* Score Header */}
          <div className="flex items-center justify-between p-6 rounded-xl border border-border bg-card">
            <div className="flex items-center gap-4">
              <div className="relative h-16 w-16 shrink-0">
                <img
                  src={result.avatar_url || `https://unavatar.io/x/${result.username}`}
                  alt={`@${result.username}`}
                  className="h-16 w-16 rounded-full object-cover ring-2 ring-purple-500/30"
                  onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
                />
                <div className="h-16 w-16 rounded-full bg-gradient-to-br from-purple-500 to-fuchsia-500 items-center justify-center text-2xl font-bold text-white" style={{ display: 'none' }}>
                  {(result.username || '?').charAt(0).toUpperCase()}
                </div>
              </div>
              <div>
                <h2 className="text-xl font-bold">@{result.username}</h2>
                <p className="text-sm text-muted-foreground">
                  {t('account.tweetsAnalyzed', { count: result.tweets_analyzed || result.tweet_count_analyzed })}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">{t('account.overallScore')}</p>
              <p className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-fuchsia-500 bg-clip-text text-transparent">
                {analysis.overall_score || 0}/100
              </p>
            </div>
          </div>

          {/* Radar + Tone */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-purple-500" />
                {t('account.performanceDimensions')}
              </h3>
              <DimensionRadar dimensions={analysis.dimensions} dimensionDetails={analysis.dimension_details} />
            </div>

            <div className="space-y-4">
              {/* Tone */}
              {analysis.tone_analysis && (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h3 className="font-semibold mb-2">{t('account.toneAnalysis')}</h3>
                  <p className="text-sm text-muted-foreground">{analysis.tone_analysis}</p>
                </div>
              )}

              {/* Posting Frequency */}
              {analysis.posting_frequency && (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h3 className="font-semibold mb-2 flex items-center gap-2">
                    <Clock className="h-4 w-4 text-blue-500" />
                    {t('account.postingFrequency')}
                  </h3>
                  <p className="text-sm text-muted-foreground">{analysis.posting_frequency}</p>
                </div>
              )}

              {/* Hashtag Strategy */}
              {analysis.hashtag_strategy && (
                <div className="rounded-xl border border-border bg-card p-6">
                  <h3 className="font-semibold mb-2">{t('account.hashtagStrategy')}</h3>
                  <p className="text-sm text-muted-foreground">{analysis.hashtag_strategy}</p>
                </div>
              )}

              {/* Growth Tips */}
              {analysis.growth_tips && (
                <div className="rounded-xl border border-border bg-card p-6 bg-gradient-to-br from-blue-500/5 to-purple-500/5">
                  <h3 className="font-semibold mb-2">{t('account.growthStrategy')}</h3>
                  <p className="text-sm text-muted-foreground">{analysis.growth_tips}</p>
                </div>
              )}
            </div>
          </div>

          {/* Strengths / Weaknesses / Recommendations */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <InfoCard
              title={t('account.strengths')}
              items={analysis.strengths}
              icon={ThumbsUp}
              color="green"
            />
            <InfoCard
              title={t('account.weaknesses')}
              items={analysis.weaknesses}
              icon={ThumbsDown}
              color="red"
            />
            <InfoCard
              title={t('account.recommendations')}
              items={analysis.recommendations}
              icon={Lightbulb}
              color="blue"
            />
          </div>

          {/* Posting Heatmap */}
          {analysis.posting_heatmap && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="font-semibold mb-4">{t('account.postingHeatmap')}</h3>
              <PostingHeatmap heatmap={analysis.posting_heatmap} />
            </div>
          )}

          {/* Top Tweets */}
          {analysis.top_tweets && analysis.top_tweets.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-6">
              <h3 className="font-semibold mb-4">{t('account.topTweets')}</h3>
              <div className="space-y-3">
                {analysis.top_tweets.map((tweet, i) => (
                  <TopTweet key={i} tweet={tweet} index={i} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {!loading && !result && (
        <div className="mt-8">
          <h3 className="font-semibold mb-4 text-muted-foreground">{t('account.previousAnalyses')}</h3>

          {/* Loading */}
          {historyLoading && history.length === 0 && (
            <div className="space-y-3">
              {[1,2,3].map(i => (
                <div key={i} className="p-4 rounded-xl border border-border bg-card animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-secondary" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-32 bg-secondary rounded" />
                      <div className="h-3 w-48 bg-secondary rounded" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error */}
          {historyError && history.length === 0 && (
            <div className="text-center py-12">
              <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground mb-3">Geçmiş yüklenemedi</p>
              <Button variant="outline" size="sm" onClick={() => fetchHistory()}>
                <RefreshCw className="h-4 w-4 mr-2" /> Tekrar Dene
              </Button>
            </div>
          )}

          {/* Empty */}
          {!historyLoading && !historyError && history.length === 0 && (
            <div className="text-center py-12">
              <Search className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">Henüz bir hesap analiz edilmedi</p>
              <p className="text-xs text-muted-foreground/60 mt-1">Yukarıdan bir kullanıcı adı girerek başla</p>
            </div>
          )}

          {/* List */}
          {history.length > 0 && (
            <div className="space-y-2">
              {history.map((item) => (
                <div
                  key={item.id}
                  onClick={() => handleViewDetail(item)}
                  className="p-4 rounded-xl border border-border bg-card hover:border-blue-500/30 transition-all cursor-pointer group relative"
                >
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <img
                      src={item.avatar_url || `https://unavatar.io/x/${item.twitter_username}`}
                      alt=""
                      className="h-10 w-10 rounded-full object-cover shrink-0"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                    />
                    <div
                      className="h-10 w-10 rounded-full bg-blue-500/20 items-center justify-center shrink-0 text-blue-400 font-bold text-sm"
                      style={{ display: 'none' }}
                    >
                      {(item.display_name || item.twitter_username || '?').charAt(0).toUpperCase()}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">@{item.twitter_username}</span>
                        {item.display_name && (
                          <span className="text-xs text-muted-foreground truncate">{item.display_name}</span>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {item.tweet_count} tweet
                        {item.followers_count > 0 && ` · ${item.followers_count.toLocaleString()} takipçi`}
                        {' · '}
                        {new Date(item.updated_at || item.created_at).toLocaleDateString("tr-TR", {
                          day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
                        })}
                      </p>
                    </div>

                    {/* Score */}
                    <div className="text-right shrink-0">
                      <span className={cn(
                        "text-lg font-bold",
                        (item.overall_score || 0) >= 70 ? "text-green-400" :
                        (item.overall_score || 0) >= 50 ? "text-yellow-400" : "text-red-400"
                      )}>
                        {item.overall_score || 0}
                      </span>
                      <span className="text-xs text-muted-foreground">/100</span>
                    </div>

                    {/* Menu */}
                    <div className="relative shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(openMenuId === item.id ? null : item.id);
                        }}
                        className="h-8 w-8 flex items-center justify-center rounded-lg opacity-0 group-hover:opacity-100 hover:bg-secondary transition-all"
                      >
                        <MoreVertical className="h-4 w-4 text-muted-foreground" />
                      </button>
                      {openMenuId === item.id && (
                        <div className="absolute right-0 top-9 z-50 bg-card border border-border rounded-lg shadow-xl py-1 min-w-[140px]">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(item.id);
                              setOpenMenuId(null);
                            }}
                            className="w-full px-3 py-2 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Geçmişten sil
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Load More */}
              {hasMore && (
                <div className="text-center pt-2">
                  <Button variant="outline" size="sm" onClick={() => fetchHistory(true)}>
                    Daha fazla yükle
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
