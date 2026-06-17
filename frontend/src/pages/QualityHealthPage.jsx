/**
 * /control/health — operator health surface.
 *
 * 8 traffic-light cards (üretim · video · metin · gate · para · tedarik
 *  · cron · kuyruk). Each card has an operator-language title and a
 * 🟢/🟡/🔴 tone. Click a non-OK card → it expands to show the actual
 * offending rows (linked to /control/lifecycle/<draft_id> when relevant).
 *
 * Engineer drawer at the bottom: raw JSON for debugging.
 */
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronRight, RefreshCcw } from "lucide-react";
import { getQualityHealth } from "@/services/hypeService";

const POLL_MS = 60_000;

const TONE_DOT = {
  ok: "🟢",
  warn: "🟡",
  danger: "🔴",
};

const TONE_BORDER = {
  ok: "border-emerald-500/40 bg-emerald-500/5",
  warn: "border-amber-500/40 bg-amber-500/5",
  danger: "border-rose-500/40 bg-rose-500/5",
};

function fmtUsd(n) {
  const v = Number(n || 0);
  return `$${v.toFixed(v < 1 ? 4 : 2)}`;
}

function Card({ title, tone, label, expandable, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen || tone !== "ok");
  return (
    <div className={`rounded-xl border ${TONE_BORDER[tone] || TONE_BORDER.ok} p-4`}>
      <button
        type="button"
        onClick={() => expandable && setOpen((v) => !v)}
        className="flex w-full items-start justify-between gap-3 text-left"
        disabled={!expandable}
      >
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">
            {title}
          </div>
          <div className="mt-1 text-lg font-semibold">
            <span className="mr-2">{TONE_DOT[tone] || "🟢"}</span>
            {label}
          </div>
        </div>
        {expandable && (
          open
            ? <ChevronDown className="h-4 w-4 mt-1 opacity-60" />
            : <ChevronRight className="h-4 w-4 mt-1 opacity-60" />
        )}
      </button>
      {expandable && open && (
        <div className="mt-3 border-t border-current/10 pt-3 text-sm">{children}</div>
      )}
    </div>
  );
}

function FailList({ rows, kind }) {
  if (!rows?.length) return <div className="text-muted-foreground">Listede satır yok.</div>;
  return (
    <ul className="space-y-1.5">
      {rows.map((r, i) => (
        <li key={`${kind}-${i}`} className="font-mono text-xs">
          <Link
            to={`/control/lifecycle/${r.draft_id || r.run_id || ""}`}
            className="text-sky-600 hover:underline dark:text-sky-400"
          >
            {(r.draft_id || r.run_id || "?").slice(0, 8)}
          </Link>{" "}
          <span className="opacity-70">[{r.platform || r.account_id?.slice(0, 8) || "-"}]</span>{" "}
          {kind === "video" && (
            <span>{r.actual_s?.toFixed?.(1)}s — {r.reason || "?"}</span>
          )}
          {kind === "formulaic" && (
            <span className="opacity-90">"{(r.opener || "").slice(0, 100)}"</span>
          )}
          {kind === "cron" && (
            <span className="text-rose-500">{(r.error || "").slice(0, 140)}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function QualityHealthPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setErr(null);
      const d = await getQualityHealth();
      setData(d);
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  if (loading && !data) {
    return <div className="p-6 text-muted-foreground">Yükleniyor…</div>;
  }
  if (err && !data) {
    return <div className="p-6 text-rose-600">Hata: {err}</div>;
  }
  if (!data) return null;

  const { produced, video, text, gate, money, supply, cron, queue, deploy } = data;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sağlık</h1>
          <p className="text-sm text-muted-foreground">
            Son 24 saat. Otomatik tazelenir.
            {data.generated_at && (
              <> · {new Date(data.generated_at).toLocaleTimeString("tr-TR")}</>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          Yenile
        </button>
      </header>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Card title="Bugün üretilen" tone={produced.tone} label={produced.label} expandable defaultOpen={false}>
          <div className="space-y-1">
            <div>Yayında: <strong>{produced.published_24h}</strong></div>
            <div>Bekleyen: <strong>{produced.stuck_pending}</strong></div>
          </div>
        </Card>

        <Card title="Video sağlığı" tone={video.tone} label={video.label} expandable={video.fail_count > 0}>
          <div className="mb-2">
            %{video.pass_pct} tam (
            <strong>{video.pass_count}</strong>/{video.total}). Kesik: <strong>{video.fail_count}</strong>.
          </div>
          <FailList rows={video.fail_list} kind="video" />
        </Card>

        <Card title="Metin kalitesi" tone={text.tone} label={text.label} expandable={text.formulaic_count > 0}>
          <div className="mb-2">
            %{text.formulaic_pct} formülaik (
            <strong>{text.formulaic_count}</strong>/{text.produced_24h}).
          </div>
          <FailList rows={text.flagged_list} kind="formulaic" />
        </Card>

        <Card title="Gate" tone={gate.tone} label={gate.label} expandable>
          <div>PASS <strong>{gate.pass}</strong> · BLOCK <strong>{gate.block}</strong> · ERROR <strong>{gate.error}</strong></div>
          {gate.error > 0 && (
            <div className="mt-1 text-rose-600">
              Gate ERROR var — faithfulness pipeline'da hata.
            </div>
          )}
        </Card>

        <Card title="Para" tone={money.tone} label={money.label} expandable>
          <div className="space-y-1">
            <div>Bugün HeyGen: <strong>{fmtUsd(money.heygen_today_usd)}</strong></div>
            <div>
              İsraf (kesik videolara harcanan):{" "}
              <strong className={money.heygen_wasted_usd > 0 ? "text-rose-600" : ""}>
                {fmtUsd(money.heygen_wasted_usd)}
              </strong>
            </div>
            <div>Pipeline/LLM: <strong>{fmtUsd(money.pipeline_usd)}</strong></div>
            <div>
              Yayın başına maliyet:{" "}
              <strong>
                {money.cost_per_published_usd != null
                  ? fmtUsd(money.cost_per_published_usd)
                  : "—"}
              </strong>
            </div>
          </div>
        </Card>

        <Card title="Tedarik" tone={supply.tone} label={supply.label} expandable>
          <ul className="space-y-1">
            {Object.entries(supply.batches_24h || {}).map(([b, n]) => (
              <li key={b} className="font-mono text-xs">
                <span className={n === 0 ? "text-rose-600" : ""}>
                  {b}: <strong>{n}</strong> (24h)
                </span>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Cron sağlığı" tone={cron.tone} label={cron.label} expandable={cron.failed_count > 0}>
          <div className="mb-2">
            Toplam run: <strong>{cron.runs_24h}</strong>. Başarısız: <strong>{cron.failed_count}</strong>.
            Editor's-desk: <strong>{cron.editor_24h}</strong> (early-exit{" "}
            <strong>{cron.editor_early_exit}</strong>).
          </div>
          <FailList rows={cron.failed_list} kind="cron" />
        </Card>

        <Card
          title="Deploy drift"
          tone={deploy?.tone || "ok"}
          label={deploy?.label || "—"}
          expandable={Boolean(deploy?.drift_files?.length)}
        >
          <div className="space-y-1">
            <div className="font-mono text-xs">
              git HEAD: <strong>{(deploy?.git_head || "").slice(0, 8) || "—"}</strong>
            </div>
            {deploy?.drift_files?.length ? (
              <ul className="space-y-1">
                {deploy.drift_files.map((f) => (
                  <li key={f.file} className="font-mono text-xs">
                    <span className="text-rose-600">{f.file}</span>
                    <span className="opacity-70"> disk={f.disk?.slice(0, 8)} head={f.head?.slice(0, 8)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="pt-2 text-xs opacity-70">{deploy?.notes}</div>
          </div>
        </Card>

        <Card title="Kuyruk" tone={queue.tone} label={queue.label} expandable>
          <div className="space-y-1">
            <div>Onay-bekliyor: <strong>{queue.active_publishable}</strong></div>
            <div>Arşiv (7g): <strong>{queue.archived_7d}</strong></div>
            <div>3+ gündür bekleyen: <strong>{queue.stale_buildup}</strong></div>
            {queue.archived_by_reason && Object.keys(queue.archived_by_reason).length > 0 && (
              <div className="pt-2">
                <div className="text-xs uppercase text-muted-foreground">Arşiv sebepleri:</div>
                <ul className="font-mono text-xs">
                  {Object.entries(queue.archived_by_reason).map(([r, n]) => (
                    <li key={r}>{r}: {n}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </Card>
      </section>

      <section className="rounded-xl border border-dashed border-border p-4">
        <button
          type="button"
          onClick={() => setDrawerOpen((v) => !v)}
          className="flex w-full items-center justify-between text-left"
        >
          <div className="text-sm font-semibold opacity-70">Engineer drawer (raw JSON)</div>
          {drawerOpen ? <ChevronDown className="h-4 w-4 opacity-50" /> : <ChevronRight className="h-4 w-4 opacity-50" />}
        </button>
        {drawerOpen && (
          <pre className="mt-3 overflow-auto rounded bg-muted/50 p-3 text-xs">
{JSON.stringify({ generated_at: data.generated_at, ...data.engineer }, null, 2)}
          </pre>
        )}
      </section>
    </div>
  );
}
