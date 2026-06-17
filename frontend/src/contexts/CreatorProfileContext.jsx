/**
 * CreatorProfileContext — Global master identity (avatar, name, title).
 * 
 * Navbar ve tüm uygulama bu context'ten master avatar/isim okur.
 * Creator Hub sayfası save sonrası updateProfile() ile anında günceller.
 * F5 gerektirmez.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { API } from "@/lib/api";

const CreatorProfileContext = createContext(null);

export function CreatorProfileProvider({ children }) {
  const [creatorProfile, setCreatorProfile] = useState({
    display_name: null,
    title: null,
    avatar_url: null,
    niches: [],
    brand_voice: null,
  });
  const [loaded, setLoaded] = useState(false);

  // Fetch on mount
  useEffect(() => {
    api.get(`${API}/profile`)
      .then((r) => {
        if (r.data) setCreatorProfile(r.data);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  // Called by CreatorHubPage after successful save
  const updateProfile = useCallback((updated) => {
    setCreatorProfile((prev) => ({ ...prev, ...updated }));
  }, []);

  return (
    <CreatorProfileContext.Provider value={{
      creatorProfile,
      updateProfile,
      loaded,
    }}>
      {children}
    </CreatorProfileContext.Provider>
  );
}

export function useCreatorProfile() {
  const ctx = useContext(CreatorProfileContext);
  if (!ctx) throw new Error("useCreatorProfile must be used within CreatorProfileProvider");
  return ctx;
}
