/**
 * AccountContext — Çoklu hesap yönetimi.
 *
 * - localStorage sync (F5 flicker yok)
 * - X-Active-Account-Id header otomatik
 * - switchAccount → API + localStorage + state
 * - Ghost/default hesaplar filtrelenir
 */
import { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import api, { API } from "@/lib/api";
import { toast } from "sonner";

const AccountContext = createContext(null);

const LS_KEY = "typehype_active_account";

// Platform avatar URL helper
const AVATAR_PROVIDERS = {
  twitter: (u) => `https://unavatar.io/twitter/${u}`,
  instagram: (u) => `${API}/accounts/avatar/instagram/${u}`,
  youtube: (u) => `https://unavatar.io/youtube/${u}`,
  tiktok: (u) => `https://unavatar.io/tiktok/${u}`,
  linkedin: (u) => `https://unavatar.io/linkedin/${u}`,
};

export function getAccountAvatar(account) {
  if (!account || account.platform === "default") return null;
  const fn = AVATAR_PROVIDERS[account.platform];
  return fn ? fn(account.username) : null;
}

export function AccountProvider({ children }) {
  const [accounts, setAccounts] = useState([]);
  const [activeAccountId, setActiveAccountId] = useState(
    () => localStorage.getItem(LS_KEY) || null
  );
  const [loading, setLoading] = useState(true);

  // Platform context override: sayfa context'ine göre geçici hesap override
  const [overrideAccountId, setOverrideAccountId] = useState(null);

  // ── Fetch accounts on mount ──
  useEffect(() => {
    api.get(`${API}/accounts`)
      .then((res) => {
        const accs = (res.data || []).filter((a) => a.platform !== "default");
        setAccounts(accs);

        // localStorage'daki ID hala geçerli mi?
        const lsId = localStorage.getItem(LS_KEY);
        if (lsId && accs.some((a) => a.id === lsId)) {
          setActiveAccountId(lsId);
        } else if (accs.length > 0) {
          // Fallback: primary veya ilk hesap
          const primary = accs.find((a) => a.is_primary) || accs[0];
          setActiveAccountId(primary.id);
          localStorage.setItem(LS_KEY, primary.id);
        } else {
          setActiveAccountId(null);
          localStorage.removeItem(LS_KEY);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Active account object (kullanıcının global seçimi) ──
  const activeAccount = useMemo(
    () => accounts.find((a) => a.id === activeAccountId) || null,
    [accounts, activeAccountId]
  );

  // ── Effective account: platform context override varsa onu, yoksa global active'i kullan ──
  const effectiveAccountId = overrideAccountId || activeAccountId;
  const effectiveAccount = useMemo(
    () => accounts.find((a) => a.id === effectiveAccountId) || activeAccount,
    [accounts, effectiveAccountId, activeAccount]
  );

  // ── Çoklu hesap var mı? ──
  const isMultiAccount = accounts.length > 1;

  // ── Hesap değiştir ──
  const switchAccount = useCallback(async (accountId) => {
    try {
      const res = await api.patch(`${API}/accounts/switch/${accountId}`);
      setActiveAccountId(accountId);
      localStorage.setItem(LS_KEY, accountId);

      const acc = accounts.find((a) => a.id === accountId);
      toast.success(`📱 @${acc?.username || "hesap"} aktif`);

      // Warning (token kopmuşsa)
      if (res.data?.warning) {
        toast.warning(res.data.warning);
      }

      return true;
    } catch (e) {
      toast.error("Hesap değiştirilemedi");
      return false;
    }
  }, [accounts]);

  // ── Hesap listesini yenile ──
  const refreshAccounts = useCallback(async () => {
    try {
      const res = await api.get(`${API}/accounts`);
      const accs = (res.data || []).filter((a) => a.platform !== "default");
      setAccounts(accs);

      // Aktif hesap hala listede mi?
      if (activeAccountId && !accs.some((a) => a.id === activeAccountId)) {
        const fallback = accs.find((a) => a.is_primary) || accs[0] || null;
        setActiveAccountId(fallback?.id || null);
        if (fallback) {
          localStorage.setItem(LS_KEY, fallback.id);
        } else {
          localStorage.removeItem(LS_KEY);
        }
      }

      return accs;
    } catch {
      return accounts;
    }
  }, [activeAccountId, accounts]);

  // ── API interceptor: X-Active-Account-Id header (effectiveAccount kullanır) ──
  useEffect(() => {
    const interceptor = api.interceptors.request.use((config) => {
      if (effectiveAccountId) {
        config.headers["X-Active-Account-Id"] = effectiveAccountId;
      }
      return config;
    });
    return () => api.interceptors.request.eject(interceptor);
  }, [effectiveAccountId]);

  // ── ACCOUNT_BROKEN event: hesabı broken olarak işaretle (reaktif) ──
  useEffect(() => {
    const handler = (e) => {
      const { platform } = e.detail || {};
      if (!platform) return;
      setAccounts((prev) =>
        prev.map((a) =>
          a.platform === platform && a.status === "active"
            ? { ...a, status: "broken", broken_reason: e.detail.message }
            : a
        )
      );
      toast.error(`⚠️ ${platform.charAt(0).toUpperCase() + platform.slice(1)} bağlantınız koptu`, {
        description: "Hesap ayarlarından yeniden bağlayın.",
        duration: 8000,
      });
    };
    window.addEventListener("account-broken", handler);
    return () => window.removeEventListener("account-broken", handler);
  }, []);

  return (
    <AccountContext.Provider value={{
      accounts,
      activeAccount,
      activeAccountId,
      effectiveAccount,
      effectiveAccountId,
      isMultiAccount,
      switchAccount,
      refreshAccounts,
      getAccountAvatar,
      setOverrideAccountId,
      loading,
    }}>
      {children}
    </AccountContext.Provider>
  );
}

export function useAccount() {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error("useAccount must be used within AccountProvider");
  return ctx;
}
