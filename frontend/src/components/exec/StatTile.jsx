/**
 * Phase 27 — Stat tile: big number + title + hint + icon, color-coded.
 *
 * Used for the 4 hero stats on top of the Executive Board:
 *   Awaiting / Auto-executed / Last meeting / Weekly cost
 */
import { Card, CardContent } from "@/components/ui/card";

const COLOR_MAP = {
  amber: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    text: "text-amber-300",
    icon: "text-amber-400",
  },
  emerald: {
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    text: "text-emerald-300",
    icon: "text-emerald-400",
  },
  purple: {
    bg: "bg-purple-500/10",
    border: "border-purple-500/30",
    text: "text-purple-300",
    icon: "text-purple-400",
  },
  blue: {
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    text: "text-blue-300",
    icon: "text-blue-400",
  },
  rose: {
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    text: "text-rose-300",
    icon: "text-rose-400",
  },
  muted: {
    bg: "bg-muted/40",
    border: "border-border/60",
    text: "text-foreground",
    icon: "text-muted-foreground",
  },
};

export default function StatTile({ icon, number, title, hint, color = "muted", emphasis = false }) {
  const c = COLOR_MAP[color] || COLOR_MAP.muted;
  return (
    <Card
      className={`relative overflow-hidden border ${c.border} ${emphasis ? c.bg : "bg-card/60"} transition-all hover:shadow-md`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className={`text-3xl font-semibold leading-tight ${emphasis ? c.text : "text-foreground"}`}>
              {number}
            </div>
            <div className="mt-1 text-xs font-medium text-foreground/80">{title}</div>
            <div className="mt-0.5 text-[11px] text-muted-foreground leading-snug">{hint}</div>
          </div>
          {icon && (
            <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${c.bg} ${c.icon}`}>
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
