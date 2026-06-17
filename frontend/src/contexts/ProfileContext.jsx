import { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { API } from "@/lib/api";
import { toast } from "sonner";

const ProfileContext = createContext(null);

export function ProfileProvider({ children }) {
  const [profiles, setProfiles] = useState([]);
  const [activeProfileId, setActiveProfileId] = useState(
    () => localStorage.getItem("cf_active_profile_id") || null
  );
  const [settings, setSettings] = useState({
    default_persona: "otorite",
    default_tone: "natural",
  });
  const [loading, setLoading] = useState(true);

  // Fetch profiles and settings on mount
  useEffect(() => {
    Promise.all([
      api.get(`${API}/styles/list`).then(r => r.data).catch(() => []),
      api.get(`${API}/settings`).then(r => r.data).catch(() => ({})),
    ]).then(([profileList, settingsData]) => {
      setProfiles(profileList);

      if (settingsData.active_profile_id) {
        setActiveProfileId(settingsData.active_profile_id);
        localStorage.setItem("cf_active_profile_id", settingsData.active_profile_id);
      } else {
        setActiveProfileId(null);
        localStorage.removeItem("cf_active_profile_id");
      }

      setSettings({
        default_persona: settingsData.default_persona || "otorite",
        default_tone: settingsData.default_tone || "natural",
      });
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    const onActiveProfileSync = (event) => {
      const nextId = event?.detail?.activeProfileId || null;
      setActiveProfileId(nextId);
      if (nextId) {
        localStorage.setItem("cf_active_profile_id", nextId);
      } else {
        localStorage.removeItem("cf_active_profile_id");
      }
    };

    window.addEventListener("cf:active-profile-sync", onActiveProfileSync);
    return () => window.removeEventListener("cf:active-profile-sync", onActiveProfileSync);
  }, []);

  const activeProfile = profiles.find(p => p.id === activeProfileId) || null;

  const setActiveProfile = useCallback(async (profileId) => {
    try {
      await api.patch(`${API}/settings`, { active_profile_id: profileId || "" });
      setActiveProfileId(profileId);
      if (profileId) {
        localStorage.setItem("cf_active_profile_id", profileId);
      } else {
        localStorage.removeItem("cf_active_profile_id");
      }
      const profile = profiles.find(p => p.id === profileId);
      toast.success(profile ? `Profil: ${profile.name} aktif` : "Profil kaldırıldı");
    } catch (e) {
      toast.error("Profil değiştirilemedi");
    }
  }, [profiles]);

  const refreshProfiles = useCallback(async () => {
    try {
      const res = await api.get(`${API}/styles/list`);
      setProfiles(res.data || []);
    } catch (e) {
      console.error("Failed to refresh profiles", e);
    }
  }, []);

  return (
    <ProfileContext.Provider value={{
      profiles,
      activeProfile,
      activeProfileId,
      setActiveProfile,
      refreshProfiles,
      settings,
      loading,
    }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}
