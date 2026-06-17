/**
 * StyleTransferMode — "Tarzını Kopyala" Pipeline UI v2
 * 
 * İyileştirmeler:
 *   - Persona seçimi: dropdown yerine merkezi modal dialog
 *   - Akıllı bağlantı çizgileri (durum bazlı renk + akış animasyonu)
 *   - Port noktaları (kartların kenarlarında)
 *   - Hover efekti (kutular hafif kalkar)
 *   - Odak (focus) border glow
 *   - Ana buton connector'ın ortasında
 *   - Çıktı boş durumu illüstrasyon
 *   - "Tekrar Dene" çıktı kutusunda
 *   - Opacity states (deaktif kutular soluk)
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2,
  ChevronDown,
  Search,
  Sparkles,
  Link as LinkIcon,
  Type,
  User,
  ExternalLink,
  Plus,
  Check,
  X,
  RotateCcw,
  FileText,
  Zap,
  ArrowRight,
  Wand2,
  PenLine,
} from "lucide-react";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";

// ─────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────
const isTwitterUrl = (text) => /(?:x|twitter)\.com\/.+\/status\/\d+/.test(text);

// ─────────────────────────────────────────────
// ANIMATED SVG CONNECTOR
// ─────────────────────────────────────────────
function Connector({ active, completed, vertical, generating }) {
  const length = vertical ? 48 : 64;
  const w = vertical ? 40 : length + 20;
  const h = vertical ? length + 10 : 40;

  const pathD = vertical
    ? `M 20 0 C 20 ${length * 0.4}, 20 ${length * 0.6}, 20 ${length}`
    : `M 0 20 C ${length * 0.4} 20, ${length * 0.6} 20, ${length} 20`;

  // Durum bazlı renk
  const baseColor = completed
    ? "rgba(139, 92, 246, 0.6)"
    : active
    ? "rgba(139, 92, 246, 0.35)"
    : "rgba(255,255,255,0.06)";

  const glowColor = "rgba(139, 92, 246, 0.8)";

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, position: "relative" }}>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible" }}>
        {/* Dotted base line */}
        <path
          d={pathD}
          fill="none"
          stroke={baseColor}
          strokeWidth="1.5"
          strokeDasharray={completed || active ? "none" : "4 6"}
          strokeLinecap="round"
          transform={vertical ? "translate(0, 5)" : "translate(10, 0)"}
          style={{ transition: "stroke 0.4s ease" }}
        />

        {/* Animated flowing dash */}
        {(active || generating) && (
          <path
            d={pathD}
            fill="none"
            stroke={glowColor}
            strokeWidth="2"
            strokeDasharray="8 12"
            strokeLinecap="round"
            transform={vertical ? "translate(0, 5)" : "translate(10, 0)"}
            style={{ animation: `flowDash ${generating ? "0.6s" : "2s"} linear infinite` }}
          />
        )}

        {/* Completed glow */}
        {completed && (
          <path
            d={pathD}
            fill="none"
            stroke={glowColor}
            strokeWidth="3"
            strokeLinecap="round"
            transform={vertical ? "translate(0, 5)" : "translate(10, 0)"}
            style={{ filter: "blur(4px)", opacity: 0.35 }}
          />
        )}

        {/* Flowing dot particle */}
        {(active || generating) && (
          <circle r="3" fill="#a78bfa" style={{ filter: "blur(1px)" }}>
            <animateMotion
              dur={generating ? "0.6s" : "2s"}
              repeatCount="indefinite"
              path={
                vertical
                  ? `M 20 5 C 20 ${length * 0.4 + 5}, 20 ${length * 0.6 + 5}, 20 ${length + 5}`
                  : `M 10 20 C ${length * 0.4 + 10} 20, ${length * 0.6 + 10} 20, ${length + 10} 20`
              }
            />
          </circle>
        )}

      </svg>
    </div>
  );
}

// ─────────────────────────────────────────────
// NODE WRAPPER (hover + focus + opacity states)
// ─────────────────────────────────────────────
function PipelineNode({ title, icon: Icon, index, active, completed, focused, noPadding, children }) {
  const borderColor = focused
    ? "rgba(139, 92, 246, 0.6)"
    : completed
    ? "rgba(139, 92, 246, 0.5)"
    : active
    ? "rgba(139, 92, 246, 0.35)"
    : "rgba(255,255,255,0.06)";

  const headerBg = completed
    ? "rgba(139, 92, 246, 0.12)"
    : active
    ? "rgba(139, 92, 246, 0.06)"
    : "rgba(255,255,255,0.02)";

  const isInactive = !active && !completed;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: isInactive ? 0.45 : 1, y: 0 }}
      transition={{ delay: index * 0.12, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        height: "480px",
        maxHeight: "480px",
        background: "var(--m-surface, #111111)",
        border: `1.5px solid ${borderColor}`,
        borderRadius: "16px",
        overflow: "hidden",
        transition: "border-color 0.3s ease, box-shadow 0.3s ease, opacity 0.4s ease",
        boxShadow: focused
          ? "0 0 35px rgba(139, 92, 246, 0.12)"
          : completed
          ? "0 0 30px rgba(139, 92, 246, 0.08)"
          : active
          ? "0 0 20px rgba(139, 92, 246, 0.05)"
          : "none",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: "8px",
        padding: "10px 14px", background: headerBg,
        borderBottom: `1px solid ${borderColor}`,
        transition: "background 0.3s ease",
      }}>
        <div style={{
          width: "22px", height: "22px", borderRadius: "6px",
          background: completed ? "rgba(139, 92, 246, 0.2)" : "rgba(255,255,255,0.05)",
          display: "flex", alignItems: "center", justifyContent: "center",
          transition: "background 0.3s ease",
        }}>
          {completed ? (
            <Check size={12} style={{ color: "#a78bfa" }} />
          ) : (
            <Icon size={12} style={{ color: active ? "#a78bfa" : "var(--m-text-faint, #555)" }} />
          )}
        </div>
        <span style={{
          fontSize: "12px", fontWeight: "600",
          color: active || completed ? "var(--m-text, #fff)" : "var(--m-text-muted, #888)",
          letterSpacing: "0.3px", textTransform: "uppercase",
        }}>
          {title}
        </span>
        {completed && (
          <motion.div
            initial={{ scale: 0 }} animate={{ scale: 1 }}
            style={{ marginLeft: "auto", width: "6px", height: "6px", borderRadius: "50%", background: "#a78bfa" }}
          />
        )}
      </div>

      {/* Body — scrollable when content overflows */}
      <div style={{ padding: noPadding ? "0" : "14px", overflow: "hidden", flex: 1, overflowY: "auto" }} className="scrollbar-hide">{children}</div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────
// NODE 1: SOURCE (Kaynak)
// ─────────────────────────────────────────────
function SourceNode({ value, onChange, fetchedTweet, onClearTweet, onFetchTweet, fetching, onFocus, onBlur }) {
  const showUrlHint = isTwitterUrl(value.trim()) && !fetchedTweet;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <AnimatePresence>
        {fetchedTweet && (
          <motion.div
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            style={{
              background: "rgba(139, 92, 246, 0.05)", border: "1px solid rgba(139, 92, 246, 0.15)",
              borderRadius: "10px", padding: "12px", position: "relative", overflow: "hidden",
            }}
          >
            <button onClick={onClearTweet} style={{
              position: "absolute", top: "8px", right: "8px", width: "20px", height: "20px",
              borderRadius: "50%", background: "rgba(255,255,255,0.08)", border: "none",
              display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", color: "var(--m-text-muted, #888)",
            }}>
              <X size={10} />
            </button>
            <div style={{ display: "flex", gap: "10px", alignItems: "start" }}>
              <img src={`https://unavatar.io/x/${fetchedTweet.author_username}`} alt=""
                style={{ width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0, background: "rgba(255,255,255,0.05)" }}
                onError={(e) => { e.target.style.display = "none"; }} />
              <div style={{ flex: 1, paddingRight: "16px" }}>
                <div style={{ fontSize: "11px", fontWeight: "600", color: "var(--m-text, #fff)", marginBottom: "2px" }}>
                  {fetchedTweet.author_name}
                  <span style={{ fontWeight: "400", color: "var(--m-text-muted, #888)", marginLeft: "6px" }}>
                    @{fetchedTweet.author_username}
                  </span>
                </div>
                <p style={{
                  fontSize: "12px", color: "var(--m-text-soft, #ccc)", lineHeight: "1.5", margin: 0,
                  whiteSpace: "pre-wrap", display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {fetchedTweet.text}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!fetchedTweet && (
        <div style={{ position: "relative" }}>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Tweet URL veya serbest metin yapıştır..."
            rows={4}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); if (showUrlHint) onFetchTweet(); }
            }}
            disabled={fetching}
            onFocus={onFocus}
            onBlur={onBlur}
            style={{
              width: "100%", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
              borderRadius: "10px", padding: "12px", color: "var(--m-text, #fff)", fontSize: "13px",
              lineHeight: "1.55", resize: "none", fontFamily: "inherit", outline: "none",
              transition: "border-color 0.2s ease",
            }}
          />
          {fetching && (
            <div style={{
              position: "absolute", bottom: "10px", right: "10px", display: "flex", alignItems: "center", gap: "5px",
              padding: "4px 10px", borderRadius: "16px", background: "rgba(139, 92, 246, 0.15)", fontSize: "11px", color: "#a78bfa",
            }}>
              <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} /> Yükleniyor
            </div>
          )}
          {showUrlHint && !fetching && (
            <button onClick={onFetchTweet} style={{
              position: "absolute", bottom: "10px", right: "10px", display: "flex", alignItems: "center", gap: "5px",
              padding: "5px 12px", borderRadius: "16px", background: "linear-gradient(135deg, #7c3aed, #a855f7)",
              border: "none", color: "white", fontSize: "11px", fontWeight: "600", cursor: "pointer", fontFamily: "inherit",
            }}>
              <LinkIcon size={10} /> Yükle
            </button>
          )}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "5px", fontSize: "10px", color: "var(--m-text-faint, #555)" }}>
        {fetchedTweet ? <><LinkIcon size={9} /> Tweet yüklendi</>
          : value.trim() ? (isTwitterUrl(value.trim()) ? <><LinkIcon size={9} /> URL algılandı</> : <><Type size={9} /> Serbest metin</>)
          : <><FileText size={9} /> URL veya metin gir</>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// PERSONA MODAL
// ─────────────────────────────────────────────
function PersonaModal({ open, onClose, profiles, selected, onSelect, loading }) {
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const filtered = profiles.filter(
    (p) => p.name.toLowerCase().includes(search.toLowerCase()) || (p.username || "").toLowerCase().includes(search.toLowerCase())
  );

  if (!open) return null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
          style={{
            position: "fixed", inset: 0, zIndex: 100,
            background: "rgba(0,0,0,0.7)", backdropFilter: "blur(8px)",
            display: "flex", alignItems: "center", justifyContent: "center",
            padding: "16px",
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%", maxWidth: "420px",
              background: "#151515", border: "1.5px solid rgba(255,255,255,0.08)",
              borderRadius: "20px", overflow: "hidden",
              boxShadow: "0 24px 80px rgba(0,0,0,0.6), 0 0 40px rgba(139,92,246,0.05)",
            }}
          >
            {/* Header */}
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "18px 20px 14px",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: "700", color: "#fff" }}>Persona Seç</h3>
                <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--m-text-muted, #888)" }}>
                  Kayıtlı personalardan seç veya yenisini oluştur
                </p>
              </div>
              <button onClick={onClose} style={{
                width: "28px", height: "28px", borderRadius: "8px",
                background: "rgba(255,255,255,0.05)", border: "none",
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer", color: "#888", transition: "all 0.15s",
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.1)"; e.currentTarget.style.color = "#fff"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.color = "#888"; }}
              >
                <X size={14} />
              </button>
            </div>

            {/* Search */}
            <div style={{ padding: "12px 16px 8px" }}>
              <div style={{
                display: "flex", alignItems: "center", gap: "8px",
                padding: "10px 14px", background: "rgba(255,255,255,0.03)",
                borderRadius: "12px", border: "1px solid rgba(255,255,255,0.06)",
              }}>
                <Search size={14} style={{ color: "#555", flexShrink: 0 }} />
                <input
                  type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                  placeholder="Kayıtlı personalarda ara..." autoFocus
                  style={{
                    background: "transparent", border: "none", outline: "none",
                    color: "#fff", fontSize: "13px", width: "100%", fontFamily: "inherit",
                  }}
                />
              </div>
            </div>

            {/* List */}
            <div style={{ maxHeight: "320px", overflowY: "auto", padding: "4px 12px 12px" }}>
              {loading ? (
                <div style={{ padding: "32px", textAlign: "center", color: "#888" }}>
                  <Loader2 size={20} style={{ animation: "spin 1s linear infinite" }} />
                </div>
              ) : filtered.length === 0 ? (
                <div style={{ padding: "32px", textAlign: "center", color: "#888", fontSize: "13px" }}>
                  {profiles.length === 0 ? "Henüz persona yok" : "Sonuç bulunamadı"}
                </div>
              ) : (
                filtered.map((p) => {
                  const isSelected = selected === p.id;
                  return (
                    <motion.button
                      key={p.id}
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      onClick={() => { onSelect(p.id); onClose(); setSearch(""); }}
                      style={{
                        width: "100%", display: "flex", alignItems: "center", gap: "12px",
                        padding: "12px 14px", marginBottom: "4px",
                        background: isSelected ? "rgba(139, 92, 246, 0.1)" : "rgba(255,255,255,0.02)",
                        border: isSelected ? "1.5px solid rgba(139,92,246,0.4)" : "1.5px solid transparent",
                        borderRadius: "14px", cursor: "pointer", fontFamily: "inherit",
                        transition: "all 0.2s ease",
                      }}
                      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.05)"; }}
                      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
                    >
                      <div style={{
                        width: "40px", height: "40px", borderRadius: "50%", overflow: "hidden", flexShrink: 0,
                        background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        {p.avatar_url ? (
                          <img src={p.avatar_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }}
                            onError={(e) => { e.target.style.display = "none"; }} />
                        ) : (
                          <span style={{ color: "white", fontSize: "16px", fontWeight: "600" }}>
                            {(p.display_name || p.name || "?")[0]}
                          </span>
                        )}
                      </div>
                      <div style={{ flex: 1, textAlign: "left" }}>
                        <div style={{ fontSize: "14px", fontWeight: "600", color: "#fff" }}>
                          {p.display_name || p.name}
                        </div>
                        <div style={{ fontSize: "11px", color: "#888", marginTop: "2px" }}>
                          @{p.username} · {p.tweet_count} tweet
                        </div>
                      </div>
                      {isSelected && (
                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }}>
                          <Check size={18} style={{ color: "#8b5cf6" }} />
                        </motion.div>
                      )}
                    </motion.button>
                  );
                })
              )}
            </div>

            {/* Add new */}
            <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", padding: "12px 16px" }}>
              <button
                onClick={() => { onClose(); navigate("/dashboard/persona-lab"); }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
                  padding: "12px", background: "rgba(139,92,246,0.08)", border: "1.5px solid rgba(139,92,246,0.2)",
                  borderRadius: "12px", cursor: "pointer", fontFamily: "inherit",
                  color: "#a78bfa", fontSize: "13px", fontWeight: "600",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(139,92,246,0.15)"; e.currentTarget.style.borderColor = "rgba(139,92,246,0.4)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(139,92,246,0.08)"; e.currentTarget.style.borderColor = "rgba(139,92,246,0.2)"; }}
              >
                <Plus size={16} />
                Yeni Persona Oluştur
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ─────────────────────────────────────────────
// NODE 2: PERSONA (modal trigger)
// ─────────────────────────────────────────────
function PersonaNode({ profiles, selected, onOpenModal, loading, generating }) {
  const selectedProfile = profiles.find((p) => p.id === selected);

  if (generating) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "12px", padding: "20px 0" }}>
        {selectedProfile?.avatar_url && (
          <div style={{ width: "48px", height: "48px", borderRadius: "50%", overflow: "hidden", position: "relative" }}>
            <img src={selectedProfile.avatar_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <div style={{ position: "absolute", inset: "-4px", borderRadius: "50%", border: "2px solid rgba(139, 92, 246, 0.5)", animation: "pulseRing 1.5s ease-out infinite" }} />
          </div>
        )}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "12px", fontWeight: "600", color: "#a78bfa", marginBottom: "4px" }}>Tarz analiz ediliyor...</div>
          <div style={{ fontSize: "11px", color: "var(--m-text-faint, #555)" }}>{selectedProfile?.display_name || selectedProfile?.name}</div>
        </div>
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: "linear" }}>
          <Loader2 size={18} style={{ color: "#7c3aed" }} />
        </motion.div>
      </div>
    );
  }

  return (
    <button
      onClick={onOpenModal}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: "10px",
        padding: "10px 12px", background: "rgba(255,255,255,0.02)",
        border: "1.5px solid rgba(255,255,255,0.06)", borderRadius: "10px",
        cursor: "pointer", transition: "all 0.2s ease", fontFamily: "inherit",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(139,92,246,0.3)"; e.currentTarget.style.background = "rgba(139,92,246,0.04)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
    >
      {selectedProfile ? (
        <>
          <div style={{
            width: "34px", height: "34px", borderRadius: "50%", overflow: "hidden", flexShrink: 0,
            background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {selectedProfile.avatar_url ? (
              <img src={selectedProfile.avatar_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }}
                onError={(e) => { e.target.style.display = "none"; }} />
            ) : (
              <span style={{ color: "white", fontSize: "14px", fontWeight: "600" }}>
                {(selectedProfile.display_name || selectedProfile.name || "?")[0]}
              </span>
            )}
          </div>
          <div style={{ flex: 1, textAlign: "left" }}>
            <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--m-text, #fff)", lineHeight: "1.3" }}>
              {selectedProfile.display_name || selectedProfile.name}
            </div>
            <div style={{ fontSize: "11px", color: "var(--m-text-muted, #888)" }}>
              @{selectedProfile.username} · {selectedProfile.tweet_count} tweet
            </div>
          </div>
          <ChevronDown size={16} style={{ color: "var(--m-text-muted, #888)", flexShrink: 0 }} />
        </>
      ) : (
        <>
          <div style={{
            width: "34px", height: "34px", borderRadius: "50%", background: "rgba(255,255,255,0.05)",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <User size={16} style={{ color: "var(--m-text-faint, #555)" }} />
          </div>
          <div style={{ fontSize: "13px", color: "var(--m-text-muted, #888)", textAlign: "left" }}>Hedef kişiyi seç</div>
          <ChevronDown size={16} style={{ color: "var(--m-text-faint, #555)", flexShrink: 0 }} />
        </>
      )}
    </button>
  );
}

// ─────────────────────────────────────────────
// NODE 3: OUTPUT (illüstrasyon + tekrar dene)
// ─────────────────────────────────────────────
function OutputNode({ jobs, onEvolve, generating, onRetry }) {
  if (generating) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "10px", padding: "24px 0", minHeight: "120px" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          {[0, 1, 2].map((i) => (
            <motion.div key={i} animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1, 0.8] }}
              transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
              style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#a78bfa" }} />
          ))}
        </div>
        <span style={{ fontSize: "12px", color: "var(--m-text-muted, #888)" }}>İçerik üretiliyor...</span>
      </div>
    );
  }

  const completedJobs = jobs.filter((j) => j.status === "completed");

  if (completedJobs.length === 0) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        gap: "12px", padding: "28px 0", minHeight: "120px",
      }}>
        {/* Artistic empty state */}
        <div style={{ position: "relative", width: "48px", height: "48px" }}>
          <motion.div
            animate={{ rotate: [0, 360] }}
            transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
            style={{
              width: "48px", height: "48px", borderRadius: "50%",
              background: "conic-gradient(from 0deg, rgba(139,92,246,0.15), rgba(168,85,247,0.05), rgba(139,92,246,0.15))",
              position: "absolute", inset: 0,
            }}
          />
          <div style={{
            position: "absolute", inset: "8px", borderRadius: "50%",
            background: "var(--m-surface, #111)", display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <PenLine size={16} style={{ color: "rgba(139,92,246,0.4)" }} />
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "12px", color: "var(--m-text-faint, #555)", lineHeight: "1.5" }}>
            Yaratılmayı bekliyor
          </div>
          <div style={{ fontSize: "10px", color: "var(--m-text-faint, #444)", marginTop: "2px" }}>
            Metin gir ve persona seç
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflowX: "hidden", wordBreak: "break-word" }}>
      {/* Scrollable variant list */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }} className="scrollbar-hide">
        {jobs.map((job, idx) => (
          <div key={job.id}>
            {idx > 0 && <div style={{ height: "1px", background: "rgba(255,255,255,0.08)", margin: "0" }} />}
            <GenerationCard job={job} onEvolve={onEvolve} compact />
          </div>
        ))}
      </div>
      {/* Sticky bottom button */}
      {completedJobs.length > 0 && onRetry && (
        <button onClick={onRetry} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: "6px",
          padding: "8px 0", borderRadius: "8px", width: "100%", flexShrink: 0,
          background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)",
          color: "var(--m-text-muted, #888)", fontSize: "12px", fontWeight: "500",
          cursor: "pointer", fontFamily: "inherit", transition: "all 0.2s ease", marginTop: "8px",
        }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(139,92,246,0.3)"; e.currentTarget.style.color = "#a78bfa"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; e.currentTarget.style.color = "var(--m-text-muted, #888)"; }}
        >
          <RotateCcw size={12} /> Tekrar Dene
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// MAIN COMPONENT
// ─────────────────────────────────────────────
let stJobIdCounter = 0;

export default function StyleTransferMode({ onEvolve, preSelectedProfileId }) {
  const [profiles, setProfiles] = useState([]);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [selectedProfileId, setSelectedProfileId] = useState(preSelectedProfileId || null);
  const [inputValue, setInputValue] = useState("");
  const [fetchedTweet, setFetchedTweet] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [mounted, setMounted] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [modalOpen, setModalOpen] = useState(false);
  const [sourceFocused, setSourceFocused] = useState(false);

  useEffect(() => {
    setMounted(true);
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`${API}/style-transfer/profiles`);
        const p = res.data.profiles || [];
        setProfiles(p);
        if (p.length === 1 && !preSelectedProfileId) setSelectedProfileId(p[0].id);
      } catch (e) { toast.error("Profiller yüklenemedi"); }
      finally { setProfilesLoading(false); }
    })();
  }, []);

  const prevInput = useRef("");
  useEffect(() => {
    const trimmed = inputValue.trim();
    if (!trimmed || fetching || fetchedTweet) return;
    if (isTwitterUrl(trimmed) && trimmed.length - prevInput.current.length > 10) handleFetchTweet(trimmed);
    prevInput.current = trimmed;
  }, [inputValue]);

  const handleFetchTweet = async (url) => {
    if (!url) url = inputValue.trim();
    if (!isTwitterUrl(url)) return;
    setFetching(true);
    try {
      const res = await api.get(`${API}/tweet/fetch`, { params: { url } });
      if (res.data.success) {
        const t = res.data.tweet;
        setFetchedTweet({ text: t.text, author_name: t.author?.name || "", author_username: t.author?.username || "", url });
        setInputValue(""); toast.success("Tweet yüklendi");
      }
    } catch (e) { toast.error("Tweet yüklenemedi"); }
    finally { setFetching(false); }
  };

  const handleGenerate = useCallback(async () => {
    const text = inputValue.trim();
    const sourceText = fetchedTweet?.text || text;
    if (!sourceText) { toast.error("Kaynak metin veya tweet URL'si gerekli"); return; }
    if (!selectedProfileId) { toast.error("Bir stil profili seç"); return; }
    if (isTwitterUrl(text) && !fetchedTweet) { await handleFetchTweet(text); return; }

    const jobId = `st-${++stJobIdCounter}`;
    const profile = profiles.find((p) => p.id === selectedProfileId);
    const targetName = profile?.display_name || profile?.name || "";

    setJobs((prev) => [{
      id: jobId, type: "style-transfer", status: "generating", startedAt: Date.now(),
      topic: fetchedTweet ? `@${fetchedTweet.author_username} → ${targetName}` : `"${text.slice(0, 40)}..." → ${targetName}`,
      persona: "ghost", personaLabel: targetName, toneLabel: "Style Transfer", lengthLabel: "", variantCount: 3, variants: null,
    }, ...prev]);
    setGenerating(true);

    try {
      const body = { target_profile_id: selectedProfileId, variant_count: 3 };
      if (fetchedTweet) { body.source_url = fetchedTweet.url; body.source_text = fetchedTweet.text; }
      else { body.source_text = text; }

      const res = await api.post(`${API}/style-transfer`, body);
      if (res.data.success) {
        setJobs((prev) => prev.map((j) => j.id === jobId ? { ...j, status: "completed", variants: res.data.variants, generationId: res.data.generation_id } : j));
        toast.success("Tarz kopyalandı ✨");
      } else {
        setJobs((prev) => prev.map((j) => j.id === jobId ? { ...j, status: "error" } : j));
        toast.error("Bir hata oluştu");
      }
    } catch (e) {
      setJobs((prev) => prev.map((j) => j.id === jobId ? { ...j, status: "error" } : j));
      toast.error(e.response?.data?.detail || "Bir hata oluştu");
    } finally { setGenerating(false); }
  }, [inputValue, fetchedTweet, selectedProfileId, profiles]);

  const handleRetry = useCallback(() => { setJobs([]); setTimeout(() => handleGenerate(), 50); }, [handleGenerate]);
  const handleReset = () => { setInputValue(""); setFetchedTweet(null); setJobs([]); };

  const hasSource = !!(inputValue.trim() || fetchedTweet);
  const hasPersona = !!selectedProfileId;
  const hasOutput = jobs.some((j) => j.status === "completed");
  const canGenerate = hasSource && hasPersona && !generating;

  return (
    <div style={{ width: "100%", maxWidth: isMobile ? "400px" : "1100px", opacity: mounted ? 1 : 0, transition: "opacity 0.5s ease", overflowX: "hidden" }}>
      {/* Title */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
        style={{ textAlign: "center", marginBottom: isMobile ? "20px" : "32px" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: "8px", padding: "6px 16px", borderRadius: "100px",
          background: "linear-gradient(135deg, rgba(139,92,246,0.1), rgba(168,85,247,0.06))",
          border: "1px solid rgba(139,92,246,0.2)", marginBottom: "10px",
        }}>
          <Zap size={14} style={{ color: "#a78bfa" }} />
          <span style={{
            fontSize: "12px", fontWeight: "600",
            background: "linear-gradient(135deg, #a78bfa, #c084fc)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", letterSpacing: "0.3px",
          }}>
            Tarzını Kopyala
          </span>
        </div>
        <p style={{ fontSize: "12px", color: "var(--m-text-muted, #888)", maxWidth: "340px", margin: "0 auto", lineHeight: "1.5" }}>
          Metin veya tweet gir → Hedef kişiyi seç → Tarzıyla yeniden yazılsın
        </p>
      </motion.div>

      {/* ═══ PIPELINE ═══ */}
      {isMobile ? (
        /* Mobile: vertical stack */
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0" }}>
          <PipelineNode title="Kaynak" icon={FileText} index={0} active={hasSource || (!hasSource && !hasPersona)} completed={hasSource} focused={sourceFocused}>
            <SourceNode value={inputValue} onChange={setInputValue} fetchedTweet={fetchedTweet}
              onClearTweet={() => setFetchedTweet(null)} onFetchTweet={() => handleFetchTweet()} fetching={fetching}
              onFocus={() => setSourceFocused(true)} onBlur={() => setSourceFocused(false)} />
          </PipelineNode>
          <Connector active={hasSource} completed={hasSource && hasPersona} vertical generating={generating} />
          <PipelineNode title="Persona" icon={User} index={1} active={hasSource && !hasOutput} completed={hasPersona} focused={modalOpen}>
            <PersonaNode profiles={profiles} selected={selectedProfileId} onOpenModal={() => setModalOpen(true)} loading={profilesLoading} generating={generating} />
          </PipelineNode>
          <Connector active={hasSource && hasPersona} completed={hasOutput} vertical generating={generating} />
          <PipelineNode title="Çıktı" icon={Sparkles} index={2} active={generating} completed={hasOutput} noPadding={hasOutput}>
            <OutputNode jobs={jobs} onEvolve={onEvolve} generating={generating} onRetry={handleRetry} />
          </PipelineNode>
        </div>
      ) : (
        /* Desktop: rigid 3-column CSS Grid, equal height */
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr auto 1fr",
          alignItems: "center",
          width: "100%",
          maxWidth: "1100px",
          margin: "0 auto",
        }}>
          {/* Col 1: Kaynak */}
          <div style={{ width: "100%", maxWidth: "340px", display: "flex", flexDirection: "column" }}>
            <PipelineNode title="Kaynak" icon={FileText} index={0} active={hasSource || (!hasSource && !hasPersona)} completed={hasSource} focused={sourceFocused}>
              <SourceNode value={inputValue} onChange={setInputValue} fetchedTweet={fetchedTweet}
                onClearTweet={() => setFetchedTweet(null)} onFetchTweet={() => handleFetchTweet()} fetching={fetching}
                onFocus={() => setSourceFocused(true)} onBlur={() => setSourceFocused(false)} />
            </PipelineNode>
          </div>

          {/* Col 2: Connector 1→2 */}
          <div style={{ display: "flex", alignItems: "center", alignSelf: "center", margin: "0 -4px" }}>
            <Connector active={hasSource} completed={hasSource && hasPersona} vertical={false} generating={generating} />
          </div>

          {/* Col 3: Persona */}
          <div style={{ width: "100%", maxWidth: "320px", justifySelf: "center", display: "flex", flexDirection: "column" }}>
            <PipelineNode title="Persona" icon={User} index={1} active={hasSource && !hasOutput} completed={hasPersona} focused={modalOpen}>
              <PersonaNode profiles={profiles} selected={selectedProfileId} onOpenModal={() => setModalOpen(true)} loading={profilesLoading} generating={generating} />
            </PipelineNode>
          </div>

          {/* Col 4: Connector 2→3 */}
          <div style={{ display: "flex", alignItems: "center", alignSelf: "center", margin: "0 -4px" }}>
            <Connector active={hasSource && hasPersona} completed={hasOutput} vertical={false} generating={generating} />
          </div>

          {/* Col 5: Çıktı */}
          <div style={{ width: "100%", maxWidth: "380px", display: "flex", flexDirection: "column" }}>
            <PipelineNode title="Çıktı" icon={Sparkles} index={2} active={generating} completed={hasOutput} noPadding={hasOutput}>
              <OutputNode jobs={jobs} onEvolve={onEvolve} generating={generating} onRetry={handleRetry} />
            </PipelineNode>
          </div>
        </div>
      )}

      {/* ═══ BOTTOM ACTIONS ═══ */}
      {/* ═══ BOTTOM ACTIONS ═══ */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
        style={{ display: "flex", justifyContent: "center", gap: "10px", marginTop: "24px" }}>
        {hasOutput && (
          <button onClick={handleReset} style={{
            display: "flex", alignItems: "center", gap: "6px", padding: "10px 18px", borderRadius: "12px",
            background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
            color: "var(--m-text-muted, #888)", fontSize: "13px", fontWeight: "500",
            cursor: "pointer", fontFamily: "inherit", transition: "all 0.2s ease",
          }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(139,92,246,0.3)"; e.currentTarget.style.color = "#a78bfa"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)"; e.currentTarget.style.color = "var(--m-text-muted, #888)"; }}
          >
            <RotateCcw size={14} /> Yeni Dönüşüm
          </button>
        )}
        {!hasOutput && (
          <motion.button
            whileHover={canGenerate ? { scale: 1.02, y: -1 } : {}}
            whileTap={canGenerate ? { scale: 0.98 } : {}}
            onClick={handleGenerate}
            disabled={!canGenerate}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
              padding: "12px 32px", borderRadius: "12px", border: "none",
              background: canGenerate ? "linear-gradient(135deg, #7c3aed, #a855f7)" : "rgba(255,255,255,0.04)",
              color: canGenerate ? "white" : "var(--m-text-faint, #555)",
              fontSize: "14px", fontWeight: "600", fontFamily: "inherit",
              cursor: canGenerate ? "pointer" : "not-allowed",
              boxShadow: canGenerate ? "0 4px 20px rgba(139, 92, 246, 0.25)" : "none",
              transition: "all 0.3s ease", minWidth: "200px",
            }}
          >
            {generating ? (
              <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Kopyalanıyor...</>
            ) : (
              <><Sparkles size={16} /> Tarzını Kopyala</>
            )}
          </motion.button>
        )}
      </motion.div>

      {/* Persona Modal */}
      <PersonaModal
        open={modalOpen} onClose={() => setModalOpen(false)}
        profiles={profiles} selected={selectedProfileId}
        onSelect={setSelectedProfileId} loading={profilesLoading}
      />

      {/* ═══ KEYFRAMES ═══ */}
      <style>{`
        @keyframes flowDash { from { stroke-dashoffset: 40; } to { stroke-dashoffset: 0; } }
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
        @keyframes pulseRing { 0% { transform: scale(1); opacity: 0.6; } 100% { transform: scale(1.5); opacity: 0; } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
