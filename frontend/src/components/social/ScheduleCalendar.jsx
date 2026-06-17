import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, CalendarDays, Inbox } from "lucide-react";
import {
  addDays, addWeeks, startOfWeek, endOfWeek, isSameDay,
  isToday, isPast, parseISO, format,
} from "date-fns";
import { tr } from "date-fns/locale";

import PlatformIcon from "./PlatformIcon";

/**
 * Phase 36 + 39.7 — Scheduled Calendar view for Social Manager.
 *
 * Week view (7 columns, Mon → Sun). Each day cell stacks the posts scheduled
 * for that day sorted by hour, with platform avatar + content preview.
 * Click a post → onSelectPost(post) (parent opens the edit dialog).
 *
 * Mobile: collapses to a vertical list grouped by day (md: 7-col grid).
 */
export default function ScheduleCalendar({ posts, onSelectPost }) {
  // weekStart is always Monday of the visible week
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date(), { weekStartsOn: 1 }));

  const days = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  }, [weekStart]);

  const weekEnd = endOfWeek(weekStart, { weekStartsOn: 1 });

  // Filter + bucket posts by day (only scheduled within visible week)
  const postsByDay = useMemo(() => {
    const buckets = days.map(() => []);
    for (const p of posts) {
      if (!p.scheduled_at) continue;
      let when;
      try { when = parseISO(p.scheduled_at); } catch { continue; }
      const idx = days.findIndex((d) => isSameDay(d, when));
      if (idx >= 0) buckets[idx].push({ ...p, _when: when });
    }
    // sort each bucket by time asc
    for (const b of buckets) b.sort((a, b) => a._when - b._when);
    return buckets;
  }, [posts, days]);

  const totalThisWeek = postsByDay.reduce((sum, b) => sum + b.length, 0);

  return (
    <div className="rounded-2xl border border-border/40 bg-card/60 backdrop-blur-xl p-3 sm:p-4">
      {/* Week navigator */}
      <div className="flex items-center justify-between mb-4 gap-2">
        <button
          onClick={() => setWeekStart((d) => addWeeks(d, -1))}
          className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-border/40 bg-secondary/30 hover:bg-secondary/60 transition-colors"
          title="Önceki hafta"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex-1 min-w-0 text-center">
          <div className="flex items-center justify-center gap-2">
            <CalendarDays className="h-4 w-4 text-sky-400" />
            <p className="text-sm sm:text-base font-semibold tracking-tight">
              {format(weekStart, "d MMM", { locale: tr })} – {format(weekEnd, "d MMM yyyy", { locale: tr })}
            </p>
          </div>
          <p className="text-[10.5px] text-muted-foreground/80 mt-0.5">
            {totalThisWeek > 0
              ? `${totalThisWeek} planlı post`
              : "Bu hafta planlı post yok"}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 }))}
            className="hidden sm:inline-flex items-center px-3 h-9 rounded-lg border border-border/40 bg-secondary/30 hover:bg-secondary/60 text-xs font-medium transition-colors"
          >
            Bugün
          </button>
          <button
            onClick={() => setWeekStart((d) => addWeeks(d, 1))}
            className="inline-flex items-center justify-center w-9 h-9 rounded-lg border border-border/40 bg-secondary/30 hover:bg-secondary/60 transition-colors"
            title="Sonraki hafta"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Day columns */}
      <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
        {days.map((d, i) => {
          const bucket = postsByDay[i];
          const today = isToday(d);
          const past = isPast(d) && !today;
          return (
            <div
              key={d.toISOString()}
              className={[
                "rounded-xl border min-h-[140px] flex flex-col",
                today
                  ? "border-sky-500/50 bg-sky-500/[0.04]"
                  : past
                    ? "border-border/30 bg-card/30"
                    : "border-border/40 bg-card/50",
              ].join(" ")}
            >
              {/* Day header */}
              <div className="px-2.5 py-2 border-b border-border/30 flex items-baseline justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                    {format(d, "EEE", { locale: tr })}
                  </p>
                  <p className={["text-lg font-bold leading-none mt-0.5", today ? "text-sky-300" : ""].join(" ")}>
                    {format(d, "d")}
                  </p>
                </div>
                {bucket.length > 0 && (
                  <span className="text-[10px] font-mono text-muted-foreground/80">
                    {bucket.length}
                  </span>
                )}
              </div>
              {/* Posts */}
              <div className="flex-1 p-1.5 space-y-1">
                {bucket.length === 0 ? (
                  <p className="text-[10.5px] text-muted-foreground/40 text-center mt-3">—</p>
                ) : (
                  <AnimatePresence>
                    {bucket.map((p) => (
                      <DayPostChip key={p.id} post={p} onClick={() => onSelectPost?.(p)} />
                    ))}
                  </AnimatePresence>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty week hint */}
      {totalThisWeek === 0 && (
        <div className="mt-4 rounded-xl border border-border/30 bg-secondary/15 px-4 py-3 flex items-start gap-2.5">
          <Inbox className="h-4 w-4 text-muted-foreground/70 mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground">
            Bu hafta planlanmış post yok. Üstteki <span className="font-semibold text-foreground/90">“Yeni Post”</span> butonundan zamanlama oluşturabilirsin.
          </p>
        </div>
      )}
    </div>
  );
}

function DayPostChip({ post, onClick }) {
  const statusStyle = {
    scheduled:  "border-amber-500/30 hover:border-amber-500/60 hover:bg-amber-500/5",
    published:  "border-emerald-500/30 hover:border-emerald-500/60 hover:bg-emerald-500/5",
    failed:     "border-rose-500/30 hover:border-rose-500/60 hover:bg-rose-500/5",
    draft:      "border-zinc-500/30 hover:border-zinc-500/60 hover:bg-zinc-500/5",
    processing: "border-sky-500/30 hover:border-sky-500/60 hover:bg-sky-500/5",
  }[post.status] || "border-border/30 hover:bg-secondary/40";

  const preview = (post.content || "").trim().slice(0, 60);

  return (
    <motion.button
      layout
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      onClick={onClick}
      className={[
        "w-full text-left rounded-lg border bg-card/60 px-2 py-1.5 transition-colors",
        statusStyle,
      ].join(" ")}
      title={`${format(post._when, "d MMM HH:mm", { locale: tr })} — ${post.content || ""}`}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <PlatformIcon identifier={post.platform} className="h-3 w-3 shrink-0" />
        <span className="font-mono text-[10px] text-muted-foreground tracking-tight">
          {format(post._when, "HH:mm")}
        </span>
      </div>
      <p className="text-[11px] leading-snug text-foreground/90 line-clamp-2 break-words">
        {preview || "(boş)"}
      </p>
    </motion.button>
  );
}
