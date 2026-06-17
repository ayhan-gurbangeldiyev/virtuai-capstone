/**
 * Phase 27 — Meeting list. Each meeting renders via MeetingTimeline
 * (chat-style transcript instead of raw <pre> blob).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { listMeetings } from "@/services/execService";
import MeetingTimeline from "./MeetingTimeline";

export default function MeetingTranscripts({ accountId, roleFilter = null }) {
  const { t } = useTranslation();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accountId) return;
    let live = true;
    setLoading(true);
    listMeetings({ accountId, days: 14, limit: 50 })
      .then((d) => { if (live) setMeetings(d.items || []); })
      .catch(() => { if (live) setMeetings([]); })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [accountId]);

  if (loading) {
    return <p className="text-xs text-muted-foreground">Yükleniyor…</p>;
  }
  if (meetings.length === 0) {
    return <p className="text-sm text-muted-foreground italic">{t("executive.meeting.empty", "Henüz toplantı kaydı yok.")}</p>;
  }
  return (
    <div className="space-y-3">
      {meetings.map((m, idx) => (
        <MeetingTimeline
          key={m.id}
          meeting={m}
          roleFilter={roleFilter}
          defaultOpen={idx === 0}
        />
      ))}
    </div>
  );
}
