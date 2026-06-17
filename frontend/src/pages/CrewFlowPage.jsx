import { useState, useEffect, useRef, useCallback } from "react";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAccount } from "@/contexts/AccountContext";
import { listRecentRuns, getRunFlow } from "@/services/hypeService";
import RunList from "@/components/crew-flow/RunList";
import CrewGraph from "@/components/crew-flow/CrewGraph";
import TrustStrip from "@/components/crew-flow/TrustStrip";
import DetailPanel from "@/components/crew-flow/DetailPanel";

/* Crew Akışı — bir run'ın 7 aşamalı pipeline görünümü (mockup v2.1).
   Sol: son run listesi. Sağ: header → güven şeridi → pipeline rail → detay. */

const DASH = "—";

function fmtTime(iso) {
  if (!iso) return DASH;
  try {
    return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return DASH;
  }
}

function fmtDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return DASH;
  const sec = Math.round(n / 1000);
  if (sec < 60) return `${sec} sn`;
  return `${Math.floor(sec / 60)} dk ${sec % 60} sn`;
}

function fmtTokens(total) {
  const n = Number(total);
  if (!Number.isFinite(n) || n <= 0) return DASH;
  if (n >= 1000) return `~${Math.round(n / 1000)}k token`;
  return `~${n} token`;
}

export default function CrewFlowPage() {
  const { activeAccountId } = useAccount();

  const [runs, setRuns] = useState([]);
  const [runsError, setRunsError] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);

  const [flow, setFlow] = useState(null);
  const [flowError, setFlowError] = useState(null);
  const [flowLoading, setFlowLoading] = useState(false);

  const [selectedNodeKey, setSelectedNodeKey] = useState(null);
  const [selectedCard, setSelectedCard] = useState(0);   // kart run'ında hangi kart
  const railRef = useRef(null);

  /* Run listesi */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setRunsError(null);
        const data = await listRecentRuns({ accountId: activeAccountId, limit: 20 });
        if (cancelled) return;
        const items = Array.isArray(data?.items) ? data.items : [];
        setRuns(items);
        setSelectedRunId((prev) => prev ?? items[0]?.id ?? null);
      } catch (e) {
        if (!cancelled) setRunsError(e?.message || "hata");
      }
    })();
    return () => { cancelled = true; };
  }, [activeAccountId]);

  /* Seçili run'ın flow'u */
  const loadFlow = useCallback(async (runId, { initial = false } = {}) => {
    if (!runId) return;
    try {
      if (initial) setFlowLoading(true);
      setFlowError(null);
      const data = await getRunFlow(runId);
      setFlow(data || null);
      if (initial) {
        setSelectedNodeKey(data?.default_selected_node || "writer");
      }
    } catch (e) {
      setFlowError(e?.message || "hata");
      if (initial) setFlow(null);
    } finally {
      if (initial) setFlowLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedRunId) return;
    let cancelled = false;
    (async () => {
      if (!cancelled) await loadFlow(selectedRunId, { initial: true });
    })();
    return () => { cancelled = true; };
  }, [selectedRunId, loadFlow]);

  /* running iken 5 sn'de bir yenile */
  useEffect(() => {
    if (!selectedRunId || flow?.run?.status !== "running") return undefined;
    const timer = setInterval(() => loadFlow(selectedRunId), 5000);
    return () => clearInterval(timer);
  }, [selectedRunId, flow?.run?.status, loadFlow]);

  const handleSelectRun = (runId) => {
    if (!runId || runId === selectedRunId) return;
    setSelectedCard(0);            // yeni run → ilk karta dön
    setSelectedRunId(runId);
  };

  const handleTrustSelect = (nodeKey) => {
    setSelectedNodeKey(nodeKey);
    railRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const run = flow?.run || null;
  const trend = run?.trend || null;
  const isCards = run?.run_kind === "cards";
  const cards = Array.isArray(flow?.cards) ? flow.cards : [];
  // Kart run'ında rail seçili kartın node'larını gösterir; yoksa haber node'ları.
  const cardIdx = Math.min(selectedCard, Math.max(0, cards.length - 1));
  const nodes = isCards && cards.length
    ? (cards[cardIdx]?.nodes || [])
    : (Array.isArray(flow?.nodes) ? flow.nodes : []);
  // Kart run'ında fan-out yalnızca SEÇİLİ kartın platformlarını gösterir
  // (run'ın tüm draftları = çok kartlı → her platform tekrarlanır). Seçili kartın
  // publish node output'unda platforms + status zaten var.
  const drafts = (() => {
    if (isCards && cards.length) {
      const pub = (cards[cardIdx]?.nodes || []).find((n) => n?.key === "publish");
      const out = pub?.output;
      const plats = Array.isArray(out?.platforms) ? out.platforms : [];
      return plats.map((p, i) => ({
        id: `c${cardIdx}_${p}_${i}`,
        platform: p,
        status: out?.status,
        postiz_post_id: out?.postiz_post_id ?? null,
        scheduled_at: out?.scheduled_at ?? null,
      }));
    }
    return Array.isArray(flow?.drafts) ? flow.drafts : [];
  })();
  const trust = flow?.trust_signals || null;
  const selectedNode = nodes.find((n) => n?.key === selectedNodeKey) || null;
  const anomaly = trust?.cost_anomaly || null;
  const headerTitle = isCards
    ? (run?.card_source === "companion"
        ? `SÖZLÜK + SENCE? kartları${trend?.topic ? ` ↳ ${trend.topic}` : ""}`
        : "SÖZLÜK + SENCE? kartları · kurak gün")
    : (trend?.topic || DASH);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Crew Akışı</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Her run'ın aşama aşama nasıl ilerlediğini izleyin.
        </p>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-4 items-start">
        {/* Sol — run listesi */}
        <RunList
          runs={runs}
          selectedId={selectedRunId}
          onSelect={handleSelectRun}
          error={runsError}
        />

        {/* Sağ kolon */}
        <div className="space-y-3 min-w-0">
          {flowError && (
            <p className="text-xs text-rose-400/90">
              Run detayı yüklenemedi. Birazdan tekrar deneyin.
            </p>
          )}
          {flowLoading && !flow && (
            <p className="text-xs text-muted-foreground">Yükleniyor…</p>
          )}

          {flow && (
            <>
              {/* Header */}
              <div className="rounded-2xl bg-card/80 border border-border/40 px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground/95 truncate">
                    {isCards && (
                      <span className="mr-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/15 border border-purple-500/40 text-purple-300 align-middle">
                        KART
                      </span>
                    )}
                    {headerTitle}
                    {trend?.url && (
                      <a
                        href={trend.url}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-2 text-[11px] font-normal text-purple-400 hover:underline inline-flex items-center gap-0.5 align-middle"
                      >
                        kaynak <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </p>
                  <p className="text-[11px] font-mono text-muted-foreground mt-0.5">
                    {fmtTime(run?.started_at)} → {fmtTime(run?.completed_at)} ·{" "}
                    {fmtDuration(run?.duration_ms)}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={cn(
                      "text-[11px] font-mono px-2 py-1 rounded-lg border",
                      anomaly
                        ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                        : "border-border/40 text-foreground/80"
                    )}
                  >
                    {run?.total_cost_usd != null
                      ? `$${Number(run.total_cost_usd).toFixed(2)}`
                      : DASH}
                    {anomaly?.ratio != null && (
                      <span className="ml-1">{Number(anomaly.ratio).toFixed(1)}x medyan</span>
                    )}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-1 rounded-lg border border-border/40 text-foreground/80">
                    {fmtTokens(run?.total_tokens)}
                  </span>
                </div>
              </div>

              {/* Güven şeridi */}
              <TrustStrip trust={trust} onSelectNode={handleTrustSelect} />

              {/* Kart seçici (kart run'ında birden fazla kart) */}
              {isCards && cards.length > 1 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] text-muted-foreground">Kart:</span>
                  {cards.map((c, i) => (
                    <button
                      key={c?.index ?? i}
                      type="button"
                      onClick={() => setSelectedCard(i)}
                      className={cn(
                        "text-[11px] px-2 py-1 rounded-lg border transition",
                        i === cardIdx
                          ? "border-purple-500/90 bg-purple-500/10 text-purple-200"
                          : "border-border/40 text-foreground/70 hover:border-purple-500/50"
                      )}
                    >
                      {i + 1}/{cards.length} · {c?.kind === "dictionary" ? "SÖZLÜK" : c?.kind === "question" ? "SENCE?" : "kart"}
                    </button>
                  ))}
                </div>
              )}

              {/* n8n-tarzı akış grafiği */}
              <div ref={railRef}>
                <CrewGraph
                  nodes={nodes}
                  drafts={drafts}
                  run={run}
                  selectedKey={selectedNodeKey}
                  onSelect={setSelectedNodeKey}
                />
              </div>

              {run?.error && (
                <p className="text-[11px] text-rose-400/90 break-words">
                  Run hatası: {run.error}
                </p>
              )}

              {/* Detay paneli */}
              <DetailPanel
                node={selectedNode}
                nodes={nodes}
                drafts={drafts}
                trust={trust}
              />
            </>
          )}

          {!flow && !flowLoading && !flowError && (
            <p className="text-xs text-muted-foreground">
              Soldan bir run seçin.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
