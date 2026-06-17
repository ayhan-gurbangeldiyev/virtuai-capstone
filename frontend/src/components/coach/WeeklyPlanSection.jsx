import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Calendar, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const DAY_NAMES = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];

function daysAgo(isoDate) {
  if (!isoDate) return "";
  const created = new Date(isoDate);
  const now = new Date();
  const diffMs = now - created;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Bugün";
  if (diffDays === 1) return "Dün";
  return `${diffDays} gün önce`;
}

export default function WeeklyPlanSection({ plan, weeklyGoal, cached, createdAt, onGenerate, onWrite, generating }) {
  const { t } = useTranslation();
  // Plan bugünden başlıyor, ilk gün = bugün
  const todayPlanIdx = 0;

  // Empty state
  if (!plan) {
    return (
      <div className="mb-8">
        <h2 className="font-outfit text-lg font-bold mb-4 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-cyan-400" />
          {t("coach.weeklyPlan")}
        </h2>
        <div className="rounded-xl border border-dashed border-white/10 p-8 text-center">
          <Calendar className="h-10 w-10 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground mb-4">{t("coach.plan.empty")}</p>
          <Button
            onClick={onGenerate}
            disabled={generating}
            className="bg-gradient-to-r from-cyan-500 to-emerald-500 hover:from-cyan-600 hover:to-emerald-600 text-white"
          >
            {generating ? (
              <><Loader2 className="h-4 w-4 animate-spin mr-2" /> {t("coach.plan.creating")}</>
            ) : (
              t("coach.plan.create")
            )}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-outfit text-lg font-bold flex items-center gap-2">
          <Calendar className="h-5 w-5 text-cyan-400" />
          {t("coach.weeklyPlan")}
        </h2>
        <div className="flex items-center gap-3">
          {cached && createdAt && (
            <span className="text-[11px] text-muted-foreground">
              {daysAgo(createdAt)} {t("coach.plan.cachedLabel") || "oluşturuldu"}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onGenerate}
            disabled={generating}
            className="text-xs h-7 text-muted-foreground hover:text-foreground"
          >
            {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {weeklyGoal && (
        <p className="text-xs text-muted-foreground mb-3 px-1">
          🎯 {weeklyGoal}
        </p>
      )}

      <div className="space-y-2">
        {(plan || []).map((day, i) => {
          const isToday = i === todayPlanIdx;
          return (
            <div
              key={i}
              className={cn(
                "flex items-center gap-3 p-3 rounded-xl border transition-colors",
                isToday
                  ? "border-cyan-500/30 bg-cyan-500/5"
                  : "border-white/5 bg-white/[0.02] hover:border-white/10"
              )}
            >
              {/* Day + Time */}
              <div className="w-20 shrink-0">
                <p className={cn("text-sm font-medium", isToday && "text-cyan-400")}>
                  {day.day}
                  {isToday && <span className="text-[10px] ml-1">•</span>}
                </p>
                <p className="text-[11px] text-muted-foreground">{day.best_time}</p>
              </div>

              {/* Topic */}
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{day.topic_suggestion}</p>
                {day.reasoning && (
                  <p className="text-[11px] text-muted-foreground truncate mt-0.5">{day.reasoning}</p>
                )}
              </div>

              {/* Badges */}
              <div className="flex gap-1 shrink-0">
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                  {day.content_type}
                </Badge>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
                  {day.persona}
                </Badge>
              </div>

              {/* Write button */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onWrite(day)}
                className="shrink-0 text-xs h-7 text-muted-foreground hover:text-foreground"
              >
                {t("coach.plan.write")}
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
