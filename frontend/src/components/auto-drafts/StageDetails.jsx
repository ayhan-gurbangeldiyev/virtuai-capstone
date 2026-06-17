/**
 * StageDetails — premium "Hype Crew nasıl düşündü?" accordion content.
 *
 * Lazy-fetches stages via GET /hype/drafts/:id/stages and renders 4 rich
 * per-agent cards. Each card shows the agent's structured output:
 *
 *  1. Trend Scout — score, category, reasoning, angle hint, urgency
 *  2. Content Strategist — etki/karakter/uzunluk/hook_type chips, brief, reasoning
 *  3. TypeHype V3 Generator — voice score, hook type, char/line counts, model
 *  4. Compliance — pass/fail, brand voice score, hard rules violated
 */
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Telescope, Target, PenLine, Shield, AlertTriangle, Check, Sparkles, Image as ImageIcon, User as UserIcon, Building2 } from "lucide-react";
import { getDraftStages } from "@/services/hypeService";
import { cn } from "@/lib/utils";

const AGENT_CONFIG = {
  "Trend Scout": {
    icon: Telescope,
    tone: "purple",
    label: "Trend Scout",
  },
  "Content Strategist": {
    icon: Target,
    tone: "blue",
    label: "Content Strategist",
  },
  "TypeHype V3 Generator": {
    icon: PenLine,
    tone: "emerald",
    label: "TypeHype V3",
  },
  "Compliance (Flow)": {
    icon: Shield,
    tone: "amber",
    label: "Compliance",
  },
  // Phase 41.E — Visual Director surfaced in the accordion. Until now it
  // was logged to hype_stages but never rendered, so Berkay couldn't see
  // *why* Cansu was used (or not). Phase 39 + 41.B decision now lives here.
  "Visual Director": {
    icon: ImageIcon,
    tone: "teal",
    label: "Visual Director",
  },
};

const TONE_MAP = {
  purple: "border-purple-500/30 bg-purple-500/5 text-purple-600 dark:text-purple-400",
  blue: "border-blue-500/30 bg-blue-500/5 text-blue-600 dark:text-blue-400",
  emerald: "border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400",
  amber: "border-amber-500/30 bg-amber-500/5 text-amber-600 dark:text-amber-400",
  rose: "border-rose-500/30 bg-rose-500/5 text-rose-600 dark:text-rose-400",
  teal: "border-teal-500/30 bg-teal-500/5 text-teal-600 dark:text-teal-400",
};

export default function StageDetails({ draft, expanded }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!expanded || !draft?.id) return;
    if (data || loading) return;
    setLoading(true);
    setError(null);
    getDraftStages(draft.id)
      .then((res) => setData(res))
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Failed"))
      .finally(() => setLoading(false));
  }, [expanded, draft?.id, data, loading]);

  if (loading) {
    return (
      <div className="rounded-xl bg-secondary/20 border border-border/40 p-4 mt-2 flex items-center justify-center text-xs text-muted-foreground gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>Yükleniyor...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-rose-500/5 border border-rose-500/30 p-4 mt-2 text-xs text-rose-600 dark:text-rose-400">
        {error}
      </div>
    );
  }

  if (!data || !data.stages || data.stages.length === 0) {
    // Fallback for synthetic / pre-Phase-17 drafts without a real run
    return (
      <div className="rounded-xl bg-secondary/20 border border-border/40 p-4 mt-2 text-xs text-muted-foreground space-y-1.5">
        <p className="text-[11px] uppercase tracking-wider font-semibold text-muted-foreground/80">
          Veri yok
        </p>
        <p>
          Bu draft eski/test verisi olduğu için per-agent reasoning kayıtlı değil.
          Yeni Hype Crew run'larında her aşama detaylı görünecek.
        </p>
      </div>
    );
  }

  const { stages, run } = data;

  return (
    <div className="space-y-3 mt-2">
      {stages.map((stage, i) => (
        <StageCard key={stage.stage_order} stage={stage} index={i} />
      ))}

      {/* Run footer */}
      {run && (
        <div className="flex items-center justify-between rounded-lg bg-secondary/30 border border-border/40 px-3 py-2 text-[11px] text-muted-foreground font-mono">
          <span>Total {run.total_tokens?.toLocaleString() || 0} tokens</span>
          <span>·</span>
          <span>${Number(run.total_cost_usd || 0).toFixed(4)}</span>
          {run.started_at && run.completed_at && (
            <>
              <span>·</span>
              <span>{computeDuration(run.started_at, run.completed_at)}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function StageCard({ stage, index }) {
  const agentName = stage.agent_name || "Stage";
  const config = AGENT_CONFIG[agentName] || { icon: Sparkles, tone: "purple", label: agentName };
  const Icon = config.icon;
  const out = stage.output || {};

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.04 }}
      className="rounded-xl bg-card border border-border/60 overflow-hidden"
    >
      {/* Header */}
      <div className={cn(
        "flex items-center gap-2 px-4 py-2.5 border-b border-border/40 text-xs",
        TONE_MAP[config.tone]
      )}>
        <Icon className="h-4 w-4" />
        <span className="font-semibold">{config.label}</span>
        <span className="flex-1" />
        <span className="text-[10px] font-mono opacity-70">
          {stage.model_used?.split("/").slice(-1)[0] || ""}
        </span>
        {stage.tokens_used != null && (
          <span className="text-[10px] font-mono opacity-70">
            · {stage.tokens_used.toLocaleString()} tok
          </span>
        )}
      </div>

      {/* Body — agent-specific renderer */}
      <div className="p-4 text-xs space-y-2.5">
        {agentName === "Trend Scout" && <TrendScoutBody out={out} />}
        {agentName === "Content Strategist" && <StrategistBody out={out} />}
        {agentName === "TypeHype V3 Generator" && <WriterBody out={out} />}
        {agentName === "Compliance (Flow)" && <ComplianceBody out={out} />}
        {agentName === "Visual Director" && <VisualDirectorBody out={out} />}
        {!["Trend Scout", "Content Strategist", "TypeHype V3 Generator", "Compliance (Flow)", "Visual Director"].includes(agentName) && (
          <pre className="text-[10px] font-mono whitespace-pre-wrap text-muted-foreground">
            {JSON.stringify(out, null, 2)}
          </pre>
        )}
      </div>
    </motion.div>
  );
}

// ─── Per-agent body renderers ──────────────────────────────────────

function TrendScoutBody({ out }) {
  const score = Number(out.score || 0);
  // Phase 41.E — show the 12-point rubric breakdown (Phase 25.A) so Berkay
  // sees WHY the trend was selected, not just the final number.
  const breakdown = out.breakdown && typeof out.breakdown === "object" ? out.breakdown : null;
  const finalScore12 = out.final_score_12 != null ? Number(out.final_score_12) : null;
  // Phase 41.D — video_worthy flag
  const videoWorthy = out.video_worthy === true;
  return (
    <>
      <Row label="Score">
        <ScorePill value={score} />
        {finalScore12 != null && (
          <Chip className="bg-purple-500/10 border-purple-500/30 text-purple-600 dark:text-purple-300 font-mono">
            {finalScore12}/12
          </Chip>
        )}
        {out.category && (
          <Chip className="bg-purple-500/10 border-purple-500/30 text-purple-600 dark:text-purple-300">
            {out.category}
          </Chip>
        )}
        {out.is_vip && (
          <Chip className="bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300">
            VIP
          </Chip>
        )}
        {videoWorthy && (
          <Chip className="bg-teal-500/10 border-teal-500/30 text-teal-600 dark:text-teal-300">
            🎥 video
          </Chip>
        )}
        {out.urgency_hours != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground">
            {out.urgency_hours}h aciliyet
          </Chip>
        )}
      </Row>
      {breakdown && <RubricBreakdown breakdown={breakdown} />}
      {out.topic && (
        <p className="text-sm font-medium text-foreground/90">{out.topic}</p>
      )}
      {out.reasoning && (
        <Paragraph label="Neden seçtim">{out.reasoning}</Paragraph>
      )}
      {out.angle_hint && (
        <Paragraph label="Açı ipucu" italic>{out.angle_hint}</Paragraph>
      )}
      {videoWorthy && out.video_reason && (
        <Paragraph label="Video gerekçesi" italic>{out.video_reason}</Paragraph>
      )}
      {out.skip_reason && (
        <Paragraph label="Skip sebebi" tone="rose">{out.skip_reason}</Paragraph>
      )}
    </>
  );
}

// Phase 41.E — 12-point rubric grid. Each sub-score (Phase 25.A schema)
// rendered as a small chip with its max. Colors hint at where the score
// came from: green = full credit, amber = partial, rose = zero.
const RUBRIC_LABELS_TR = {
  duyuru_tipi: { label: "Duyuru tipi", max: 5 },
  erisim: { label: "Erişim", max: 2 },
  kullanilabilirlik: { label: "Kullanılabilirlik", max: 2 },
  kaynak: { label: "Kaynak", max: 1 },
  rekabet: { label: "Rekabet", max: 1 },
  fiyat: { label: "Fiyat", max: 1 },
};

function RubricBreakdown({ breakdown }) {
  return (
    <Row label="Skor kırılımı">
      {Object.entries(RUBRIC_LABELS_TR).map(([key, meta]) => {
        const val = Number(breakdown[key] ?? 0);
        const ratio = meta.max > 0 ? val / meta.max : 0;
        let cls = "bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300";
        if (ratio >= 1) {
          cls = "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300";
        } else if (ratio >= 0.5) {
          cls = "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300";
        }
        return (
          <Chip key={key} className={cls + " font-mono"}>
            {meta.label} {val}/{meta.max}
          </Chip>
        );
      })}
    </Row>
  );
}

// Phase 41.E — Turkish labels for voice modes / content types so non-technical
// readers (Berkay) see why a 3rd-person journalist tone was picked.
const VOICE_MODE_TR = {
  first_person_witty: "1. şahıs samimi",
  third_person_neutral: "3. şahıs gazeteci",
  hybrid: "hibrit (gazeteci + reaksiyon)",
};

function StrategistBody({ out }) {
  const chipBlue = "bg-blue-500/10 border-blue-500/30 text-blue-600 dark:text-blue-300";
  const chipBluePale = "bg-blue-500/5 border-blue-500/20 text-blue-700 dark:text-blue-200";
  return (
    <>
      {/* Phase 41.E — content_type + voice_mode shown first because they */}
      {/* drive every downstream routing decision (writer, visual, video). */}
      {(out.content_type || out.voice_mode) && (
        <Row label="Mod">
          {out.content_type && (
            <Chip className={chipBluePale}>
              tip: {out.content_type}
            </Chip>
          )}
          {out.voice_mode && (
            <Chip className={chipBluePale}>
              ses: {VOICE_MODE_TR[out.voice_mode] || out.voice_mode}
            </Chip>
          )}
        </Row>
      )}
      <Row label="Plan">
        {out.etki && <Chip className={chipBlue}>etki: {out.etki}</Chip>}
        {out.karakter && <Chip className={chipBlue}>{out.karakter}</Chip>}
        {out.uzunluk && <Chip className={chipBlue}>{out.uzunluk}</Chip>}
        {out.hook_type && <Chip className={chipBlue}>hook: {out.hook_type}</Chip>}
      </Row>
      {out.target_engagement && (
        <Row label="Hedef">
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground">
            → {out.target_engagement}
          </Chip>
        </Row>
      )}
      {out.brief && (
        <Paragraph label="Brief">{out.brief}</Paragraph>
      )}
      {out.angle && (
        <Paragraph label="Açı" italic>{out.angle}</Paragraph>
      )}
      {out.reasoning && (
        <Paragraph label="Strateji">{out.reasoning}</Paragraph>
      )}
    </>
  );
}

function WriterBody({ out }) {
  const voice = Number(out.voice_alignment_score ?? 0);
  return (
    <>
      <Row label="Çıktı">
        <ScorePill value={voice} suffix="voice" />
        {out.hook_type && (
          <Chip className="bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300">
            {out.hook_type}
          </Chip>
        )}
        {out.character_count != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            {out.character_count} ch
          </Chip>
        )}
        {out.line_count != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            {out.line_count} sat
          </Chip>
        )}
      </Row>
      {Array.isArray(out.has_corporate_words) && out.has_corporate_words.length > 0 && (
        <Row label="Kurumsal kelimeler">
          {out.has_corporate_words.map((w) => (
            <Chip key={w} className="bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300">
              {w}
            </Chip>
          ))}
        </Row>
      )}
      {out.has_em_dash && (
        <Paragraph tone="rose">⚠ Em-dash içeriyor (hard rule)</Paragraph>
      )}
    </>
  );
}

function ComplianceBody({ out }) {
  const approved = out.approved === true;
  const voice = Number(out.brand_voice_score ?? 0);
  return (
    <>
      <Row label="Sonuç">
        {approved ? (
          <Chip className="bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300 gap-1">
            <Check className="h-3 w-3" /> Onaylandı
          </Chip>
        ) : (
          <Chip className="bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300 gap-1">
            <AlertTriangle className="h-3 w-3" /> Reddedildi
          </Chip>
        )}
        <ScorePill value={voice} suffix="voice" />
        {out.confidence != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            {out.confidence}% confidence
          </Chip>
        )}
      </Row>
      {Array.isArray(out.hard_rules_violated) && out.hard_rules_violated.length > 0 && (
        <Row label="İhlaller">
          {out.hard_rules_violated.map((r) => (
            <Chip key={r} className="bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300 font-mono">
              {r}
            </Chip>
          ))}
        </Row>
      )}
      {Array.isArray(out.forbidden_topics_detected) && out.forbidden_topics_detected.length > 0 && (
        <Row label="Yasaklı konular">
          {out.forbidden_topics_detected.map((t) => (
            <Chip key={t} className="bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300">
              {t}
            </Chip>
          ))}
        </Row>
      )}
      {out.similarity_to_recent != null && Number(out.similarity_to_recent) > 0 && (
        <Row label="Tekrar oranı">
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            {(Number(out.similarity_to_recent) * 100).toFixed(0)}%
          </Chip>
        </Row>
      )}
      {out.rejection_reason && (
        <Paragraph label="Sebep" tone="rose">{out.rejection_reason}</Paragraph>
      )}
    </>
  );
}

// Phase 41.E — Visual Director stage card. Surfaces the Phase 39 / 41.B
// LLM router output ("needs_cansu + reason") + compliance scores so Berkay
// can tell at a glance: was Cansu chosen? why? did the image pass quality?
function VisualDirectorBody({ out }) {
  const chipTeal = "bg-teal-500/10 border-teal-500/30 text-teal-600 dark:text-teal-300";
  const needsCansu = out.visual_decision_needs_cansu;
  const decisionPath = out.visual_decision_path;
  const decisionReason = out.visual_decision_reason;
  const verdict = out.compliance_verdict || "SKIPPED";
  const verdictMap = {
    PASS: { cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300", label: "Geçti" },
    NEEDS_REVIEW: { cls: "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300", label: "Gözden geçir" },
    FAIL: { cls: "bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300", label: "Reddedildi" },
    SKIPPED: { cls: "bg-secondary/60 border-border/40 text-muted-foreground", label: "Atlandı" },
  };
  const v = verdictMap[verdict] || verdictMap.SKIPPED;

  return (
    <>
      <Row label="Karar">
        {needsCansu === true && (
          <Chip className={chipTeal + " gap-1"}>
            <UserIcon className="h-3 w-3" /> Cansu
          </Chip>
        )}
        {needsCansu === false && (
          <Chip className={chipTeal + " gap-1"}>
            <Building2 className="h-3 w-3" /> Marka görseli
          </Chip>
        )}
        {decisionPath && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            path: {decisionPath}
          </Chip>
        )}
        {out.visual_mode && (
          <Chip className={chipTeal}>{out.visual_mode}</Chip>
        )}
      </Row>
      {decisionReason && (
        <Paragraph label="Neden">{decisionReason}</Paragraph>
      )}
      <Row label="Sahne">
        {out.scene_type && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground">
            {out.scene_type}
          </Chip>
        )}
        {out.mood && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground">
            {out.mood}
          </Chip>
        )}
        {out.aspect_ratio && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            {out.aspect_ratio}
          </Chip>
        )}
      </Row>
      <Row label="Kalite">
        <Chip className={v.cls + " gap-1"}>
          {verdict === "PASS" ? <Check className="h-3 w-3" /> : verdict === "FAIL" ? <AlertTriangle className="h-3 w-3" /> : null}
          {v.label}
        </Chip>
        {out.clip_similarity != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            CLIP {Number(out.clip_similarity).toFixed(2)}
          </Chip>
        )}
        {out.aesthetic_score != null && (
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            estetik {Number(out.aesthetic_score).toFixed(2)}
          </Chip>
        )}
        {out.ocr_flagged && (
          <Chip className="bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300">
            OCR uyarı
          </Chip>
        )}
      </Row>
      {out.cost_usd != null && (
        <Row label="Maliyet">
          <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
            ${Number(out.cost_usd).toFixed(4)}
          </Chip>
          {out.model_slug && (
            <Chip className="bg-secondary/60 border-border/40 text-muted-foreground font-mono">
              {out.model_slug.split("/").slice(-1)[0]}
            </Chip>
          )}
        </Row>
      )}
      {out.compliance_reasoning && (
        <Paragraph label="Compliance notu" italic>{out.compliance_reasoning}</Paragraph>
      )}
    </>
  );
}

// ─── Primitives ───────────────────────────────────────────────────

function Row({ label, children }) {
  return (
    <div className="flex items-start gap-2 flex-wrap">
      <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground w-24 shrink-0 pt-1">
        {label}
      </span>
      <div className="flex items-center gap-1.5 flex-wrap flex-1">
        {children}
      </div>
    </div>
  );
}

function Chip({ className, children }) {
  return (
    <span className={cn(
      "inline-flex items-center px-2 py-0.5 rounded-md text-[11px] border font-medium",
      className
    )}>
      {children}
    </span>
  );
}

function ScorePill({ value, suffix }) {
  let cls = "bg-rose-500/10 border-rose-500/30 text-rose-600 dark:text-rose-300";
  if (value >= 70) cls = "bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-300";
  else if (value >= 40) cls = "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-300";
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] border font-mono",
      cls
    )}>
      {value}
      {suffix && <span className="opacity-60">/{suffix}</span>}
    </span>
  );
}

function Paragraph({ label, children, italic, tone }) {
  const toneCls = tone === "rose"
    ? "text-rose-600 dark:text-rose-400"
    : "text-foreground/85";
  return (
    <div className="space-y-1">
      {label && (
        <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
          {label}
        </span>
      )}
      <p className={cn(
        "text-xs leading-relaxed",
        toneCls,
        italic && "italic"
      )}>
        {children}
      </p>
    </div>
  );
}

function computeDuration(start, end) {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}
