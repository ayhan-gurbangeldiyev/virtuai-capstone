/**
 * OnboardingTour — first-visit guided 3-step intro.
 *
 * Detects via localStorage flag `hype_tour_seen`. Pure Framer Motion overlay,
 * no extra dependency.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { Zap, ListChecks, Settings as SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "hype_tour_seen";

export default function OnboardingTour() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch { /* ignore */ }
  }, []);

  const finish = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignore */ }
    setOpen(false);
  };

  const steps = [
    {
      icon: Zap,
      title: t("autoDrafts.tour.step1Title"),
      body: t("autoDrafts.tour.step1Body"),
    },
    {
      icon: ListChecks,
      title: t("autoDrafts.tour.step2Title"),
      body: t("autoDrafts.tour.step2Body"),
    },
    {
      icon: SettingsIcon,
      title: t("autoDrafts.tour.step3Title"),
      body: t("autoDrafts.tour.step3Body"),
    },
  ];

  if (!open) return null;
  const s = steps[step];
  const Icon = s.icon;
  const isLast = step === steps.length - 1;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-background/70 backdrop-blur-sm p-4"
      >
        <motion.div
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          transition={{ duration: 0.25 }}
          className="w-full max-w-sm rounded-2xl bg-card border border-border/60 shadow-2xl p-6"
        >
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center mb-4 shadow-lg shadow-purple-500/30">
            <Icon className="h-6 w-6 text-white" />
          </div>
          <h3 className="text-lg font-semibold font-outfit mb-2">{s.title}</h3>
          <p className="text-sm text-muted-foreground leading-relaxed mb-5">{s.body}</p>

          {/* Step dots */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {steps.map((_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === step ? "w-6 bg-purple-500" : "w-1.5 bg-border"
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={finish}>
                {t("autoDrafts.tour.skip")}
              </Button>
              {isLast ? (
                <Button
                  size="sm"
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                  onClick={finish}
                >
                  {t("autoDrafts.tour.done")}
                </Button>
              ) : (
                <Button
                  size="sm"
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                  onClick={() => setStep((v) => v + 1)}
                >
                  {t("autoDrafts.tour.next")}
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
