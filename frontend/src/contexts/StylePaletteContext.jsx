/**
 * StylePaletteContext — Draft stil paleti (Kendi Sesim, Klonlanmış, Arketipler).
 *
 * Aktif draft tarzını ve tüm stil seçeneklerini global olarak yönetir.
 * changeDefaultStyle() → PATCH /settings ile default stil değiştirilir.
 * Pattern: CreatorProfileContext ile aynı yapı.
 */
import { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { API } from "@/lib/api";

const StylePaletteContext = createContext(null);

function getCompatibleActiveProfileId(styleObj) {
  if (styleObj?.type === "cloned") return styleObj.profile_id || null;
  return null;
}

export function StylePaletteProvider({ children }) {
  const [palette, setPalette] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchPalette = useCallback(async () => {
    try {
      const r = await api.get(`${API}/styles/palette`);
      if (r.data) setPalette(r.data);
    } catch (err) {
      // Backend henüz hazır değilse veya endpoint yoksa sessizce devam et
      console.warn("Style palette alınamadı", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Mount'ta çek
  useEffect(() => {
    fetchPalette();
  }, [fetchPalette]);

  /**
   * Default draft stilini değiştirir.
   * Optimistic update yapar, hata durumunda geri alır.
   * @param {Object} styleObj  { type: "own_voice" } | { type: "cloned", profile_id } | { type: "archetype", key }
   */
  const changeDefaultStyle = useCallback(async (styleObj) => {
    const nextActiveProfileId = getCompatibleActiveProfileId(styleObj);

    // Optimistic update
    setPalette(prev =>
      prev
        ? {
            ...prev,
            default: styleObj,
            active_profile_id: nextActiveProfileId,
          }
        : prev
    );

    try {
      await api.patch(`${API}/settings`, {
        default_draft_style: styleObj,
        active_profile_id: nextActiveProfileId || "",
      });

      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("cf:active-profile-sync", {
            detail: { activeProfileId: nextActiveProfileId },
          })
        );
      }
    } catch {
      // Hata durumunda backend'den gerçek state'i çek
      fetchPalette();
    }
  }, [fetchPalette]);

  /** Paleti backend'den yeniden çeker */
  const refreshPalette = useCallback(() => {
    setLoading(true);
    fetchPalette();
  }, [fetchPalette]);

  return (
    <StylePaletteContext.Provider
      value={{ palette, loading, changeDefaultStyle, refreshPalette }}
    >
      {children}
    </StylePaletteContext.Provider>
  );
}

export function useStylePalette() {
  const ctx = useContext(StylePaletteContext);
  if (!ctx) throw new Error("useStylePalette must be used within StylePaletteProvider");
  return ctx;
}
