import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

export function ErrorState({ onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <AlertTriangle className="h-12 w-12 text-destructive/70" />
      <p className="mt-4 text-lg font-medium text-foreground">
        Feed yüklenirken bir hata oluştu.
      </p>
      <Button onClick={onRetry} variant="outline" className="mt-4 gap-2">
        <RefreshCw className="h-4 w-4" />
        Tekrar Dene
      </Button>
    </div>
  );
}
