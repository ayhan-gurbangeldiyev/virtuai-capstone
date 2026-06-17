import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from 'react-i18next';
import {
  ChevronLeft, ChevronRight, Copy, Heart, ExternalLink,
  Flame, Calendar, Twitter, Quote, MessageSquare, PenLine,
  FileText, ArrowRight, TrendingUp
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";

/* ── Config ─────────────────────────────────────── */

const typeConfig = {
  tweet:   { labelKey: "calendar.typeLabels.tweet",   icon: Twitter,        color: "bg-sky-500",    ring: "ring-sky-400",    text: "text-sky-500",    bg: "bg-sky-500/15" },
  quote:   { labelKey: "calendar.typeLabels.quote",   icon: Quote,          color: "bg-purple-500", ring: "ring-purple-400", text: "text-purple-500", bg: "bg-purple-500/15" },
  reply:   { labelKey: "calendar.typeLabels.reply",   icon: MessageSquare,  color: "bg-emerald-500",ring: "ring-emerald-400",text: "text-emerald-500",bg: "bg-emerald-500/15" },
  article: { labelKey: "calendar.typeLabels.article", icon: FileText,        color: "bg-orange-500", ring: "ring-orange-400", text: "text-orange-500", bg: "bg-orange-500/15" },
};

// DAY_NAMES_SHORT and MONTH_NAMES are now loaded from translations inside components

/* ── Helpers ────────────────────────────────────── */

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function getToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatDateKey(year, month, day) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function getDayIdx(year, month, day) {
  const d = new Date(year, month - 1, day);
  return (d.getDay() + 6) % 7; // Monday = 0
}

/* ── Stories Date Bubble ────────────────────────── */

function DateBubble({ day, dayName, isToday, isSelected, count, types, onClick }) {
  const { t } = useTranslation();
  const hasContent = count > 0;

  // Get dominant type for ring color
  const dominantType = types
    ? Object.entries(types).sort((a, b) => b[1] - a[1])[0]?.[0]
    : null;

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-center gap-1.5 shrink-0 transition-all duration-300 group",
        "focus:outline-none",
        isSelected ? "scale-105" : "hover:scale-105"
      )}
    >
      {/* Ring container */}
      <div
        className={cn(
          "relative rounded-full p-[2.5px] transition-all duration-300",
          hasContent && !isSelected && "bg-gradient-to-br from-purple-500 via-pink-500 to-indigo-500",
          isSelected && "bg-gradient-to-br from-purple-400 via-pink-400 to-indigo-400 shadow-lg shadow-purple-500/25",
          !hasContent && !isSelected && "bg-border/50",
          isToday && !isSelected && hasContent && "shadow-md shadow-purple-500/20"
        )}
      >
        <div
          className={cn(
            "w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300",
            isSelected
              ? "bg-gradient-to-br from-purple-500 to-pink-500 text-white"
              : "bg-card",
            isToday && !isSelected && "bg-purple-500/5"
          )}
        >
          <span
            className={cn(
              "text-sm font-semibold transition-colors",
              isSelected && "text-white",
              !isSelected && hasContent && "text-foreground",
              !isSelected && !hasContent && "text-muted-foreground/60"
            )}
          >
            {day}
          </span>
        </div>

        {/* Content count badge */}
        {hasContent && (
          <div className={cn(
            "absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white transition-transform",
            "bg-gradient-to-br from-purple-500 to-pink-500",
            isSelected && "scale-110"
          )}>
            {count > 9 ? "9+" : count}
          </div>
        )}
      </div>

      {/* Day name */}
      <span
        className={cn(
          "text-[10px] font-medium transition-colors",
          isSelected ? "text-purple-500" : "text-muted-foreground/70",
          isToday && !isSelected && "text-purple-400"
        )}
      >
        {isToday ? t('calendar.today') : dayName}
      </span>
    </button>
  );
}

/* ── Generation Preview Card ────────────────────── */

function GenerationPreviewCard({ gen, index }) {
  const { t } = useTranslation();
  const type = typeConfig[gen.type] || typeConfig.tweet;
  const TypeIcon = type.icon;

  const handleCopy = (e) => {
    e.stopPropagation();
    if (gen.content) {
      navigator.clipboard.writeText(gen.content);
      toast.success(t('common.copied'));
    }
  };

  return (
    <div
      className={cn(
        "group relative p-4 rounded-2xl border border-border/50 bg-card/50 backdrop-blur-sm",
        "hover:border-purple-500/20 hover:shadow-sm transition-all duration-300",
        "animate-in slide-in-from-bottom-2 fade-in"
      )}
      style={{ animationDelay: `${index * 80}ms`, animationFillMode: "both" }}
    >
      <div className="flex items-start gap-3">
        {/* Type icon */}
        <div className={cn("p-2 rounded-xl shrink-0", type.bg)}>
          <TypeIcon className={cn("h-4 w-4", type.text)} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {gen.topic && (
            <p className="text-[11px] text-muted-foreground mb-1 truncate">
              {gen.topic}
            </p>
          )}
          <p className="text-sm leading-relaxed text-foreground/80 line-clamp-2">
            {gen.content || ""}
          </p>
        </div>

        {/* Actions */}
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (gen.content) {
                window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(gen.content)}`, "_blank");
              }
            }}
            className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-sky-500 transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Time */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/30">
        <Badge className={cn("text-[10px] gap-1 rounded-lg", type.bg, type.text)}>
          <TypeIcon className="h-2.5 w-2.5" /> {t(type.labelKey)}
        </Badge>
        <span className="text-[10px] text-muted-foreground">
          {gen.created_at
            ? new Date(gen.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
            : ""}
        </span>
      </div>
    </div>
  );
}

/* ── Main Calendar Component ────────────────────── */

export default function ContentCalendar({ embedded = false }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const scrollRef = useRef(null);
  const todayStr = getToday();
  const MONTH_NAMES = t('calendar.months', { returnObjects: true });
  const DAY_NAMES_SHORT = t('calendar.shortDays', { returnObjects: true });

  const [currentYear, setCurrentYear] = useState(() => new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(() => new Date().getMonth() + 1);
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const [calendarData, setCalendarData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch calendar data
  const fetchCalendar = useCallback(async (year, month) => {
    setLoading(true);
    try {
      const res = await api.get(`${API}/generations/calendar?year=${year}&month=${month}`);
      setCalendarData(res.data);
    } catch (e) {
      setCalendarData({ days: {}, streak: 0, total_this_month: 0 });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchCalendar(currentYear, currentMonth);
  }, [currentYear, currentMonth, fetchCalendar]);

  // Scroll to today on mount
  useEffect(() => {
    if (scrollRef.current) {
      const todayEl = scrollRef.current.querySelector('[data-today="true"]');
      if (todayEl) {
        // Only scroll horizontally within the calendar container, don't affect page scroll
        const container = scrollRef.current;
        const containerRect = container.getBoundingClientRect();
        const todayRect = todayEl.getBoundingClientRect();
        const scrollLeft = todayRect.left - containerRect.left - (containerRect.width / 2) + (todayRect.width / 2) + container.scrollLeft;
        container.scrollTo({ left: scrollLeft, behavior: "smooth" });
      }
    }
  }, [calendarData]);

  // Month navigation
  const goToPrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  const goToNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  const daysInMonth = getDaysInMonth(currentYear, currentMonth);
  const days = calendarData?.days || {};
  const streak = calendarData?.streak || 0;
  const totalThisMonth = calendarData?.total_this_month || 0;
  const selectedDayData = days[selectedDate];

  // Type summary for selected day
  const typeSummary = selectedDayData?.types
    ? Object.entries(selectedDayData.types)
        .map(([tp, c]) => `${c} ${typeConfig[tp]?.labelKey ? t(typeConfig[tp].labelKey) : tp}`)
        .join(" · ")
    : null;

  const isCurrentMonth =
    currentYear === new Date().getFullYear() &&
    currentMonth === new Date().getMonth() + 1;

  const Wrapper = embedded ? "div" : Card;
  const wrapperClass = embedded
    ? "h-full"
    : "rounded-3xl border-border/50 overflow-hidden shadow-lg shadow-black/[0.03] dark:shadow-black/20";

  return (
    <Wrapper className={wrapperClass}>
      {/* Gradient top accent */}
      {!embedded && <div className="h-[2px] bg-gradient-to-r from-purple-500 via-pink-500 to-indigo-500" />}

      <div className={embedded ? "p-5" : "p-6"}>
        {/* ── Header: Month nav + Stats ── */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-500/10">
              <Calendar className="h-5 w-5 text-purple-500" />
            </div>
            <div>
              <h3 className="font-outfit font-semibold text-lg">
                {MONTH_NAMES[currentMonth - 1]} {currentYear}
              </h3>
              <p className="text-xs text-muted-foreground">
                {totalThisMonth > 0
                  ? t('calendar.thisMonthGenerated', { count: totalThisMonth })
                  : t('calendar.noContentThisMonth')}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Streak badge */}
            {streak > 0 && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-orange-500/10 to-amber-500/10 border border-orange-500/20">
                <Flame className="h-4 w-4 text-orange-500" />
                <span className="text-sm font-semibold text-orange-500">{streak}</span>
                <span className="text-[10px] text-orange-500/70 hidden sm:inline">{t('calendar.dayStreak')}</span>
              </div>
            )}

            {/* Month nav */}
            <div className="flex items-center gap-1">
              <button
                onClick={goToPrevMonth}
                className="p-2 rounded-xl hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {!isCurrentMonth && (
                <button
                  onClick={() => {
                    const now = new Date();
                    setCurrentYear(now.getFullYear());
                    setCurrentMonth(now.getMonth() + 1);
                    setSelectedDate(todayStr);
                  }}
                  className="px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-purple-500/10 hover:bg-purple-500/20 transition-colors text-purple-500 border border-purple-500/20"
                >
                  {t('calendar.today')}
                </button>
              )}
              <button
                onClick={goToNextMonth}
                className="p-2 rounded-xl hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* ── Stories Date Roller ── */}
        <div className="relative mb-6">
          {/* Left fade */}
          <div className="absolute left-0 top-0 bottom-0 w-10 bg-gradient-to-r from-[hsl(var(--card))] to-transparent z-10 pointer-events-none rounded-l-xl" />
          {/* Right fade */}
          <div className="absolute right-0 top-0 bottom-0 w-10 bg-gradient-to-l from-[hsl(var(--card))] to-transparent z-10 pointer-events-none rounded-r-xl" />

          <div
            ref={scrollRef}
            className="flex gap-3 overflow-x-auto scrollbar-hide py-2 px-2 snap-x snap-mandatory"
            style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
          >
            {Array.from({ length: daysInMonth }, (_, i) => {
              const day = i + 1;
              const dateKey = formatDateKey(currentYear, currentMonth, day);
              const dayData = days[dateKey];
              const isToday = dateKey === todayStr;
              const isSelected = dateKey === selectedDate;

              return (
                <div key={day} data-today={isToday || undefined} className="snap-center">
                  <DateBubble
                    day={day}
                    dayName={DAY_NAMES_SHORT[getDayIdx(currentYear, currentMonth, day)]}
                    isToday={isToday}
                    isSelected={isSelected}
                    count={dayData?.count || 0}
                    types={dayData?.types}
                    onClick={() => setSelectedDate(dateKey)}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Selected Day Content ── */}
        <div className="min-h-[120px]">
          {selectedDayData && selectedDayData.count > 0 ? (
            <>
              {/* Summary bar */}
              <div className="flex items-center justify-between mb-4 p-3 rounded-2xl bg-purple-500/5 border border-purple-500/10">
                <div className="flex items-center gap-2">
                  <PenLine className="h-4 w-4 text-purple-500" />
                  <span className="text-sm font-medium">
                    {selectedDate === todayStr ? t('calendar.today') : new Date(selectedDate + "T00:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" })}
                    {" — "}
                    <span className="text-purple-500 font-semibold">{t('calendar.nContentGenerated', { count: selectedDayData.count })}</span>
                  </span>
                </div>
                {typeSummary && (
                  <span className="text-[11px] text-muted-foreground hidden sm:inline">
                    {typeSummary}
                  </span>
                )}
              </div>

              {/* Generation cards */}
              <div className="space-y-3">
                {selectedDayData.generations.map((gen, i) => (
                  <GenerationPreviewCard key={gen.id} gen={gen} index={i} />
                ))}
              </div>
            </>
          ) : (
            /* Empty state */
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-500/10 to-pink-500/10 flex items-center justify-center mb-3">
                <PenLine className="h-6 w-6 text-purple-500/40" />
              </div>
              <p className="text-sm text-muted-foreground mb-1">
                {selectedDate === todayStr
                  ? t('calendar.todayNoContent')
                  : t('calendar.dateSilent', { date: new Date(selectedDate + "T00:00:00").toLocaleDateString("tr-TR", { day: "numeric", month: "long" }) })}
              </p>
              {selectedDate === todayStr && (
                <>
                  <p className="text-xs text-muted-foreground/60 mb-4">
                    {t('calendar.needInspiration')}
                  </p>
                  <Button
                    size="sm"
                    onClick={() => navigate("/dashboard/create?platform=twitter")}
                    className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-xl gap-1.5"
                  >
                    <PenLine className="h-3.5 w-3.5" /> {t('calendar.generateContent')}
                  </Button>
                </>
              )}
            </div>
          )}
        </div>

        {/* ── Monthly Stats Strip ── */}
        {totalThisMonth > 0 && (
          <div className="flex items-center justify-between mt-5 pt-4 border-t border-border/30">
            {/* Type breakdown pills */}
            <div className="flex gap-2 flex-wrap">
              {Object.entries(
                Object.values(days).reduce((acc, d) => {
                  Object.entries(d.types).forEach(([t, c]) => {
                    acc[t] = (acc[t] || 0) + c;
                  });
                  return acc;
                }, {})
              ).map(([type, count]) => {
                const cfg = typeConfig[type] || typeConfig.tweet;
                const Icon = cfg.icon;
                return (
                  <div
                    key={type}
                    className={cn(
                      "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium",
                      cfg.bg, cfg.text
                    )}
                  >
                    <Icon className="h-3 w-3" />
                    {count} {t(cfg.labelKey)}
                  </div>
                );
              })}
            </div>

            {/* Monthly total */}
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <TrendingUp className="h-3.5 w-3.5" />
              <span>{t('calendar.totalThisMonth')} <span className="font-semibold text-foreground">{totalThisMonth}</span></span>
            </div>
          </div>
        )}
      </div>
    </Wrapper>
  );
}
