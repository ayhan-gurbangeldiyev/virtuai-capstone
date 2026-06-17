/**
 * Phase 27.2 — Team roster.
 *
 * Prominent 5-card grid at the top of the Executive Board showing each
 * persona's name, title, what they do, and their most recent activity.
 *
 * Click a card → filters the activity (callable via onSelect prop).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Card, CardContent } from "@/components/ui/card";
import { listDecisions, listMemos } from "@/services/execService";
import { PERSONAS, ROLE_ORDER } from "./lib/personas";
import {
  humanizeDecisionType,
  humanizeMemoKind,
  humanizeStatus,
  relativeTime,
} from "./lib/translators";

function buildLatestActivity({ memos, decisions }) {
  // returns { role: {summary, time, status} } from most recent memo+decision per role
  const out = {};
  for (const r of ROLE_ORDER) out[r] = null;

  for (const d of decisions || []) {
    const r = d.role_responsible;
    if (!out[r] || new Date(d.created_at) > new Date(out[r].time)) {
      out[r] = {
        time: d.created_at,
        summary: humanizeDecisionType(d.decision_type),
        type: "decision",
        status: d.status,
      };
    }
  }
  for (const m of memos || []) {
    const r = m.author_role;
    if (!out[r] || new Date(m.created_at) > new Date(out[r].time)) {
      out[r] = {
        time: m.created_at,
        summary: humanizeMemoKind(m.kind).label + " paylaştı",
        type: "memo",
        status: null,
      };
    }
  }
  return out;
}

function PersonaCard({ role, activity, onSelect, selected }) {
  const { t } = useTranslation();
  const p = PERSONAS[role];

  let activityText = t("executive.team.idle", "Henüz aktivite yok");
  let activityColor = "text-muted-foreground";
  let activityStyle = "";

  if (activity) {
    activityText = activity.summary;
    if (activity.status === "awaiting_approval") {
      activityColor = "text-amber-300";
      activityStyle = "font-medium";
    } else if (activity.status === "auto_executed" || activity.status === "executed") {
      activityColor = "text-emerald-300";
    }
  }

  return (
    <button
      type="button"
      onClick={() => onSelect?.(role)}
      className={`group text-left transition-all ${selected ? "scale-[1.02]" : ""}`}
    >
      <Card
        className={`relative overflow-hidden border-2 transition-all ${
          selected ? `${p.accent.border} shadow-lg` : "border-border/40 hover:border-border/80"
        } ${p.accent.bg.replace("bg-", "hover:bg-")}/30`}
      >
        {/* Color accent bar on top */}
        <div className={`h-1 ${p.accent.dot}`} aria-hidden />

        <CardContent className="p-4 space-y-3">
          {/* Avatar + name */}
          <div className="flex items-center gap-3">
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-xl border ${p.accent.border} ${p.accent.bg} text-2xl shadow-sm`}
            >
              {p.avatar}
            </div>
            <div className="leading-tight min-w-0">
              <div className={`text-base font-bold ${p.accent.text}`}>{p.name}</div>
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground truncate">
                {t(`executive.roles.${role}.title`, p.titleFallback)}
              </div>
            </div>
          </div>

          {/* What this role does */}
          <p className="text-[12px] leading-relaxed text-foreground/70 min-h-[40px]">
            {p.summary}
          </p>

          {/* Last activity */}
          <div className="border-t border-border/40 pt-2 space-y-0.5">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground/80">
              {t("executive.team.lastActivity", "Son aktivite")}
            </div>
            <div className={`text-[12px] ${activityColor} ${activityStyle} leading-snug line-clamp-2`}>
              {activityText}
            </div>
            {activity?.time && (
              <div className="text-[10px] text-muted-foreground">
                {relativeTime(activity.time)}
                {activity.status === "awaiting_approval" && (
                  <span className="ml-1.5 text-amber-400">
                    · {humanizeStatus("awaiting_approval").label}
                  </span>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </button>
  );
}

export default function TeamRoster({ accountId, selectedRole, onSelectRole }) {
  const { t } = useTranslation();
  const [activity, setActivity] = useState({});

  useEffect(() => {
    if (!accountId) return;
    let live = true;
    Promise.all([
      listDecisions({ accountId, days: 7, limit: 100 }),
      listMemos({ accountId, days: 7, limit: 100 }),
    ])
      .then(([decRes, memoRes]) => {
        if (!live) return;
        setActivity(
          buildLatestActivity({
            decisions: decRes.items || [],
            memos: memoRes.items || [],
          }),
        );
      })
      .catch(() => {});
    return () => { live = false; };
  }, [accountId]);

  return (
    <section>
      <div className="mb-3 flex items-center gap-2 flex-wrap">
        <h3 className="text-base font-semibold tracking-tight text-foreground">
          {t("executive.team.title", "Yönetim Ekibi")}
        </h3>
        <span className="text-[11px] text-muted-foreground">
          {t("executive.team.subtitle", "5 AI yönetici · Cansu'nun otonom sistemini izliyor")}
        </span>
        {selectedRole && (
          <button
            onClick={() => onSelectRole?.(null)}
            className="ml-auto text-[11px] text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
          >
            {t("executive.team.clearFilter", "Filtreyi temizle")}
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {ROLE_ORDER.map((role) => (
          <PersonaCard
            key={role}
            role={role}
            activity={activity[role]}
            selected={selectedRole === role}
            onSelect={(r) => onSelectRole?.(selectedRole === r ? null : r)}
          />
        ))}
      </div>
    </section>
  );
}
