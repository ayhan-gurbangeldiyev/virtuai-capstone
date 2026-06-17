import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

/* Sol kolon — son run listesi. Durum noktası + trend başlığı + saat · maliyet. */

function dotClass(run) {
  const status = run?.status || "";
  if (status === "running") return "bg-purple-500 animate-pulse";
  if (status === "failed") return "bg-rose-500";
  // Boş run (post üretmedi) → nötr; "completed" yeşili yanıltmasın
  if (run?.produced === false) return "bg-zinc-600";
  if (["no_candidates", "skipped", "skip"].includes(status)) return "bg-zinc-500";
  if (["blocked", "pending_review"].includes(status) || run?.has_warnings) return "bg-amber-400";
  if (status === "completed") return "bg-emerald-400";
  return "bg-zinc-500";
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

function fmtCost(usd) {
  const n = Number(usd);
  if (!Number.isFinite(n)) return null;
  return `$${n.toFixed(2)}`;
}

export default function RunList({ runs, selectedId, onSelect, error }) {
  if (error) {
    return (
      <div className="text-xs text-rose-400/80 px-2 py-3">Run listesi yüklenemedi.</div>
    );
  }
  if (!Array.isArray(runs) || runs.length === 0) {
    return (
      <div className="text-xs text-muted-foreground px-2 py-3">Henüz run yok.</div>
    );
  }
  return (
    <div className="space-y-2">
      {runs.map((run) => {
        const cost = fmtCost(run?.total_cost_usd);
        return (
          <button
            key={run?.id}
            type="button"
            onClick={() => onSelect?.(run?.id)}
            className={cn(
              "w-full text-left rounded-xl px-3 py-2.5 transition bg-card/80 border",
              run?.id === selectedId
                ? "border-purple-500/80"
                : "border-border/40 hover:border-border/70"
            )}
          >
            <div className="flex items-start gap-2">
              <span className={cn("mt-1 h-2 w-2 rounded-full shrink-0", dotClass(run))} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-foreground/90 truncate">
                  {run?.run_kind === "cards" && (
                    <span className="mr-1 text-[8px] font-mono px-1 py-0.5 rounded bg-purple-500/15 border border-purple-500/40 text-purple-300 align-middle">
                      KART
                    </span>
                  )}
                  {run?.trend_title || "—"}
                </p>
                <p className="text-[10px] font-mono text-muted-foreground mt-0.5">
                  {fmtTime(run?.started_at)}
                  {cost ? ` · ${cost}` : ""}
                </p>
                {run?.produced === false && run?.reason && (
                  <p className="text-[9px] text-zinc-500 mt-0.5 truncate">{run.reason}</p>
                )}
              </div>
              {run?.has_warnings && (
                <AlertTriangle className="h-3 w-3 text-amber-400 shrink-0 mt-0.5" />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
