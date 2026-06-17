/**
 * PersonaLabPage — Bağımsız Persona Lab sayfası
 * 
 * 2 ana görünüm:
 *   1. Karşılama: Kayıtlı persona grid + yeni oluştur
 *   2. Stüdyo: Seçilen persona ile pipeline workflow (StyleTransferMode)
 */

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  ArrowLeft,
  Loader2,
  User,
  Sparkles,
  Search,
  Trash2,
  Zap,
  ChevronRight,
  Fingerprint,
  Brain,
  X,
  Check,
  RefreshCw,
} from "lucide-react";
import { FaXTwitter } from "react-icons/fa6";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import { useProfile } from "@/contexts/ProfileContext";
import StyleTransferMode from "@/components/generation/StyleTransferMode";

// ─────────────────────────────────────────────
// ANALYSIS PROGRESS OVERLAY
// ─────────────────────────────────────────────
const ANALYSIS_STEPS = [
  { label: "Tweetler taranıyor", detail: "Son 500 tweet çekiliyor...", pct: 15 },
  { label: "Retweet ve spam filtreleniyor", detail: "Temiz içerik ayrıştırılıyor...", pct: 30 },
  { label: "Yazım tarzı analiz ediliyor", detail: "Kelime dağarcığı, uzunluk, yapı...", pct: 50 },
  { label: "AI derin analiz yapıyor", detail: "Stil parmak izi çıkarılıyor...", pct: 70 },
  { label: "Embedding oluşturuluyor", detail: "Semantik arama için vektörler...", pct: 85 },
  { label: "Profil kaydediliyor", detail: "Persona hazır!", pct: 100 },
];

function AnalysisProgress({ username, currentStep, onCancel }) {
  const step = ANALYSIS_STEPS[Math.min(currentStep, ANALYSIS_STEPS.length - 1)];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.8)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          padding: "32px",
          textAlign: "center",
        }}
      >
        {/* Avatar with pulse */}
        <div style={{ position: "relative", display: "inline-block", marginBottom: "24px" }}>
          <div
            style={{
              width: "80px",
              height: "80px",
              borderRadius: "50%",
              overflow: "hidden",
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto",
            }}
          >
            <img
              src={`https://unavatar.io/x/${username}`}
              alt=""
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
              onError={(e) => {
                e.target.style.display = "none";
                e.target.parentElement.innerHTML = `<span style="color:white;font-size:28px;font-weight:700">@</span>`;
              }}
            />
          </div>
          {/* Pulse rings */}
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              animate={{
                scale: [1, 1.8],
                opacity: [0.4, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                delay: i * 0.6,
                ease: "easeOut",
              }}
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                border: "2px solid rgba(139, 92, 246, 0.4)",
              }}
            />
          ))}
        </div>

        <h3
          style={{
            fontSize: "18px",
            fontWeight: "700",
            color: "white",
            marginBottom: "4px",
          }}
        >
          @{username}
        </h3>
        <p style={{ fontSize: "13px", color: "rgba(255,255,255,0.5)", marginBottom: "28px" }}>
          Persona oluşturuluyor
        </p>

        {/* Progress bar */}
        <div
          style={{
            width: "100%",
            height: "4px",
            borderRadius: "4px",
            background: "rgba(255,255,255,0.08)",
            marginBottom: "16px",
            overflow: "hidden",
          }}
        >
          <motion.div
            animate={{ width: `${step.pct}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{
              height: "100%",
              borderRadius: "4px",
              background: "linear-gradient(90deg, #7c3aed, #a855f7, #c084fc)",
            }}
          />
        </div>

        {/* Step label */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
          >
            <div style={{ fontSize: "14px", fontWeight: "600", color: "#a78bfa", marginBottom: "4px" }}>
              {step.label}
            </div>
            <div style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)" }}>
              {step.detail}
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Cancel */}
        <button
          onClick={onCancel}
          style={{
            marginTop: "24px",
            padding: "8px 20px",
            borderRadius: "8px",
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "rgba(255,255,255,0.4)",
            fontSize: "12px",
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.2s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.1)";
            e.currentTarget.style.color = "rgba(255,255,255,0.7)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,0.06)";
            e.currentTarget.style.color = "rgba(255,255,255,0.4)";
          }}
        >
          İptal
        </button>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────
// PERSONA CARD
// ─────────────────────────────────────────────
function PersonaCard({ persona, onSelect, onDelete, deleting }) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      whileHover={{ y: -4 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSelect(persona)}
      style={{
        position: "relative",
        background: "var(--m-surface, #111)",
        border: hovered
          ? "1.5px solid rgba(139, 92, 246, 0.4)"
          : "1.5px solid rgba(255,255,255,0.06)",
        borderRadius: "16px",
        padding: "20px",
        cursor: "pointer",
        transition: "border-color 0.3s ease, box-shadow 0.3s ease",
        boxShadow: hovered ? "0 8px 30px rgba(139, 92, 246, 0.1)" : "none",
        overflow: "hidden",
      }}
    >
      {/* Delete button */}
      <AnimatePresence>
        {hovered && (
          <motion.button
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(persona.id);
            }}
            disabled={deleting}
            style={{
              position: "absolute",
              top: "10px",
              right: "10px",
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              color: "#ef4444",
              zIndex: 2,
            }}
          >
            {deleting ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Trash2 size={12} />}
          </motion.button>
        )}
      </AnimatePresence>

      {/* Avatar */}
      <div
        style={{
          width: "56px",
          height: "56px",
          borderRadius: "50%",
          overflow: "hidden",
          background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "14px",
          border: hovered ? "2px solid rgba(139, 92, 246, 0.4)" : "2px solid transparent",
          transition: "border-color 0.3s ease",
        }}
      >
        {persona.avatar_url ? (
          <img
            src={persona.avatar_url}
            alt=""
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            onError={(e) => { e.target.style.display = "none"; }}
          />
        ) : (
          <span style={{ color: "white", fontSize: "20px", fontWeight: "700" }}>
            {(persona.display_name || persona.name || "?")[0]}
          </span>
        )}
      </div>

      {/* Info */}
      <h3
        style={{
          fontSize: "15px",
          fontWeight: "700",
          color: "var(--m-text, #fff)",
          marginBottom: "2px",
          lineHeight: "1.3",
        }}
      >
        {persona.display_name || persona.name}
      </h3>
      <div
        style={{
          fontSize: "12px",
          color: "var(--m-text-muted, #888)",
          marginBottom: "12px",
        }}
      >
        @{persona.username}
      </div>

      {/* Stats */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          fontSize: "11px",
          color: "var(--m-text-faint, #555)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <Fingerprint size={11} />
          {persona.tweet_count} tweet
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <Brain size={11} />
          RAG
        </span>
      </div>

      {/* Hover glow */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            bottom: "-20px",
            left: "50%",
            transform: "translateX(-50%)",
            width: "80%",
            height: "40px",
            background: "radial-gradient(ellipse, rgba(139,92,246,0.15) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />
      )}
    </motion.div>
  );
}

// ─────────────────────────────────────────────
// CREATE PERSONA DIALOG
// ─────────────────────────────────────────────
function CreatePersonaDialog({ open, onClose, onCreated }) {
  const [username, setUsername] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [abortController, setAbortController] = useState(null);

  const handleCreate = async () => {
    const clean = username.trim().replace(/^@/, "");
    if (!clean) {
      toast.error("Kullanıcı adı gir");
      return;
    }

    setAnalyzing(true);
    setAnalysisStep(0);

    // Simulated progress steps (actual API call is single request)
    const stepInterval = setInterval(() => {
      setAnalysisStep((prev) => {
        if (prev >= ANALYSIS_STEPS.length - 2) {
          clearInterval(stepInterval);
          return prev;
        }
        return prev + 1;
      });
    }, 3500);

    const controller = new AbortController();
    setAbortController(controller);

    try {
      const res = await api.post(
        `${API}/styles/create-from-handle`,
        { twitter_username: clean },
        { signal: controller.signal }
      );

      clearInterval(stepInterval);
      setAnalysisStep(ANALYSIS_STEPS.length - 1);

      // Brief pause to show completion
      await new Promise((r) => setTimeout(r, 800));

      if (res.data?.id) {
        toast.success(`@${clean} persona oluşturuldu ✨`);
        onCreated(res.data);
        onClose();
        setUsername("");
      }
    } catch (e) {
      clearInterval(stepInterval);
      if (e.name !== "AbortError" && e.code !== "ERR_CANCELED") {
        toast.error(e.response?.data?.detail || "Analiz başarısız oldu");
      }
    } finally {
      setAnalyzing(false);
      setAnalysisStep(0);
      setAbortController(null);
    }
  };

  const handleCancel = () => {
    if (abortController) abortController.abort();
    setAnalyzing(false);
    setAnalysisStep(0);
  };

  return (
    <>
      {/* Analysis overlay */}
      <AnimatePresence>
        {analyzing && (
          <AnalysisProgress
            username={username.trim().replace(/^@/, "")}
            currentStep={analysisStep}
            onCancel={handleCancel}
          />
        )}
      </AnimatePresence>

      {/* Input dialog */}
      <AnimatePresence>
        {open && !analyzing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 90,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(0,0,0,0.6)",
              backdropFilter: "blur(8px)",
            }}
            onClick={onClose}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              style={{
                width: "100%",
                maxWidth: "400px",
                background: "var(--m-surface, #111)",
                border: "1.5px solid rgba(255,255,255,0.08)",
                borderRadius: "20px",
                padding: "28px",
                margin: "16px",
              }}
            >
              {/* Header */}
              <div style={{ textAlign: "center", marginBottom: "24px" }}>
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "14px",
                    background: "linear-gradient(135deg, rgba(139,92,246,0.2), rgba(168,85,247,0.1))",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 12px",
                  }}
                >
                  <FaXTwitter size={20} style={{ color: "#a78bfa" }} />
                </div>
                <h3 style={{ fontSize: "17px", fontWeight: "700", color: "var(--m-text, #fff)", marginBottom: "4px" }}>
                  Yeni Persona Oluştur
                </h3>
                <p style={{ fontSize: "13px", color: "var(--m-text-muted, #888)", lineHeight: "1.5" }}>
                  X kullanıcı adını gir, tweetlerini analiz edelim.
                </p>
              </div>

              {/* Input */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "12px 14px",
                  background: "rgba(255,255,255,0.03)",
                  border: "1.5px solid rgba(255,255,255,0.08)",
                  borderRadius: "12px",
                  marginBottom: "16px",
                  transition: "border-color 0.2s ease",
                }}
              >
                <span style={{ color: "var(--m-text-muted, #888)", fontSize: "14px", fontWeight: "500" }}>@</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="kullaniciadi"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreate();
                  }}
                  style={{
                    flex: 1,
                    background: "transparent",
                    border: "none",
                    outline: "none",
                    color: "var(--m-text, #fff)",
                    fontSize: "14px",
                    fontFamily: "inherit",
                  }}
                />
              </div>

              {/* Actions */}
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={onClose}
                  style={{
                    flex: 1,
                    padding: "11px",
                    borderRadius: "10px",
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    color: "var(--m-text-muted, #888)",
                    fontSize: "13px",
                    fontWeight: "500",
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  İptal
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!username.trim()}
                  style={{
                    flex: 2,
                    padding: "11px",
                    borderRadius: "10px",
                    background: username.trim()
                      ? "linear-gradient(135deg, #7c3aed, #a855f7)"
                      : "rgba(255,255,255,0.04)",
                    border: "none",
                    color: username.trim() ? "white" : "var(--m-text-faint, #555)",
                    fontSize: "13px",
                    fontWeight: "600",
                    cursor: username.trim() ? "pointer" : "not-allowed",
                    fontFamily: "inherit",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                  }}
                >
                  <Zap size={14} />
                  Analiz Et
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

// ─────────────────────────────────────────────
// MAIN: PersonaLabPage
// ─────────────────────────────────────────────
export default function PersonaLabPage({ embedded = false }) {
  const { refreshProfiles } = useProfile();
  const [personas, setPersonas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activePersona, setActivePersona] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    loadPersonas();
  }, []);

  const loadPersonas = async () => {
    try {
      const res = await api.get(`${API}/style-transfer/profiles`);
      setPersonas(res.data.profiles || []);
    } catch (e) {
      toast.error("Personalar yüklenemedi");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Bu personayı silmek istediğine emin misin?")) return;
    setDeletingId(id);
    try {
      await api.delete(`${API}/styles/${id}`);
      setPersonas((prev) => prev.filter((p) => p.id !== id));
      refreshProfiles(); // Global profil listesini güncelle
      toast.success("Persona silindi");
    } catch (e) {
      toast.error("Silinemedi");
    } finally {
      setDeletingId(null);
    }
  };

  const handleCreated = (newProfile) => {
    loadPersonas();
    refreshProfiles(); // Global profil listesini güncelle (XAIModule dropdown)
  };

  const filtered = personas.filter(
    (p) =>
      (p.display_name || p.name || "").toLowerCase().includes(search.toLowerCase()) ||
      (p.username || "").toLowerCase().includes(search.toLowerCase())
  );

  // ═══ STUDIO MODE ═══
  if (activePersona) {
    return (
      <div
        style={{
          minHeight: "calc(100vh - 80px)",
          background: "var(--m-bg, #0a0a0a)",
          padding: window.innerWidth < 640 ? "12px" : "24px 16px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {/* Back bar */}
        <div
          style={{
            width: "100%",
            maxWidth: "1100px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "20px",
          }}
        >
          <button
            onClick={() => setActivePersona(null)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 14px",
              borderRadius: "10px",
              background: "rgba(24,24,27,0.9)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "#888",
              fontSize: "13px",
              fontWeight: "500",
              cursor: "pointer",
              fontFamily: "inherit",
              backdropFilter: "blur(12px)",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "rgba(139, 92, 246, 0.3)";
              e.currentTarget.style.color = "#a78bfa";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
              e.currentTarget.style.color = "#888";
            }}
          >
            <ArrowLeft size={14} />
            Personalar
          </button>

          {/* Active persona chip */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 14px 6px 6px",
              borderRadius: "100px",
              background: "rgba(139, 92, 246, 0.08)",
              border: "1px solid rgba(139, 92, 246, 0.2)",
              backdropFilter: "blur(12px)",
            }}
          >
            <div
              style={{
                width: "24px",
                height: "24px",
                borderRadius: "50%",
                overflow: "hidden",
                background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
              }}
            >
              {activePersona.avatar_url && (
                <img
                  src={activePersona.avatar_url}
                  alt=""
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              )}
            </div>
            <span style={{ fontSize: "12px", fontWeight: "600", color: "#a78bfa" }}>
              {activePersona.display_name || activePersona.name}
            </span>
          </div>
        </div>

        {/* Pipeline workflow */}
        <StyleTransferMode
          preSelectedProfileId={activePersona.id}
          onEvolve={() => {}}
        />
      </div>
    );
  }

  // ═══ WELCOME / GRID VIEW ═══
  return (
    <div
      style={{
        minHeight: embedded ? "auto" : "calc(100vh - 80px)",
        background: embedded ? "transparent" : "var(--m-bg, #0a0a0a)",
        padding: embedded ? "0" : (window.innerWidth < 640 ? "16px 12px" : "32px 24px"),
        fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        color: "var(--m-text, #fff)",
      }}
    >
      <div style={{ maxWidth: "900px", margin: "0 auto" }}>
        {/* Header */}
        {!embedded && <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: mounted ? 1 : 0, y: mounted ? 0 : -16 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          style={{ marginBottom: "32px" }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 14px",
              borderRadius: "100px",
              background: "linear-gradient(135deg, rgba(139,92,246,0.1), rgba(168,85,247,0.06))",
              border: "1px solid rgba(139,92,246,0.2)",
              marginBottom: "14px",
            }}
          >
            <Zap size={14} style={{ color: "#a78bfa" }} />
            <span
              style={{
                fontSize: "12px",
                fontWeight: "600",
                background: "linear-gradient(135deg, #a78bfa, #c084fc)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Persona Lab
            </span>
          </div>

          <h1
            style={{
              fontSize: "clamp(22px, 4vw, 32px)",
              fontWeight: "700",
              marginBottom: "8px",
              letterSpacing: "-0.02em",
              lineHeight: "1.2",
            }}
          >
            Başka biri gibi yaz
          </h1>
          <p
            style={{
              fontSize: "14px",
              color: "var(--m-text-muted, #888)",
              lineHeight: "1.6",
              maxWidth: "480px",
            }}
          >
            X hesaplarını analiz et, yazım tarzlarını klonla. Her persona için 500+ tweet,
            stil parmak izi ve RAG tabanlı semantik eşleşme.
          </p>
        </motion.div>}

        {/* Toolbar */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: mounted ? 1 : 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "24px",
            flexWrap: "wrap",
          }}
        >
          {/* Search */}
          {personas.length > 3 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 12px",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.06)",
                borderRadius: "10px",
                flex: 1,
                minWidth: "180px",
                maxWidth: "300px",
              }}
            >
              <Search size={14} style={{ color: "var(--m-text-faint, #555)" }} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Persona ara..."
                style={{
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  color: "var(--m-text, #fff)",
                  fontSize: "13px",
                  width: "100%",
                  fontFamily: "inherit",
                }}
              />
            </div>
          )}

          {/* Create button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setCreateOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              border: "none",
              color: "white",
              fontSize: "13px",
              fontWeight: "600",
              cursor: "pointer",
              fontFamily: "inherit",
              boxShadow: "0 4px 16px rgba(139, 92, 246, 0.25)",
              marginLeft: personas.length > 3 ? "auto" : "0",
            }}
          >
            <Plus size={16} />
            Yeni Persona
          </motion.button>
        </motion.div>

        {/* Grid */}
        {loading ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "60px 0",
              color: "var(--m-text-muted, #888)",
              fontSize: "13px",
            }}
          >
            <Loader2 size={20} style={{ animation: "spin 1s linear infinite", marginRight: "8px" }} />
            Yükleniyor...
          </div>
        ) : filtered.length === 0 ? (
          /* Empty state */
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            style={{
              textAlign: "center",
              padding: "60px 20px",
              background: "var(--m-surface, #111)",
              border: "1.5px dashed rgba(255,255,255,0.08)",
              borderRadius: "20px",
            }}
          >
            <div
              style={{
                width: "64px",
                height: "64px",
                borderRadius: "16px",
                background: "linear-gradient(135deg, rgba(139,92,246,0.15), rgba(168,85,247,0.08))",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
              <User size={28} style={{ color: "#a78bfa" }} />
            </div>
            <h3
              style={{
                fontSize: "16px",
                fontWeight: "600",
                color: "var(--m-text, #fff)",
                marginBottom: "8px",
              }}
            >
              {search ? "Sonuç bulunamadı" : "Henüz persona yok"}
            </h3>
            <p
              style={{
                fontSize: "13px",
                color: "var(--m-text-muted, #888)",
                marginBottom: "20px",
                maxWidth: "300px",
                margin: "0 auto 20px",
                lineHeight: "1.5",
              }}
            >
              İlk personanı oluşturmak için bir X kullanıcı adı gir.
              Tweetleri analiz edilecek, yazım tarzı klonlanacak.
            </p>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setCreateOpen(true)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "12px 24px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
                border: "none",
                color: "white",
                fontSize: "14px",
                fontWeight: "600",
                cursor: "pointer",
                fontFamily: "inherit",
                boxShadow: "0 4px 16px rgba(139, 92, 246, 0.25)",
              }}
            >
              <Plus size={16} />
              İlk Personanı Oluştur
            </motion.button>
          </motion.div>
        ) : (
          /* Persona grid */
          <motion.div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
              gap: "16px",
            }}
          >
            <AnimatePresence>
              {filtered.map((persona) => (
                <PersonaCard
                  key={persona.id}
                  persona={persona}
                  onSelect={(p) => setActivePersona(p)}
                  onDelete={handleDelete}
                  deleting={deletingId === persona.id}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </div>

      {/* Create Dialog */}
      <CreatePersonaDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />

      {/* Keyframes */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
