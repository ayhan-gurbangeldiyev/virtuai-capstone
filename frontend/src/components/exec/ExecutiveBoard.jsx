/**
 * Phase 27.2 — Executive Board container.
 *
 * New layout (top → bottom):
 *   1. Header (title + subtitle)
 *   2. LiveStatusHeader — what's the team doing right now
 *   3. TeamRoster — 5 persona cards (who is who, what they do, last activity)
 *   4. 4 StatTiles — awaiting / auto-executed 24h / last meeting / weekly cost
 *   5. Primary tabs:
 *        - Kararlar (decisions feed)
 *        - Toplantılar (meeting timeline, latest auto-open)
 *        - Notlar (memo bubbles)
 *   6. Role filter applies to all 3 tabs.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Clock, CheckCircle2, Users, Wallet } from "lucide-react";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { listDecisions, execSummary } from "@/services/execService";
import { humanizeMeetingKind, relativeTime } from "./lib/translators";

import LiveStatusHeader from "./LiveStatusHeader";
import TeamRoster from "./TeamRoster";
import StatTile from "./StatTile";
import DecisionsQueue from "./DecisionsQueue";
import MemosTimeline from "./MemosTimeline";
import MeetingTranscripts from "./MeetingTranscripts";

export default function ExecutiveBoard({ accountId }) {
  const { t } = useTranslation();
  const [summary, setSummary] = useState(null);
  const [pendingDecisions, setPendingDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedRole, setSelectedRole] = useState(null);
  const [tab, setTab] = useState("decisions");

  useEffect(() => {
    if (!accountId) return;
    let live = true;
    const load = async () => {
      try {
        const [s, p] = await Promise.all([
          execSummary(accountId),
          listDecisions({ accountId, status: "awaiting_approval", days: 14, limit: 5 }),
        ]);
        if (!live) return;
        setSummary(s);
        setPendingDecisions(p.items || []);
        setLoading(false);
      } catch {
        if (live) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 30_000);
    return () => { live = false; clearInterval(id); };
  }, [accountId]);

  const lastMeetingLabel = summary?.last_meeting
    ? humanizeMeetingKind(summary.last_meeting.kind).label
    : "—";
  const lastMeetingRel = summary?.last_meeting?.started_at
    ? relativeTime(summary.last_meeting.started_at)
    : "";

  const pendingCount = summary?.pending_approval ?? 0;
  const autoCount = summary?.auto_executed_24h ?? 0;
  const weeklyCost = Number(summary?.weekly_cost_usd ?? 0);

  // When user clicks a persona card, switch to meetings tab (most informative)
  const handleSelectRole = (role) => {
    setSelectedRole(role);
    if (role && tab === "decisions") setTab("meetings");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <header>
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          {t("executive.header.title", "Yönetim")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed max-w-2xl">
          {t(
            "executive.header.subtitle",
            "Cansu'nun otonom yönetim ekibi — 5 AI kişilik sistemi sürekli izliyor, gerektiğinde sana danışıyor.",
          )}
        </p>
      </header>

      {/* Live status */}
      <LiveStatusHeader
        summary={summary}
        pendingDecisions={pendingDecisions}
        loading={loading}
      />

      {/* Team roster (prominent 5-card grid) */}
      <TeamRoster
        accountId={accountId}
        selectedRole={selectedRole}
        onSelectRole={handleSelectRole}
      />

      {/* Stat tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatTile
          icon={<Clock className="h-5 w-5" />}
          number={pendingCount}
          title={t("executive.stats.awaiting.title", "Onayını bekliyor")}
          hint={t("executive.stats.awaiting.hint", "Yöneticiler bir karar için sana danışıyor")}
          color="amber"
          emphasis={pendingCount > 0}
        />
        <StatTile
          icon={<CheckCircle2 className="h-5 w-5" />}
          number={autoCount}
          title={t("executive.stats.autoExecuted.title", "Otomatik yapıldı")}
          hint={t("executive.stats.autoExecuted.hint", "Son 24 saatte yöneticilerin tek başına aldığı kararlar")}
          color="emerald"
        />
        <StatTile
          icon={<Users className="h-5 w-5" />}
          number={lastMeetingRel || "—"}
          title={t("executive.stats.lastMeeting.title", "Son toplantı")}
          hint={lastMeetingLabel}
          color="blue"
        />
        <StatTile
          icon={<Wallet className="h-5 w-5" />}
          number={`$${weeklyCost.toFixed(2)}`}
          title={t("executive.stats.weeklyCost.title", "Bu hafta toplam maliyet")}
          hint={t("executive.stats.weeklyCost.hint", "Yönetim ekibinin LLM harcaması")}
          color="purple"
        />
      </div>

      {/* Primary tabs */}
      <div>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="grid grid-cols-3 w-full sm:w-auto sm:inline-grid">
            <TabsTrigger value="decisions">
              {t("executive.tabs.decisions", "Kararlar")}
            </TabsTrigger>
            <TabsTrigger value="meetings">
              {t("executive.tabs.meetings", "Toplantılar")}
            </TabsTrigger>
            <TabsTrigger value="memos">
              {t("executive.tabs.memos", "Notlar")}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="decisions" className="mt-5">
            <DecisionsQueue accountId={accountId} />
          </TabsContent>

          <TabsContent value="meetings" className="mt-5">
            <MeetingTranscripts accountId={accountId} roleFilter={selectedRole} />
          </TabsContent>

          <TabsContent value="memos" className="mt-5">
            <MemosTimeline accountId={accountId} roleFilter={selectedRole} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
