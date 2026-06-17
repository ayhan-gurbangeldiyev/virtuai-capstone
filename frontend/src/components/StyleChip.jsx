/**
 * StyleChip — Draft kartlarında hangi stille içerik üretildiğini gösteren küçük pill badge.
 *
 * Props:
 *   styleType  "own_voice" | "cloned" | "archetype"
 *   styleName  Gösterilecek isim
 *   size       "sm" (default) | "md"
 */
import { cn } from "@/lib/utils";

const STYLE_ICONS = {
  own_voice: "🎤",
  cloned: "👤",
  archetype: "📐",
};

export default function StyleChip({ styleType, styleName, size = "sm" }) {
  const icon = STYLE_ICONS[styleType] ?? "✨";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium",
        "bg-violet-500/10 text-violet-400 border border-violet-500/20",
        size === "sm"
          ? "text-[10px] px-2 py-0.5"
          : "text-xs px-2.5 py-1"
      )}
    >
      <span aria-hidden="true">{icon}</span>
      {styleName && (
        <span className="truncate max-w-[120px]">{styleName}</span>
      )}
    </span>
  );
}
