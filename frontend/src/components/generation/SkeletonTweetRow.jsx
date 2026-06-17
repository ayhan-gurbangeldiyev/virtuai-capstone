export default function SkeletonTweetRow() {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-border">
      {/* Left: Small rounded square placeholder */}
      <div className="h-8 w-8 rounded-md bg-muted animate-pulse shrink-0" />

      {/* Middle: Two skeleton bars */}
      <div className="flex-1 space-y-2">
        <div className="h-3 w-full rounded bg-muted animate-pulse" />
        <div className="h-3 w-3/5 rounded bg-muted animate-pulse" />
      </div>

      {/* Right: Small square placeholder */}
      <div className="h-6 w-6 rounded bg-muted animate-pulse shrink-0" />
    </div>
  );
}
