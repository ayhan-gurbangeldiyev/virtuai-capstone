import { Brain, Newspaper, Trophy, Bell } from "lucide-react";

const MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

export function formatRelativeTime(dateStr) {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "az önce";
  if (diffMin < 60) return `${diffMin}dk önce`;
  if (diffHour < 24) return `${diffHour}s önce`;
  if (diffDay < 7) return `${diffDay}g önce`;

  const d = new Date(dateStr);
  return `${d.getDate()} ${MONTHS_TR[d.getMonth()]}`;
}

export function formatNumber(n) {
  if (n < 1000) return n.toString();
  if (n < 10000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  if (n < 1000000) return `${Math.round(n / 1000)}K`;
  if (n < 10000000) return `${(n / 1000000).toFixed(1).replace(/\.0$/, "")}M`;
  return `${Math.round(n / 1000000)}M`;
}

export function getCategoryConfig(batchType) {
  const map = {
    ai_tech: { color: "#3B82F6", bgColor: "rgba(59,130,246,0.1)", icon: Brain, label: "AI/Tech" },
    tr_haber: { color: "#EF4444", bgColor: "rgba(239,68,68,0.1)", icon: Newspaper, label: "Haber" },
    spor: { color: "#22C55E", bgColor: "rgba(34,197,94,0.1)", icon: Trophy, label: "Spor" },
    monitor: { color: "#F97316", bgColor: "rgba(249,115,22,0.1)", icon: Bell, label: "Monitor" },
  };
  return map[batchType];
}

