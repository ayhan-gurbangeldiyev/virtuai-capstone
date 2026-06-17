const sorts = [
  { value: "recent", label: "Son Eklenenler" },
  { value: "popular", label: "En Popüler" },
];

export function FeedHeader({ sort, onSortChange }) {
  return (
    <div className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="flex">
        {sorts.map(({ value, label }) => {
          const isActive = value === sort;
          return (
            <button
              key={value}
              onClick={() => onSortChange(value)}
              className="group relative flex flex-1 items-center justify-center py-4 transition-colors hover:bg-white/[0.03]"
            >
              <span
                className={`text-[15px] ${
                  isActive
                    ? "font-bold text-foreground"
                    : "font-medium text-muted-foreground"
                }`}
              >
                {label}
              </span>
              {isActive && (
                <div className="absolute bottom-0 h-1 w-16 rounded-full bg-[hsl(var(--primary))]" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
