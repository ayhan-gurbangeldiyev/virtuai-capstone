/**
 * API configuration - centralized axios setup with security headers.
 */
import axios from "axios";

// Defensive: trim any trailing whitespace/newline (Vercel env vars sometimes
// carry a trailing \n that produces URLs like "https://api.typehype.io\n/api/...",
// which silently fail on certain paths).
const API_BASE = `${(process.env.REACT_APP_BACKEND_URL || "").trim()}/api`;

// Create axios instance with security headers
const api = axios.create({
  baseURL: API_BASE,
});

// Add security headers + auth token to every request
api.interceptors.request.use((config) => {
  config.headers["X-TH-Client"] = "web-app";
  config.headers["X-Requested-With"] = "XMLHttpRequest";

  // Auto-attach auth token from Supabase session
  if (!config.headers["Authorization"]) {
    try {
      const raw = localStorage.getItem(
        Object.keys(localStorage).find((k) => k.startsWith("sb-") && k.endsWith("-auth-token")) || ""
      );
      if (raw) {
        const parsed = JSON.parse(raw);
        const token = parsed?.access_token;
        if (token) {
          config.headers["Authorization"] = `Bearer ${token}`;
        }
      }
    } catch {
      // ignore parse errors
    }
  }

  // Replay protection: timestamp + nonce for mutation requests
  if (config.method === "post" || config.method === "put" || config.method === "patch" || config.method === "delete") {
    config.headers["X-TH-Timestamp"] = Math.floor(Date.now() / 1000).toString();
    config.headers["X-TH-Nonce"] = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  return config;
});

// Sanitize error responses + ACCOUNT_BROKEN detection
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      // ACCOUNT_BROKEN: hesap bağlantısı kopmuş, custom event fırlat
      if (status === 403 && data?.code === "ACCOUNT_BROKEN") {
        window.dispatchEvent(new CustomEvent("account-broken", {
          detail: { platform: data.platform, message: data.message },
        }));
        return Promise.reject(error);
      }

      // Keep user-facing messages from known HTTP errors
      if (status === 401 || status === 403 || status === 429 || status === 400) {
        return Promise.reject(error);
      }

      // For 500s, replace with generic message
      if (status >= 500) {
        error.response.data = { detail: "Bir hata oluştu. Lütfen tekrar deneyin." };
      }
    }
    return Promise.reject(error);
  }
);

export { API_BASE as API };
export default api;
