/**
 * Phase 43.E — Quality Audit relative-time helper.
 * Mirrors Phase 32's formatRelativeTime in DraftCard.jsx; isolated here
 * so the quality-audit folder doesn't reach into auto-drafts.
 */
export function formatRelativeTime(date) {
  if (!date) return null;
  const diffMs = Date.now() - new Date(date).getTime();
  if (diffMs < 0) return "az önce";
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "az önce";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} dk önce`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} saat önce`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay} gün önce`;
  const diffWeek = Math.floor(diffDay / 7);
  if (diffWeek < 4) return `${diffWeek} hafta önce`;
  const diffMonth = Math.floor(diffDay / 30);
  return `${diffMonth} ay önce`;
}

export function formatMonthLabel(monthIsoOrDate) {
  if (!monthIsoOrDate) return "—";
  const d = new Date(monthIsoOrDate);
  if (Number.isNaN(d.getTime())) return String(monthIsoOrDate);
  try {
    return d.toLocaleDateString("tr-TR", {
      year: "numeric",
      month: "long",
      timeZone: "Europe/Istanbul",
    });
  } catch {
    return String(monthIsoOrDate);
  }
}

export function formatFullDateTime(date) {
  if (!date) return null;
  try {
    return new Date(date).toLocaleString("tr-TR", {
      timeZone: "Europe/Istanbul",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(date);
  }
}
