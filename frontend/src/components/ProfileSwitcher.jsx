/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState } from "react";
import { useTranslation } from 'react-i18next';
import { Dna, ChevronUp, Plus, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProfile } from "@/contexts/ProfileContext";
import { useNavigate } from "react-router-dom";

export default function ProfileSwitcher() {
  const { t } = useTranslation();
  const { profiles, activeProfile, setActiveProfile } = useProfile();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="relative">
      {/* Popup list */}
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-popover border border-border rounded-lg shadow-xl overflow-hidden z-50">
          <div className="p-2 border-b border-border">
            <p className="text-xs font-medium text-muted-foreground px-2">{t('profileSwitcher.styleProfiles')}</p>
          </div>
          <div className="max-h-[200px] overflow-y-auto p-1">
            {/* No profile option */}
            <button
              onClick={() => { setActiveProfile(null); setOpen(false); }}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                !activeProfile ? "bg-primary/10 text-primary" : "hover:bg-secondary"
              )}
            >
              <div className="h-6 w-6 rounded-full bg-secondary flex items-center justify-center shrink-0">
                <Dna className="h-3 w-3 text-muted-foreground" />
              </div>
              <span className="truncate">{t('profileSwitcher.noProfile')}</span>
              {!activeProfile && <Check className="h-4 w-4 ml-auto shrink-0" />}
            </button>

            {profiles.map((profile) => (
              <button
                key={profile.id}
                onClick={() => { setActiveProfile(profile.id); setOpen(false); }}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
                  activeProfile?.id === profile.id ? "bg-purple-500/10 text-purple-400" : "hover:bg-secondary"
                )}
              >
                <div className="h-6 w-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shrink-0">
                  <span className="text-[10px] font-bold text-white">
                    {profile.name?.charAt(0)?.toUpperCase() || "S"}
                  </span>
                </div>
                <span className="truncate">{profile.name}</span>
                {activeProfile?.id === profile.id && <Check className="h-4 w-4 ml-auto text-purple-400 shrink-0" />}
              </button>
            ))}
          </div>
          <div className="p-1 border-t border-border">
            <button
              onClick={() => { navigate("/dashboard/style-lab"); setOpen(false); }}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-muted-foreground hover:bg-secondary transition-colors"
            >
              <Plus className="h-4 w-4" />
              {t('profileSwitcher.createNewProfile')}
            </button>
          </div>
        </div>
      )}

      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors",
          "hover:bg-secondary/80 border border-transparent",
          open && "bg-secondary border-border"
        )}
      >
        <div className={cn(
          "h-8 w-8 rounded-full flex items-center justify-center shrink-0",
          activeProfile
            ? "bg-gradient-to-br from-purple-500 to-pink-500"
            : "bg-secondary"
        )}>
          {activeProfile ? (
            <span className="text-xs font-bold text-white">
              {activeProfile.name?.charAt(0)?.toUpperCase() || "S"}
            </span>
          ) : (
            <Dna className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-sm font-medium truncate">
            {activeProfile ? activeProfile.name : t('profileSwitcher.profileNotSelected')}
          </p>
          <p className="text-[10px] text-muted-foreground">
            {activeProfile ? t('profileSwitcher.activeStyleProfile') : t('profileSwitcher.styleCloningOff')}
          </p>
        </div>
        <ChevronUp className={cn(
          "h-4 w-4 text-muted-foreground transition-transform",
          !open && "rotate-180"
        )} />
      </button>
    </div>
  );
}
