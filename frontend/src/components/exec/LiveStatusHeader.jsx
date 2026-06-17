/**
 * Phase 27 — Live status banner.
 *
 * Reads execSummary + first pending decision to compose a plain-Turkish
 * "what's the team doing right now?" message. Pulses if anything pending.
 */
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { getPersona } from "./lib/personas";
import { relativeTime, timeUntilNextHour } from "./lib/translators";

export default function LiveStatusHeader({ summary, pendingDecisions = [], loading }) {
  const { t } = useTranslation();

  let message = "";
  let tone = "calm"; // calm | pending | idle | loading

  if (loading) {
    message = t("executive.liveStatus.loading", "Loading team status…");
    tone = "loading";
  } else if ((summary?.pending_approval ?? 0) > 0 && pendingDecisions[0]) {
    const role = pendingDecisions[0].role_responsible;
    const p = getPersona(role);
    message = t("executive.liveStatus.pending", {
      name: p.name,
      title: t(`executive.roles.${role}.title`, p.titleFallback),
    });
    tone = "pending";
  } else if (summary?.last_meeting?.started_at) {
    const ageMs = Date.now() - new Date(summary.last_meeting.started_at).getTime();
    if (ageMs < 60 * 60 * 1000) {
      message = t("executive.liveStatus.calm", { relative: relativeTime(summary.last_meeting.started_at) });
      tone = "calm";
    } else {
      message = t("executive.liveStatus.idle", { at: timeUntilNextHour() });
      tone = "idle";
    }
  } else {
    message = t("executive.liveStatus.idle", { at: timeUntilNextHour() });
    tone = "idle";
  }

  const toneStyles = {
    pending: "border-amber-500/30 bg-amber-500/10",
    calm: "border-emerald-500/30 bg-emerald-500/10",
    idle: "border-border/60 bg-card/60",
    loading: "border-border/60 bg-card/60",
  }[tone];

  const dotStyles = {
    pending: "bg-amber-500 animate-pulse",
    calm: "bg-emerald-500",
    idle: "bg-muted-foreground",
    loading: "bg-muted-foreground animate-pulse",
  }[tone];

  return (
    <div className={`flex items-center gap-3 rounded-xl border ${toneStyles} px-4 py-3`}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotStyles}`} aria-hidden />
      <Sparkles className="h-4 w-4 text-foreground/60" />
      <p className="text-sm font-medium text-foreground leading-snug">{message}</p>
    </div>
  );
}
