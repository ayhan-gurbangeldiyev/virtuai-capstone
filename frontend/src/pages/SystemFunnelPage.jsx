/**
 * @deprecated KULLANILMIYOR (2026-06-14) — route + nav kaldırıldı, sitede erişilemez.
 * Referans için tutuluyor; aktif uygulama akışının parçası DEĞİL. Bkz: docs/DEPRECATED_MODULES.md
 */
/**
 * /dashboard/sistem — Sistem Sağlığı + Huni (teknik tanı paneli).
 *
 * "Sistem çalışıyor mu, nerede tıkandı" tek bakışta: bottleneck hero + Kaynaklar
 * (supply + "Şimdi trend çek") + Huni + Son Çalıştırma + Cron.
 *
 * Görsel dil = SystemHealthPage (dashboard koyu kart tarzı: rounded-2xl border
 * bg-card, ikon başlık, Badge + toneClasses, progress bar). Dashboard dark
 * temasında render edilir → shadcn token'ları doğru/zengin çözülür.
 *
 * Veri: GET /hype/funnel-health (fail-open). Buton: POST /hype/trend-fetch/trigger
 * — DB-kalıcı gerçek durum gösterir (Çalışıyor…/✓ N trend/✗ hata), sahte toast değil.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, RefreshCcw, Rss, Filter, PlayCircle, Clock, Download,
  AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2, ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { getFunnelHealth, triggerTrendFetch } from "@/services/hypeService";

const POLL_MS = 20_000;

function toneClasses(tone, target = "border") {
  if (tone === "danger") {
    return target === "bg"
      ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/40"
      : "border-rose-500/40 text-rose-600 dark:text-rose-400";
  }
  if (tone === "warn") {
    return target === "bg"
      ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/40"
      : "border-amber-500/40 text-amber-600 dark:text-amber-400";
  }
  return target === "bg"
    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
    : "border-emerald-500/40 text-emerald-600 dark:text-emerald-400";
}

const BAR = { ok: "bg-emerald-500", warn: "bg-amber-500", danger: "bg-rose-500" };

function CardShell({ icon: Icon, title, badge, children }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-foreground/70" />
          <h2 className="text-base font-semibold">{title}</h2>
        </div>
        {badge}
      </header>
      {children}
    </section>
  );
}

/* Huni aşaması: etiket + sayı + havuz'a göre oransal bar. */
function Stage({ label, value, base, tone = "ok" }) {
  const pct = base > 0 && value != null ? Math.min(100, Math.round((value / base) * 100)) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-mono", value === 0 && "text-rose-500")}>{value ?? "—"}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn("h-full rounded-full transition-[width] duration-300", BAR[tone])} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* "Şimdi trend çek" — DB-kalıcı gerçek durum makinesi. */
function FetchControl({ fetchRun, onTriggered }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const running = fetchRun?.status === "running";

  const handle = useCallback(async () => {
    if (!window.confirm(
      "Şimdi trend taraması başlatılsın mı?\n\n" +
      "GPT + Twitter (XQuik) çağırır (maliyetli) ve 2-6 dk sürer. " +
      "Son taramadan 5 dakika geçmiş olmalı."
    )) return;
    setBusy(true); setMsg(null);
    try {
      const res = await triggerTrendFetch();
      setMsg({ tone: "warn", text: res?.message || "Trend taraması başlatıldı" });
      onTriggered?.();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 409) setMsg({ tone: "warn", text: detail || "Zaten çalışıyor" });
      else if (status === 429) setMsg({ tone: "warn", text: detail || "Çok sık — biraz bekle" });
      else setMsg({ tone: "danger", text: detail || e?.message || "Tetik başarısız" });
    } finally { setBusy(false); }
  }, [onTriggered]);

  let result = null;
  if (fetchRun) {
    if (fetchRun.status === "running") result = { tone: "warn", text: `Çalışıyor… (${fetchRun.rel || "az önce"})` };
    else if (fetchRun.status === "done") result = {
      tone: "ok",
      text: `✓ ${fetchRun.rel}: ${fetchRun.trends_saved ?? "?"} trend kaydedildi` +
        (fetchRun.twitter_items != null ? ` (${fetchRun.twitter_items} sinyal)` : ""),
    };
    else if (fetchRun.status === "stuck") result = { tone: "danger", text: `Son tarama takıldı (${fetchRun.rel}) — tekrar dene` };
    else if (fetchRun.status === "failed") result = { tone: "danger", text: `✗ ${fetchRun.rel}: ${(fetchRun.error || "hata").slice(0, 120)}` };
  }
  const toneText = { ok: "text-emerald-500", warn: "text-amber-500", danger: "text-rose-500" };

  return (
    <div className="pt-1">
      <Button size="sm" onClick={handle} disabled={busy || running} className="w-full">
        {busy || running ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <Download className="h-4 w-4 mr-1.5" />}
        {running ? "Tarama sürüyor…" : busy ? "Başlatılıyor…" : "Şimdi trend çek"}
      </Button>
      {msg && <p className={cn("mt-2 text-xs", toneText[msg.tone])}>{msg.text}</p>}
      {result && <p className={cn("mt-2 text-xs", toneText[result.tone])}>{result.text}</p>}
    </div>
  );
}

export default function SystemFunnelPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const refresh = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const res = await getFunnelHealth();
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "load failed");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    const id = setInterval(() => { if (!document.hidden) refresh({ silent: true }); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const d = data || {};
  const supply = d.supply || {};
  const funnel = d.funnel || {};
  const gate = funnel.last_run_gate || {};
  const fetch = d.fetch || {};
  const cron = d.cron || {};
  const lastRun = d.last_run;
  const bottleneck = d.bottleneck;
  const heroTone = bottleneck ? "danger" : "ok";
  const heroText = bottleneck ? (d.bottleneck_message || "Bir yerde tıkanma var") : "Sistem çalışıyor";
  const supplyTone = Object.values(supply).some((s) => s.tone === "danger") ? "danger" : "ok";

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="h-6 w-6 text-emerald-500" />
            Sistem
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Kaynak → huni → çalıştırma → cron. Nerede tıkandığını tek bakışta gösterir.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refresh()} disabled={loading} className="self-start">
          <RefreshCcw className={cn("h-4 w-4 mr-1.5", loading && "animate-spin")} />
          Yenile
        </Button>
      </header>

      {d.checked_at && (
        <p className="text-[11px] text-muted-foreground font-mono">
          {new Date(d.checked_at).toLocaleString("tr-TR")} · otomatik tazelenir
        </p>
      )}

      {error && !loading && (
        <div role="alert" className="rounded-md border border-rose-500/40 bg-rose-500/5 p-4 text-sm text-rose-600 dark:text-rose-400 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <div><p className="font-semibold">Yüklenemedi</p><p className="text-xs text-muted-foreground mt-1">{String(error)}</p></div>
        </div>
      )}

      {loading && !data ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-56 rounded-2xl border border-border bg-card animate-pulse" />)}
        </div>
      ) : data ? (
        <>
          {/* Hero — 2 saniyede "çalışıyor mu / nerede tıkandı" */}
          <section className={cn("rounded-2xl border p-5 flex items-center gap-3", toneClasses(heroTone, "bg"))}>
            {bottleneck ? <AlertTriangle className="h-7 w-7 shrink-0" /> : <CheckCircle2 className="h-7 w-7 shrink-0" />}
            <p className="text-xl md:text-2xl font-semibold tracking-tight">{heroText}</p>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Kaynaklar */}
            <CardShell
              icon={Rss}
              title="Kaynaklar"
              badge={<Badge variant="outline" className={cn("text-xs", toneClasses(supplyTone))}>{supplyTone === "danger" ? "düşük" : "yeterli"}</Badge>}
            >
              <div className="space-y-2">
                {Object.entries(supply).map(([batch, s]) => (
                  <div key={batch} className={cn("rounded-md border p-2.5 text-xs flex items-center justify-between", toneClasses(s.tone, "bg"))}>
                    <span className="font-mono font-medium">{batch}</span>
                    <span className="font-mono">{s.tweets}/{s.threshold} tweet · {s.accounts}/{s.min_accounts} hesap</span>
                  </div>
                ))}
                {Object.keys(supply).length === 0 && <p className="text-xs text-muted-foreground">Kaynak verisi yok.</p>}
              </div>
              <p className="text-[11px] text-muted-foreground font-mono">
                Son trend: {fetch.last_trend_rel || "—"}{fetch.new_trends_4h != null && ` · son 4s: ${fetch.new_trends_4h} yeni`}
              </p>
              <FetchControl fetchRun={fetch.run} onTriggered={() => refresh({ silent: true })} />
            </CardShell>

            {/* Huni */}
            <CardShell icon={Filter} title="Huni">
              <div className="space-y-3">
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Havuz · son 48 saat</p>
                <Stage label="Gelen trend" value={funnel.trends_48h} base={funnel.trends_48h || 1} tone={funnel.trends_48h === 0 ? "danger" : "ok"} />
                <Stage label="Skor ≥ 75" value={funnel.score_ok} base={funnel.trends_48h || 1} tone="ok" />
                <Stage label="Görünür + uygun kategori" value={funnel.visible} base={funnel.trends_48h || 1} tone={funnel.visible === 0 ? "danger" : "ok"} />
              </div>
              <div className="space-y-2 pt-2 border-t border-border">
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Son çalıştırma</p>
                {Object.keys(gate).length ? (
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {[
                      ["İncelenen", gate.examined, false],
                      ["Dedup", gate.dedup, gate.passed === 0 && (gate.dedup || 0) > 0],
                      ["AI-dışı", gate.ai_reject, gate.passed === 0 && (gate.ai_reject || 0) > 0],
                      ["Geçen → aday", gate.passed, gate.passed === 0],
                    ].map(([label, val, danger]) => (
                      <div key={label} className={cn("rounded-md p-2 border", danger ? toneClasses("danger", "bg") : "bg-muted/40 border-border")}>
                        <p className="text-muted-foreground">{label}</p>
                        <p className="font-mono mt-0.5">{val ?? "—"}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">Son çalıştırmada huni dökümü yok.</p>
                )}
                {gate.reason && <p className="text-[11px] text-muted-foreground">{gate.reason}</p>}
              </div>
            </CardShell>

            {/* Son çalıştırma */}
            <CardShell
              icon={PlayCircle}
              title="Son çalıştırma"
              badge={lastRun && <Badge variant="outline" className={cn("text-xs", toneClasses(lastRun.tone))}>{lastRun.status}</Badge>}
            >
              {lastRun ? (
                <div className="space-y-2 text-sm">
                  <p className="font-mono text-foreground">{lastRun.rel || "—"}</p>
                  <p className="text-muted-foreground text-xs">{lastRun.produced ? "İçerik üretildi" : "İçerik üretilmedi"}</p>
                  {lastRun.reason && <p className="text-xs text-muted-foreground">{lastRun.reason}</p>}
                  <Link to="/dashboard/crew-flow" className="inline-flex items-center gap-1 text-xs text-emerald-500 hover:underline">
                    Crew Akışı'nda gör <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              ) : <p className="text-xs text-muted-foreground">Çalıştırma kaydı yok.</p>}
            </CardShell>

            {/* Cron */}
            <CardShell
              icon={Clock}
              title="Cron / servisler"
              badge={<Badge variant="outline" className={cn("text-xs", toneClasses(cron.tone || "ok"))}>{cron.tone === "danger" ? "gecikme" : "canlı"}</Badge>}
            >
              <ul className="space-y-1.5">
                {[
                  ["last_hype_run", "Pipeline (hype-crew)"],
                  ["last_tweet_feed", "Tweet besleme"],
                  ["last_trend", "Trend çekme"],
                ].map(([key, label]) => {
                  const c = cron[key];
                  if (!c) return null;
                  return (
                    <li key={key} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-2">
                        <span className={cn("inline-block w-2 h-2 rounded-full", c.stale ? "bg-rose-500" : "bg-emerald-500")} />
                        {label}
                      </span>
                      <span className={cn("font-mono", c.stale ? "text-rose-500" : "text-muted-foreground")}>{c.rel || "hiç"}</span>
                    </li>
                  );
                })}
              </ul>
            </CardShell>
          </div>

          {/* Engineer drawer */}
          <section className="rounded-2xl border border-dashed border-border p-4">
            <button type="button" onClick={() => setDrawerOpen((v) => !v)} className="flex w-full items-center justify-between text-left">
              <span className="text-sm font-semibold opacity-70">Ham veri (JSON)</span>
              {drawerOpen ? <ChevronDown className="h-4 w-4 opacity-50" /> : <ChevronRight className="h-4 w-4 opacity-50" />}
            </button>
            {drawerOpen && (
              <pre className="mt-3 overflow-auto rounded bg-muted/50 p-3 text-xs font-mono">{JSON.stringify(data, null, 2)}</pre>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
