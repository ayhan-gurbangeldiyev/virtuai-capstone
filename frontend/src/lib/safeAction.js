/**
 * Phase 41.A — Undo Snackbar pattern for irreversible actions.
 *
 * Berkay'ın "bir anda bişeye bastın mı gidiyor" şikayetinin çözümü.
 * Sub-agent /debate sonucu (3 agent %85 hemfikir): confirm dialog yanlış
 * araç (reflexive Enter bypass + fatigue), undo snackbar doğru paradigm.
 *
 * Pattern: client tıklamada optimistic UI uygular + setTimeout queue +
 * Sonner action toast 5sn. Geri Al tıklanırsa setTimeout cancel, API
 * çağrısı atılmaz, state restore edilir.
 *
 * Kullanım:
 *   safeAction({
 *     label: "Onaylandı",
 *     undoMs: 5000,
 *     onCommit: async () => approveDraft(draft.id),
 *     onUndo: () => setDrafts(prev => [draft, ...prev]),  // optimistic restore
 *     onError: (e) => { ... },
 *   });
 *
 * onCommit = setTimeout sonrası gerçek API call (sayfa kapanırsa atılmaz)
 * onUndo  = Geri Al tıklanırsa state restore callback
 * onError = onCommit reject olursa
 */
import { toast } from "sonner";

export function safeAction({
  label,
  description = null,
  undoMs = 5000,
  onCommit,
  onUndo,
  onError,
  successMessage = null,
}) {
  if (!onCommit) {
    throw new Error("safeAction requires onCommit callback");
  }

  let cancelled = false;
  let toastId = null;

  // Schedule the real action — after undoMs unless cancelled
  const timer = setTimeout(async () => {
    if (cancelled) return;
    try {
      await onCommit();
      if (successMessage) {
        toast.success(successMessage, { duration: 2000 });
      }
    } catch (e) {
      // API call failed — restore optimistic state if onUndo is provided
      if (onUndo) onUndo();
      const msg = e?.response?.data?.detail || e?.message || "İşlem başarısız";
      toast.error(typeof msg === "string" ? msg : "İşlem başarısız", { duration: 5000 });
      if (onError) onError(e);
    } finally {
      // Dismiss the action toast if still open (it shouldn't be after undoMs)
      if (toastId !== null) toast.dismiss(toastId);
    }
  }, undoMs);

  // Show action toast with Undo button
  toastId = toast(label, {
    description,
    duration: undoMs,
    action: {
      label: "Geri Al",
      onClick: () => {
        cancelled = true;
        clearTimeout(timer);
        if (onUndo) onUndo();
        toast.success("Geri alındı", { duration: 1500 });
      },
    },
  });

  // Return a handle so callers can imperatively cancel (e.g. on unmount)
  return {
    cancel: () => {
      cancelled = true;
      clearTimeout(timer);
      if (toastId !== null) toast.dismiss(toastId);
    },
  };
}

/**
 * Debounce keyboard handler — Phase 41.A safety.
 * Aynı tuşa ardışık basışları engelle (keyboard repeat / kahve kazası
 * senaryosu). Default 300ms — Doherty Threshold uygun.
 *
 * Kullanım:
 *   const debouncedKey = useKeyboardDebounce(300);
 *   // sonra:
 *   if (debouncedKey.shouldIgnore(e.key)) return;
 *   handleApprove(...);
 */
export function createKeyboardDebouncer(windowMs = 300) {
  let lastKey = null;
  let lastTime = 0;
  return {
    shouldIgnore: (key) => {
      const now = Date.now();
      const sinceLast = now - lastTime;
      const isRepeat = key === lastKey && sinceLast < windowMs;
      // Update tracking AFTER decision (so caller can use the gate result first)
      lastKey = key;
      lastTime = now;
      return isRepeat;
    },
    reset: () => {
      lastKey = null;
      lastTime = 0;
    },
  };
}
