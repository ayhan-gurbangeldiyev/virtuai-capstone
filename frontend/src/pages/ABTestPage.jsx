import { useState, useCallback, useRef, useMemo } from "react";
import { useTranslation } from 'react-i18next';
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, RotateCcw, Check, Trophy, Award } from "lucide-react";

// ══════════════════════════════════════════
// CONFIG — 3 mode: RAG, No RAG, User Style
// ══════════════════════════════════════════

const MODES = {
  beatstobytes: { id: "beatstobytes", labelKey: "abTest.modes.beatstobytes", color: "violet", forceRag: "beatstobytes" },
  none:         { id: "none",         labelKey: "abTest.modes.none",         color: "blue",   forceRag: "none" },
  user_style:   { id: "user_style",   labelKey: "abTest.modes.userStyle",    color: "amber",  forceRag: "user_style" },
};

const MODE_KEYS = Object.keys(MODES);
const MIN_TESTS = 10;
const STORAGE_KEY = "ab_shitpost_3way_results";

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ══════════════════════════════════════════
// COMPONENTS
// ══════════════════════════════════════════

function VariantTabs({ variants, activeIdx, onSelect }) {
  if (!variants || variants.length <= 1) return null;
  return (
    <div className="flex gap-1 mb-3">
      {variants.map((_, i) => (
        <button
          key={i}
          onClick={() => onSelect(i)}
          className={`px-3 py-1 text-xs rounded-md transition-colors ${
            i === activeIdx ? "bg-white/20 text-white" : "bg-white/5 text-white/50 hover:text-white/70"
          }`}
        >
          #{i + 1}
        </button>
      ))}
    </div>
  );
}

function ColumnCard({ label, variants, loading, selected, onSelect, revealed, modeLabel, colorClass }) {
  const { t } = useTranslation();
  const [activeIdx, setActiveIdx] = useState(0);
  const currentVariant = variants?.[activeIdx];

  const borderClass = revealed
    ? selected
      ? "border-green-500 ring-2 ring-green-500/30 bg-green-500/5"
      : "border-white/5 bg-white/[0.02] opacity-60"
    : "border-white/10";

  return (
    <Card className={`flex-1 p-5 bg-[#111] border transition-all duration-500 ${borderClass}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{label}</h3>
        <div className="flex items-center gap-2">
          {revealed && (
            <Badge className={`text-xs ${colorClass}`}>
              {modeLabel}
            </Badge>
          )}
          {revealed && selected && <Trophy className="w-4 h-4 text-yellow-400" />}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-white/40">
          <Loader2 className="w-6 h-6 animate-spin mr-2" />
          {t('abTest.generating')}
        </div>
      ) : variants ? (
        <>
          <VariantTabs variants={variants} activeIdx={activeIdx} onSelect={setActiveIdx} />
          <div className="bg-[#0A0A0A] rounded-lg p-4 min-h-[120px] text-white/90 text-sm leading-relaxed whitespace-pre-wrap mb-4">
            {currentVariant || "(boş)"}
          </div>
          {!revealed && (
            <Button
              variant="outline"
              className="w-full border-white/20 text-white hover:bg-white/10"
              onClick={onSelect}
            >
              <Check className="w-4 h-4 mr-2" />
              {t('abTest.thisBetter')}
            </Button>
          )}
        </>
      ) : (
        <div className="flex items-center justify-center py-16 text-white/20 text-sm">
          {t('abTest.notGenerated')}
        </div>
      )}
    </Card>
  );
}

function saveResult(result) {
  try {
    const existing = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    existing.push(result);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
  } catch (e) { /* ignore */ }
}

function getResults() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); } catch { return []; }
}

const COLOR_MAP = {
  beatstobytes: "bg-violet-500/20 text-violet-400 border-violet-500/30",
  none: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  user_style: "bg-amber-500/20 text-amber-400 border-amber-500/30",
};

const LABEL_KEYS = ["abTest.left", "abTest.center", "abTest.right"];

// ══════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════

export default function ABTestPage() {
  const { t } = useTranslation();
  const [topic, setTopic] = useState("");
  const [variantCount, setVariantCount] = useState(3);
  const [cols, setCols] = useState([
    { loading: false, variants: null },
    { loading: false, variants: null },
    { loading: false, variants: null },
  ]);
  const [winner, setWinner] = useState(null);
  const [revealed, setRevealed] = useState(false);

  const orderRef = useRef(MODE_KEYS); // shuffled each round

  const generate = useCallback(async () => {
    if (!topic.trim()) return;
    setWinner(null);
    setRevealed(false);
    setCols([
      { loading: true, variants: null },
      { loading: true, variants: null },
      { loading: true, variants: null },
    ]);

    // Randomize order
    const order = shuffle(MODE_KEYS);
    orderRef.current = order;

    const fetchMode = async (modeKey) => {
      const mode = MODES[modeKey];
      try {
        const res = await api.post(`/v2/generate/tweet?engine=v3&force_model=shitpost&force_rag=${mode.forceRag}`, {
          topic: topic.trim(),
          etki: "shitpost",
          yapi: "dogal",
          acilis: "otomatik",
          bitis: "dogal",
          derinlik: "standart",
          language: "auto",
          is_ultra: false,
          variants: variantCount,
        });
        const data = res.data;
        if (data.variants && Array.isArray(data.variants)) {
          return data.variants.map((v) => (typeof v === "string" ? v : v.text || v.content || JSON.stringify(v)));
        }
        if (data.content) return [data.content];
        return [JSON.stringify(data, null, 2)];
      } catch (err) {
        return [`Hata: ${err.response?.data?.detail || err.message}`];
      }
    };

    const results = await Promise.allSettled(order.map(fetchMode));
    setCols(results.map(r => ({
      loading: false,
      variants: r.status === "fulfilled" ? r.value : [`Hata: ${r.reason}`],
    })));
  }, [topic, variantCount]);

  const selectWinner = (colIdx) => {
    setWinner(colIdx);
    setRevealed(true);
    const winnerMode = orderRef.current[colIdx];
    saveResult({
      timestamp: new Date().toISOString(),
      topic,
      winner: winnerMode,
      losers: orderRef.current.filter((_, i) => i !== colIdx),
    });
  };

  const results = getResults();
  const wins = {};
  MODE_KEYS.forEach(k => { wins[k] = results.filter(r => r.winner === k).length; });
  const totalTests = results.length;

  const topMode = MODE_KEYS.reduce((a, b) => (wins[a] >= wins[b] ? a : b));
  const topPct = totalTests > 0 ? Math.round((wins[topMode] / totalTests) * 100) : 0;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white">
      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold mb-1">{t('abTest.title')}</h1>
          <p className="text-white/40 text-sm">{t('abTest.subtitle')}</p>
        </div>

        {/* Scoreboard */}
        <Card className="p-4 mb-6 bg-[#111] border-white/10">
          <div className="flex items-center gap-6 flex-wrap">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{totalTests}</div>
              <div className="text-xs text-white/40">{t('abTest.total')}</div>
            </div>
            <div className="w-px h-10 bg-white/10" />
            {MODE_KEYS.map(k => (
              <div key={k} className="text-center">
                <div className={`text-2xl font-bold ${k === "beatstobytes" ? "text-violet-400" : k === "none" ? "text-blue-400" : "text-amber-400"}`}>
                  {wins[k]}
                </div>
                <div className="text-xs text-white/40">{t(MODES[k].labelKey)}</div>
              </div>
            ))}
            {totalTests > 0 && (
              <>
                <div className="w-px h-10 bg-white/10" />
                <div className="flex-1 min-w-[200px]">
                  <div className="flex h-3 rounded-full overflow-hidden bg-white/5">
                    {MODE_KEYS.map(k => (
                      <div
                        key={k}
                        className={`transition-all ${k === "beatstobytes" ? "bg-violet-500" : k === "none" ? "bg-blue-500" : "bg-amber-500"}`}
                        style={{ width: `${totalTests > 0 ? (wins[k] / totalTests) * 100 : 0}%` }}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}
            {totalTests > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => { if (confirm(t('abTest.resetConfirm'))) { localStorage.removeItem(STORAGE_KEY); window.location.reload(); } }}
                className="text-red-400/60 hover:text-red-400 text-xs"
              >
                {t('abTest.reset')}
              </Button>
            )}
          </div>

          {totalTests >= MIN_TESTS && (
            <div className="mt-4 p-3 rounded-lg text-sm bg-green-500/10 border border-green-500/20 text-green-400">
              <Award className="w-4 h-4 inline mr-2" />
              <strong>{t('abTest.leader')}:</strong> {t(MODES[topMode].labelKey)} ({topPct}%, {wins[topMode]}/{totalTests})
            </div>
          )}
          {totalTests > 0 && totalTests < MIN_TESTS && (
            <div className="mt-4 p-3 rounded-lg text-sm bg-white/5 border border-white/10 text-white/50">
              📊 {t('abTest.moreTestsNeeded', { count: MIN_TESTS - totalTests })} ({totalTests}/{MIN_TESTS})
            </div>
          )}
        </Card>

        {/* Input */}
        <div className="space-y-4 mb-8">
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder={t('abTest.topicPlaceholder')}
            rows={2}
            className="w-full bg-[#141414] border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:ring-1 focus:ring-white/20 resize-none"
          />

          <div className="flex items-center gap-4">
            <div>
              <div className="text-xs text-white/30 mb-1.5">{t('abTest.variantLabel')}</div>
              <div className="flex gap-1">
                {[1, 2, 3].map(n => (
                  <button
                    key={n}
                    onClick={() => setVariantCount(n)}
                    className={`w-7 h-7 rounded-md text-xs transition-colors ${
                      variantCount === n ? "bg-white text-black font-medium" : "bg-white/5 text-white/50 hover:bg-white/10"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3 ml-auto">
              <Button
                onClick={generate}
                disabled={!topic.trim() || cols[0].loading}
                className="bg-white text-black hover:bg-white/90 px-8 font-medium"
              >
                {cols[0].loading ? (
                  <><Loader2 className="w-4 h-4 animate-spin mr-2" /> {t('abTest.generating')}</>
                ) : (
                  t('abTest.generateAndCompare')
                )}
              </Button>
              {cols[0].variants && !cols[0].loading && (
                <Button variant="outline" onClick={generate} className="border-white/20 text-white hover:bg-white/10">
                  <RotateCcw className="w-4 h-4 mr-2" /> {t('abTest.retry')}
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Reveal */}
        {revealed && winner !== null && (
          <div className="mb-4 p-4 rounded-xl bg-gradient-to-r from-green-500/10 via-green-500/5 to-transparent border border-green-500/20">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                <Trophy className="w-5 h-5 text-yellow-400" />
              </div>
              <div>
                <div className="text-green-400 font-semibold">

                  {t('abTest.won', { label: t(LABEL_KEYS[winner]) })} → <span className="text-white text-lg">{t(MODES[orderRef.current[winner]].labelKey)}</span>
                </div>
                <div className="text-white/40 text-xs mt-0.5">
                  {orderRef.current.map((k, i) => `${t(LABEL_KEYS[i])} = ${t(MODES[k].labelKey)}`).join(" · ")}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3 Columns */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[0, 1, 2].map(i => (
            <ColumnCard
              key={i}
              label={`${t(LABEL_KEYS[i])} ◼`}
              variants={cols[i].variants}
              loading={cols[i].loading}
              selected={winner === i}
              onSelect={() => winner === null && selectWinner(i)}
              revealed={revealed}
              modeLabel={MODES[orderRef.current[i]]?.labelKey ? t(MODES[orderRef.current[i]].labelKey) : ""}
              colorClass={COLOR_MAP[orderRef.current[i]] || ""}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
