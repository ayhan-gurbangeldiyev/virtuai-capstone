/**
 * Phase 27 — Memos timeline (chat-bubble style).
 *
 * Each memo is rendered like a Slack/iMessage chat bubble:
 *  [persona avatar]   bubble with content + kind pill + relative time
 *
 * Filterable by role. Falls back to all roles.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { listMemos } from "@/services/execService";
import { getPersona, ROLE_ORDER } from "./lib/personas";
import { humanizeMemoKind, relativeTime } from "./lib/translators";

const KIND_COLORS = {
  purple: "bg-purple-500/10 border-purple-500/30 text-purple-300",
  blue: "bg-blue-500/10 border-blue-500/30 text-blue-300",
  amber: "bg-amber-500/10 border-amber-500/30 text-amber-300",
  rose: "bg-rose-500/10 border-rose-500/30 text-rose-300",
  muted: "bg-muted/30 border-border text-muted-foreground",
};

function MemoBubble({ memo }) {
  const { t } = useTranslation();
  const p = getPersona(memo.author_role);
  const k = humanizeMemoKind(memo.kind);
  const kindPill = KIND_COLORS[k.color] || KIND_COLORS.muted;
  return (
    <div className="flex gap-3 items-start">
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border ${p.accent.border} ${p.accent.bg} text-lg`}
        aria-label={`${p.name} ${p.titleFallback}`}
      >
        {p.avatar}
      </div>
      <div className={`flex-1 rounded-2xl border ${p.accent.border} bg-card/60 px-4 py-3`}>
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={`text-sm font-semibold ${p.accent.text}`}>{p.name}</span>
          <span className="text-[11px] text-muted-foreground">· {p.titleFallback}</span>
          <span className="text-muted-foreground/60">·</span>
          <span className="text-[11px] text-muted-foreground">{relativeTime(memo.created_at)}</span>
          <span className={`ml-auto inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] ${kindPill}`}>
            <span aria-hidden>{k.icon}</span>
            {t(`executive.memo.kind.${memo.kind}`, k.label)}
          </span>
        </div>
        <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">{memo.content}</p>
      </div>
    </div>
  );
}

export default function MemosTimeline({ accountId, roleFilter = null }) {
  const { t } = useTranslation();
  const [role, setRole] = useState(roleFilter || "all");
  const [memos, setMemos] = useState([]);

  useEffect(() => {
    setRole(roleFilter || "all");
  }, [roleFilter]);

  useEffect(() => {
    if (!accountId) return;
    let live = true;
    listMemos({ accountId, role: role === "all" ? undefined : role, days: 14 })
      .then((d) => { if (live) setMemos(d.items || []); })
      .catch(() => { if (live) setMemos([]); });
    return () => { live = false; };
  }, [accountId, role]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={role} onValueChange={setRole}>
          <SelectTrigger className="w-44 h-9">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("executive.memo.filterAll", "Tümü")}</SelectItem>
            {ROLE_ORDER.map((r) => {
              const p = getPersona(r);
              return (
                <SelectItem key={r} value={r}>
                  {p.avatar} {p.name} · {p.titleFallback}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground">
          {memos.length} · 14 gün
        </span>
      </div>

      {memos.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">{t("executive.memo.empty", "Henüz not yok.")}</p>
      ) : (
        <ol className="space-y-3">
          {memos.map((m) => (
            <li key={m.id}>
              <MemoBubble memo={m} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
