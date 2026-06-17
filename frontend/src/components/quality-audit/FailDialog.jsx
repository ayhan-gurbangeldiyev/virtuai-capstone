/**
 * Phase 43.E.5 — FailDialog
 * Opens after the Fail button on AuditCard. Single optional textarea
 * ("Neden fail?"). Submit calls onSubmit(notes) which the parent wires
 * to rateAudit(auditId, { rating:'fail', notes }).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function FailDialog({
  open,
  onOpenChange,
  onSubmit,
  draftPreview = "",
}) {
  const { t } = useTranslation();
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Clear notes whenever the dialog (re)opens.
  useEffect(() => {
    if (open) {
      setNotes("");
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onSubmit?.(notes.trim() || null);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    if (submitting) return;
    onOpenChange?.(false);
  };

  return (
    <Dialog open={!!open} onOpenChange={(o) => !submitting && onOpenChange?.(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-rose-600 dark:text-rose-400">
            {t("qualityAudit.failDialog.title")}
          </DialogTitle>
          <DialogDescription>
            {t("qualityAudit.failDialog.subtitle")}
          </DialogDescription>
        </DialogHeader>

        {draftPreview && (
          <p className="text-xs text-muted-foreground rounded-md bg-muted/40 p-3 line-clamp-4">
            {draftPreview}
          </p>
        )}

        <textarea
          autoFocus
          rows={4}
          maxLength={2000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={t("qualityAudit.failDialog.notesPlaceholder")}
          className="w-full rounded-md border border-input bg-background px-3 py-2
                     text-sm placeholder:text-muted-foreground focus-visible:outline-none
                     focus-visible:ring-2 focus-visible:ring-rose-500/40 resize-none"
          disabled={submitting}
        />

        <DialogFooter className="flex flex-col-reverse gap-2 sm:flex-row sm:gap-2">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={submitting}
          >
            {t("qualityAudit.failDialog.cancel")}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="bg-rose-600 hover:bg-rose-700 text-white"
          >
            {submitting
              ? t("qualityAudit.failDialog.submitting")
              : t("qualityAudit.failDialog.submit")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
