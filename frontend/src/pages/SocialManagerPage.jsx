import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import { Send, Plus, AlertCircle, Inbox, RefreshCw, CalendarDays, List } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { listPosts, listIntegrations } from "@/services/postizService";
import PostCard from "@/components/social/PostCard";
import ScheduleDialog from "@/components/social/ScheduleDialog";
import PlatformIcon, { platformLabel } from "@/components/social/PlatformIcon";
import ScheduleCalendar from "@/components/social/ScheduleCalendar";

const TAB_KEYS = [
  { key: "scheduled", label: "Planlı" },
  { key: "published", label: "Yayında" },
  { key: "failed",    label: "Hata" },
  { key: "all",       label: "Tümü" },
];

export default function SocialManagerPage() {
  // Phase 39.7 (Berkay 31 May 2026) — Calendar is the default view ("scheduled
  // calendar" as originally requested). List view kept as a toggle alternative.
  const [view, setView] = useState("calendar");
  const [tab, setTab] = useState("scheduled");
  const [platform, setPlatform] = useState("all");
  const [integrations, setIntegrations] = useState([]);
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  // Fetch integrations once for platform filter chips.
  useEffect(() => {
    listIntegrations()
      .then((res) => setIntegrations(res?.items || []))
      .catch(() => {/* non-fatal, ignore */});
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Calendar view shows ALL statuses across a wide window so the user can
      // page back to past weeks and see what was actually published, not just
      // future-planned posts. List view obeys the tab filter.
      const useCalendarScope = view === "calendar";
      const data = await listPosts({
        status: useCalendarScope ? undefined : (tab === "all" ? undefined : tab),
        platform: platform === "all" ? undefined : platform,
        days: useCalendarScope ? 90 : 60,
      });
      setPosts(data?.items || []);
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || "Postlar yüklenemedi";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [tab, platform, view]);

  useEffect(() => { refresh(); }, [refresh]);

  const counts = useMemo(() => {
    return {
      scheduled: posts.filter((p) => p.status === "scheduled").length,
      published: posts.filter((p) => p.status === "published").length,
      failed:    posts.filter((p) => p.status === "failed").length,
    };
  }, [posts]);

  function handleEdit(post) {
    setEditing(post);
    setScheduleOpen(true);
  }

  function handleClosed() {
    setScheduleOpen(false);
    setEditing(null);
  }

  function handleSuccess() {
    setScheduleOpen(false);
    setEditing(null);
    refresh();
  }

  function handleCancelled(postId) {
    setPosts((prev) => prev.filter((p) => p.id !== postId));
  }

  return (
    <div className={`${view === "calendar" ? "max-w-6xl" : "max-w-3xl"} mx-auto px-4 sm:px-0 pb-24 transition-all`}>
      {/* Header */}
      <header className="mb-7 mt-4">
        <div className="flex items-start gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/30">
            <Send className="h-5 w-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold font-outfit tracking-tight">
              Sosyal Medya
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Tüm hesaplarındaki postları tek yerden gör, planla ve düzenle.
            </p>
          </div>
          <Button
            onClick={() => { setEditing(null); setScheduleOpen(true); }}
            className="shrink-0 bg-gradient-to-br from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white border-0 shadow-lg shadow-sky-500/25 gap-2"
            size="sm"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Yeni Post</span>
          </Button>
        </div>
      </header>

      {/* Stat tiles */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <StatTile label="Planlı" value={counts.scheduled} color="amber" />
        <StatTile label="Yayında" value={counts.published} color="emerald" />
        <StatTile label="Hata" value={counts.failed} color="rose" />
      </div>

      {/* View toggle (Takvim / Liste) */}
      <div className="flex items-center gap-2 mb-4">
        <div className="inline-flex p-1 rounded-xl bg-card/80 backdrop-blur-xl border border-border/60">
          <ViewToggleButton active={view === "calendar"} onClick={() => setView("calendar")} icon={CalendarDays}>
            Takvim
          </ViewToggleButton>
          <ViewToggleButton active={view === "list"} onClick={() => setView("list")} icon={List}>
            Liste
          </ViewToggleButton>
        </div>
        {view === "list" && (
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="bg-card/80 backdrop-blur-xl border border-border/60 p-1 rounded-xl">
              {TAB_KEYS.map((t) => (
                <TabsTrigger
                  key={t.key}
                  value={t.key}
                  className="rounded-lg data-[state=active]:bg-gradient-to-br data-[state=active]:from-sky-500/20 data-[state=active]:to-indigo-500/20 data-[state=active]:text-sky-200 text-xs sm:text-sm"
                >
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
      </div>

      {/* Platform filter chips */}
      {integrations.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-5 text-xs">
          <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground/80 mr-1">
            Platform
          </span>
          <FilterChip active={platform === "all"} onClick={() => setPlatform("all")}>
            Tümü
          </FilterChip>
          {integrations.map((i) => (
            <FilterChip
              key={i.id}
              active={platform === i.identifier}
              onClick={() => setPlatform(i.identifier)}
            >
              <PlatformIcon identifier={i.identifier} className="h-3 w-3" />
              <span>{i.name || platformLabel(i.identifier)}</span>
            </FilterChip>
          ))}
          <button
            onClick={refresh}
            className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            title="Yenile"
          >
            <RefreshCw className="h-3 w-3" />
            Yenile
          </button>
        </div>
      )}

      {/* Body */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center">
          <AlertCircle className="h-6 w-6 text-rose-400 mx-auto mb-2" />
          <p className="text-sm font-medium text-rose-200">{error}</p>
          <Button variant="outline" size="sm" onClick={refresh} className="mt-3">
            Tekrar dene
          </Button>
        </div>
      ) : view === "calendar" ? (
        <ScheduleCalendar posts={posts} onSelectPost={handleEdit} />
      ) : posts.length === 0 ? (
        <div className="rounded-2xl border border-border/40 bg-card/60 backdrop-blur-xl p-12 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500/20 to-indigo-500/20 mb-3">
            <Inbox className="h-6 w-6 text-sky-300" />
          </div>
          <p className="text-base font-medium">Bu sekmede gösterilecek post yok</p>
          <p className="text-xs text-muted-foreground mt-1">
            {tab === "scheduled"
              ? "Planlanmış yeni post yaratmak için yukarıdaki '+ Yeni Post' butonunu kullan."
              : "Filtreyi değiştirerek diğer postları görebilirsin."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence>
            {posts.map((post) => (
              <PostCard key={post.id} post={post} onEdit={handleEdit} onCancelled={handleCancelled} />
            ))}
          </AnimatePresence>
        </div>
      )}

      <ScheduleDialog
        open={scheduleOpen}
        onClose={handleClosed}
        mode={editing ? "edit" : "create"}
        initialPost={editing}
        onSuccess={handleSuccess}
      />
    </div>
  );
}

function StatTile({ label, value, color }) {
  const ringMap = {
    amber:   "from-amber-500/15 to-amber-500/5 text-amber-300 border-amber-500/20",
    emerald: "from-emerald-500/15 to-emerald-500/5 text-emerald-300 border-emerald-500/20",
    rose:    "from-rose-500/15 to-rose-500/5 text-rose-300 border-rose-500/20",
  };
  return (
    <div className={`rounded-2xl border bg-gradient-to-br ${ringMap[color]} backdrop-blur-xl px-4 py-3`}>
      <p className="text-[10.5px] uppercase tracking-wider text-muted-foreground/80">{label}</p>
      <p className="text-2xl font-bold font-mono mt-0.5">{value}</p>
    </div>
  );
}

function ViewToggleButton({ active, onClick, icon: Icon, children }) {
  return (
    <button
      onClick={onClick}
      className={[
        "inline-flex items-center gap-1.5 px-3 h-8 rounded-lg text-xs font-medium transition-colors",
        active
          ? "bg-gradient-to-br from-sky-500/20 to-indigo-500/20 text-sky-200"
          : "text-muted-foreground hover:text-foreground",
      ].join(" ")}
    >
      <Icon className="h-3.5 w-3.5" />
      {children}
    </button>
  );
}

function FilterChip({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={[
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-colors",
        active
          ? "border-sky-500/50 bg-sky-500/10 text-sky-200"
          : "border-border/40 bg-secondary/30 text-muted-foreground hover:bg-secondary/50 hover:text-foreground",
      ].join(" ")}
    >
      {children}
    </button>
  );
}
