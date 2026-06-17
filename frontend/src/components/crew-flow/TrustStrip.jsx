import { cn } from "@/lib/utils";

/* Güven şeridi — chip'ler yalnız sinyal varsa görünür.
   Chip tıklaması ilgili node'u seçer (parent rail'e scroll eder). */

function Chip({ tone = "amber", onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "text-[11px] px-2.5 py-1 rounded-full border transition whitespace-nowrap",
        tone === "amber" &&
          "bg-amber-500/10 border-amber-500/30 text-amber-300 hover:border-amber-500/60",
        tone === "rose" &&
          "bg-rose-500/10 border-rose-500/30 text-rose-300 hover:border-rose-500/60"
      )}
    >
      {children}
    </button>
  );
}

export default function TrustStrip({ trust, onSelectNode }) {
  if (!trust) return null;

  const chips = [];

  const sim = trust.opening_similarity;
  if (sim) {
    const pct = Number.isFinite(Number(sim.max_ratio))
      ? Math.round(Number(sim.max_ratio) * 100)
      : "—";
    const a = sim.platforms?.[0] || "?";
    const b = sim.platforms?.[1] || "?";
    chips.push(
      <Chip key="sim" tone="amber" onClick={() => onSelectNode?.("writer")}>
        açılışlar %{pct} benzer ({a}↔{b})
      </Chip>
    );
  }

  const repairs = trust.gate_repairs;
  if (repairs) {
    chips.push(
      <Chip key="repair" tone="amber" onClick={() => onSelectNode?.("gate")}>
        kapı onarımı: {repairs.repaired ?? 0} draft yeniden yazıldı
      </Chip>
    );
    if ((repairs.still_blocked ?? 0) > 0) {
      chips.push(
        <Chip key="blocked" tone="rose" onClick={() => onSelectNode?.("gate")}>
          {repairs.still_blocked} draft hâlâ blokta
        </Chip>
      );
    }
  }

  if (chips.length === 0) return null;

  return <div className="flex flex-wrap items-center gap-2">{chips}</div>;
}
