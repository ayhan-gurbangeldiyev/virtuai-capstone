/**
 * TrendSourcesSheet — manage the X account list that feeds the trends pipeline.
 *
 * - 3 tabs: AI/Tech, Haber, Spor
 * - Each tab: chip list + add input + toggle/remove buttons
 * - Optimistic updates with rollback on error
 */
import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { X, Plus, Power, PowerOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import {
  listTrendSources,
  addTrendSource,
  removeTrendSource,
  toggleTrendSource,
} from "@/services/trendSourcesService";
import { cn } from "@/lib/utils";

// Live AI batches first (operator-managed), legacy/inactive batches last.
const BATCHES = ["ai_core", "ai_news_en", "ai_news_tr", "ai_tech", "tr_haber", "spor"];
const EMPTY_SOURCES = {
  ai_core: [],
  ai_news_en: [],
  ai_news_tr: [],
  ai_tech: [],
  tr_haber: [],
  spor: [],
};
const HANDLE_RE = /^[A-Za-z0-9_]{1,30}$/;

export default function TrendSourcesSheet({ open, onClose }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState("ai_core");
  const [sources, setSources] = useState(EMPTY_SOURCES);
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listTrendSources();
      setSources({ ...EMPTY_SOURCES, ...(data.sources || {}) });
    } catch (e) {
      toast.error(t("trends.sources.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (open) refresh();
  }, [open, refresh]);

  const handleAdd = async () => {
    const handle = draft.trim().replace(/^@/, "");
    if (!handle) return;
    if (!HANDLE_RE.test(handle)) {
      toast.error(t("trends.sources.invalid"));
      return;
    }
    if ((sources[tab] || []).some((s) => s.username.toLowerCase() === handle.toLowerCase())) {
      toast.error(t("trends.sources.duplicate"));
      return;
    }
    setDraft("");
    // Optimistic
    const temp = {
      id: `temp-${Date.now()}`,
      batch_type: tab,
      username: handle,
      is_active: true,
      fetch_limit: null,
      _pending: true,
    };
    setSources((prev) => ({ ...prev, [tab]: [...(prev[tab] || []), temp] }));
    try {
      const created = await addTrendSource({ batch_type: tab, username: handle });
      setSources((prev) => ({
        ...prev,
        [tab]: prev[tab].map((s) => (s.id === temp.id ? created : s)),
      }));
      toast.success(t("trends.sources.added", { username: handle }));
    } catch (e) {
      setSources((prev) => ({
        ...prev,
        [tab]: prev[tab].filter((s) => s.id !== temp.id),
      }));
      if (e?.response?.status === 409) toast.error(t("trends.sources.duplicate"));
      else toast.error(t("trends.sources.invalid"));
    }
  };

  const handleRemove = async (source) => {
    const prevList = sources[source.batch_type] || [];
    setSources((prev) => ({
      ...prev,
      [source.batch_type]: prev[source.batch_type].filter((s) => s.id !== source.id),
    }));
    try {
      await removeTrendSource(source.id);
      toast.success(t("trends.sources.removed", { username: source.username }));
    } catch (e) {
      setSources((prev) => ({ ...prev, [source.batch_type]: prevList }));
      toast.error(t("common.error"));
    }
  };

  const handleToggle = async (source) => {
    const next = !source.is_active;
    setSources((prev) => ({
      ...prev,
      [source.batch_type]: prev[source.batch_type].map((s) =>
        s.id === source.id ? { ...s, is_active: next } : s
      ),
    }));
    try {
      await toggleTrendSource(source.id);
      toast.success(
        t("trends.sources.toggled", {
          username: source.username,
          state: next ? t("trends.sources.activated") : t("trends.sources.deactivated"),
        })
      );
    } catch (e) {
      setSources((prev) => ({
        ...prev,
        [source.batch_type]: prev[source.batch_type].map((s) =>
          s.id === source.id ? { ...s, is_active: source.is_active } : s
        ),
      }));
      toast.error(t("common.error"));
    }
  };

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle className="font-outfit">{t("trends.sources.title")}</SheetTitle>
          <SheetDescription>{t("trends.sources.description")}</SheetDescription>
        </SheetHeader>

        <div className="py-5">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="grid grid-cols-3 w-full bg-card border border-border/60 p-1 rounded-xl">
              {BATCHES.map((b) => (
                <TabsTrigger
                  key={b}
                  value={b}
                  className="rounded-lg data-[state=active]:bg-purple-500/10 data-[state=active]:text-purple-600 dark:data-[state=active]:text-purple-300 text-xs sm:text-sm"
                >
                  {t(`trends.sources.batches.${b}`)}
                  <span className="ml-1.5 text-[10px] text-muted-foreground font-mono">
                    {(sources[b] || []).length}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>

            {BATCHES.map((b) => (
              <TabsContent key={b} value={b} className="mt-4 space-y-3">
                {/* Add row */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={tab === b ? draft : ""}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAdd();
                      }
                    }}
                    placeholder={t("trends.sources.addPlaceholder")}
                    className="flex-1 h-10 px-3 rounded-lg border border-border/60 bg-card text-sm focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 outline-none transition"
                  />
                  <Button
                    onClick={handleAdd}
                    size="sm"
                    className="h-10 px-4 gap-1.5 bg-purple-600 hover:bg-purple-700 text-white"
                    disabled={!draft.trim()}
                  >
                    <Plus className="h-4 w-4" />
                    {t("common.add")}
                  </Button>
                </div>

                {/* List */}
                {loading ? (
                  <div className="flex items-center justify-center py-10 text-muted-foreground text-sm gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t("common.loading")}
                  </div>
                ) : (sources[b] || []).length === 0 ? (
                  <div className="text-center text-sm text-muted-foreground py-10">
                    {t("trends.sources.empty")}
                  </div>
                ) : (
                  <ul className="space-y-1.5">
                    <AnimatePresence initial={false}>
                      {sources[b].map((s) => (
                        <SourceRow
                          key={s.id}
                          source={s}
                          onToggle={() => handleToggle(s)}
                          onRemove={() => handleRemove(s)}
                        />
                      ))}
                    </AnimatePresence>
                  </ul>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function SourceRow({ source, onToggle, onRemove }) {
  const inactive = source.is_active === false;
  return (
    <motion.li
      layout
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 8 }}
      transition={{ duration: 0.15 }}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded-lg border bg-card transition",
        inactive
          ? "border-border/40 opacity-50"
          : "border-border/60 hover:border-purple-500/30"
      )}
    >
      <span
        className={cn(
          "font-mono text-sm flex-1 truncate",
          inactive && "line-through"
        )}
      >
        @{source.username}
      </span>
      {source._pending && (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
      )}
      <button
        type="button"
        onClick={onToggle}
        title={inactive ? "Aktif et" : "Pasif et"}
        className="p-1.5 rounded-md hover:bg-secondary/60 text-muted-foreground hover:text-foreground transition-colors"
      >
        {inactive ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
      </button>
      <button
        type="button"
        onClick={onRemove}
        title="Kaldır"
        className="p-1.5 rounded-md hover:bg-rose-500/10 text-muted-foreground hover:text-rose-500 transition-colors"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </motion.li>
  );
}
