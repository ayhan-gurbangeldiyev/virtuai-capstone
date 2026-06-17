import { useState, useCallback, useEffect } from "react";
import { Home, Brain, Newspaper, Trophy, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { fetchFeed } from "@/services/feedService";
import { FeedHeader } from "@/components/feed/FeedHeader";
import { FeedList } from "@/components/feed/FeedList";
import { FeedGeneratePanel } from "@/components/feed/FeedGeneratePanel";
import TrendSourcesSheet from "@/components/trends/TrendSourcesSheet";

const LIMIT = 20;

const feedCategories = [
  { id: undefined, label: "Tümü", icon: Home },
  { id: "ai_tech", label: "AI/Tech", icon: Brain },
  { id: "tr_haber", label: "Haber", icon: Newspaper },
  { id: "spor", label: "Spor", icon: Trophy },
];

export default function TrendDashboardPage() {
  const { t } = useTranslation();
  const [category, setCategory] = useState(undefined);
  const [sort, setSort] = useState("recent");
  const [items, setItems] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);
  const [generateItem, setGenerateItem] = useState(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const loadFeed = useCallback(
    async (reset) => {
      const newOffset = reset ? 0 : offset;
      if (reset) {
        setLoading(true);
        setError(false);
      } else {
        setLoadingMore(true);
      }

      try {
        const res = await fetchFeed({
          batch_type: category,
          limit: LIMIT,
          offset: newOffset,
          sort,
        });

        setItems((prev) => (reset ? res.items : [...prev, ...res.items]));
        setOffset(newOffset + LIMIT);
        setHasMore(res.has_more);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [category, sort, offset]
  );

  useEffect(() => {
    setOffset(0);
    setItems([]);
    setHasMore(true);
    loadFeed(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, sort]);

  const handleLoadMore = useCallback(() => {
    if (!loadingMore && hasMore) loadFeed(false);
  }, [loadFeed, loadingMore, hasMore]);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Trends
        </h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSourcesOpen(true)}
          className="gap-2"
        >
          <Settings className="h-4 w-4" />
          <span className="hidden sm:inline">{t("trends.manageSources")}</span>
        </Button>
      </div>

      {/* Category Filters */}
      <div className="flex items-center gap-2 mb-4 overflow-x-auto no-scrollbar pb-1">
        {feedCategories.map(({ id, label, icon: Icon }) => (
          <button
            key={label}
            onClick={() => setCategory(id)}
            className={cn(
              "shrink-0 flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap",
              category === id
                ? "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/25"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Sort Header */}
      <FeedHeader sort={sort} onSortChange={setSort} />

      {/* Feed List */}
      <FeedList
        items={items}
        loading={loading}
        loadingMore={loadingMore}
        hasMore={hasMore}
        error={error}
        onLoadMore={handleLoadMore}
        onRetry={() => loadFeed(true)}
        onGenerate={setGenerateItem}
      />

      <FeedGeneratePanel
        open={!!generateItem}
        onOpenChange={(val) => { if (!val) setGenerateItem(null); }}
        item={generateItem}
      />

      <TrendSourcesSheet
        open={sourcesOpen}
        onClose={() => setSourcesOpen(false)}
      />
    </div>
  );
}
