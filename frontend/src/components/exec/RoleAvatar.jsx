/**
 * Phase 27 — Role avatar pill.
 *
 * Renders the persona for an executive role with avatar emoji + name + title.
 * Two variants:
 *   size="sm"  — inline chip (for decision lists, memo timeline rows)
 *   size="lg"  — hero header (used inside DecisionCard, ApprovalDialog)
 */
import { getPersona } from "./lib/personas";

export default function RoleAvatar({ role, size = "sm", showTitle = true, className = "" }) {
  const p = getPersona(role);
  if (size === "lg") {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl border ${p.accent.border} ${p.accent.bg} text-2xl shadow-sm`}
          aria-label={`${p.name} (${p.titleFallback})`}
        >
          {p.avatar}
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-foreground">{p.name}</div>
          {showTitle && (
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              {p.titleFallback}
            </div>
          )}
        </div>
      </div>
    );
  }
  // sm
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${p.accent.border} ${p.accent.bg} px-2 py-0.5 text-[11px] ${className}`}
      title={`${p.name} · ${p.titleFallback}`}
    >
      <span className="text-sm leading-none">{p.avatar}</span>
      <span className={`font-medium ${p.accent.text}`}>{p.name}</span>
      {showTitle && (
        <span className="text-muted-foreground hidden sm:inline">· {p.titleFallback}</span>
      )}
    </span>
  );
}
