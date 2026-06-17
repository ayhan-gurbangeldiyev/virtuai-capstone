/**
 * Phase 27 — Executive personas (UI-only mapping).
 *
 * Roles in the DB stay as enum (CEO/CPO/CBPO/CFO/CRO). In the UI we
 * present them as humanlike personas with a name, title, emoji avatar
 * and accent color. This makes the Executive Board feel like a team
 * rather than a sysadmin dashboard.
 */

export const PERSONAS = {
  CEO: {
    name: "Berkay",
    titleKey: "executive.roles.CEO.title",
    titleFallback: "Stratejik Direktör",
    avatar: "🎯",
    color: "purple",
    accent: {
      ring: "ring-purple-500/30",
      border: "border-purple-500/30",
      bg: "bg-purple-500/10",
      text: "text-purple-300",
      dot: "bg-purple-500",
      left: "border-l-purple-500",
    },
    summary: "Vizyon + büyük stratejik kararlar",
  },
  CPO: {
    name: "Ayhan",
    titleKey: "executive.roles.CPO.title",
    titleFallback: "Sistem Yöneticisi",
    avatar: "⚙️",
    color: "blue",
    accent: {
      ring: "ring-blue-500/30",
      border: "border-blue-500/30",
      bg: "bg-blue-500/10",
      text: "text-blue-300",
      dot: "bg-blue-500",
      left: "border-l-blue-500",
    },
    summary: "Pipeline sağlığı, model seçimi, çalışma süresi",
  },
  CBPO: {
    name: "Didem",
    titleKey: "executive.roles.CBPO.title",
    titleFallback: "Marka Sorumlusu",
    avatar: "🎨",
    color: "emerald",
    accent: {
      ring: "ring-emerald-500/30",
      border: "border-emerald-500/30",
      bg: "bg-emerald-500/10",
      text: "text-emerald-300",
      dot: "bg-emerald-500",
      left: "border-l-emerald-500",
    },
    summary: "Marka tonu, içerik karışımı, görsel kimlik",
  },
  CFO: {
    name: "Yiğit",
    titleKey: "executive.roles.CFO.title",
    titleFallback: "Finans Sorumlusu",
    avatar: "💰",
    color: "amber",
    accent: {
      ring: "ring-amber-500/30",
      border: "border-amber-500/30",
      bg: "bg-amber-500/10",
      text: "text-amber-300",
      dot: "bg-amber-500",
      left: "border-l-amber-500",
    },
    summary: "Maliyet kontrolü, bütçe, kar/zarar",
  },
  CRO: {
    name: "Simge",
    titleKey: "executive.roles.CRO.title",
    titleFallback: "Risk Sorumlusu",
    avatar: "🛡️",
    color: "rose",
    accent: {
      ring: "ring-rose-500/30",
      border: "border-rose-500/30",
      bg: "bg-rose-500/10",
      text: "text-rose-300",
      dot: "bg-rose-500",
      left: "border-l-rose-500",
    },
    summary: "Marka güvenliği, uyumsuzluk, kriz yönetimi",
  },
};

export const ROLE_ORDER = ["CEO", "CPO", "CBPO", "CFO", "CRO"];

export function getPersona(role) {
  return PERSONAS[role] || {
    name: role || "Bilinmiyor",
    titleFallback: "",
    avatar: "👤",
    color: "muted",
    accent: {
      ring: "ring-border",
      border: "border-border",
      bg: "bg-muted/30",
      text: "text-muted-foreground",
      dot: "bg-muted-foreground",
      left: "border-l-muted-foreground",
    },
    summary: "",
  };
}
