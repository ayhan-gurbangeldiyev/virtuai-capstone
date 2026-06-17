import { useEffect, useState } from "react";
import { useTranslation } from 'react-i18next';
import { Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";

const TYPE_LABEL_KEYS = {
  tweet: "generation.queue.tweetGeneration",
  quote: "generation.queue.quoteGeneration",
  reply: "generation.queue.replyGeneration",
  article: "generation.queue.articleGeneration",
};

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function QueueItem({ job, onDismiss }) {
  const { t } = useTranslation();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (job.status !== "generating") return;
    const start = job.startedAt || Date.now();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [job.status, job.startedAt]);

  const typeLabel = TYPE_LABEL_KEYS[job.type] ? t(TYPE_LABEL_KEYS[job.type]) : t("generation.queue.contentGeneration");

  return (
    <div
      className={cn(
        "flex items-center gap-3 p-4 rounded-xl bg-card border shadow-xl min-w-[320px]",
        "border-orange-500/30 animate-in slide-in-from-right duration-300"
      )}
    >
      {/* Spinning Loader */}
      <div className="shrink-0">
        <Loader2 className="h-5 w-5 animate-spin text-orange-400" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-orange-400">{t('generation.queue.generating')}</p>
        <p className="text-xs text-muted-foreground truncate mt-0.5">
          {typeLabel} · {job.topic}
        </p>
      </div>

      {/* Timer + Dismiss */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-xs text-muted-foreground tabular-nums">
          {formatElapsed(elapsed)}
        </span>
        <button
          onClick={() => onDismiss(job.id)}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default function FloatingQueue({ jobs, onDismiss }) {
  // Only show generating jobs, max 3 visible
  const activeJobs = jobs
    .filter((j) => j.status === "generating")
    .slice(0, 3);

  if (activeJobs.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
      {activeJobs.map((job) => (
        <QueueItem key={job.id} job={job} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
