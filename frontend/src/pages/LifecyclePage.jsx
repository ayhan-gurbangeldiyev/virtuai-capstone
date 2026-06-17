/**
 * LifecyclePage — operator-language view of one draft's full journey.
 *
 * Source of truth: backend/routes/hype.py:get_draft_lifecycle. The
 * outer sections speak in OPERATOR words (Kaynak / Neden örtüyor /
 * Ne yazıldı / Görsel / Gate geçti mi / Nerede yayında). Internal
 * surface names (faithfulness_verdicts, hype_stages, persona_assets,
 * editorial_lead_judgments) live ONLY inside a collapsed
 * "Detaylar (teknik)" disclosure.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { fetchDraftLifecycle } from "@/services/hypeService";

export default function LifecyclePage() {
  const { draftId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!draftId) return;
    setError(null);
    try {
      const r = await fetchDraftLifecycle(draftId);
      setData(r);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <Shell>
        <p className="text-neutral-500 text-sm">Yaşam döngüsü yükleniyor…</p>
      </Shell>
    );
  }

  if (error || !data) {
    return (
      <Shell>
        <div className="space-y-4">
          <p className="text-neutral-700">
            Bu taslağın yaşam döngüsü şu an yüklenemiyor.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setLoading(true); setError(null); load(); }}
            className="border-neutral-400 text-neutral-900 hover:bg-neutral-100"
          >
            Yeniden dene
          </Button>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <Header draft={data.draft} />
      <SectionSource source={data.source} />
      <SectionWhyCoverable why={data.why_coverable} />
      <SectionWhatWritten what={data.what_written} />
      <SectionVisual visual={data.visual} image={data.draft?.image_url} />
      <SectionGate gate={data.gate_passed} />
      <SectionWherePublished where={data.where_published} />
      <EngineerDrawer engineer={data.engineer} />
    </Shell>
  );
}

/* ── Shell ─────────────────────────────────────────────────────── */

function Shell({ children }) {
  return (
    <main>
      <div className="px-6 md:px-12 pt-8 md:pt-12 pb-24">
        <div className="mx-auto w-full max-w-3xl space-y-10">
          <BackLink />
          {children}
        </div>
      </div>
    </main>
  );
}

function BackLink() {
  return (
    <p className="text-[11px] tracking-[0.08em] uppercase">
      <Link to="/control" className="text-neutral-500 hover:text-neutral-900 underline underline-offset-4">
        ← Bugün
      </Link>
    </p>
  );
}

function Header({ draft }) {
  if (!draft) return null;
  return (
    <header className="space-y-3">
      <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500">
        Taslak · {draft.status_label || "—"}
      </p>
      <h1 className="text-2xl md:text-4xl leading-tight font-semibold text-neutral-900">
        {draft.title}
      </h1>
      <p className="text-sm text-neutral-600">
        {draft.platform}
        {draft.scheduled_at ? " · " + formatTs(draft.scheduled_at) : ""}
      </p>
    </header>
  );
}

/* ── Sections ──────────────────────────────────────────────────── */

function SectionSource({ source }) {
  if (!source || !source.topic) return null;
  return (
    <SectionCard label="Kaynak">
      <p className="text-base text-neutral-800">
        {source.url ? (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-neutral-900"
          >
            {source.topic}
          </a>
        ) : (
          source.topic
        )}
      </p>
      <p className="text-xs text-neutral-500 mt-1">
        {source.source_name ? `@${source.source_name}` : ""}
        {source.published_at ? ` · yayın: ${formatTs(source.published_at)}` : ""}
        {source.discovered_at ? ` · keşfedildi: ${formatTs(source.discovered_at)}` : ""}
      </p>
    </SectionCard>
  );
}

function SectionWhyCoverable({ why }) {
  if (!why) return null;
  return (
    <SectionCard label="Neden örtüldü">
      {why.operator_sentence && (
        <p className="text-base text-neutral-800 leading-relaxed">
          {why.operator_sentence}
        </p>
      )}
      <p className="text-xs text-neutral-500 mt-2">
        Karar: <span className="text-neutral-700">{why.decision}</span>
        {why.lead_outcome ? ` · sonuç: ${formatOutcome(why.lead_outcome)}` : ""}
        {why.judgment_date ? ` · ${why.judgment_date}` : ""}
      </p>
    </SectionCard>
  );
}

function SectionWhatWritten({ what }) {
  if (!what?.this_post) return null;
  const sibs = what.thread_siblings || [];
  return (
    <SectionCard label="Ne yazıldı">
      <p className="text-sm text-neutral-500 mb-2">
        {what.this_post.platform} · {what.this_post.char_count} karakter
      </p>
      <pre className="whitespace-pre-wrap font-sans text-base text-neutral-800 leading-relaxed">
        {what.this_post.content || "(içerik yok)"}
      </pre>
      {sibs.length > 0 && (
        <div className="mt-4 pt-3 border-t border-neutral-200 space-y-1">
          <p className="text-[11px] tracking-[0.12em] uppercase text-neutral-500">
            Diğer platformlardaki varyantları
          </p>
          {sibs.map((s) => (
            <p key={s.draft_id} className="text-xs text-neutral-600">
              <Link
                to={`/control/lifecycle/${s.draft_id}`}
                className="underline underline-offset-4 hover:text-neutral-900"
              >
                {s.platform}
              </Link>
              {" · "}
              {s.release_url ? "yayında" : (s.status || "—")}
              {s.has_video ? " · video" : ""}
            </p>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

function SectionVisual({ visual, image }) {
  if (!visual && !image) return null;
  return (
    <SectionCard label="Görsel">
      {image ? (
        <img
          src={image}
          alt="Visual"
          className="w-full max-w-md rounded-lg border border-neutral-200"
          loading="lazy"
        />
      ) : (
        <p className="text-sm text-neutral-500">(görsel yok)</p>
      )}
      {visual && (
        <p className="text-xs text-neutral-500 mt-2">
          {visual.composition_type || visual.scene_type || "—"}
        </p>
      )}
    </SectionCard>
  );
}

function SectionGate({ gate }) {
  if (!gate) return null;
  const tone = gate.state === "geçti"
    ? "text-emerald-700"
    : gate.state === "engellendi"
      ? "text-red-700"
      : "text-neutral-700";
  return (
    <SectionCard label="Gate geçti mi">
      <p className={`text-base ${tone}`}>{gate.state}</p>
      {gate.detail && (
        <p className="text-xs text-neutral-500 mt-1">{gate.detail}</p>
      )}
    </SectionCard>
  );
}

function SectionWherePublished({ where }) {
  if (!where) return null;
  return (
    <SectionCard label="Nerede yayında">
      <p className="text-base text-neutral-800">{where.state}</p>
      {where.release_url && (
        <p className="text-sm mt-2">
          <a
            href={where.release_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-4 hover:text-neutral-900"
          >
            Yayın bağlantısı ↗
          </a>
        </p>
      )}
      {where.scheduled_at && (
        <p className="text-xs text-neutral-500 mt-1">
          {formatTs(where.scheduled_at)}
        </p>
      )}
    </SectionCard>
  );
}

function EngineerDrawer({ engineer }) {
  if (!engineer) return null;
  return (
    <section className="mt-8 pt-4 border-t border-neutral-200">
      <details className="group">
        <summary className="cursor-pointer text-[11px] tracking-[0.12em] uppercase text-neutral-500 hover:text-neutral-900 select-none">
          Detaylar (teknik)
        </summary>
        <div className="mt-4 space-y-3 text-xs text-neutral-700 font-mono">
          {Object.entries(engineer).map(([k, v]) => (
            v == null ? null : (
              <div key={k}>
                <p className="text-neutral-500 mb-1">{k}</p>
                <pre className="bg-neutral-100 rounded p-2 whitespace-pre-wrap break-all">
                  {JSON.stringify(v, null, 2)}
                </pre>
              </div>
            )
          ))}
        </div>
      </details>
    </section>
  );
}

/* ── Bits ──────────────────────────────────────────────────────── */

function SectionCard({ label, children }) {
  return (
    <section>
      <p className="text-[11px] font-semibold tracking-[0.18em] uppercase text-neutral-500 mb-2">
        {label}
      </p>
      <div>{children}</div>
    </section>
  );
}

function formatTs(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return `${d.toLocaleDateString("tr-TR", { day: "numeric", month: "long" })}, ${d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}`;
  } catch {
    return "";
  }
}

function formatOutcome(o) {
  return ({
    covered: "yazıldı",
    covered_published: "yayınlandı",
    refused_dedup: "tekrar olarak atlandı",
    refused_gate: "gate tarafından engellendi",
    refused_other: "atlandı",
    pending: "beklemede",
  })[o] || o;
}
