/**
 * EmptyState — friendly placeholder when no drafts match the current filter.
 *
 * Pulse-animated zap icon (gradient bg) + CTA to open config.
 */
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Zap, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function EmptyState({ onOpenConfig }) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 rounded-2xl border border-dashed border-border/60 bg-card/30">
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="relative mb-6"
      >
        <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500/20 to-indigo-500/20 border border-purple-500/30 flex items-center justify-center">
          <motion.div
            animate={{ scale: [1, 1.12, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            className="absolute inset-0 rounded-2xl bg-purple-500/10 blur-xl"
          />
          <Zap className="h-10 w-10 text-purple-500 relative z-10" />
        </div>
      </motion.div>

      <h2 className="text-xl font-semibold font-outfit mb-2">
        {t("autoDrafts.empty.title")}
      </h2>
      <p className="text-sm text-muted-foreground max-w-sm mb-6 leading-relaxed">
        {t("autoDrafts.empty.body")}
      </p>
      <Button
        onClick={onOpenConfig}
        variant="outline"
        size="sm"
        className="gap-2 border-purple-500/30 hover:bg-purple-500/10 hover:text-purple-600 dark:hover:text-purple-300"
      >
        <Settings className="h-4 w-4" />
        {t("autoDrafts.empty.cta")}
      </Button>
    </div>
  );
}
