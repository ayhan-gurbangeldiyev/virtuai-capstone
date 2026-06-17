import { Brain } from "lucide-react";
import { useTranslation } from "react-i18next";

function getGreeting(t) {
  const hour = new Date().getHours();
  if (hour < 12) return t("coach.greeting.morning");
  if (hour < 18) return t("coach.greeting.afternoon");
  return t("coach.greeting.evening");
}

export default function CoachHeader({ cardCount }) {
  const { t } = useTranslation();

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-1">
        <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <Brain className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="font-outfit text-2xl font-bold tracking-tight">
            {getGreeting(t)} 👋
          </h1>
          {cardCount > 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("coach.cardCount", { count: cardCount })}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("coach.subtitle")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
