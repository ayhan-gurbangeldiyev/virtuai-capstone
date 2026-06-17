import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

/* Detay paneli — 3 sekme: Özet / Çıktılar / Teknik.
   Her render parçası savunmacı: optional chaining + "—" fallback. */

const DASH = "—";

function fmtDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return DASH;
  const sec = Math.round(n / 1000);
  if (sec < 60) return `${sec} sn`;
  return `${Math.floor(sec / 60)} dk ${sec % 60} sn`;
}

function fmtDateTime(iso) {
  if (!iso) return DASH;
  try {
    return new Date(iso).toLocaleString("tr-TR", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return DASH;
  }
}

function val(v) {
  if (v === null || v === undefined || v === "") return DASH;
  return String(v);
}

function Field({ label, children }) {
  return (
    <div className="flex items-baseline gap-2 text-xs">
      <span className="text-muted-foreground shrink-0 min-w-[120px]">{label}</span>
      <span className="text-foreground/90 break-words min-w-0">{children ?? DASH}</span>
    </div>
  );
}

function RawBlock({ output }) {
  const text = typeof output === "string" ? output : JSON.stringify(output, null, 2);
  return (
    <div className="mt-3">
      <p className="text-[11px] text-amber-400/80 mb-1">Ham çıktı (yapılandırılamadı)</p>
      <pre className="text-[10px] font-mono bg-black/30 border border-border/40 rounded-lg p-3 whitespace-pre-wrap break-words max-h-64 overflow-auto">
        {text || DASH}
      </pre>
    </div>
  );
}

/* ── Özet — node bazlı operatör dili ── */

function TrendScoutSummary({ o }) {
  const score =
    o?.final_score_12 != null
      ? `${o.final_score_12}/12`
      : o?.score != null
        ? `${o.score}/100`
        : DASH;
  const candidates = Array.isArray(o?.candidates_considered) ? o.candidates_considered : [];
  return (
    <div className="space-y-2">
      <Field label="Konu">{val(o?.topic)}</Field>
      <Field label="Skor">{score}</Field>
      <Field label="Kazanma nedeni">{val(o?.selection_delta?.winning_reason)}</Field>
      <Field label="İkinci aday">{val(o?.selection_delta?.runner_up_topic)}</Field>
      <Field label="Değerlendirilen">{candidates.length > 0 ? `${candidates.length} aday` : DASH}</Field>
      {candidates.slice(0, 3).map((c, i) => (
        <p key={i} className="text-[11px] text-muted-foreground pl-2 border-l border-border/40">
          {val(c?.topic)} <span className="text-foreground/60">· {val(c?.outcome)}</span>
        </p>
      ))}
      {o?.reasoning && (
        <p className="text-[11px] text-muted-foreground italic">
          {String(o.reasoning).slice(0, 200)}
          {String(o.reasoning).length > 200 ? "…" : ""}
        </p>
      )}
    </div>
  );
}

function StrategistSummary({ o }) {
  return (
    <div className="space-y-2">
      <Field label="Etki">{val(o?.impact ?? o?.etki)}</Field>
      <Field label="Karakter">{val(o?.character ?? o?.karakter)}</Field>
      <Field label="Uzunluk">{val(o?.length ?? o?.uzunluk)}</Field>
      <Field label="Voice mode">{val(o?.voice_mode)}</Field>
      <Field label="İçerik tipi">{val(o?.content_type)}</Field>
      {o?.brief && (
        <div>
          <p className="text-[11px] text-muted-foreground mb-1">Brief</p>
          <p className="text-xs text-foreground/85 whitespace-pre-wrap">{String(o.brief)}</p>
        </div>
      )}
    </div>
  );
}

function WriterSummary({ o, drafts, trust }) {
  const content = typeof o?.content === "string" ? o.content : "";
  return (
    <div className="space-y-2">
      {content ? (
        <blockquote className="border-l-2 border-purple-500 pl-3 text-xs text-foreground/85 italic">
          {content.slice(0, 140)}
          {content.length > 140 ? "…" : ""}
        </blockquote>
      ) : (
        <p className="text-xs text-muted-foreground">{DASH}</p>
      )}
      <Field label="Karakter sayısı">{val(o?.character_count)}</Field>
      <Field label="Ses uyumu">
        {o?.voice_alignment_score != null ? `${o.voice_alignment_score}/100` : DASH}
      </Field>
      <Field label="Platform sayısı">{Array.isArray(drafts) ? drafts.length : DASH}</Field>
      {trust?.opening_similarity && (
        <p className="text-[11px] text-amber-400">
          ⚠ Açılışlar %
          {Math.round(Number(trust.opening_similarity.max_ratio || 0) * 100)} benzer (
          {trust.opening_similarity.platforms?.[0] || "?"}↔
          {trust.opening_similarity.platforms?.[1] || "?"})
        </p>
      )}
    </div>
  );
}

function GateSummary({ o, trust }) {
  const violations = Array.isArray(o?.hard_rules_violated) ? o.hard_rules_violated : [];
  return (
    <div className="space-y-2">
      <Field label="Onay">
        {o?.approved === true ? (
          <span className="text-emerald-400">✓ onaylandı</span>
        ) : o?.approved === false ? (
          <span className="text-rose-400">✗ reddedildi</span>
        ) : (
          DASH
        )}
      </Field>
      <Field label="Marka sesi skoru">{val(o?.brand_voice_score)}</Field>
      <Field label="Kural ihlalleri">
        {violations.length > 0 ? violations.join(", ") : "ihlal yok"}
      </Field>
      <Field label="Red nedeni">{val(o?.rejection_reason)}</Field>
      {trust?.gate_repairs && (
        <span className="inline-block text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300">
          onarıldı · {trust.gate_repairs.repaired ?? 0} draft yeniden yazıldı
        </span>
      )}
    </div>
  );
}

function VisualSummary({ o }) {
  return (
    <div className="space-y-2">
      <Field label="Kompozisyon">{val(o?.composition_type)}</Field>
      <Field label="Karar yolu">
        {val(o?.visual_decision_path)}
        {o?.visual_decision_reason ? ` — ${o.visual_decision_reason}` : ""}
      </Field>
      <Field label="Uygunluk">{val(o?.compliance_verdict)}</Field>
      <Field label="Maliyet">
        {o?.cost_usd != null ? `$${Number(o.cost_usd).toFixed(3)}` : DASH}
      </Field>
      {o?.image_url && (
        <a href={o.image_url} target="_blank" rel="noreferrer" className="inline-block">
          <img
            src={o.image_url}
            alt="görsel"
            className="h-20 rounded-lg border border-border/40 object-cover"
          />
        </a>
      )}
    </div>
  );
}

function VideoSummary({ o, node }) {
  if (node?.state === "skipped") {
    return (
      <p className="text-xs text-muted-foreground">
        Atlandı{node?.skip_reason ? ` — ${node.skip_reason}` : ""}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {/* 2026-06-11 (Berkay: "video üretmiş ama görüntüleyemiyorsun") —
          Video node'una tıklayan operatör videoyu GÖRMEK ister; player
          yalnız Çıktılar sekmesinin IG/LI/YT tab'larında saklıydı. */}
      {o?.video_url && (
        <video
          controls
          preload="metadata"
          src={o.video_url}
          poster={o?.thumbnail_url || undefined}
          className="max-h-64 rounded-lg border border-border/40"
        />
      )}
      <Field label="Kullanılan yöntem">{val(o?.pipeline_used)}</Field>
      <Field label="Süre">{o?.duration_sec != null ? `${o.duration_sec} sn` : DASH}</Field>
      <Field label="Maliyet">
        {o?.cost_usd != null ? `$${Number(o.cost_usd).toFixed(3)}` : DASH}
      </Field>
      <Field label="Hedef platform">{val(o?.target_platform)}</Field>
    </div>
  );
}

function PublishSummary({ drafts }) {
  const list = Array.isArray(drafts) ? drafts : [];
  if (list.length === 0) return <p className="text-xs text-muted-foreground">Draft yok.</p>;
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-muted-foreground text-left">
          <th className="font-normal pb-1">Platform</th>
          <th className="font-normal pb-1">Durum</th>
          <th className="font-normal pb-1">Planlanan</th>
        </tr>
      </thead>
      <tbody>
        {list.map((d, i) => (
          <tr key={d?.id || i} className="border-t border-border/30">
            <td className="py-1.5 text-foreground/90">{val(d?.platform)}</td>
            <td className="py-1.5">{val(d?.postiz_state ?? d?.status)}</td>
            <td className="py-1.5 font-mono text-muted-foreground">{fmtDateTime(d?.scheduled_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ── SÖZLÜK/SENCE? kart node özetleri ── */
function CardContentSummary({ o, node }) {
  const isDict = o?.kind === "dictionary";
  return (
    <div className="space-y-2">
      <Field label="Tür">{isDict ? "SÖZLÜK (terim)" : "SENCE? (soru)"}</Field>
      <Field label={isDict ? "Terim" : "Soru"}>{val(o?.main)}</Field>
      {o?.sub && <Field label="Açıklama">{val(o.sub)}</Field>}
      <Field label="Caption">{val(o?.caption)}</Field>
      <Field label="Model">{val(node?.model_used)}</Field>
      <Field label="Token">{node?.tokens_used ? `~${node.tokens_used}` : DASH}</Field>
      <Field label="Deneme">{val(o?.attempts)}</Field>
    </div>
  );
}

function CardGateSummary({ o }) {
  return (
    <div className="space-y-2">
      <Field label="Sonuç">
        <span className={o?.ok ? "text-emerald-400" : "text-rose-400"}>
          {o?.ok ? "GEÇTİ" : "REDDEDİLDİ"}
        </span>
      </Field>
      <Field label="Gerekçe">{val(o?.reason)}</Field>
    </div>
  );
}

function CardRenderSummary({ o }) {
  return (
    <div className="space-y-2">
      <Field label="Kart görseli">{o?.image_url ? "üretildi" : DASH}</Field>
      {o?.image_url && (
        <a href={o.image_url} target="_blank" rel="noreferrer" className="inline-block">
          <img src={o.image_url} alt="kart" className="max-h-64 rounded-lg border border-border/40" />
        </a>
      )}
    </div>
  );
}

function CardPublishSummary({ o }) {
  const plats = Array.isArray(o?.platforms) ? o.platforms : [];
  return (
    <div className="space-y-2">
      <Field label="Platformlar">{plats.length ? plats.join(", ") : DASH}</Field>
      <Field label="Zamanlama">{fmtDateTime(o?.scheduled_at)}</Field>
      <Field label="Durum">{val(o?.status)}</Field>
      <Field label="Postiz id">{val(o?.postiz_post_id)}</Field>
    </div>
  );
}

function SummaryTab({ node, drafts, trust }) {
  if (!node) return <p className="text-xs text-muted-foreground">Bir aşama seçin.</p>;
  const o = node.output && typeof node.output === "object" ? node.output : {};
  let body;
  switch (node.key) {
    case "trend_scout": body = <TrendScoutSummary o={o} />; break;
    case "strategist": body = <StrategistSummary o={o} />; break;
    case "writer": body = <WriterSummary o={o} drafts={drafts} trust={trust} />; break;
    case "gate": body = <GateSummary o={o} trust={trust} />; break;
    case "visual": body = <VisualSummary o={o} />; break;
    case "video": body = <VideoSummary o={o} node={node} />; break;
    case "publish":
      body = (o?.card_index !== undefined && o?.card_index !== null)
        ? <CardPublishSummary o={o} />
        : <PublishSummary drafts={drafts} />;
      break;
    // SÖZLÜK/SENCE? kart node'ları
    case "icerik": body = <CardContentSummary o={o} node={node} />; break;
    case "card_gate": body = <CardGateSummary o={o} />; break;
    case "render": body = <CardRenderSummary o={o} />; break;
    default: body = <p className="text-xs text-muted-foreground">{DASH}</p>;
  }
  return (
    <div>
      {node.error && (
        <p className="text-[11px] text-rose-400 mb-2 break-words">Hata: {node.error}</p>
      )}
      {body}
      {node.output_truncated === true && <RawBlock output={node.output} />}
    </div>
  );
}

/* ── Çıktılar — platform tab'ları + tam metin + medya ── */

function statusLabel(d) {
  return d?.postiz_state || d?.status || DASH;
}

function OutputsTab({ drafts }) {
  const list = Array.isArray(drafts) ? drafts : [];
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (idx >= list.length) setIdx(0);
  }, [list.length, idx]);
  if (list.length === 0) return <p className="text-xs text-muted-foreground">Çıktı yok.</p>;
  const d = list[Math.min(idx, list.length - 1)] || {};
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {list.map((item, i) => (
          <button
            key={item?.id || i}
            type="button"
            onClick={() => setIdx(i)}
            className={cn(
              "text-[11px] px-2.5 py-1 rounded-full border transition",
              i === idx
                ? "bg-purple-500/15 border-purple-500/60 text-purple-300"
                : "border-border/40 text-muted-foreground hover:border-border/70"
            )}
          >
            {item?.platform || `#${i + 1}`}
            {/* videolu platformlar tab üzerinden keşfedilebilir olsun —
                ilk tab (twitter) videosuz olduğu için video saklı kalıyordu */}
            {item?.video_url ? " 🎬" : ""}
          </button>
        ))}
      </div>
      <p className="text-xs text-foreground/90 whitespace-pre-wrap break-words">
        {d?.content || DASH}
      </p>
      {(d?.video_url || d?.image_url) && (
        <div className="flex items-start gap-3">
          {d?.video_url && (
            <video
              controls
              preload="metadata"
              src={d.video_url}
              className="max-h-64 rounded-lg border border-border/40"
            />
          )}
          {d?.image_url && (
            <a href={d.image_url} target="_blank" rel="noreferrer">
              <img
                src={d.image_url}
                alt="görsel"
                className={cn(
                  "rounded-lg border border-border/40 object-cover",
                  d?.video_url ? "h-20" : "max-h-48"
                )}
              />
            </a>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground border-t border-border/30 pt-2">
        <span className="font-mono">{d?.char_count != null ? `${d.char_count} karakter` : DASH}</span>
        <span>{statusLabel(d)}</span>
        {d?.release_url && (
          <a
            href={d.release_url}
            target="_blank"
            rel="noreferrer"
            className="text-emerald-400 hover:underline inline-flex items-center gap-0.5"
          >
            yayında <ExternalLink className="h-3 w-3" />
          </a>
        )}
        <Link to="/dashboard/auto-drafts" className="text-purple-400 hover:underline">
          AutoDrafts'ta aç
        </Link>
      </div>
    </div>
  );
}

/* ── Teknik — tüm stage'lerin ham dökümü ── */

function TechnicalTab({ nodes }) {
  const list = Array.isArray(nodes) ? nodes : [];
  if (list.length === 0) return <p className="text-xs text-muted-foreground">Veri yok.</p>;
  return (
    <div className="space-y-3">
      {list.map((n, i) => (
        <div key={n?.key || i} className="border border-border/30 rounded-lg p-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono">
            <span className="text-foreground/90">{n?.key || DASH}</span>
            <span className="text-muted-foreground">{n?.model_used || DASH}</span>
            <span className="text-muted-foreground">
              {n?.tokens_used != null
                ? `${n?.tokens_estimated ? "~" : ""}${n.tokens_used} token`
                : DASH}
            </span>
            <span className="text-muted-foreground">{fmtDuration(n?.derived_duration_ms)}</span>
            <span
              className={cn(
                n?.state === "success" && "text-emerald-400",
                n?.state === "failed" && "text-rose-400",
                n?.state === "running" && "text-purple-400",
                (n?.state === "skipped" || n?.state === "pending") && "text-zinc-500"
              )}
            >
              {n?.state || DASH}
            </span>
          </div>
          {n?.error && (
            <p className="text-[11px] text-rose-400 mt-1 break-words">{n.error}</p>
          )}
          {n?.output != null && (
            <details className="mt-2">
              <summary className="text-[11px] text-muted-foreground cursor-pointer select-none">
                ham çıktı
              </summary>
              <pre className="text-[10px] font-mono bg-black/30 rounded-lg p-2 mt-1 whitespace-pre-wrap break-words max-h-64 overflow-auto">
                {typeof n.output === "string" ? n.output : JSON.stringify(n.output, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Panel ── */

const TABS = [
  { key: "ozet", label: "Özet" },
  { key: "ciktilar", label: "Çıktılar" },
  { key: "teknik", label: "Teknik" },
];

export default function DetailPanel({ node, nodes, drafts, trust }) {
  const [tab, setTab] = useState("ozet");
  return (
    <div className="rounded-2xl bg-card/80 border border-border/40 p-4">
      <div className="flex items-center gap-1.5 mb-4">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "text-xs px-3 py-1.5 rounded-lg transition",
              tab === t.key
                ? "bg-purple-500/15 text-purple-300 border border-purple-500/40"
                : "text-muted-foreground border border-transparent hover:bg-white/5"
            )}
          >
            {t.label}
          </button>
        ))}
        {node?.label && (
          <span className="ml-auto text-[11px] text-muted-foreground">{node.label}</span>
        )}
      </div>
      {tab === "ozet" && <SummaryTab node={node} drafts={drafts} trust={trust} />}
      {tab === "ciktilar" && <OutputsTab drafts={drafts} />}
      {tab === "teknik" && <TechnicalTab nodes={nodes} />}
    </div>
  );
}
