import { useEffect, useRef } from "react";
import { TweetCard } from "./TweetCard";
import { TweetCardSkeleton } from "./TweetCardSkeleton";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

export function FeedList({ items, loading, loadingMore, hasMore, error, onLoadMore, onRetry, onGenerate }) {
  const sentinelRef = useRef(null);

  useEffect(() => {
    if (!hasMore || loadingMore || loading) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onLoadMore();
      },
      { rootMargin: "200px" }
    );

    const el = sentinelRef.current;
    if (el) observer.observe(el);
    return () => {
      if (el) observer.unobserve(el);
    };
  }, [hasMore, loadingMore, loading, onLoadMore]);

  if (error && items.length === 0) {
    return <ErrorState onRetry={onRetry} />;
  }

  if (loading) {
    return (
      <div>
        {Array.from({ length: 5 }).map((_, i) => (
          <TweetCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return <EmptyState />;
  }

  return (
    <div>
      {items.map((item) => (
        <TweetCard key={item.id} item={item} onGenerate={onGenerate} />
      ))}
      {loadingMore &&
        Array.from({ length: 3 }).map((_, i) => (
          <TweetCardSkeleton key={`skel-${i}`} />
        ))}
      <div ref={sentinelRef} className="h-1" />
    </div>
  );
}
