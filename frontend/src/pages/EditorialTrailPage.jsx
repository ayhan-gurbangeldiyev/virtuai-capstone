/**
 * EditorialTrailPage — operator-facing "Seçimler" view at /control/karar-izi.
 *
 * Renamed from "Karar İzi" → "Seçimler" (C4 reframe, 2026-06-07).
 *
 * Two sections, split honestly:
 *   1. Canlı seçimler (live) — judgments that drove the actual drafts.
 *                              Each row shows the stored lead_outcome
 *                              (yazıldı / yayınlandı / atlandı / …).
 *   2. Dahili değerlendirmeler (dry-run) — historical validation rows
 *                              that never reached a draft.
 *
 * Read-only. Data comes from editorial_lead_judgments via
 * /hype/editorial-trail. Does NOT trigger LLM calls, does NOT affect
 * live publishing.
 */
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { fetchEditorialTrail } from "@/services/hypeService";

export default function EditorialTrailPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const d = await fetchEditorialTrail(7);
        setData(d);
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return <Shell><p className="text-neutral-500 text-sm">Seçimler yükleniyor…</p></Shell>;
  }
  if (error || !data) {
    return (
      <Shell>
        <p className="text-neutral-600">Bu sayfada bir sorun var. Tekrar deneyin.</p>
      </Shell>
    );
  }

  const days = data.days || [];
  // C4 split — by is_live (set server-side from dry_run).
  const live = days.filter((d) => d.is_live);
  const dryRun = days.filter((d) => !d.is_live);

  return (
    <Shell>
      <header className="mb-10">
        <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500">
          Seçimler · son 7 gün
        </p>
        <p className="text-xs text-neutral-400 mt-1">
          Cansu'nun her gün hangi haberi öne çıkardığı, hangi haberi öne çıkarmadığı
          ve neden — her iddia kayıtlı bir alana veya kaynak alıntısına bağlı.
        </p>
      </header>

      {/* ── Canlı seçimler ─────────────────────────────────────────── */}
      <section className="space-y-12 mb-16">
        <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-emerald-700">
          Canlı seçimler ({live.length})
        </h2>
        {live.length === 0 && (
          <p className="text-sm text-neutral-500">
            Henüz canlı yayını yönlendiren bir seçim yapılmadı.
          </p>
        )}
        {live.map((d) => (
          <DayCard key={d.judgment_id} card={d} kind="live" />
        ))}
      </section>

      {/* ── Dahili değerlendirmeler ───────────────────────────────── */}
      {dryRun.length > 0 && (
        <section className="space-y-12 mb-12">
          <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500">
            Dahili değerlendirmeler ({dryRun.length})
          </h2>
          <p className="text-xs text-neutral-400 -mt-6">
            Canlı yayına bağlı olmayan tarihi değerlendirme kayıtları.
          </p>
          {dryRun.map((d) => (
            <DayCard key={d.judgment_id} card={d} kind="dry" />
          ))}
        </section>
      )}

      {/* ── Seçim kuralı (footer) ─────────────────────────────────── */}
      <SelectionRuleFooter />
    </Shell>
  );
}

function SelectionRuleFooter() {
  return (
    <section className="pt-10 mt-12 border-t border-neutral-200">
      <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500 mb-3">
        Seçim kuralı
      </p>
      <ol className="text-xs text-neutral-600 leading-relaxed space-y-1 list-decimal pl-5">
        <li>
          Aday havuzu Lever A'dan (persona-gate + dedup) geçen trendlerle başlar.
        </li>
        <li>
          Editor's-desk her aday için bir <span className="text-neutral-800">önem skoru</span>
          {" "}ve <span className="text-neutral-800">topraklanabilir iddia listesi</span> çıkarır.
        </li>
        <li>
          Re-lead hafızası: son 3 günde aynı trend_id, küme veya başlık
          imzasıyla yapılmış canlı seçimler havuzdan elenir.
        </li>
        <li>
          Lider seçilir; ikinci en güçlü aday "yazmadı" olarak kaydedilir.
        </li>
        <li>
          Sonuç (yazıldı / yayınlandı / atlandı) bu sayfada her kart için
          ayrıca görünür.
        </li>
      </ol>
    </section>
  );
}

/* ── Shell ────────────────────────────────────────────────────────── */

function Shell({ children }) {
  return (
    <main className="min-h-screen bg-neutral-50">
      <div className="px-6 md:px-12 pt-12 md:pt-16 pb-24">
        <div className="mx-auto w-full max-w-3xl">{children}</div>
      </div>
    </main>
  );
}

/* ── Day card ─────────────────────────────────────────────────────── */

function DayCard({ card, kind = "live" }) {
  const [open, setOpen] = useState(false);

  const cands = card.candidates || [];
  const actual = card.actual_publishes || [];
  const outcomeLabel = formatOutcome(card.lead_outcome);

  return (
    <article className="border-t border-neutral-200 pt-8">
      <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500 mb-5">
        {formatDateTr(card.judgment_date)}
        {outcomeLabel && (
          <span className={`ml-3 inline-block text-[10px] tracking-wider uppercase px-1.5 py-0.5 rounded ${outcomeTone(card.lead_outcome)}`}>
            {outcomeLabel}
          </span>
        )}
        {kind === "dry" && (
          <span className="ml-3 inline-block text-[10px] tracking-wider uppercase px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-500">
            dahili
          </span>
        )}
      </p>

      {/* Top — the decision in operator language. */}
      <DecisionTop card={card} />

      {/* Layer 2 toggle. */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="mt-6 text-xs text-neutral-600 hover:text-neutral-900 underline underline-offset-4"
      >
        {open ? "Detayları gizle" : `Detayları göster (${cands.length} aday, ${actual.length} fiili paylaşım)`}
      </button>

      {open && (
        <div className="mt-6 space-y-8 border-l-2 border-neutral-200 pl-5">
          {/* Reason clauses — one per grounded claim. */}
          {(card.reason_clauses || []).length > 0 && (
            <Section title="Önem nedeni — iddia → kanıt">
              <ul className="space-y-3">
                {card.reason_clauses.map((rc, i) => (
                  <li key={i} className="text-sm leading-relaxed">
                    <p className="text-neutral-800">{rc.clause || "—"}</p>
                    {rc.grounding && (
                      <p className="mt-1 text-xs text-neutral-500">
                        <span className="font-medium">
                          {rc.grounding.type === "recorded_field"
                            ? "Kayıtlı alan: "
                            : "Kaynak alıntısı: "}
                        </span>
                        {rc.grounding.evidence || "—"}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* All evaluated candidates. */}
          <Section title={`Değerlendirilen adaylar (${cands.length})`}>
            <ul className="space-y-3">
              {cands.map((c) => (
                <CandidateRow key={c.trend_id} c={c} />
              ))}
            </ul>
          </Section>

          {/* Dropped claims — honesty. */}
          {(card.dropped_claims || []).length > 0 && (
            <Section title="Düşürülen iddialar (topraklanamadı)">
              <ul className="space-y-2">
                {card.dropped_claims.map((dc, i) => (
                  <li key={i} className="text-xs text-neutral-600 leading-relaxed">
                    • {dc}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Divergence vs Cansu's actual publishes. */}
          <Section title="Sıralama vs fiili paylaşım (mevcut dahili durum)">
            <DivergencePanel card={card} />
          </Section>
        </div>
      )}
    </article>
  );
}

function DecisionTop({ card }) {
  // If we have both lead + passed-over, render a two-row decision block
  // (Yazdı / Yazmadı) with both titles clickable to their proof URLs.
  // Otherwise fall back to the operator sentence as-is.
  if (card.lead_topic) {
    return (
      <section aria-label="Editöryel karar">
        <DecisionRow
          label="Yazdı"
          tone="accent"
          title={card.lead_topic}
          link={card.lead_source_url}
          emphasized
        />
        {card.passed_over_topic && (
          <>
            <Separator />
            <DecisionRow
              label="Yazmadı"
              tone="muted"
              title={card.passed_over_topic}
              link={card.passed_over_source_url}
              emphasized={false}
            />
          </>
        )}
        {card.operator_sentence && (
          <p className="mt-6 text-sm md:text-base leading-relaxed text-neutral-700">
            {card.operator_sentence}
          </p>
        )}
      </section>
    );
  }
  return (
    <p className="text-base text-neutral-700">{card.operator_sentence || "—"}</p>
  );
}

function DecisionRow({ label, tone, title, link, emphasized }) {
  const labelClass = tone === "accent" ? "text-emerald-700" : "text-neutral-400";
  const titleClass = emphasized
    ? "text-2xl md:text-3xl leading-tight text-neutral-900 font-semibold"
    : "text-xl md:text-2xl leading-snug text-neutral-500 font-medium";
  return (
    <div className="py-2">
      <p className={`text-[10px] font-bold tracking-[0.22em] uppercase mb-2 ${labelClass}`}>
        {label}
      </p>
      {link ? (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className={`${titleClass} block hover:underline underline-offset-4 decoration-2`}
        >
          {title}
        </a>
      ) : (
        <p className={titleClass}>{title || "—"}</p>
      )}
    </div>
  );
}

function Separator() {
  return (
    <div className="my-2 flex items-center gap-3">
      <div className="flex-1 h-px bg-neutral-200" />
      <span className="text-[10px] tracking-[0.22em] uppercase text-neutral-400 font-semibold">
        vs
      </span>
      <div className="flex-1 h-px bg-neutral-200" />
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <h3 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500 mb-3">
        {title}
      </h3>
      {children}
    </div>
  );
}

function CandidateRow({ c }) {
  const roleLabel = {
    lead: "lider",
    passed_over: "en güçlü elenmiş",
    other: "değerlendirildi",
  }[c.role] || "değerlendirildi";
  const roleClass = {
    lead: "bg-emerald-100 text-emerald-800",
    passed_over: "bg-amber-100 text-amber-800",
    other: "bg-neutral-100 text-neutral-600",
  }[c.role] || "bg-neutral-100 text-neutral-600";
  return (
    <li className="text-sm">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={`text-[10px] font-bold tracking-wider uppercase px-1.5 py-0.5 rounded ${roleClass}`}>
          {roleLabel}
        </span>
        {c.source_url ? (
          <a
            href={c.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-neutral-900 hover:underline underline-offset-4"
          >
            {c.topic || "(başlık yok)"}
          </a>
        ) : (
          <span className="text-neutral-900">{c.topic || "(başlık yok)"}</span>
        )}
      </div>
      <div className="mt-1 text-xs text-neutral-500 flex gap-x-3 gap-y-1 flex-wrap">
        {c.content_type && (
          <span>haber türü: <span className="text-neutral-700">{c.content_type}</span></span>
        )}
        {(c.score !== undefined && c.score !== null) && (
          <span>önem skoru: <span className="text-neutral-700">{c.score}</span></span>
        )}
        {Array.isArray(c.semantic_triggers) && c.semantic_triggers.length > 0 && (
          <span>
            anlamsal sinyaller:{" "}
            <span className="text-neutral-700">{c.semantic_triggers.join(", ")}</span>
          </span>
        )}
        {c.source_name && <span>kaynak: <span className="text-neutral-700">{c.source_name}</span></span>}
      </div>
    </li>
  );
}

function DivergencePanel({ card }) {
  const actual = card.actual_publishes || [];
  if (actual.length === 0) {
    return (
      <p className="text-xs text-neutral-600">
        Bu gün Cansu'nun fiili (linkli) paylaşımı kayıtlı değil.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-xs text-neutral-600">
        Editöryel sıralamada lider:{" "}
        <span className="text-neutral-800 font-medium">{card.lead_topic || "—"}</span>
      </p>
      <p className="text-xs text-neutral-600">
        Cansu'nun fiili paylaşımları:
      </p>
      <ul className="text-xs text-neutral-700 space-y-1.5">
        {actual.map((p, i) => (
          <li key={p.trend_id || i}>
            •{" "}
            {/* C3 (2026-06-07): title navigates to the lifecycle page
                when we have a draft_id; release_url remains as the
                external "↗" link suffix. */}
            {p.draft_id ? (
              <RouterLink
                to={`/control/lifecycle/${p.draft_id}`}
                className="hover:underline underline-offset-4"
              >
                {p.trend_topic || "(başlık yok)"}
              </RouterLink>
            ) : p.release_url ? (
              <a
                href={p.release_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline underline-offset-4"
              >
                {p.trend_topic || "(başlık yok)"}
              </a>
            ) : (
              <span>{p.trend_topic || "(başlık yok)"}</span>
            )}
            {p.platform && <span className="text-neutral-500"> · {p.platform}</span>}
            {p.draft_id && p.release_url && (
              <>
                {" "}
                <a
                  href={p.release_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-neutral-500 hover:underline underline-offset-4"
                >
                  ↗
                </a>
              </>
            )}
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-neutral-500 leading-relaxed">
        {card.lead_matches_actual
          ? "Editöryel lider Cansu'nun fiili paylaşımları arasında."
          : "Editöryel lider Cansu'nun fiili paylaşımları arasında değil — bu, mevcut dahili sıralama ile yayın kuyruğu arasındaki farkı gösteriyor."}
      </p>
    </div>
  );
}

/* ── Utilities ──────────────────────────────────────────────────────── */

// C4 — lead_outcome label + tone in plain Turkish.
function formatOutcome(o) {
  return ({
    covered: "yazıldı",
    covered_published: "yayınlandı",
    refused_dedup: "tekrar — atlandı",
    refused_gate: "gate engelledi",
    refused_other: "atlandı",
    pending: "beklemede",
  })[o] || null;
}

function outcomeTone(o) {
  return ({
    covered: "bg-emerald-100 text-emerald-800",
    covered_published: "bg-emerald-100 text-emerald-800",
    refused_dedup: "bg-amber-100 text-amber-800",
    refused_gate: "bg-red-100 text-red-800",
    refused_other: "bg-neutral-100 text-neutral-600",
    pending: "bg-neutral-100 text-neutral-500",
  })[o] || "bg-neutral-100 text-neutral-500";
}

function formatDateTr(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso + "T00:00:00Z");
    return d.toLocaleDateString("tr-TR", {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return iso;
  }
}
