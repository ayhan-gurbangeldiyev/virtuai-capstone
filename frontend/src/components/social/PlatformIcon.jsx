import {
  Twitter, Linkedin, Youtube, Instagram, Facebook,
  BookOpen, Newspaper, Globe, Music2,
} from "lucide-react";

// Phase 36 — Mini platform icon + brand color mapping (premium dark mode).
// Identifier comes from Postiz `integration.identifier` (e.g. "x",
// "linkedin", "linkedin-page", "youtube", "instagram", "devto", "medium",
// "tiktok", "facebook", "threads", "bluesky"). Unknown identifiers fall
// back to a neutral globe.

const SPEC = {
  x:                    { Icon: Twitter,   className: "text-sky-400",     label: "X" },
  twitter:              { Icon: Twitter,   className: "text-sky-400",     label: "X" },
  linkedin:             { Icon: Linkedin,  className: "text-blue-500",    label: "LinkedIn" },
  "linkedin-page":      { Icon: Linkedin,  className: "text-blue-500",    label: "LinkedIn" },
  youtube:              { Icon: Youtube,   className: "text-red-500",     label: "YouTube" },
  instagram:            { Icon: Instagram, className: "text-pink-500",    label: "Instagram" },
  "instagram-standalone": { Icon: Instagram, className: "text-pink-500",  label: "Instagram" },
  facebook:             { Icon: Facebook,  className: "text-blue-600",    label: "Facebook" },
  devto:                { Icon: BookOpen,  className: "text-emerald-400", label: "Dev.to" },
  medium:               { Icon: Newspaper, className: "text-zinc-300",    label: "Medium" },
  tiktok:               { Icon: Music2,    className: "text-rose-400",    label: "TikTok" },
};

export default function PlatformIcon({ identifier, className = "h-4 w-4", showLabel = false }) {
  const spec = SPEC[(identifier || "").toLowerCase()] || {
    Icon: Globe,
    className: "text-muted-foreground",
    label: identifier || "Diğer",
  };
  const { Icon, className: iconClass, label } = spec;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon className={`${className} ${iconClass}`} />
      {showLabel && <span className="text-xs font-medium">{label}</span>}
    </span>
  );
}

export function platformLabel(identifier) {
  return (SPEC[(identifier || "").toLowerCase()] || { label: identifier }).label;
}
