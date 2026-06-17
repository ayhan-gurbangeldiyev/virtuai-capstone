/**
 * Phase 27.2 — Single meeting rendered as a conversation timeline.
 *
 *   Header (bold, banner-style):
 *     ☀️ Günlük toplantı · 2 dk önce
 *     🎯 Defne · ⚙️ Emir · 🎨 Naz · 💰 Berk · 🛡️ Yiğit (5 yönetici katıldı)
 *
 *   Body:
 *     - For each attended role with content, a chat-bubble (memo text + decision pill)
 *
 *   Footer:
 *     N karar üretildi · X onay bekliyor · Y otomatik uygulandı · $Z maliyet
 *
 * Auto-expands when prop `defaultOpen` is true (latest meeting).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight } from "lucide-react";

import { listMemos, listDecisions } from "@/services/execService";
import { PERSONAS, getPersona, ROLE_ORDER } from "./lib/personas";
import {
  humanizeMeetingKind,
  humanizeDecisionType,
  humanizeStatus,
  relativeTime,
} from "./lib/translators";

function groupByRole({ memos, decisions }) {
  const out = {};
  for (const r of ROLE_ORDER) out[r] = { memos: [], decisions: [] };
  (memos || []).forEach((m) => {
    if (!out[m.author_role]) out[m.author_role] = { memos: [], decisions: [] };
    out[m.author_role].memos.push(m);
  });
  (decisions || []).forEach((d) => {
    if (!out[d.role_responsible]) out[d.role_responsible] = { memos: [], decisions: [] };
    out[d.role_responsible].decisions.push(d);
  });
  return out;
}

const STATUS_COLOR = {
  amber: "bg-amber-500/15 border-amber-500/40 text-amber-200",
  emerald: "bg-emerald-500/15 border-emerald-500/40 text-emerald-200",
  blue: "bg-blue-500/15 border-blue-500/40 text-blue-200",
  rose: "bg-rose-500/15 border-rose-500/40 text-rose-200",
  muted: "bg-muted/30 border-border text-muted-foreground",
};

function RoleBubble({ role, memos, decisions }) {
  const p = getPersona(role);
  if (!memos.length && !decisions.length) return null;
  return (
    <div className="flex gap-3 items-start">
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 ${p.accent.border} ${p.accent.bg} text-xl shadow-sm`}
        aria-label={`${p.name} ${p.titleFallback}`}
      >
        {p.avatar}
      </div>
      <div className={`flex-1 rounded-2xl border-l-4 ${p.accent.left} border-r border-y border-border/60 bg-card/60 px-4 py-3`}>
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          <span className={`text-sm font-bold ${p.accent.text}`}>{p.name}</span>
          <span className="text-[11px] text-muted-foreground">· {p.titleFallback}</span>
        </div>
        {memos.map((m) => (
          <p key={m.id} className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed mb-2">
            {m.content}
          </p>
        ))}
        {decisions.map((d) => {
          const s = humanizeStatus(d.status);
          const palette = STATUS_COLOR[s.color || "muted"];
          return (
            <div key={d.id} className="mt-2 inline-flex items-center gap-2 flex-wrap">
              <span className="text-[11px] uppercase tracking-wider text-muted-foreground">Aksiyon:</span>
              <span className="text-[13px] font-semibold text-foreground">
                {humanizeDecisionType(d.decision_type)}
              </span>
              <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${palette}`}>
                <span aria-hidden>{s.icon}</span>
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function MeetingTimeline({ meeting, defaultOpen = false, roleFilter = null }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({ memos: [], decisions: [] });

  useEffect(() => {
    if (!open || !meeting?.id) return;
    let live = true;
    setLoading(true);
    Promise.all([
      listMemos({ accountId: meeting.account_id, days: 90, limit: 200 }),
      listDecisions({ accountId: meeting.account_id, days: 90, limit: 200 }),
    ])
      .then(([memoRes, decRes]) => {
        if (!live) return;
        const memos = (memoRes.items || []).filter((m) => m.meeting_id === meeting.id);
        const decisions = (decRes.items || []).filter((d) => d.meeting_id === meeting.id);
        setData({ memos, decisions });
      })
      .catch(() => {})
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [open, meeting?.id, meeting?.account_id]);

  if (!meeting) return null;
  const kind = humanizeMeetingKind(meeting.kind);
  const grouped = groupByRole(data);
  const attendees = meeting.attendees || [];

  const decisionsByStatus = data.decisions.reduce((acc, d) => {
    acc[d.status] = (acc[d.status] || 0) + 1;
    return acc;
  }, {});
  const pendingCount = decisionsByStatus.awaiting_approval || 0;
  const autoCount = (decisionsByStatus.auto_executed || 0) + (decisionsByStatus.executed || 0);
  const cost = Number(meeting.total_cost_usd || 0);
  const totalDecisions = data.decisions.length || (meeting.decisions_made_ids || []).length;

  // If filtered by role, only show that one bubble
  const visibleRoles = roleFilter
    ? ROLE_ORDER.filter((r) => r === roleFilter)
    : ROLE_ORDER;
  const hasContent = visibleRoles.some(
    (r) => grouped[r].memos.length || grouped[r].decisions.length,
  );

  return (
    <div className="rounded-xl border-2 border-border/60 bg-card/40 overflow-hidden">
      {/* Banner-style header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left hover:bg-card/80 transition-colors"
      >
        <div className="px-4 py-3 flex items-start gap-3">
          {open ? <ChevronDown className="h-4 w-4 mt-1 shrink-0" /> : <ChevronRight className="h-4 w-4 mt-1 shrink-0" />}
          <div className="flex-1 space-y-1.5 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xl leading-none">{kind.emoji}</span>
              <span className="font-semibold text-base">{kind.label}</span>
              <span className="text-xs text-muted-foreground">· {relativeTime(meeting.started_at)}</span>
            </div>
            {/* Attendees row — visible right in the header */}
            {attendees.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                {attendees.map((r) => {
                  const p = PERSONAS[r];
                  if (!p) return null;
                  return (
                    <span
                      key={r}
                      className={`inline-flex items-center gap-1 rounded-full border ${p.accent.border} ${p.accent.bg} px-1.5 py-0.5 text-[11px]`}
                      title={`${p.name} · ${p.titleFallback}`}
                    >
                      <span className="leading-none">{p.avatar}</span>
                      <span className={`font-medium ${p.accent.text}`}>{p.name}</span>
                    </span>
                  );
                })}
                <span className="text-[11px] text-muted-foreground">
                  ({attendees.length} {t("executive.meeting.attended", "yönetici katıldı")})
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Outcome footer in header (visible even when collapsed) */}
        <div className="px-4 pb-3 flex items-center gap-3 flex-wrap text-[11px]">
          <span className="inline-flex items-center gap-1 rounded-full bg-muted/40 px-2 py-0.5">
            <span className="text-muted-foreground">Karar:</span>
            <span className="font-semibold">{totalDecisions}</span>
          </span>
          {pendingCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-200 px-2 py-0.5">
              <span>⏳</span>
              <span className="font-medium">{pendingCount} onay bekliyor</span>
            </span>
          )}
          {autoCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 px-2 py-0.5">
              <span>✓</span>
              <span className="font-medium">{autoCount} otomatik</span>
            </span>
          )}
          {cost > 0 && (
            <span className="ml-auto text-muted-foreground">
              Maliyet: <span className="font-mono">${cost.toFixed(4)}</span>
            </span>
          )}
        </div>
      </button>

      {/* Body */}
      {open && (
        <div className="px-4 pb-4 pt-3 space-y-3 border-t border-border/40 bg-background/40">
          {loading && <p className="text-xs text-muted-foreground">Yükleniyor…</p>}
          {!loading && !hasContent && (
            <p className="text-xs text-muted-foreground italic">
              {roleFilter
                ? t("executive.meeting.noContentForRole", "Bu toplantıda seçili rol konuşmamış.")
                : t("executive.meeting.noTranscript", "Bu toplantıdan kayıt yok.")}
            </p>
          )}
          {!loading && hasContent && (
            <div className="space-y-3">
              {visibleRoles.map((r) => (
                <RoleBubble
                  key={r}
                  role={r}
                  memos={grouped[r].memos}
                  decisions={grouped[r].decisions}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
