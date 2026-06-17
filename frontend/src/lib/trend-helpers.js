import {
  Brain, Code, Palette, Bitcoin, Rocket, Megaphone, Briefcase,
  FlaskConical, Heart, GraduationCap, Gamepad2, Newspaper,
} from "lucide-react";

/* ── Time helpers ── */

export function timeAgo(dateString) {
  if (!dateString) return null;
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now - date;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "az \u00f6nce";
  if (diffMin < 60) return `${diffMin} dk \u00f6nce`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} saat \u00f6nce`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return "d\u00fcn";
  if (diffD < 7) return `${diffD} g\u00fcn \u00f6nce`;
  return date.toLocaleDateString("tr-TR");
}

export function hoursAgo(dateString) {
  if (!dateString) return Infinity;
  return (Date.now() - new Date(dateString).getTime()) / 3600000;
}

export function formatEngagement(num) {
  if (!num || num <= 0) return null;
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return String(num);
}

/* ── Category maps ── */

export const CATEGORY_LABELS = {
  AI: "Yapay Zek\u00e2",
  Dev: "Yaz\u0131l\u0131m",
  Design: "Tasar\u0131m",
  Crypto: "Kripto",
  Startup: "Giri\u015fim",
  Marketing: "Pazarlama",
  Business: "\u0130\u015f D\u00fcnyas\u0131",
  Science: "Bilim",
  Lifestyle: "Ya\u015fam",
  Education: "E\u011fitim",
  Entertainment: "E\u011flence",
  News: "G\u00fcndem",
};

export const CATEGORY_ICONS = {
  ai: Brain, dev: Code, design: Palette, crypto: Bitcoin,
  startup: Rocket, marketing: Megaphone, business: Briefcase,
  science: FlaskConical, lifestyle: Heart, education: GraduationCap,
  entertainment: Gamepad2, news: Newspaper,
};

/* ── Content generation ── */

export const PILLAR_CONFIG = {
  insight: { emoji: "\ud83d\udca1", gradient: "from-blue-500 to-cyan-500" },
  building: { emoji: "\ud83d\udd28", gradient: "from-green-500 to-emerald-500" },
  hot_take: { emoji: "\ud83d\udd25", gradient: "from-fuchsia-500 to-purple-500" },
  engagement: { emoji: "\ud83d\udcac", gradient: "from-violet-500 to-purple-500" },
};

export const TIER_COLORS = {
  1: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  2: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  3: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

export const PLATFORMS = [
  { id: "twitter", label: "X", emoji: "\ud835\udd4f" },
  { id: "blog", label: "Blog", emoji: "\ud83d\udcdd" },
  { id: "linkedin", label: "LinkedIn", emoji: "\ud83d\udcbc" },
  { id: "instagram", label: "Instagram", emoji: "\ud83d\udcf8" },
  { id: "youtube", label: "YouTube", emoji: "\u25b6\ufe0f" },
  { id: "tiktok", label: "TikTok", emoji: "\ud83c\udfb5" },
];
