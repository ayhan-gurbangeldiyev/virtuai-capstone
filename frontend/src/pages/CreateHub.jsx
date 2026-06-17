/**
 * @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import edilmiyor; route/nav yok.
 * Referans icin tutuluyor; aktif uygulama akisinin parcasi DEGIL. Bkz: docs/DEPRECATED_MODULES.md
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Zap, ChevronDown, ChevronUp, Plus, Minus, RefreshCw, Link, X, Dna,
  Trash2, Brain, Loader2, Check, Heart, Wand2, Copy, Settings2, Lightbulb,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";
import FloatingQueue from "@/components/generation/FloatingQueue";
import { useProfile } from "@/contexts/ProfileContext";
import { useTheme } from "@/components/ThemeProvider";

// ══════════════════════════════════════════
// SVG ICONS (Manus birebir)
// ══════════════════════════════════════════

const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const ChainIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const SettingsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

const EmojiIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><path d="M8 14s1.5 2 4 2 4-2 4-2" /><line x1="9" y1="9" x2="9.01" y2="9" /><line x1="15" y1="9" x2="15.01" y2="9" />
  </svg>
);

const MicIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2L12 22M12 2L5 9M12 2L19 9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
);

const ConnectChainIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 7h3a5 5 0 0 1 5 5 5 5 0 0 1-5 5h-3m-6 0H6a5 5 0 0 1-5-5 5 5 0 0 1 5-5h3" /><line x1="8" y1="12" x2="16" y2="12" />
  </svg>
);

// ══════════════════════════════════════════
// PLATFORM LOGOS (Manus birebir circular mini icons)
// ══════════════════════════════════════════

const XLogoMini = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="#000" />
    <path d="M16.3 8h2.1l-4.6 5.3L19 20h-3.5l-3-3.9L9 20H6.9l4.9-5.6L6.6 8h3.6l2.7 3.5L16.3 8zm-.7 10.8h1.2L10.1 9.2H8.8l6.8 9.6z" fill="#fff" />
  </svg>
);

const YoutubeLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="#FF0000" />
    <path d="M20.2 10.5a1.7 1.7 0 0 0-1.2-1.2C17.9 9 14 9 14 9s-3.9 0-5 .3a1.7 1.7 0 0 0-1.2 1.2 18 18 0 0 0-.3 3.5c0 1.2.1 2.4.3 3.5a1.7 1.7 0 0 0 1.2 1.2c1.1.3 5 .3 5 .3s3.9 0 5-.3a1.7 1.7 0 0 0 1.2-1.2c.2-1.1.3-2.3.3-3.5s-.1-2.4-.3-3.5z" fill="#fff" />
    <polygon points="12.2,16.5 16.8,14 12.2,11.5" fill="#FF0000" />
  </svg>
);

const InstagramLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <defs>
      <linearGradient id="ig-grad" x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#FFDC80" />
        <stop offset="25%" stopColor="#F77737" />
        <stop offset="50%" stopColor="#E1306C" />
        <stop offset="75%" stopColor="#C13584" />
        <stop offset="100%" stopColor="#833AB4" />
      </linearGradient>
    </defs>
    <circle cx="14" cy="14" r="14" fill="url(#ig-grad)" />
    <rect x="8" y="8" width="12" height="12" rx="3.5" fill="none" stroke="#fff" strokeWidth="1.5" />
    <circle cx="14" cy="14" r="3" fill="none" stroke="#fff" strokeWidth="1.5" />
    <circle cx="18" cy="10" r="1" fill="#fff" />
  </svg>
);

const TiktokLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="#000" />
    <path d="M17.5 8h-2v9.5a2.5 2.5 0 1 1-2.5-2.5v-2a4.5 4.5 0 1 0 4.5 4.5V12.8A5.5 5.5 0 0 0 20.5 14v-2a3.5 3.5 0 0 1-3-4z" fill="#25F4EE" />
    <path d="M16.5 8h-2v9.5a2.5 2.5 0 1 1-1.5-2.3v-2a4.5 4.5 0 1 0 3.5 4.3V12.8A5.5 5.5 0 0 0 19.5 14v-2a3.5 3.5 0 0 1-3-4z" fill="#FE2C55" />
    <path d="M15.5 8v9.5a2.5 2.5 0 1 1-2.5-2.5v-2a4.5 4.5 0 1 0 4.5 4.5V12.8A5.5 5.5 0 0 0 20.5 14v-2a3.5 3.5 0 0 1-3-4h-2z" fill="#fff" />
  </svg>
);

const LinkedinLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="#0A66C2" />
    <path d="M10 11.5v7h-2v-7h2zm-1-3a1.15 1.15 0 1 1 0 2.3 1.15 1.15 0 0 1 0-2.3zM12 18.5h2v-3.5c0-1 .2-2 1.4-2s1.3 1.1 1.3 2v3.5h2v-4c0-2.1-.5-3.7-2.8-3.7a2.5 2.5 0 0 0-2.2 1.2v-1H12v7.5z" fill="#fff" />
  </svg>
);

const BlogLogo = () => (
  <svg width="28" height="28" viewBox="0 0 28 28">
    <circle cx="14" cy="14" r="14" fill="#6366F1" />
    <path d="M9 8h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" fill="none" stroke="#fff" strokeWidth="1.3" />
    <line x1="10" y1="11" x2="18" y2="11" stroke="#fff" strokeWidth="1.2" />
    <line x1="10" y1="14" x2="18" y2="14" stroke="#fff" strokeWidth="1.2" />
    <line x1="10" y1="17" x2="15" y2="17" stroke="#fff" strokeWidth="1.2" />
  </svg>
);

// ══════════════════════════════════════════
// THEMES (Manus birebir)
// ══════════════════════════════════════════

// Use CSS variables from index.css (single source of truth for light/dark)
// This wrapper maps t.xxx to var(--m-xxx) so both CreateHub and XAIModule use same colors
const cssTheme = {
  bg: "var(--m-bg)",
  radial: "var(--m-grain)", // reuse grain slot for radial
  text: "var(--m-text)",
  textSoft: "var(--m-text-soft)",
  textMuted: "var(--m-text-muted)",
  textFaint: "var(--m-text-faint)",
  border: "var(--m-border)",
  borderLight: "var(--m-border-light)",
  surface: "var(--m-surface)",
  surfaceHover: "var(--m-surface-hover)",
  inputBg: "var(--m-input-bg)",
  inputBorder: "var(--m-input-border)",
  popupBg: "var(--m-popup-bg)",
  cardBg: "var(--m-card-bg)",
  shadow: "var(--m-shadow)",
  caret: "var(--m-caret)",
  accent: "var(--m-accent)",
  sendBg: "var(--m-send-bg)",
  sendText: "var(--m-send-text)",
  sendBgIdle: "var(--m-send-bg-idle)",
  sendTextIdle: "var(--m-send-text-idle)",
  scrollbar: "var(--m-scrollbar)",
  hoverBrightness: "var(--m-hover-brightness)",
  purple: "var(--m-purple)",
  purpleSoft: "var(--m-purple-soft)",
  purpleBorder: "var(--m-purple-border)",
  greenSoft: "var(--m-green-soft)",
  greenBorder: "var(--m-green-border)",
  green: "var(--m-green)",
  pillActiveBg: "var(--m-pill-active-bg)",
  pillActiveText: "var(--m-pill-active-text)",
  iconBtnBorder: "var(--m-icon-btn-border)",
  iconColor: "var(--m-icon-color)",
};

// ══════════════════════════════════════════
// DATA: Personas, Tones, Lengths, etc.
// ══════════════════════════════════════════

const personas = [
  { id: "saf", label: "Saf", desc: "Karakter yok, sadece sen" },
  { id: "otorite", label: "Otorite", desc: "Insider perspective, kesin" },
  { id: "insider", label: "Insider", desc: "Exclusive bilgi vibe" },
  { id: "mentalist", label: "Mentalist", desc: "Teknik + motivasyon" },
  { id: "haber", label: "Haber", desc: "Haber formatı" },
];

const tones = [
  { id: "natural", label: "Natural", desc: "Sıfır yapı, doğal akış" },
  { id: "raw", label: "Raw", desc: "Ham düşünce akışı" },
  { id: "polished", label: "Polished", desc: "Thesis→Evidence→Insight" },
  { id: "unhinged", label: "Unhinged", desc: "Shock→Escalate→Twist" },
];

const knowledgeModes = [
  { id: null, label: "Yok", desc: "Ekstra bilgi modu yok" },
  { id: "insider", label: "Insider", desc: "Perde arkası bilgi" },
  { id: "contrarian", label: "Contrarian", desc: "Herkesin tersini savun" },
  { id: "hidden", label: "Hidden", desc: "Gizli, az bilinen bilgi" },
  { id: "expert", label: "Expert", desc: "Derin uzmanlık bilgisi" },
];

const tweetLengths = [
  { id: "micro", label: "Micro", range: "50-100" },
  { id: "punch", label: "Punch", range: "140-280" },
  { id: "spark", label: "Spark", range: "400-600" },
  { id: "storm", label: "Storm", range: "700-1K" },
  { id: "thread", label: "Thread", range: "3-7 tweet" },
];

const replyLengths = [
  { id: "micro", label: "Micro", range: "50-100" },
  { id: "punch", label: "Punch", range: "140-280" },
  { id: "spark", label: "Spark", range: "400-600" },
];

const replyModes = [
  { id: "support", label: "Support", desc: "Katılır ve değer ekler" },
  { id: "challenge", label: "Challenge", desc: "Saygılıca karşı görüş sunar" },
  { id: "question", label: "Question", desc: "Merak edilen bir soru sorar" },
  { id: "expand", label: "Expand", desc: "Konuyu yeni bir boyuta taşır" },
  { id: "joke", label: "Joke", desc: "Esprili ve eğlenceli yanıt verir" },
];

const languages = [
  { id: "auto", label: "Otomatik" },
  { id: "tr", label: "Türkçe" },
  { id: "en", label: "English" },
];

const linkedinPersonas = [
  { id: "professional", label: "Profesyonel", desc: "Kurumsal ve ciddi" },
  { id: "thought_leader", label: "Thought Leader", desc: "Vizyoner ve ilham verici" },
  { id: "storyteller", label: "Storyteller", desc: "Hikaye anlatıcı" },
];

const youtubeStyles = [
  { id: "educational", label: "Eğitici" },
  { id: "entertaining", label: "Eğlenceli" },
  { id: "documentary", label: "Belgesel" },
  { id: "vlog", label: "Vlog" },
];

const blogStyles = [
  { id: "raw", label: "Raw" },
  { id: "authority", label: "Authority" },
  { id: "story", label: "Story" },
  { id: "tutorial", label: "Tutorial" },
  { id: "opinion", label: "Opinion" },
];

const blogLengths = [
  { id: "brief", label: "Brief", range: "1.5-2K" },
  { id: "standard", label: "Standard", range: "3-3.5K" },
  { id: "deep", label: "Deep", range: "5K+" },
];

// ══════════════════════════════════════════
// PLATFORM CONFIG
// ══════════════════════════════════════════

const PLATFORM_CONFIG = {
  twitter: {
    label: "X (Twitter)",
    heading: "\ud835\udd4f'te ne paylaşmak istersin?",
    placeholder: "Tweet konusu yaz veya bir fikir paylaş...",
    Logo: XLogoMini,
    contentTypes: [
      { id: "tweet", label: "Tweet yaz" },
      { id: "quote", label: "Alıntı" },
      { id: "reply", label: "Yanıt" },
      { id: "thread", label: "Thread" },
    ],
    hasUltraMode: true,
    hasStyleProfile: true,
  },
  linkedin: {
    label: "LinkedIn",
    heading: "LinkedIn'de ne paylaşmak istersin?",
    placeholder: "LinkedIn post konusu yaz...",
    Logo: LinkedinLogo,
    contentTypes: [
      { id: "post", label: "Post yaz" },
      { id: "carousel", label: "Carousel" },
      { id: "hook", label: "Hook üret" },
    ],
    hasUltraMode: false,
    hasStyleProfile: false,
  },
  instagram: {
    label: "Instagram",
    heading: "Instagram için ne üretmek istersin?",
    placeholder: "Instagram içeriği için konu yaz...",
    Logo: InstagramLogo,
    contentTypes: [
      { id: "caption", label: "Caption" },
      { id: "reel-script", label: "Reel Script" },
      { id: "story", label: "Story" },
      { id: "hashtags", label: "Hashtag" },
    ],
    hasUltraMode: false,
    hasStyleProfile: false,
  },
  youtube: {
    label: "YouTube",
    heading: "YouTube için ne oluşturmak istersin?",
    placeholder: "YouTube video konusu yaz...",
    Logo: YoutubeLogo,
    contentTypes: [
      { id: "idea", label: "Fikir" },
      { id: "script", label: "Script" },
      { id: "title", label: "Başlık" },
      { id: "description", label: "Açıklama" },
    ],
    hasUltraMode: false,
    hasStyleProfile: false,
  },
  tiktok: {
    label: "TikTok",
    heading: "TikTok için ne çekmek istersin?",
    placeholder: "TikTok video konusu yaz...",
    Logo: TiktokLogo,
    contentTypes: [
      { id: "script", label: "Script" },
      { id: "caption", label: "Caption" },
    ],
    hasUltraMode: false,
    hasStyleProfile: false,
  },
  blog: {
    label: "Blog",
    heading: "Blog için ne yazmak istersin?",
    placeholder: "Blog yazısı konusu yaz...",
    Logo: BlogLogo,
    contentTypes: [
      { id: "outline", label: "Taslak" },
      { id: "full", label: "Tam Yazı" },
      { id: "seo", label: "SEO" },
    ],
    hasUltraMode: false,
    hasStyleProfile: false,
  },
};

const PLATFORM_LOGOS = [
  { id: "twitter", Logo: XLogoMini },
  { id: "youtube", Logo: YoutubeLogo },
  { id: "instagram", Logo: InstagramLogo },
  { id: "tiktok", Logo: TiktokLogo },
  { id: "linkedin", Logo: LinkedinLogo },
  { id: "blog", Logo: BlogLogo },
];

// Promo cards
const promoCards = [
  { title: "Stil Klonlama", desc: "Beğendiğin hesabın yazım stilini klonla ve o tarzda içerik üret." },
  { title: "Ultra Mode", desc: "Viral potansiyeli en yüksek içerikler için ⚡ Ultra modunu dene." },
  { title: "Thread Gücü", desc: "Tek tweet yetmiyorsa, 3-7 tweet'lik thread'ler oluştur." },
];

// ══════════════════════════════════════════
// SETTINGS POPUP
// ══════════════════════════════════════════

function SettingsPopup({ open, onClose, settings, onSettingsChange, activeTab, platform, t }) {
  if (!open) return null;

  const isTwitter = platform === "twitter";
  const isLinkedIn = platform === "linkedin";
  const isBlog = platform === "blog";
  const isYouTube = platform === "youtube";

  const currentLengths = isTwitter
    ? (activeTab === "reply" ? replyLengths : tweetLengths)
    : isBlog ? blogLengths : null;

  const pillStyle = (isActive) => ({
    padding: "6px 14px",
    borderRadius: "999px",
    border: isActive ? "none" : `1px solid ${t.border}`,
    background: isActive ? t.pillActiveBg : "transparent",
    color: isActive ? t.pillActiveText : t.textSoft,
    fontSize: "13px",
    cursor: "pointer",
    transition: "all 0.2s ease",
  });

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div style={{ position: "relative", zIndex: 50, width: "100%", marginTop: "8px" }}>
        <div style={{
          background: t.popupBg,
          border: `1px solid ${t.border}`,
          borderRadius: "16px",
          padding: "14px 16px",
          backdropFilter: "blur(20px)",
          boxShadow: "0 -8px 30px rgba(0,0,0,0.3)",
          maxHeight: "50vh",
          overflowY: "auto",
        }}>
          <div className="flex items-center justify-between mb-3">
            <span style={{ fontSize: "13px", fontWeight: "600", color: t.text }}>Üretim Ayarları</span>
            <button onClick={onClose} style={{ background: "transparent", border: "none", color: t.textMuted, cursor: "pointer" }}>
              <X size={16} />
            </button>
          </div>

          {/* Persona (Twitter + LinkedIn) */}
          {(isTwitter || isLinkedIn) && (
            <div className="mb-2.5">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Karakter</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {(isLinkedIn ? linkedinPersonas : personas).map((p) => (
                  <button key={p.id} onClick={() => onSettingsChange({ ...settings, persona: p.id })} style={pillStyle(settings.persona === p.id)}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tone (Twitter only) */}
          {isTwitter && (
            <div className="mb-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Ton</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {tones.map((tn) => (
                  <button key={tn.id} onClick={() => onSettingsChange({ ...settings, tone: tn.id })} style={pillStyle(settings.tone === tn.id)}>
                    {tn.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Length (Twitter + Blog) */}
          {currentLengths && (
            <div className="mb-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Uzunluk</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {currentLengths.map((l) => (
                  <button key={l.id} onClick={() => onSettingsChange({ ...settings, length: l.id })} style={pillStyle(settings.length === l.id)}>
                    {l.label} <span style={{ opacity: 0.5, marginLeft: "4px" }}>{l.range}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Knowledge (Twitter only) */}
          {isTwitter && (
            <div className="mb-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Knowledge Mode</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {knowledgeModes.map((k) => (
                  <button key={k.id || "none"} onClick={() => onSettingsChange({ ...settings, knowledge: k.id })} style={pillStyle(settings.knowledge === k.id)}>
                    {k.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* YouTube Style */}
          {isYouTube && (
            <div className="mb-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Video Stili</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {youtubeStyles.map((s) => (
                  <button key={s.id} onClick={() => onSettingsChange({ ...settings, youtubeStyle: s.id })} style={pillStyle(settings.youtubeStyle === s.id)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Blog Style */}
          {isBlog && (
            <div className="mb-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Yazı Stili</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {blogStyles.map((s) => (
                  <button key={s.id} onClick={() => onSettingsChange({ ...settings, blogStyle: s.id })} style={pillStyle(settings.blogStyle === s.id)}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Language */}
          <div className="mb-2">
            <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Dil</label>
            <div style={{ display: "flex", gap: "8px" }}>
              {languages.map((l) => (
                <button key={l.id} onClick={() => onSettingsChange({ ...settings, language: l.id })} style={pillStyle(settings.language === l.id)}>
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Variant Count */}
          <div className="mb-2">
            <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Varyant Sayısı</label>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button onClick={() => onSettingsChange({ ...settings, variants: Math.max(1, settings.variants - 1) })}
                style={{ width: "32px", height: "32px", borderRadius: "50%", border: `1px solid ${t.border}`, background: "transparent", color: t.textSoft, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                <Minus size={14} />
              </button>
              <span style={{ fontSize: "18px", fontWeight: "600", color: t.text, width: "24px", textAlign: "center" }}>{settings.variants}</span>
              <button onClick={() => onSettingsChange({ ...settings, variants: Math.min(5, settings.variants + 1) })}
                style={{ width: "32px", height: "32px", borderRadius: "50%", border: `1px solid ${t.border}`, background: "transparent", color: t.textSoft, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                <Plus size={14} />
              </button>
            </div>
          </div>

          {/* Reply Mode (Twitter reply only) */}
          {isTwitter && activeTab === "reply" && (
            <div className="mb-2 mt-2">
              <label style={{ fontSize: "12px", color: t.textMuted, marginBottom: "4px", display: "block" }}>Reply Modu</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {replyModes.map((rm) => (
                  <button key={rm.id} onClick={() => onSettingsChange({ ...settings, replyMode: rm.id })} style={pillStyle(settings.replyMode === rm.id)}>
                    {rm.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════
// STYLE PROFILE BADGE
// ══════════════════════════════════════════

function StyleProfileBadge({ t }) {
  const { profiles, activeProfile, activeProfileId, setActiveProfile } = useProfile();
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setDropdownPos({ top: rect.top - 8, left: rect.left });
  }, []);

  useEffect(() => {
    if (!showDropdown) return;
    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    const handleClickOutside = (e) => {
      if (triggerRef.current?.contains(e.target) || dropdownRef.current?.contains(e.target)) return;
      setShowDropdown(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showDropdown, updatePosition]);

  if (!profiles || profiles.length === 0) return null;

  return (
    <div style={{ position: "relative" }}>
      <button
        ref={triggerRef}
        onClick={() => setShowDropdown(!showDropdown)}
        style={{
          display: "flex", alignItems: "center", gap: "6px", padding: "6px 14px",
          borderRadius: "999px",
          border: activeProfile ? `1px solid ${t.purpleBorder}` : `1px solid ${t.border}`,
          background: activeProfile ? t.purpleSoft : "transparent",
          color: activeProfile ? t.purple : t.textMuted,
          fontSize: "13px", cursor: "pointer", transition: "all 0.2s ease", whiteSpace: "nowrap",
        }}
      >
        {activeProfile?.twitter_usernames?.[0] ? (
          <img src={`https://unavatar.io/x/${activeProfile.twitter_usernames[0]}`} alt=""
            style={{ width: 18, height: 18, borderRadius: "50%", objectFit: "cover" }}
            onError={(e) => { e.target.style.display = "none"; }} />
        ) : (
          <Dna size={14} />
        )}
        {activeProfile ? activeProfile.name.split(" ")[0] : "Stil"}
        <ChevronDown size={12} style={{ opacity: 0.5 }} />
      </button>

      {showDropdown && (
        <div ref={dropdownRef} style={{
          position: "fixed", left: dropdownPos.left, top: dropdownPos.top,
          transform: "translateY(-100%)",
          background: t.popupBg, border: `1px solid ${t.border}`, borderRadius: "12px",
          padding: "8px", minWidth: "220px", backdropFilter: "blur(20px)", zIndex: 100, boxShadow: t.shadow,
        }}>
          {profiles.map((profile) => (
            <button key={profile.id} onClick={() => { setActiveProfile(profile.id); setShowDropdown(false); }}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px",
                borderRadius: "8px", border: "none",
                background: profile.id === activeProfileId ? t.purpleSoft : "transparent",
                color: profile.id === activeProfileId ? t.purple : t.textSoft,
                fontSize: "13px", cursor: "pointer", transition: "all 0.15s ease", textAlign: "left",
              }}>
              {profile.twitter_usernames?.[0] ? (
                <img src={`https://unavatar.io/x/${profile.twitter_usernames[0]}`} alt=""
                  style={{ width: 24, height: 24, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
                  onError={(e) => { e.target.onerror = null; e.target.style.display = "none"; }} />
              ) : (
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "linear-gradient(135deg, #a855f7, #ec4899)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <span style={{ fontSize: "10px", fontWeight: "700", color: "#fff" }}>{profile.name?.charAt(0)?.toUpperCase() || "S"}</span>
                </div>
              )}
              <span style={{ flex: 1 }}>{profile.name}</span>
              {profile.id === activeProfileId && <Check size={14} />}
            </button>
          ))}
          <div style={{ borderTop: `1px solid ${t.borderLight}`, margin: "4px 0", paddingTop: "4px" }}>
            <button onClick={() => { setActiveProfile(null); setShowDropdown(false); }}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", borderRadius: "8px", border: "none", background: "transparent", color: t.textMuted, fontSize: "13px", cursor: "pointer" }}>
              <X size={14} /><span>Stil kapalı</span>
            </button>
            <button onClick={() => { navigate("/dashboard/style-lab"); setShowDropdown(false); }}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px", borderRadius: "8px", border: "none", background: "transparent", color: t.purple, fontSize: "13px", cursor: "pointer" }}>
              <Dna size={14} /><span>Style Lab</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// TWEET PREVIEW CARD
// ══════════════════════════════════════════

function TweetPreviewCard({ tweet, t }) {
  if (!tweet) return null;
  const fmt = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num?.toString() || "0";
  };

  return (
    <div style={{ background: t.surface, border: `1px solid ${t.borderLight}`, borderRadius: "12px", padding: "14px 16px", marginBottom: "12px" }}>
      <div style={{ display: "flex", alignItems: "start", gap: "10px" }}>
        {tweet.author?.avatar && (
          <img src={tweet.author.avatar.replace("_normal", "_bigger")} alt="" style={{ width: "36px", height: "36px", borderRadius: "50%" }} />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: "600", fontSize: "13px", color: t.text }}>{tweet.author?.name}</span>
            <span style={{ fontSize: "12px", color: t.textMuted }}>@{tweet.author?.username}</span>
          </div>
          <p style={{ fontSize: "13px", color: t.textSoft, marginTop: "4px", whiteSpace: "pre-wrap", lineHeight: "1.5" }}>{tweet.text}</p>
          <div style={{ display: "flex", gap: "16px", marginTop: "8px", fontSize: "12px", color: t.textFaint }}>
            <span>💬 {fmt(tweet.metrics?.replies)}</span>
            <span>🔁 {fmt(tweet.metrics?.retweets)}</span>
            <span>❤️ {fmt(tweet.metrics?.likes)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════
// AI ANALYSIS DIALOG
// ══════════════════════════════════════════

function AIAnalysisDialog({ open, onOpenChange, profileData }) {
  const [copied, setCopied] = useState(false);
  if (!profileData) return null;
  const fp = profileData.style_fingerprint || {};
  const aiAnalysis = fp.ai_analysis || "";
  const stylePrompt = profileData.style_prompt || "";

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(stylePrompt);
    setCopied(true);
    toast.success("Stil prompt kopyalandı!");
    setTimeout(() => setCopied(false), 2000);
  };

  const sections = [];
  if (aiAnalysis) {
    const parts = aiAnalysis.split(/\d+\.\s+\*\*/);
    for (const part of parts) {
      if (!part.trim()) continue;
      const titleEnd = part.indexOf("**");
      if (titleEnd > 0) {
        sections.push({ title: part.substring(0, titleEnd).replace(/\*\*/g, "").trim(), content: part.substring(titleEnd + 2).replace(/^\s*:\s*/, "").trim() });
      } else {
        sections.push({ title: "", content: part.trim() });
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-purple-400" />
            AI Stil Analizi: {profileData.name}
          </DialogTitle>
          <DialogDescription>{fp.tweet_count || 0} tweet analiz edildi</DialogDescription>
        </DialogHeader>
        <div className="space-y-6 py-4">
          <div className="grid grid-cols-4 gap-3">
            {[
              { val: fp.tweet_count || 0, label: "Tweet", color: "sky" },
              { val: fp.avg_length || 0, label: "Ort. Karakter", color: "pink" },
              { val: fp.avg_engagement?.likes?.toFixed(0) || 0, label: "Ort. Beğeni", color: "green" },
              { val: fp.emoji_usage?.toFixed(1) || 0, label: "Emoji/Tweet", color: "purple" },
            ].map(({ val, label, color }) => (
              <div key={label} className={`p-3 rounded-xl bg-gradient-to-br from-${color}-500/10 to-${color}-500/10 border border-${color}-500/20 text-center`}>
                <p className={`text-2xl font-bold text-${color}-400`}>{val}</p>
                <p className="text-xs text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
          {sections.length > 0 && (
            <div className="space-y-3">
              {sections.map((section, idx) => (
                <div key={idx} className="p-4 rounded-xl bg-gradient-to-r from-purple-500/5 to-pink-500/5 border border-purple-500/10">
                  {section.title && <h5 className="font-medium text-purple-300 mb-2">{section.title}</h5>}
                  <p className="text-sm text-muted-foreground whitespace-pre-line leading-relaxed">{section.content}</p>
                </div>
              ))}
            </div>
          )}
          {stylePrompt && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-medium flex items-center gap-2">
                  <Wand2 className="h-4 w-4 text-pink-400" /> Stil Prompt
                </h4>
                <Button variant="ghost" size="sm" onClick={handleCopyPrompt} className="h-8 text-xs">
                  {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                  {copied ? "Kopyalandı" : "Kopyala"}
                </Button>
              </div>
              <div className="p-4 rounded-xl bg-secondary/30 border border-border/50 font-mono text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
                {stylePrompt}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ══════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════

let jobIdCounter = 0;

export default function CreateHub() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const t = cssTheme; // Single source: CSS variables handle light/dark automatically

  // State
  const [selectedPlatform, setSelectedPlatform] = useState(searchParams.get("platform") || "twitter");
  const [activeTab, setActiveTab] = useState(null);
  const [inputValue, setInputValue] = useState("");
  const [isLoaded, setIsLoaded] = useState(false);
  const [activeCard, setActiveCard] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tweetUrl, setTweetUrl] = useState("");
  const [tweetData, setTweetData] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageBase64, setImageBase64] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState(null);
  const [guideOpen, setGuideOpen] = useState(false);
  const textareaRef = useRef(null);
  const { activeProfileId, activeProfile } = useProfile();

  const [settings, setSettings] = useState({
    mode: "classic",
    persona: "otorite",
    tone: "natural",
    length: "punch",
    knowledge: null,
    language: "auto",
    variants: 3,
    replyMode: "support",
    youtubeStyle: "educational",
    blogStyle: "authority",
  });

  const platformCfg = PLATFORM_CONFIG[selectedPlatform] || PLATFORM_CONFIG.twitter;
  const contentTypes = platformCfg.contentTypes;
  const currentTab = activeTab || contentTypes[0]?.id || "tweet";

  // Platform switch
  const switchPlatform = (pid) => {
    setSelectedPlatform(pid);
    setActiveTab(null);
    setFetched(false);
    setTweetData(null);
    setTweetUrl("");
    setSearchParams({ platform: pid });
  };

  const switchContentType = (ctId) => {
    setActiveTab(ctId);
    setFetched(false);
    setTweetData(null);
    setTweetUrl("");
    if (selectedPlatform === "twitter") {
      if (ctId === "thread") setSettings((s) => ({ ...s, length: "thread" }));
      else if (ctId === "reply") setSettings((s) => ({ ...s, length: "punch" }));
    }
  };

  // URL params sync
  useEffect(() => {
    const p = searchParams.get("platform");
    if (p && p !== selectedPlatform) setSelectedPlatform(p);
  }, [searchParams]);

  // Init
  useEffect(() => {
    setIsLoaded(true);
    const topic = searchParams.get("topic") || "";
    const context = searchParams.get("trend_context") || "";
    if (topic) setInputValue(topic);
    if (context) setInputValue((prev) => prev ? `${prev}\n\n${context}` : context);
    const interval = setInterval(() => setActiveCard((prev) => (prev + 1) % promoCards.length), 5000);
    return () => clearInterval(interval);
  }, []);

  // History
  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await api.get(`${API}/generations/history`, { params: { limit: 20 } });
      setHistory(res.data || []);
    } catch (e) { /* silent */ } finally { setHistoryLoading(false); }
  }, []);

  useEffect(() => { fetchHistory(); }, [fetchHistory]);
  useEffect(() => { if (jobs.some((j) => j.status === "completed")) fetchHistory(); }, [jobs, fetchHistory]);

  const handleTextareaInput = (e) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  };

  // Fetch tweet
  const handleFetchTweet = async () => {
    const url = inputValue.trim();
    if (!url.match(/x\.com|twitter\.com/)) { toast.error("Tweet linki girin"); return; }
    setFetching(true);
    try {
      const response = await api.get(`${API}/tweet/fetch`, { params: { url } });
      if (response.data.success) {
        setTweetData(response.data.tweet);
        setTweetUrl(url);
        setFetched(true);
        toast.success("Tweet çekildi!");
      } else { toast.error("Tweet çekilemedi"); }
    } catch (error) { toast.error(error.response?.data?.detail || "Tweet çekilemedi"); }
    finally { setFetching(false); }
  };

  const updateJob = useCallback((jobId, updates) => {
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)));
  }, []);

  const dismissJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  // ══════════════════════════════════════════
  // GENERATE (platform-aware)
  // ══════════════════════════════════════════

  const handleGenerate = useCallback(async () => {
    const input = inputValue.trim();

    if (selectedPlatform === "twitter" && (currentTab === "quote" || currentTab === "reply")) {
      if (!fetched) {
        if (input.match(/x\.com|twitter\.com/)) { await handleFetchTweet(); return; }
        toast.error("Önce tweet linkini yapıştır");
        return;
      }
    } else if (!input) {
      toast.error("Bir şeyler yaz");
      return;
    }

    const jobId = `job-${++jobIdCounter}`;
    const newJob = {
      id: jobId,
      type: currentTab,
      platform: selectedPlatform,
      status: "generating",
      startedAt: Date.now(),
      topic: input.slice(0, 60) + (input.length > 60 ? "..." : ""),
      persona: settings.persona,
      personaLabel: personas.find((p) => p.id === settings.persona)?.label,
      toneLabel: tones.find((tn) => tn.id === settings.tone)?.label,
      variantCount: settings.variants,
      variants: null,
    };

    setJobs((prev) => [newJob, ...prev]);
    setGenerating(true);

    try {
      let endpoint, body;

      if (selectedPlatform === "twitter") {
        const type = currentTab === "thread" ? "tweet" : currentTab;
        if (type === "tweet") {
          endpoint = `${API}/generate/tweet`;
          body = {
            topic: input, mode: settings.mode,
            length: currentTab === "thread" ? "thread" : settings.length,
            variants: settings.variants, persona: settings.persona, tone: settings.tone,
            knowledge: settings.knowledge, language: settings.language,
            additional_context: null, style_profile_id: activeProfileId || null,
            image_url: imageUrl || null, image_base64: imageBase64 || null,
          };
        } else if (type === "quote") {
          endpoint = `${API}/generate/quote`;
          body = {
            tweet_url: tweetUrl, tweet_content: tweetData?.text || input,
            length: settings.length, variants: settings.variants, persona: settings.persona,
            tone: settings.tone, knowledge: settings.knowledge, language: settings.language,
            additional_context: null,
          };
        } else if (type === "reply") {
          endpoint = `${API}/generate/reply`;
          body = {
            tweet_url: tweetUrl, tweet_content: tweetData?.text || input,
            length: settings.length, reply_mode: settings.replyMode, variants: settings.variants,
            persona: settings.persona, tone: settings.tone, knowledge: settings.knowledge,
            language: settings.language, additional_context: null,
          };
        }
      } else if (selectedPlatform === "linkedin") {
        endpoint = `${API}/generate/linkedin`;
        body = {
          topic: input, format: currentTab || "post",
          persona: settings.persona || "professional",
          language: settings.language === "auto" ? "tr" : settings.language,
          additional_context: null,
        };
      } else if (selectedPlatform === "instagram") {
        endpoint = `${API}/generate/instagram/caption`;
        body = {
          topic: input, format: currentTab || "caption",
          language: settings.language === "auto" ? "tr" : settings.language,
          additional_context: null, variants: settings.variants,
        };
      } else if (selectedPlatform === "youtube") {
        endpoint = `${API}/generate/youtube/script`;
        body = {
          topic: input, duration_minutes: 10,
          style: settings.youtubeStyle || "educational",
          language: settings.language === "auto" ? "tr" : settings.language,
        };
      } else if (selectedPlatform === "tiktok") {
        endpoint = `${API}/generate/tiktok/script`;
        body = {
          topic: input, duration: "60",
          language: settings.language === "auto" ? "tr" : settings.language,
          additional_context: null,
        };
      } else if (selectedPlatform === "blog") {
        endpoint = `${API}/generate/blog/full`;
        body = {
          topic: input, style: settings.blogStyle || "authority",
          length: settings.length || "standard",
          language: settings.language === "auto" ? "tr" : settings.language,
          additional_context: null,
        };
      }

      const response = await api.post(endpoint, body);

      if (response.data.success || response.data.variants || response.data.content) {
        const variants = response.data.variants || (response.data.content ? [{ content: response.data.content }] : []);
        updateJob(jobId, { status: "completed", variants, generationId: response.data.generation_id });
        toast.success("İçerik üretildi!");
      } else {
        updateJob(jobId, { status: "error" });
        toast.error(response.data.error || "Üretim başarısız");
      }
    } catch (error) {
      updateJob(jobId, { status: "error" });
      toast.error(error.response?.data?.detail || "Bir hata oluştu");
    } finally {
      setGenerating(false);
    }
  }, [inputValue, currentTab, selectedPlatform, settings, fetched, tweetUrl, tweetData, activeProfileId, imageUrl, imageBase64, updateJob]);

  // Derived
  const needsUrl = selectedPlatform === "twitter" && (currentTab === "quote" || currentTab === "reply");
  const settingsSummary = selectedPlatform === "twitter"
    ? `${personas.find((p) => p.id === settings.persona)?.label} · ${tones.find((tn) => tn.id === settings.tone)?.label} · ${settings.variants}x`
    : `${settings.variants}x · ${languages.find((l) => l.id === settings.language)?.label}`;

  // ══════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════

  return (
    <div
      style={{
        minHeight: "100vh",
        background: t.bg,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        color: t.text,
        padding: "24px 16px",
        position: "relative",
        overflow: "hidden",
        transition: "background 0.35s ease, color 0.35s ease",
      }}
    >
      {/* Background radial */}
      {/* Subtle radial gradient overlay - hidden, bg comes from CSS vars */}

      {/* Spacer */}
      <div style={{ height: "12vh", flexShrink: 0 }} />

      {/* Plan Badge / Style Profile Badge */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: "0",
          background: t.borderLight, borderRadius: "999px", padding: "6px 4px",
          marginBottom: "28px", border: `1px solid ${t.borderLight}`,
          opacity: isLoaded ? 1 : 0, transform: isLoaded ? "translateY(0)" : "translateY(-8px)",
          transition: "all 0.5s ease 0.1s",
        }}
      >
        {platformCfg.hasStyleProfile ? (
          <StyleProfileBadge t={t} />
        ) : (
          <span style={{ fontSize: "13px", color: t.textMuted, padding: "4px 14px" }}>
            {platformCfg.label}
          </span>
        )}
        <span style={{ width: "1px", height: "14px", background: t.border }} />
        <span style={{ fontSize: "13px", color: t.textMuted, padding: "4px 14px", letterSpacing: "0.01em" }}>
          {settingsSummary}
        </span>
      </div>

      {/* Main Heading */}
      <h1
        style={{
          fontSize: "clamp(28px, 5vw, 42px)", fontWeight: "400",
          fontFamily: "'Georgia', 'Times New Roman', 'Noto Serif', serif",
          textAlign: "center", marginBottom: "36px", letterSpacing: "-0.01em",
          lineHeight: "1.25", fontStyle: "italic",
          opacity: isLoaded ? 1 : 0, transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.2s",
        }}
      >
        {platformCfg.heading}
      </h1>

      {/* Fetched Tweet Preview */}
      {fetched && tweetData && (
        <div style={{ width: "100%", maxWidth: "680px", marginBottom: "12px" }}>
          <TweetPreviewCard tweet={tweetData} t={t} />
        </div>
      )}

      {/* Chat Input Container */}
      <div
        style={{
          width: "100%", maxWidth: "680px", marginBottom: "16px",
          opacity: isLoaded ? 1 : 0, transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.3s",
        }}
      >
        {/* Ultra glow wrapper */}
        <div className={settings.mode === "apex" ? "ultra-glow-border" : ""} style={{ borderRadius: "18px", position: "relative" }}>
          <div
            style={{
              background: t.inputBg, border: `1px solid ${t.inputBorder}`,
              borderRadius: "16px", padding: "16px 18px 0", position: "relative",
              boxShadow: t.shadow,
              transition: "background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease",
            }}
          >
            {/* Image Preview */}
            {imageUrl && (
              <div style={{ marginBottom: "12px", position: "relative", display: "inline-block" }}>
                <img src={imageUrl} alt="" style={{ maxHeight: "80px", borderRadius: "8px" }} />
                <button onClick={() => { setImageUrl(null); setImageBase64(null); }}
                  style={{ position: "absolute", top: "-6px", right: "-6px", width: "20px", height: "20px", borderRadius: "50%", background: "#ef4444", border: "none", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
                  <X size={12} />
                </button>
              </div>
            )}

            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleTextareaInput}
              placeholder={platformCfg.placeholder}
              rows={2}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleGenerate(); }
              }}
              style={{
                width: "100%", background: "transparent", border: "none", outline: "none",
                color: t.text, fontSize: "15px", lineHeight: "1.55", resize: "none",
                fontFamily: "inherit", padding: "0", marginBottom: "14px", caretColor: t.caret,
              }}
            />

            {/* Toolbar (inside input box) */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: "12px" }}>
              {/* Left: Ultra, Link, Settings */}
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                {/* Ultra Mode Toggle (Zap replaces PlusIcon) */}
                {platformCfg.hasUltraMode && (
                  <button
                    onClick={() => setSettings((s) => ({ ...s, mode: s.mode === "apex" ? "classic" : "apex" }))}
                    style={{
                      width: "36px", height: "36px", borderRadius: "50%",
                      border: settings.mode === "apex" ? "1px solid rgba(234, 179, 8, 0.4)" : `1px solid ${t.iconBtnBorder}`,
                      background: settings.mode === "apex" ? "rgba(234, 179, 8, 0.12)" : "transparent",
                      color: settings.mode === "apex" ? "#eab308" : t.iconColor,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      cursor: "pointer", transition: "all 0.3s ease",
                      boxShadow: settings.mode === "apex" ? "0 0 12px rgba(234, 179, 8, 0.2)" : "none",
                    }} title={settings.mode === "apex" ? "Ultra mod aktif" : "Ultra moda geç"}>
                    <Zap size={18} style={{ fill: settings.mode === "apex" ? "#eab308" : "none" }} />
                  </button>
                )}

                {/* Link (ChainIcon - tweet fetch, only quote/reply) */}
                {needsUrl && (
                  <button onClick={handleFetchTweet} disabled={fetching}
                    style={{
                      width: "36px", height: "36px", borderRadius: "50%",
                      border: fetched ? `1px solid ${t.greenBorder}` : `1px solid ${t.iconBtnBorder}`,
                      background: fetched ? t.greenSoft : "transparent",
                      color: fetched ? t.green : t.iconColor,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      cursor: "pointer", transition: "all 0.2s ease",
                    }} title="Tweet çek">
                    {fetching ? <Loader2 size={18} className="animate-spin" /> : <ChainIcon />}
                  </button>
                )}

                {/* Settings (SettingsIcon) */}
                <button onClick={() => setSettingsOpen(!settingsOpen)}
                  style={{
                    width: "36px", height: "36px", borderRadius: "50%",
                    border: `1px solid ${t.iconBtnBorder}`,
                    background: settingsOpen ? t.surfaceHover : "transparent",
                    color: t.iconColor,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: "pointer", transition: "all 0.2s ease",
                  }} title="Ayarlar">
                  <SettingsIcon />
                </button>
              </div>

              {/* Right: Emoji, Mic, Send */}
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                {/* EmojiIcon placeholder */}
                <button style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  border: `1px solid ${t.iconBtnBorder}`, background: "transparent",
                  color: t.iconColor, display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: "pointer", transition: "all 0.2s ease", opacity: 0.5,
                }} title="Emoji">
                  <EmojiIcon />
                </button>

                {/* MicIcon placeholder */}
                <button style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  border: `1px solid ${t.iconBtnBorder}`, background: "transparent",
                  color: t.iconColor, display: "flex", alignItems: "center", justifyContent: "center",
                  cursor: "pointer", transition: "all 0.2s ease", opacity: 0.5,
                }} title="Sesli giriş">
                  <MicIcon />
                </button>

                {/* SendIcon (Generate) */}
                <button onClick={handleGenerate} disabled={generating}
                  style={{
                    width: "36px", height: "36px", borderRadius: "50%", border: "none",
                    background: inputValue.trim() || fetched ? t.sendBg : t.sendBgIdle,
                    color: inputValue.trim() || fetched ? t.sendText : t.sendTextIdle,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    cursor: inputValue.trim() || fetched ? "pointer" : "default",
                    transition: "all 0.25s ease",
                  }}>
                  {generating ? <Loader2 size={18} className="animate-spin" /> : <SendIcon />}
                </button>
              </div>
            </div>

            {/* Connect Tools Bar (inside input, border-top) */}
            <div
              style={{
                borderTop: `1px solid ${t.borderLight}`,
                padding: "10px 0 12px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <span style={{ fontSize: "12px", color: t.textMuted, whiteSpace: "nowrap", marginRight: "4px" }}>
                <ConnectChainIcon />{" "}
              </span>
              <span style={{ fontSize: "12px", color: t.textMuted, whiteSpace: "nowrap" }}>
                Platformunuzu seçin
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "auto" }}>
                {PLATFORM_LOGOS.map(({ id, Logo }) => {
                  const isActive = selectedPlatform === id;
                  return (
                    <button
                      key={id}
                      onClick={() => switchPlatform(id)}
                      className="tool-logo"
                      style={{
                        background: "none", border: "none", padding: "0", cursor: "pointer",
                        borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                        outline: isActive ? `2px solid ${t.accent}` : "none",
                        outlineOffset: "2px",
                        transform: isActive ? "scale(1.15)" : "scale(1)",
                        transition: "all 0.2s ease",
                        opacity: isActive ? 1 : 0.6,
                      }}
                      title={PLATFORM_CONFIG[id]?.label}
                    >
                      <Logo />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Settings Popup */}
        <SettingsPopup
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          settings={settings}
          onSettingsChange={setSettings}
          activeTab={currentTab}
          platform={selectedPlatform}
          t={t}
        />
      </div>

      {/* Quick Action Pills */}
      <div
        style={{
          display: "flex", flexWrap: "wrap", gap: "10px", justifyContent: "center",
          maxWidth: "680px", marginBottom: jobs.length > 0 ? "24px" : "40px",
          opacity: isLoaded ? 1 : 0, transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.45s",
        }}
      >
        {contentTypes.map((ct) => {
          const isActive = currentTab === ct.id;
          return (
            <button
              key={ct.id}
              onClick={() => switchContentType(ct.id)}
              style={{
                display: "flex", alignItems: "center", gap: "8px",
                padding: "9px 18px", borderRadius: "999px",
                border: isActive ? `1px solid ${t.textFaint}` : `1px solid ${t.border}`,
                background: isActive ? t.surfaceHover : "transparent",
                color: isActive ? t.text : t.textSoft,
                fontSize: "13.5px", cursor: "pointer", transition: "all 0.2s ease",
                fontFamily: "inherit", whiteSpace: "nowrap", letterSpacing: "0.01em",
                fontWeight: isActive ? "500" : "400",
              }}
            >
              {ct.label}
            </button>
          );
        })}
      </div>

      {/* Generation Results */}
      {jobs.length > 0 && (
        <div style={{ width: "100%", maxWidth: "680px", marginBottom: "24px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {jobs.map((job) => (
              <GenerationCard key={job.id} job={job} />
            ))}
          </div>
        </div>
      )}

      {/* Generation History */}
      <div style={{ width: "100%", maxWidth: "680px", marginBottom: "40px" }}>
        <button onClick={() => setHistoryOpen((p) => !p)}
          style={{
            display: "flex", alignItems: "center", gap: "8px", width: "100%", padding: "12px 0",
            background: "transparent", border: "none", cursor: "pointer",
            color: t.textSoft, fontSize: "14px", fontWeight: "600", fontFamily: "inherit",
          }}>
          {historyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          Geçmiş
          {history.length > 0 && (
            <span style={{ fontSize: "12px", color: t.textMuted, fontWeight: "400" }}>({history.length})</span>
          )}
        </button>

        {historyOpen && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {historyLoading && history.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px", color: t.textMuted, fontSize: "13px" }}>Yükleniyor...</div>
            )}
            {!historyLoading && history.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px", color: t.textMuted, fontSize: "13px" }}>Henüz üretim geçmişi yok</div>
            )}
            {history.map((gen) => {
              const isExpanded = expandedHistoryId === gen.id;
              const variants = gen.variants || [];
              const createdAt = gen.created_at ? new Date(gen.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
              const preview = variants[0]?.content?.slice(0, 100) || gen.topic?.slice(0, 100) || "";

              return (
                <div key={gen.id} style={{ background: t.surface, border: `1px solid ${t.borderLight}`, borderRadius: "12px", overflow: "hidden", transition: "border-color 0.2s ease" }}>
                  <button onClick={() => setExpandedHistoryId(isExpanded ? null : gen.id)}
                    style={{ display: "flex", alignItems: "center", gap: "12px", width: "100%", padding: "12px 16px", background: "transparent", border: "none", cursor: "pointer", textAlign: "left", fontFamily: "inherit", color: t.text }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "2px" }}>
                        <span style={{ fontSize: "13px", fontWeight: "500", color: t.text }}>{gen.topic || gen.type || "İçerik"}</span>
                        <span style={{ fontSize: "11px", padding: "2px 8px", borderRadius: "999px", background: t.borderLight, color: t.textMuted }}>{variants.length} varyant</span>
                      </div>
                      <div style={{ fontSize: "12px", color: t.textMuted }}>
                        {createdAt}
                        {!isExpanded && preview && <span style={{ marginLeft: "8px", opacity: 0.7 }}>— {preview}{preview.length >= 100 ? "..." : ""}</span>}
                      </div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} style={{ color: t.textMuted, flexShrink: 0 }} /> : <ChevronDown size={14} style={{ color: t.textMuted, flexShrink: 0 }} />}
                  </button>

                  {isExpanded && variants.length > 0 && (
                    <div style={{ padding: "0 16px 16px", display: "flex", flexDirection: "column", gap: "8px" }}>
                      {variants.map((variant, idx) => (
                        <div key={variant.id || idx} style={{ border: `1px solid ${t.borderLight}`, borderRadius: "8px", padding: "12px" }}>
                          <p style={{ fontSize: "13px", whiteSpace: "pre-wrap", lineHeight: "1.55", color: t.text, marginBottom: "10px" }}>{variant.content}</p>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: `1px solid ${t.borderLight}`, paddingTop: "8px" }}>
                            <span style={{ fontSize: "11px", color: t.textMuted }}>
                              {variant.character_count || variant.content?.length || 0} karakter
                              {variants.length > 1 && ` · Varyant ${idx + 1}`}
                            </span>
                            <div style={{ display: "flex", gap: "4px" }}>
                              {[
                                { icon: "📋", label: "Kopyala", action: () => { navigator.clipboard.writeText(variant.content); toast.success("Kopyalandı!"); } },
                                { icon: "♡", label: "Favori", action: () => { api.post(`${API}/favorites/toggle`, { content: variant.content, type: gen.type || "tweet", generation_id: gen.id, variant_index: idx }).then(() => toast.success("Favori güncellendi")).catch(() => toast.error("Hata")); } },
                                { icon: "🐦", label: "Tweetle", action: () => window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(variant.content)}`, "_blank") },
                              ].map((btn) => (
                                <button key={btn.label} onClick={btn.action} title={btn.label}
                                  style={{ padding: "4px 8px", borderRadius: "6px", border: `1px solid ${t.borderLight}`, background: "transparent", cursor: "pointer", fontSize: "12px", color: t.textSoft, transition: "all 0.15s ease", fontFamily: "inherit" }}>
                                  {btn.icon}
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom Promo Card Carousel */}
      <div
        style={{
          display: "flex", flexDirection: "column", alignItems: "center", gap: "12px",
          marginBottom: "40px",
          opacity: isLoaded ? 1 : 0, transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.55s",
        }}
      >
        <div
          style={{
            background: t.cardBg,
            border: `1px solid ${t.borderLight}`,
            borderRadius: "14px",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            gap: "20px",
            maxWidth: "440px",
            width: "max-content",
            cursor: "pointer",
            boxShadow: t.shadow,
            transition: "background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease",
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "15px", fontWeight: "600", marginBottom: "5px", color: t.text }}>
              {promoCards[activeCard].title}
            </div>
            <div style={{ fontSize: "13px", color: t.textMuted, lineHeight: "1.45" }}>
              {promoCards[activeCard].desc}
            </div>
          </div>
          <div
            style={{
              width: "90px", height: "64px",
              background: isDark ? "rgba(0,0,0,0.4)" : "rgba(0,0,0,0.06)",
              borderRadius: "8px",
              border: `1px solid ${t.borderLight}`,
              display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0,
            }}
          >
            <div style={{ height: "14px", background: t.surface, display: "flex", alignItems: "center", gap: "3px", padding: "0 5px" }}>
              <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#FF5F57" }} />
              <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#FEBC2E" }} />
              <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#28C840" }} />
              <span style={{ marginLeft: "6px", width: "30px", height: "3px", background: t.border, borderRadius: "2px" }} />
            </div>
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill={isDark ? "white" : "#1a1a1a"}>
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
            </div>
          </div>
        </div>

        {/* Carousel Dots */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          {promoCards.map((_, i) => (
            <button
              key={i}
              onClick={() => setActiveCard(i)}
              style={{
                width: i === activeCard ? "8px" : "6px",
                height: i === activeCard ? "8px" : "6px",
                borderRadius: "50%", border: "none",
                background: i === activeCard ? t.textSoft : t.border,
                cursor: "pointer", padding: 0, transition: "all 0.3s ease",
              }}
            />
          ))}
        </div>
      </div>

      {/* Floating Queue */}
      <FloatingQueue jobs={jobs} onDismiss={dismissJob} />

      {/* Global Styles */}
      <style>{`
        ::placeholder { color: ${t.textFaint}; }
        textarea:focus { outline: none !important; box-shadow: none !important; border-color: transparent !important; }
        textarea::-webkit-scrollbar { width: 4px; }
        textarea::-webkit-scrollbar-track { background: transparent; }
        textarea::-webkit-scrollbar-thumb { background: ${t.scrollbar}; border-radius: 4px; }
        button:focus { outline: none; }
        button:hover { filter: brightness(${t.hoverBrightness}); }
        .tool-logo:hover { transform: scale(1.2) !important; }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 640px) {
          h1 { font-size: 26px !important; }
        }
        @property --ultra-angle {
          syntax: '<angle>';
          initial-value: 0deg;
          inherits: false;
        }
        @keyframes ultra-rotate {
          from { --ultra-angle: 0deg; }
          to { --ultra-angle: 360deg; }
        }
        .ultra-glow-border {
          position: relative;
          background: transparent;
        }
        .ultra-glow-border::before {
          content: '';
          position: absolute;
          inset: 0;
          border-radius: 18px;
          padding: 2px;
          background: conic-gradient(
            from var(--ultra-angle, 0deg),
            #a855f7, #3b82f6, #06b6d4, #ec4899, #ef4444, #f97316, #a855f7
          );
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          animation: ultra-rotate 6s linear infinite;
          pointer-events: none;
        }
      `}</style>
    </div>
  );
}
