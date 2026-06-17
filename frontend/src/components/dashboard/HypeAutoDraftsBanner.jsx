/**
 * HypeAutoDraftsBanner — homepage entry point to Auto-Drafts.
 *
 * Always visible when an account is active. Copy switches based on whether
 * there are pending drafts: with pending → "X draft awaits", without →
 * "Hype Crew is running, review past runs". Click → /dashboard/auto-drafts.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Zap, ArrowRight } from "lucide-react";
import { useAccount } from "@/contexts/AccountContext";
import { listAutoDrafts, getConfig } from "@/services/hypeService";

export default function HypeAutoDraftsBanner() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { activeAccountId } = useAccount();
  const [count, setCount] = useState(0);
  const [dryRun, setDryRun] = useState(true);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!activeAccountId) return;
    Promise.all([
      listAutoDrafts({ accountId: activeAccountId, status: "pending", limit: 50 })
        .catch(() => ({ items: [] })),
      getConfig(activeAccountId).catch(() => null),
    ]).then(([draftsRes, cfg]) => {
      setCount((draftsRes.items || []).length);
      setDryRun(cfg ? cfg.dry_run_mode !== false : true);
      setLoaded(true);
    });
  }, [activeAccountId]);

  if (!activeAccountId || !loaded) return null;

  return (
    <motion.button
      type="button"
      onClick={() => navigate("/dashboard/auto-drafts")}
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.25 }}
      className="group block w-full text-left rounded-2xl border border-purple-500/30 bg-gradient-to-r from-purple-500/10 via-indigo-500/5 to-transparent backdrop-blur-sm p-5 hover:shadow-lg hover:shadow-purple-500/10 transition-shadow border-l-[3px]"
    >
      <div className="flex items-center gap-4">
        <div className="relative shrink-0">
          <div className="absolute inset-0 rounded-xl bg-purple-500/30 blur-md group-hover:bg-purple-500/40 transition" />
          <div className="relative w-11 h-11 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/30">
            <Zap className="h-5 w-5 text-white" />
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="font-outfit text-base font-semibold text-foreground">
              {t("autoDrafts.home.widgetTitle")}
            </h3>
            {dryRun && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300">
                <span className="h-1 w-1 rounded-full bg-amber-500 animate-pulse" />
                DRY RUN
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {count > 0
              ? t("autoDrafts.home.widgetBody", { count })
              : t("autoDrafts.home.widgetBodyEmpty")}
          </p>
        </div>

        <div className="flex items-center gap-1.5 text-purple-600 dark:text-purple-400 text-sm font-medium shrink-0">
          <span className="hidden sm:inline">{t("autoDrafts.home.widgetCta")}</span>
          <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
        </div>
      </div>
    </motion.button>
  );
}
