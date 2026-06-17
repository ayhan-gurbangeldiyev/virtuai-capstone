/**
 * TagInput — chip input. Add with Enter or comma, remove with backspace or X.
 */
import { useState } from "react";
import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export default function TagInput({
  value = [],
  onChange,
  placeholder,
  presets = [],
  max = 30,
  validate,
}) {
  const [draft, setDraft] = useState("");

  const add = (raw) => {
    const v = (raw || "").trim().replace(/^,+|,+$/g, "");
    if (!v) return;
    if (value.includes(v)) return;
    if (value.length >= max) return;
    if (validate && !validate(v)) return;
    onChange([...value, v]);
    setDraft("");
  };

  const remove = (idx) => {
    const next = value.filter((_, i) => i !== idx);
    onChange(next);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      remove(value.length - 1);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5 min-h-[40px] rounded-lg border border-border/60 bg-card px-2 py-2 focus-within:border-purple-500/50 focus-within:ring-1 focus-within:ring-purple-500/20 transition">
        {value.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/30"
          >
            {v}
            <button
              type="button"
              onClick={() => remove(i)}
              className="hover:text-rose-500 transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKey}
          onBlur={() => draft && add(draft)}
          placeholder={value.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[80px] bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>

      {presets.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {presets
            .filter((p) => !value.includes(p))
            .map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => add(p)}
                className="px-2 py-0.5 rounded-md text-[11px] text-muted-foreground bg-secondary/50 hover:bg-purple-500/10 hover:text-purple-600 dark:hover:text-purple-300 border border-border/40 hover:border-purple-500/30 transition"
              >
                + {p}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
