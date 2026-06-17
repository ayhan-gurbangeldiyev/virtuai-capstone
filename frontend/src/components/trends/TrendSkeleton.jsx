export default function TrendSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border/30 bg-card/50 p-4 space-y-3 animate-pulse">
          <div className="flex justify-between">
            <div className="h-3 w-16 bg-secondary rounded" />
            <div className="h-3 w-12 bg-secondary rounded" />
          </div>
          <div className="h-4 w-full bg-secondary rounded mt-2" />
          <div className="h-4 w-3/4 bg-secondary rounded" />
          <div className="h-3 w-full bg-secondary/60 rounded mt-1" />
          <div className="h-3 w-5/6 bg-secondary/60 rounded" />
          <div className="flex justify-between mt-3 pt-3 border-t border-border/20">
            <div className="h-3 w-12 bg-secondary rounded" />
            <div className="h-7 w-16 bg-purple-500/20 rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  );
}
