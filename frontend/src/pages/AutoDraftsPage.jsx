/**
 * AutoDraftsPage — Hype Crew approval console.
 *
 * One page, tab-based IA:
 *   Pending / Approved / Rejected / All
 *
 * Each card: trend topic, content, voice score, scheduling countdown,
 * collapsible "how Hype Crew thought" details, and 3 actions
 * (approve, reject, edit). Reject/edit open dialogs that write feedback
 * to memory.
 *
 * Sub-components live in components/auto-drafts/* to keep this file slim.
 */
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Settings, Zap, Sparkles, AlertCircle } from "lucide-react";
import { toast } from "sonner";

import { useAccount } from "@/contexts/AccountContext";
import { supabase, isSupabaseConfigured } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import {
  listAutoDrafts,
  approveDraft,
  rejectDraft,
  cancelApprovedDraft,
  getConfig,
  updateConfig,
} from "@/services/hypeService";

import DraftCard from "@/components/auto-drafts/DraftCard";
import ThreadCard from "@/components/auto-drafts/ThreadCard";
import IterationDialog from "@/components/auto-drafts/IterationDialog";
import HypeConfigSheet from "@/components/auto-drafts/HypeConfigSheet";
import { approveThread } from "@/services/hypeService";
import { safeAction, createKeyboardDebouncer } from "@/lib/safeAction";
import EmptyState from "@/components/auto-drafts/EmptyState";
import StatsRow from "@/components/auto-drafts/StatsRow";
import OnboardingTour from "@/components/auto-drafts/OnboardingTour";
import ExecutiveBoard from "@/components/exec/ExecutiveBoard";

// Phase 34.1 — Executive Board tab gizlendi. Daemon (hype-exec) Hetzner'da
// stop+disable edildi. ExecutiveBoard import + conditional render dead code
// olarak kalıyor — multi-persona ortamına geçilince geri açılır.
// Phase 41.A — 5 tab → 3 (Critic finding: Rejected ve All redundant view'lar).
// "history" tek arşiv tab — backend "all" status filter ile her ikisini birden gösterir.
const TABS = ["pending", "history"];

export default function AutoDraftsPage() {
  const { t } = useTranslation();
  const { activeAccountId, activeAccount } = useAccount();

  const [tab, setTab] = useState("pending");
  const [platformFilter, setPlatformFilter] = useState("all");  // Phase 20
  const [sortOrder, setSortOrder] = useState("newest");  // Phase 39.9 — sort control
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [config, setConfig] = useState(null);

  // Phase 28.Q — RejectDialog kaldırıldı. Iterate (IterationDialog) iç scope picker
  // ile image-only flow'u kapsadı. "Sil" doğrudan reject API çağırır (1-click confirm).
  const [iterTarget, setIterTarget] = useState(null);
  const [configOpen, setConfigOpen] = useState(false);

  // Map tab → backend status filter
  // Phase 28.R-Lite-V2: backend now unifies legacy and modern values, so we
  // can pass the canonical name and let it match both ('approved' OR
  // 'auto_approved', 'rejected' OR 'auto_rejected').
  const statusFilter = useMemo(() => {
    if (tab === "pending") return "pending";
    // Phase 41.A — "history" = approved + rejected + cancelled birleşik
    return "all";
  }, [tab]);

  // 2026-06-10 — onayı süren thread'ler (approve gate+arbiter ile 60-90sn
  // sürebiliyor). Periyodik refresh, backend statüleri flip etmeden draftları
  // hâlâ pending gördüğünden optimistic-hide edilen kartı GERİ getiriyordu →
  // operatör tekrar tıklayıp çift approve tetikliyordu (96d1157f çift Postiz
  // schedule vakası; backend'de de 'approving' kilidi var, bu UX tarafı).
  const inFlightThreadsRef = useRef(new Set());

  // ── Fetch drafts ──────────────────────────────────────────
  const refresh = useCallback(async () => {
    if (!activeAccountId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Phase 28 Fix 2 — backend route already scopes to .eq("user_id", user.id),
      // so omitting account_id (which is platform-specific) returns drafts from
      // ALL of the user's connected platform accounts. We always omit account_id
      // and let `platform` do the filtering when a specific chip is selected.
      const isAllPlatforms = platformFilter === "all";
      const data = await listAutoDrafts({
        accountId: undefined,
        status: statusFilter,
        platform: isAllPlatforms ? undefined : platformFilter,
        limit: 200,
      });
      const items = (data.items || []).filter(
        (d) => !inFlightThreadsRef.current.has(d.content_thread_id)
      );
      setDrafts(items);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Failed");
    } finally {
      setLoading(false);
    }
  }, [activeAccountId, statusFilter, platformFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  // Berkay 6 Haz 2026 — long-open tab staleness fix. Without this, a
  // user who left the page open before a server-side draft edit (PR #17
  // in-place caption update was the trigger case) would keep seeing
  // their initial fetch's content forever, because there's no
  // auto-refetch and `refresh()` only fires when filters change. Two
  // signals that cheaply catch DB drift without spamming the API:
  //   (1) 30s interval polling while the tab is visible
  //   (2) immediate refetch when the tab becomes visible again
  useEffect(() => {
    if (!activeAccountId) return undefined;
    const POLL_MS = 30_000;
    const tick = () => {
      if (document.visibilityState === "visible") refresh();
    };
    const intervalId = setInterval(tick, POLL_MS);
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [activeAccountId, refresh]);

  // ── Fetch config (for dry-run badge + auto-publish state) ──
  useEffect(() => {
    if (!activeAccountId) return;
    getConfig(activeAccountId).then(setConfig).catch(() => setConfig(null));
  }, [activeAccountId]);

  // ── Actions ──────────────────────────────────────────────
  // Phase 41.A — safeAction undo snackbar. Tıklamada optimistic UI uygular,
  // 5sn boyunca Geri Al butonu gösterir. Geri Al tıklanırsa API call atılmaz,
  // kart geri eklenir. Berkay'ın "bir anda bişeye bastın mı gidiyor" şikayet
  // edilmesinin nihai çözümü (sub-agent /debate 1 Haz 2026 konsensüsü).
  const bumpActionCount = useCallback(() => {
    try {
      const cur = Number(localStorage.getItem("autoDraftsActionCount") || 0);
      localStorage.setItem("autoDraftsActionCount", String(cur + 1));
    } catch { /* localStorage unavailable */ }
  }, []);

  const handleApprove = useCallback(async (draft) => {
    // 7 Haz 2026 fix — fire the POST IMMEDIATELY. The previous safeAction
    // wrapper deferred onCommit inside a 5s setTimeout (for "Geri Al" undo),
    // but a page refresh / navigation within that window destroyed the
    // setTimeout and the POST never fired. Symptom: operator clicks Onayla,
    // optimistic UI hides the draft, then on refresh the draft reappears
    // and the journal shows OPTIONS preflight without a matching POST.
    // The iteration-dialog approve uses immediate await and works — same
    // pattern applied here. Toast is fired-and-forget; success is the
    // optimistic UI removal + the new postiz_post_id materializing on
    // next refresh.
    setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
    bumpActionCount();
    try {
      await approveDraft(draft.id);
      toast.success(t("autoDrafts.approve.snackbar", "Onaylandı"), {
        description: draft.platform
          ? `${draft.platform} · ${(draft.trend_topic || "").slice(0, 50)}`
          : undefined,
        duration: 2500,
      });
    } catch (e) {
      // POST failed — restore the draft to the list so the operator sees it
      setDrafts((prev) => [draft, ...prev]);
      const msg = e?.response?.data?.detail?.message
                   || e?.response?.data?.detail
                   || e?.message
                   || t("autoDrafts.approve.error", "Onay başarısız");
      toast.error(typeof msg === "string" ? msg : t("autoDrafts.approve.error"), {
        duration: 6000,
      });
      refresh();
    }
  }, [refresh, t, bumpActionCount]);

  // Phase 28.P — approve the latest iteration of a draft (called from IterationDialog).
  // Returns a Promise so the dialog can await before closing.
  const handleIterationApprove = useCallback(async () => {
    const draft = iterTarget;
    if (!draft) return;
    setIterTarget(null);
    setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
    try {
      await approveDraft(draft.id);
      toast.success(t("autoDrafts.approve.success"));
    } catch (e) {
      toast.error(t("autoDrafts.approve.error"));
      refresh();
      throw e;
    }
  }, [iterTarget, refresh, t]);

  // 7 Haz 2026 fix — same root cause as approve. safeAction's setTimeout(5s)
  // gets destroyed by page refresh, so the reject POST never fires. The
  // draft would stay pending_review forever from the operator's view.
  // Fire immediately; on failure restore.
  const handleIterationReject = useCallback(async ({ category, feedback, rejection_target }) => {
    const draft = iterTarget;
    if (!draft) return;
    setIterTarget(null);
    setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
    try {
      await rejectDraft(draft.id, { category, feedback, rejection_target });
      toast.success(t("autoDrafts.reject.snackbar", "Reddedildi"), {
        description: draft.platform
          ? `${draft.platform} · ${(draft.trend_topic || "").slice(0, 50)}`
          : undefined,
        duration: 2500,
      });
    } catch (e) {
      setDrafts((prev) => [draft, ...prev]);
      const msg = e?.response?.data?.detail?.message
                   || e?.response?.data?.detail
                   || e?.message
                   || t("autoDrafts.reject.error", "Reddet başarısız");
      toast.error(typeof msg === "string" ? msg : t("autoDrafts.reject.error"), {
        duration: 6000,
      });
      refresh();
    }
  }, [iterTarget, refresh, t]);

  // 7 Haz 2026 fix — direct reject, same immediate-fire pattern.
  const handleDirectReject = useCallback(async (draft, body) => {
    setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
    bumpActionCount();
    try {
      await rejectDraft(draft.id, body);
      toast.success(t("autoDrafts.reject.snackbar", "Reddedildi"), {
        description: draft.platform
          ? `${draft.platform} · ${(draft.trend_topic || "").slice(0, 50)}`
          : undefined,
        duration: 2500,
      });
    } catch (e) {
      setDrafts((prev) => [draft, ...prev]);
      const msg = e?.response?.data?.detail?.message
                   || e?.response?.data?.detail
                   || e?.message
                   || t("autoDrafts.reject.error", "Reddet başarısız");
      toast.error(typeof msg === "string" ? msg : t("autoDrafts.reject.error"), {
        duration: 6000,
      });
      refresh();
    }
  }, [refresh, t, bumpActionCount]);

  // Phase 28.R-Lite-V2 — Cancel a previously-approved draft. Backend cancels
  // Postiz schedule and flips status to auto_rejected. Surfaces 409 with a
  // friendly toast when the post already published (cannot recall).
  const handleCancelApproval = useCallback(async (draft) => {
    setDrafts((prev) => prev.filter((d) => d.id !== draft.id));
    try {
      const res = await cancelApprovedDraft(draft.id);
      toast.success(
        res?.postiz_cancelled
          ? t("autoDrafts.cancel.success", "Yayın iptal edildi, Postiz'den çekildi")
          : t("autoDrafts.cancel.successNoPostiz", "Draft iptal edildi"),
      );
    } catch (e) {
      const detail = e?.response?.data?.detail || "";
      if (typeof detail === "string" && detail.startsWith("already_published")) {
        toast.error(
          t("autoDrafts.cancel.alreadyPublished",
            "Bu post zaten yayında — sosyal medya hesabından manuel silmen gerek."),
          { duration: 8000 },
        );
      } else {
        toast.error(t("autoDrafts.cancel.error", "İptal edilemedi"));
      }
      refresh();
    }
  }, [refresh, t]);

  const handleConfigSave = useCallback(async (patch) => {
    if (!activeAccountId) return;
    try {
      const updated = await updateConfig(activeAccountId, patch);
      setConfig(updated);
      toast.success(t("autoDrafts.config.saved"));
      setConfigOpen(false);
    } catch (e) {
      toast.error(t("autoDrafts.config.error"));
    }
  }, [activeAccountId, t]);

  // Phase 41.A — Keyboard shortcuts + 300ms debounce + window.confirm removed.
  // Sub-agent /debate konsensüsü: undo snackbar pattern confirm dialog yerine
  // safer + faster. Keyboard repeat (kahve kazası) için 300ms throttle.
  const kbDebouncer = useMemo(() => createKeyboardDebouncer(300), []);
  useEffect(() => {
    const handler = (e) => {
      if (iterTarget || configOpen) return;
      if (tab === "executive") return;
      const tag = (document.activeElement?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || document.activeElement?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const top = drafts[0];
      if (!top || (top.status !== "pending" && top.status !== "pending_review")) return;
      // Phase 41.A — 300ms keystroke debounce (key-specific). Prevents accidental
      // repeats from coffee spills, sticky keys, key repeat at OS level.
      const k = e.key.toLowerCase();
      if (["a", "d", "backspace", "delete"].includes(k)) {
        if (kbDebouncer.shouldIgnore(k)) {
          e.preventDefault();
          return;
        }
      }
      if (k === "a") {
        e.preventDefault();
        handleApprove(top);
      } else if (k === "d") {
        e.preventDefault();
        setIterTarget(top);
      } else if (k === "backspace" || k === "delete") {
        e.preventDefault();
        // Phase 41.A — window.confirm REMOVED. safeAction undo snackbar tutarlı.
        handleDirectReject(top, { category: "other", feedback: "keyboard-deleted", rejection_target: "both" });
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [drafts, tab, iterTarget, configOpen, handleApprove, handleDirectReject, kbDebouncer]);

  // ── Realtime: new hype_auto drafts fade in live ──────────
  useEffect(() => {
    if (!activeAccountId || !isSupabaseConfigured() || !supabase) return;
    const channel = supabase
      .channel(`hype_drafts_live_${activeAccountId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "daily_drafts",
          filter: `account_id=eq.${activeAccountId}`,
        },
        (payload) => {
          const row = payload?.new;
          if (!row || row.source !== "hype_auto") return;
          // Only inject when on pending/all tab AND row matches filter
          setDrafts((prev) => {
            if (prev.some((d) => d.id === row.id)) return prev;
            return [row, ...prev];
          });
          toast.success(
            t("autoDrafts.realtime.newDraft", { topic: row.trend_topic || "" }),
            { duration: 4000 }
          );
          if (typeof navigator !== "undefined" && navigator.vibrate) {
            try { navigator.vibrate(40); } catch { /* ignore */ }
          }
        }
      )
      .subscribe();
    return () => {
      try { supabase.removeChannel(channel); } catch { /* ignore */ }
    };
  }, [activeAccountId, t]);

  // ── Render ───────────────────────────────────────────────
  const dryRunOn = config?.dry_run_mode !== false;
  const autoPublishOn = config?.auto_publish_enabled === true;

  return (
    <div className="max-w-3xl mx-auto pb-24">
      {/* Header */}
      <header className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 shadow-lg shadow-purple-500/20">
                <Zap className="h-5 w-5 text-white" />
              </div>
              <h1 className="text-3xl font-bold font-outfit tracking-tight">
                {t("autoDrafts.title")}
              </h1>
            </div>
            <p className="text-sm text-muted-foreground max-w-xl leading-relaxed">
              {t("autoDrafts.subtitle")}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfigOpen(true)}
              className="gap-2"
            >
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">{t("autoDrafts.openConfig")}</span>
            </Button>
          </div>
        </div>

        {/* Dry-run / auto-publish badges */}
        <div className="flex flex-wrap gap-2 mt-4">
          {dryRunOn && (
            <Badge
              variant="outline"
              className="bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300 gap-1.5 py-1 pl-2 pr-2.5"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
              </span>
              <span className="text-[11px] font-medium uppercase tracking-wider">
                {t("autoDrafts.dryRunBadge")}
              </span>
            </Badge>
          )}
          {autoPublishOn && (
            <Badge
              variant="outline"
              className="bg-rose-500/10 border-rose-500/40 text-rose-700 dark:text-rose-300 gap-1.5 py-1 pl-2 pr-2.5"
            >
              <Sparkles className="h-3 w-3" />
              <span className="text-[11px] font-medium uppercase tracking-wider">
                {t("autoDrafts.autoPublishBadge")}
              </span>
            </Badge>
          )}
        </div>

        {/* Stats */}
        <div className="mt-6">
          <StatsRow accountId={activeAccountId} drafts={drafts} config={config} />
        </div>
      </header>

      {/* Phase 41.A — Tabs reduced 5→3 (Bekleyen / Geçmiş; Yönetim hidden).
          Platform filter + sort dropdown removed from pending tab (ThreadCard
          already groups multi-platform, sorting newest-first is always
          correct for review velocity). History tab still shows platform
          filter for archive search. */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-card border border-border/60 p-1 rounded-xl">
            <TabsTrigger
              value="pending"
              className="rounded-lg data-[state=active]:bg-purple-500/10 data-[state=active]:text-purple-600 dark:data-[state=active]:text-purple-300 text-xs sm:text-sm"
            >
              {t("autoDrafts.tabs.pending", "Bekleyen")}
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="rounded-lg data-[state=active]:bg-purple-500/10 data-[state=active]:text-purple-600 dark:data-[state=active]:text-purple-300 text-xs sm:text-sm"
            >
              {t("autoDrafts.tabs.history", "Geçmiş")}
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {/* Sort toggle — only visible in pending if order changed from default */}
        {sortOrder !== "newest" && (
          <button
            type="button"
            onClick={() => setSortOrder("newest")}
            className="text-[11px] text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
            title="En yeni önce sıralamaya dön"
          >
            🔄 En yeni önce
          </button>
        )}
      </div>

      {/* Keyboard shortcut hint — hides after 10 actions (localStorage counter, Phase 41.A) */}
      {tab === "pending" && drafts.length > 0 && (() => {
        const actionCount = Number(localStorage.getItem("autoDraftsActionCount") || 0);
        if (actionCount >= 10) return null;
        return (
          <p className="mb-3 text-[11px] text-muted-foreground/60 hidden sm:flex items-center gap-2">
            <span>Klavye:</span>
            <kbd className="px-1.5 py-0.5 rounded bg-secondary/60 border border-border/40 font-mono text-[10px]">A</kbd>
            <span>onayla</span>
            <span className="text-muted-foreground/40">·</span>
            <kbd className="px-1.5 py-0.5 rounded bg-secondary/60 border border-border/40 font-mono text-[10px]">D</kbd>
            <span>düzelt</span>
            <span className="text-muted-foreground/40">·</span>
            <kbd className="px-1.5 py-0.5 rounded bg-secondary/60 border border-border/40 font-mono text-[10px]">⌫</kbd>
            <span>sil</span>
            <span className="text-muted-foreground/40 ml-2">·</span>
            <span className="text-muted-foreground/40">yanlış basarsan 5 saniye "Geri Al" hakkın var</span>
          </p>
        );
      })()}

      {/* Phase 41.A — Platform filter chips ONLY on history tab (archive search).
          Pending tab uses ThreadCard which already groups multi-platform. */}
      {tab === "history" && (
        <div className="mb-6 flex items-center gap-2 flex-wrap text-xs">
          <span className="text-muted-foreground uppercase tracking-wider text-[10px] font-semibold">
            {t("autoDrafts.platforms.label", "Platform")}
          </span>
          {[
            { key: "all", label: t("autoDrafts.platforms.all", "Tümü") },
            { key: "twitter", label: "X" },
            { key: "linkedin", label: "LinkedIn" },
            { key: "devto", label: "dev.to" },
            { key: "instagram", label: "Instagram" },
          ].map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setPlatformFilter(p.key)}
              className={`px-2.5 py-1 rounded-md border transition-colors ${
                platformFilter === p.key
                  ? "bg-purple-500/10 text-purple-600 dark:text-purple-300 border-purple-500/40 font-medium"
                  : "bg-card border-border/60 text-muted-foreground hover:text-foreground hover:border-purple-500/30"
              }`}
            >
              {p.label}
            </button>
          ))}

          <span className="mx-1 text-muted-foreground/40">·</span>
          <button
            type="button"
            onClick={() => setSortOrder(sortOrder === "newest" ? "oldest" : "newest")}
            className="px-2 py-1 rounded-md border border-border/60 bg-card text-foreground/90 text-xs hover:border-purple-500/30 inline-flex items-center gap-1"
          >
            {sortOrder === "newest" ? "↓ En yeni" : "↑ En eski"}
          </button>
        </div>
      )}

      {/* Executive Board tab (Phase 26) — distinct view, not a draft list */}
      {tab === "executive" ? (
        <ExecutiveBoard accountId={activeAccountId} />
      ) : (
        <div className="space-y-4">
          {loading ? (
            <ListSkeleton />
          ) : error ? (
            <ErrorBlock message={error} onRetry={refresh} />
          ) : drafts.length === 0 ? (
            <EmptyState onOpenConfig={() => setConfigOpen(true)} />
          ) : tab === "pending" ? (
            // Phase 40 — Bekleyen tab: thread-grouped view. Drafts sharing a
            // content_thread_id render as ONE card with platform tabs + a
            // single "Onayla" button. Drafts without a thread_id fall back to
            // legacy per-platform DraftCard.
            (() => {
              const groups = new Map();
              const orphans = [];
              for (const d of drafts) {
                const tid = d.content_thread_id;
                if (!tid) { orphans.push(d); continue; }
                if (!groups.has(tid)) {
                  groups.set(tid, {
                    thread_id: tid,
                    trend_topic: d.trend_topic || "",
                    created_at: d.created_at,
                    drafts: [],
                  });
                }
                const g = groups.get(tid);
                g.drafts.push(d);
                if (new Date(d.created_at) < new Date(g.created_at)) {
                  g.created_at = d.created_at;
                }
                if (!g.trend_topic && d.trend_topic) g.trend_topic = d.trend_topic;
              }
              const threadsArr = Array.from(groups.values());
              const sortFn = (a, b) => {
                const ta = new Date(a.created_at || 0).getTime();
                const tb = new Date(b.created_at || 0).getTime();
                return sortOrder === "oldest" ? ta - tb : tb - ta;
              };
              threadsArr.sort(sortFn);
              orphans.sort((a, b) => {
                const ta = new Date(a.created_at || 0).getTime();
                const tb = new Date(b.created_at || 0).getTime();
                return sortOrder === "oldest" ? ta - tb : tb - ta;
              });
              return (
                <>
                  {threadsArr.map((thread, threadIdx) => (
                    <ThreadCard
                      key={thread.thread_id}
                      thread={thread}
                      isTopForKeyboard={threadIdx === 0}
                      onApproveThread={(tid) => {
                        // Phase 41.A — undo snackbar wraps the multi-platform approve.
                        // 7 Haz 2026 fix — fire immediately; the previous
                        // safeAction setTimeout(5s) was destroyed by page
                        // refresh, killing the POST. Same root cause as the
                        // per-draft approve. Optimistic hide stays; failure
                        // restores from `removed`.
                        const removed = thread.drafts;
                        inFlightThreadsRef.current.add(tid);
                        setDrafts((prev) => prev.filter((d) => d.content_thread_id !== tid));
                        (async () => {
                          try {
                            await approveThread(tid);
                            inFlightThreadsRef.current.delete(tid);
                            toast.success(
                              `${removed.length} platform onaylandı`,
                              {
                                description: (thread.trend_topic || "").slice(0, 60),
                                duration: 2500,
                              },
                            );
                          } catch (e) {
                            inFlightThreadsRef.current.delete(tid);
                            setDrafts((prev) => [...removed, ...prev]);
                            // Backend now returns detail={message, error, ...}
                            // (PART A3 2026-06-07). Render the operator-language
                            // `message` if present; fall back to legacy string
                            // detail. Never silently swallow into "başarısız".
                            const d = e?.response?.data?.detail;
                            let msg = "Thread onayı başarısız";
                            if (typeof d === "string") {
                              msg = d;
                            } else if (d && typeof d === "object") {
                              msg = d.message || d.error || msg;
                            } else if (e?.message) {
                              msg = e.message;
                            }
                            toast.error(msg, {
                              duration: 8000,
                              description: d?.error && d.error !== msg ? `(${d.error})` : undefined,
                            });
                            refresh();
                          }
                        })();
                      }}
                      onRejectDraft={(d) => handleDirectReject(d, { category: "other", feedback: "" })}
                      onRefineDraft={(d) => setIterTarget(d)}
                    />
                  ))}
                  {/* Phase 41.A — visual separator between threads and orphan drafts
                      (Critic finding: same pending list mixes two completely
                      different approval models, brain re-identifies on every card) */}
                  {threadsArr.length > 0 && orphans.length > 0 && (
                    <div className="my-4 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <div className="flex-1 h-px bg-border/40" />
                      <span className="uppercase tracking-wider">
                        {t("autoDrafts.orphanDivider", "Bağımsız taslaklar")}
                      </span>
                      <div className="flex-1 h-px bg-border/40" />
                    </div>
                  )}
                  {orphans.map((d, idx) => (
                    <DraftCard
                      key={d.id}
                      draft={d}
                      index={idx}
                      isTopForKeyboard={threadsArr.length === 0 && idx === 0}
                      onApprove={() => handleApprove(d)}
                      onRefine={() => setIterTarget(d)}
                      onReject={(body) => handleDirectReject(d, body)}
                      onCancelApproval={() => handleCancelApproval(d)}
                    />
                  ))}
                </>
              );
            })()
          ) : (
            // Approved / Rejected / All tabs — legacy per-platform DraftCard.
            // Thread-grouping doesn't add value once decisions are made.
            [...drafts]
              .sort((a, b) => {
                const ta = new Date(a.created_at || a.scheduled_at || 0).getTime();
                const tb = new Date(b.created_at || b.scheduled_at || 0).getTime();
                return sortOrder === "oldest" ? ta - tb : tb - ta;
              })
              .map((d, idx) => (
              <DraftCard
                key={d.id}
                draft={d}
                index={idx}
                onApprove={() => handleApprove(d)}
                onRefine={() => setIterTarget(d)}
                onReject={(body) => handleDirectReject(d, body)}
                onCancelApproval={() => handleCancelApproval(d)}
              />
            ))
          )}
        </div>
      )}

      {/* Phase 28.Q — Single unified review dialog. Scope picker (text/image/both)
          inside the dialog replaces the old "Sadece görsel kötü" standalone button
          and the separate RejectDialog. */}
      <IterationDialog
        draft={iterTarget}
        open={!!iterTarget}
        onClose={() => setIterTarget(null)}
        onApprove={handleIterationApprove}
        onReject={handleIterationReject}
      />
      <HypeConfigSheet
        open={configOpen}
        config={config}
        accountUsername={activeAccount?.username}
        onClose={() => setConfigOpen(false)}
        onSave={handleConfigSave}
      />
      <OnboardingTour />
    </div>
  );
}

function ListSkeleton() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-2xl border border-border/60 bg-card p-6 space-y-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-6 w-16" />
            <Skeleton className="h-6 w-20" />
            <div className="flex-1" />
            <Skeleton className="h-6 w-16" />
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <div className="flex gap-2 pt-2">
            <Skeleton className="h-9 flex-1" />
            <Skeleton className="h-9 flex-1" />
            <Skeleton className="h-9 flex-1" />
          </div>
        </div>
      ))}
    </>
  );
}

function ErrorBlock({ message, onRetry }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-8 text-center">
      <AlertCircle className="h-8 w-8 text-rose-500 mx-auto mb-3" />
      <p className="text-base font-semibold mb-1">{t("autoDrafts.errorTitle")}</p>
      <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">{message}</p>
      <Button size="sm" variant="outline" onClick={onRetry}>
        {t("autoDrafts.errorRetry")}
      </Button>
    </div>
  );
}
