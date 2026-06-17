import { Inbox } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <Inbox className="h-12 w-12 text-muted-foreground/50" />
      <p className="mt-4 text-lg font-medium text-foreground">
        Bu kategoride henüz tweet yok.
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Veriler her birkaç saatte güncellenir.
      </p>
    </div>
  );
}
