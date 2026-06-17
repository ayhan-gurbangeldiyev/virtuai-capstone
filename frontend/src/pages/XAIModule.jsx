import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from 'react-i18next';
import { createPortal } from "react-dom";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Zap,
  ChevronDown,
  ChevronUp,
  Plus,
  Minus,
  RefreshCw,
  Link,
  Image,
  Upload,
  Repeat2,
  Settings2,
  X,
  Dna,
  Trash2,
  Brain,
  Loader2,
  Check,
  Heart,
  Target,
  Wand2,
  Copy,
  TrendingUp,
  Lightbulb,
  MessageSquare,
  Quote,
  MessageCircleReply,
  FileText,
  Send,
  Mic,
  Smile,
  MoreHorizontal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api, { API } from "@/lib/api";
import GenerationCard from "@/components/generation/GenerationCard";
import EvolvePanel from "@/components/generation/EvolvePanel";
import FloatingQueue from "@/components/generation/FloatingQueue";
import RepurposeModal from "@/components/RepurposeModal";
import StyleTransferMode from "@/components/generation/StyleTransferMode";
import { useProfile } from "@/contexts/ProfileContext";

// ══════════════════════════════════════════
// DATA: Personas, Tones, Lengths, etc.
// ══════════════════════════════════════════

// v1 settings (diğer platformlar için korunuyor)
const personas = [
  { id: "saf", labelKey: "create.personas.saf", descKey: "create.personas.safDesc" },
  { id: "otorite", labelKey: "create.personas.otorite", descKey: "create.personas.otoriteDesc" },
  { id: "insider", labelKey: "create.personas.insider", descKey: "create.personas.insiderDesc" },
  { id: "mentalist", labelKey: "create.personas.mentalist", descKey: "create.personas.mentalistDesc" },
  { id: "haber", labelKey: "create.personas.haber", descKey: "create.personas.haberDesc" },
];

const tones = [
  { id: "natural", labelKey: "create.tones.natural", descKey: "create.tones.naturalDesc" },
  { id: "raw", labelKey: "create.tones.raw", descKey: "create.tones.rawDesc" },
  { id: "polished", labelKey: "create.tones.polished", descKey: "create.tones.polishedDesc" },
  { id: "unhinged", labelKey: "create.tones.unhinged", descKey: "create.tones.unhingedDesc" },
];

const knowledgeModes = [
  { id: null, labelKey: "create.knowledgeModes.none", descKey: "create.knowledgeModes.noneDesc" },
  { id: "insider", labelKey: "create.knowledgeModes.insider", descKey: "create.knowledgeModes.insiderDesc" },
  { id: "contrarian", labelKey: "create.knowledgeModes.contrarian", descKey: "create.knowledgeModes.contrarianDesc" },
  { id: "hidden", labelKey: "create.knowledgeModes.hidden", descKey: "create.knowledgeModes.hiddenDesc" },
  { id: "expert", labelKey: "create.knowledgeModes.expert", descKey: "create.knowledgeModes.expertDesc" },
];

// ══════════════════════════════════════════
// V2 DATA: Etki, Karakter, Yapı, etc. (sadece X platformu)
// ══════════════════════════════════════════

const v2Etkiler = [
  { id: "patlassin", labelKey: "create.effects.patlassin", descKey: "create.effects.patlassinDesc" },
  { id: "konustursun", labelKey: "create.effects.konustursun", descKey: "create.effects.konustursunDesc" },
  { id: "ogretsin", labelKey: "create.effects.ogretsin", descKey: "create.effects.ogretsinDesc" },
  { id: "iz_biraksin", labelKey: "create.effects.izBiraksin", descKey: "create.effects.izBiraksinDesc" },
  { id: "shitpost", labelKey: "create.effects.shitpost", descKey: "create.effects.shitpostDesc" },
];

const v2Karakterler = [
  { id: "uzman", labelKey: "create.characters.uzman", descKey: "create.characters.uzmanDesc" },
  { id: "otorite", labelKey: "create.characters.otorite", descKey: "create.characters.otoriteDesc" },
  { id: "iceriden", labelKey: "create.characters.iceriden", descKey: "create.characters.iceridenDesc" },
  { id: "mentalist", labelKey: "create.characters.mentalist", descKey: "create.characters.mentalistDesc" },
  { id: "haberci", labelKey: "create.characters.haberci", descKey: "create.characters.haberciDesc" },
];

const v2Yapilar = [
  { id: "dogal", labelKey: "create.structures.dogal", descKey: "create.structures.dogalDesc" },
  { id: "kurgulu", labelKey: "create.structures.kurgulu", descKey: "create.structures.kurguluDesc" },
  { id: "cesur", labelKey: "create.structures.cesur", descKey: "create.structures.cesurDesc" },
];

const v2Acilislar = [
  { id: "otomatik", labelKey: "create.openings.otomatik", descKey: "create.openings.otomatikDesc" },
  { id: "zit_gorus", labelKey: "create.openings.zitGorus", descKey: "create.openings.zitGorusDesc" },
  { id: "merak", labelKey: "create.openings.merak", descKey: "create.openings.merakDesc" },
  { id: "hikaye", labelKey: "create.openings.hikaye", descKey: "create.openings.hikayeDesc" },
  { id: "tartisma", labelKey: "create.openings.tartisma", descKey: "create.openings.tartismaDesc" },
];

const v2Bitisler = [
  { id: "otomatik", labelKey: "create.endings.otomatik", descKey: "create.endings.otomatikDesc" },
  { id: "soru", labelKey: "create.endings.soru", descKey: "create.endings.soruDesc" },
  { id: "dogal", labelKey: "create.endings.dogal", descKey: "create.endings.dogalDesc" },
];

const v2Derinlikler = [
  { id: "standart", labelKey: "create.depths.standart", descKey: "create.depths.standartDesc" },
  { id: "karsi_gorus", labelKey: "create.depths.karsiGorus", descKey: "create.depths.karsiGorusDesc" },
  { id: "perde_arkasi", labelKey: "create.depths.perdeArkasi", descKey: "create.depths.perdeArkasiDesc" },
  { id: "uzmanlik", labelKey: "create.depths.uzmanlik", descKey: "create.depths.uzmanlikDesc" },
];

const v2SmartDefaults = {
  patlassin:   { karakter: "uzman",    yapi: "kurgulu", uzunluk: "punch", acilis: "otomatik", bitis: "otomatik", derinlik: "standart" },
  konustursun: { karakter: "iceriden", yapi: "dogal",   uzunluk: "spark", acilis: "tartisma", bitis: "soru",     derinlik: "karsi_gorus" },
  ogretsin:    { karakter: "otorite",  yapi: "kurgulu", uzunluk: "punch", acilis: "merak",    bitis: "dogal",    derinlik: "uzmanlik" },
  iz_biraksin: { karakter: "uzman",    yapi: "dogal",   uzunluk: "spark", acilis: "hikaye",   bitis: "dogal",    derinlik: "standart" },
  shitpost:    { karakter: null,       yapi: "dogal",   uzunluk: null,    acilis: "otomatik", bitis: "dogal",    derinlik: "standart" },
};

const v2KarakterYapiUyum = {
  uzman:    { dogal: true, kurgulu: true, cesur: true },
  otorite:  { dogal: true, kurgulu: true, cesur: true },
  iceriden: { dogal: true, kurgulu: true, cesur: false },
  mentalist:{ dogal: true, kurgulu: true, cesur: false },
  haberci:  { dogal: true, kurgulu: true, cesur: false },
};

const tweetLengths = [
  { id: "micro", labelKey: "create.lengths.micro", range: "50-100" },
  { id: "punch", labelKey: "create.lengths.punch", range: "140-280" },
  { id: "spark", labelKey: "create.lengths.spark", range: "400-600" },
  { id: "storm", labelKey: "create.lengths.storm", range: "700-1K" },
  { id: "thread", labelKey: "create.lengths.thread", range: "3-7 tweet" },
];

const replyLengths = [
  { id: "micro", labelKey: "create.lengths.micro", range: "50-100" },
  { id: "punch", labelKey: "create.lengths.punch", range: "140-280" },
  { id: "spark", labelKey: "create.lengths.spark", range: "400-600" },
];

const articleLengths = [
  { id: "brief", labelKey: "create.lengths.brief", range: "1.5-2K" },
  { id: "standard", labelKey: "create.lengths.standard", range: "3-3.5K" },
  { id: "deep", labelKey: "create.lengths.deep", range: "5K+" },
];

const replyModes = [
  { id: "support", labelKey: "create.replyModes.support", descKey: "create.replyModes.supportDesc" },
  { id: "challenge", labelKey: "create.replyModes.challenge", descKey: "create.replyModes.challengeDesc" },
  { id: "question", labelKey: "create.replyModes.question", descKey: "create.replyModes.questionDesc" },
  { id: "expand", labelKey: "create.replyModes.expand", descKey: "create.replyModes.expandDesc" },
  { id: "joke", labelKey: "create.replyModes.joke", descKey: "create.replyModes.jokeDesc" },
];

const articleStyles = [
  { id: "raw", labelKey: "create.articleStyles.raw", descKey: "create.articleStyles.rawDesc" },
  { id: "authority", labelKey: "create.articleStyles.authority", descKey: "create.articleStyles.authorityDesc" },
  { id: "story", labelKey: "create.articleStyles.story", descKey: "create.articleStyles.storyDesc" },
  { id: "tutorial", labelKey: "create.articleStyles.tutorial", descKey: "create.articleStyles.tutorialDesc" },
  { id: "opinion", labelKey: "create.articleStyles.opinion", descKey: "create.articleStyles.opinionDesc" },
];

const languages = [
  { id: "auto", labelKey: "create.languages.auto" },
  { id: "tr", labelKey: "create.languages.tr" },
  { id: "en", labelKey: "create.languages.en" },
];

// Content type tabs for quick actions (legacy, unused — see PLATFORM_CONTENT_TYPES_DATA)
const contentTypes = [
  { id: "tweet", icon: MessageSquare, labelKey: "create.contentTypes.tweet" },
  { id: "quote", icon: Repeat2, labelKey: "create.contentTypes.quote" },
  { id: "reply", icon: MessageCircleReply, labelKey: "create.contentTypes.reply" },
  { id: "thread", icon: FileText, labelKey: "create.contentTypes.thread" },
];

// Content type label keys resolved via t() in component
const PLATFORM_CONTENT_TYPES_DATA = {
  twitter: [
    { id: "tweet", icon: MessageSquare, labelKey: "create.contentTypes.tweet" },
    { id: "quote", icon: Repeat2, labelKey: "create.contentTypes.quote" },
    { id: "reply", icon: MessageCircleReply, labelKey: "create.contentTypes.reply" },
    { id: "thread", icon: FileText, labelKey: "create.contentTypes.thread" },
  ],
  youtube: [
    { id: "video-script", icon: FileText, labelKey: "create.contentTypes.videoScript" },
    { id: "title-desc", icon: MessageSquare, labelKey: "create.contentTypes.titleDesc" },
    { id: "shorts-script", icon: Repeat2, labelKey: "create.contentTypes.shortsScript" },
  ],
  instagram: [
    { id: "caption", icon: MessageSquare, labelKey: "create.contentTypes.caption" },
    { id: "reel-script", icon: FileText, labelKey: "create.contentTypes.reelScript" },
    { id: "story", icon: Quote, labelKey: "create.contentTypes.storyText" },
  ],
  tiktok: [
    { id: "hook", icon: Repeat2, labelKey: "create.contentTypes.hook" },
    { id: "script", icon: FileText, labelKey: "create.contentTypes.script" },
    { id: "caption", icon: MessageSquare, labelKey: "create.contentTypes.caption" },
  ],
  linkedin: [
    { id: "post", icon: MessageSquare, labelKey: "create.contentTypes.postWrite" },
    { id: "article", icon: FileText, labelKey: "create.contentTypes.article" },
    { id: "carousel", icon: Quote, labelKey: "create.contentTypes.carousel" },
  ],
  blog: [
    { id: "blog-article", icon: FileText, labelKey: "create.contentTypes.blogArticle" },
    { id: "blog-listicle", icon: MessageSquare, labelKey: "create.contentTypes.listicle" },
    { id: "blog-tutorial", icon: Quote, labelKey: "create.contentTypes.tutorial" },
  ],
};

// Placeholder keys - resolved via t() in component
const PLATFORM_PLACEHOLDER_KEYS = {
  twitter: {
    tweet: "create.placeholders.tweetTopic",
    quote: "create.placeholders.quoteTweet",
    reply: "create.placeholders.replyTweet",
    thread: "create.placeholders.threadTopic",
  },
  youtube: {
    "video-script": "create.placeholders.videoScript",
    "title-desc": "create.placeholders.titleDesc",
    "shorts-script": "create.placeholders.shortsScript",
  },
  instagram: {
    caption: "create.placeholders.captionTopic",
    "reel-script": "create.placeholders.reelIdea",
    story: "create.placeholders.storyTopic",
  },
  tiktok: {
    hook: "create.placeholders.hookTopic",
    script: "create.placeholders.tiktokScript",
    caption: "create.placeholders.tiktokCaption",
  },
  linkedin: {
    post: "create.placeholders.linkedinPost",
    article: "create.placeholders.linkedinArticle",
    carousel: "create.placeholders.linkedinCarousel",
  },
  blog: {
    article: "create.placeholders.blogArticle",
    listicle: "create.placeholders.blogListicle",
    tutorial: "create.placeholders.blogTutorial",
  },
};

// Platform headings resolved via t() inside component
const PLATFORM_HEADING_KEYS = {
  twitter: "create.platformHeadings.twitter",
  youtube: "create.platformHeadings.youtube",
  instagram: "create.platformHeadings.instagram",
  tiktok: "create.platformHeadings.tiktok",
  linkedin: "create.platformHeadings.linkedin",
  blog: "create.platformHeadings.blog",
};

// ══════════════════════════════════════════
// SVG Icons (Manus-style)
// ══════════════════════════════════════════

const TypeHypeLogo = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

// ══════════════════════════════════════════
// SETTINGS POPUP
// ══════════════════════════════════════════

// LinkedIn ayarları
const linkedinPersonas = [
  { id: "thought_leader", labelKey: "create.linkedinPersonas.thoughtLeader", descKey: "create.linkedinPersonas.thoughtLeaderDesc" },
  { id: "storyteller", labelKey: "create.linkedinPersonas.storyteller", descKey: "create.linkedinPersonas.storytellerDesc" },
  { id: "data_driven", labelKey: "create.linkedinPersonas.dataDriven", descKey: "create.linkedinPersonas.dataDrivenDesc" },
  { id: "motivator", labelKey: "create.linkedinPersonas.motivator", descKey: "create.linkedinPersonas.motivatorDesc" },
];
const linkedinFormats = [
  { id: "standard", labelKey: "create.linkedinFormats.standard", descKey: "create.linkedinFormats.standardDesc" },
  { id: "listicle", labelKey: "create.linkedinFormats.listicle", descKey: "create.linkedinFormats.listicleDesc" },
  { id: "story", labelKey: "create.linkedinFormats.story", descKey: "create.linkedinFormats.storyDesc" },
  { id: "carousel_text", labelKey: "create.linkedinFormats.carouselText", descKey: "create.linkedinFormats.carouselTextDesc" },
  { id: "poll", labelKey: "create.linkedinFormats.poll", descKey: "create.linkedinFormats.pollDesc" },
  { id: "micro", labelKey: "create.linkedinFormats.micro", descKey: "create.linkedinFormats.microDesc" },
];

// Blog ayarları
const blogStyles = [
  { id: "informative", labelKey: "create.blogStyles.informative", descKey: "create.blogStyles.informativeDesc" },
  { id: "personal", labelKey: "create.blogStyles.personal", descKey: "create.blogStyles.personalDesc" },
  { id: "technical", labelKey: "create.blogStyles.technical", descKey: "create.blogStyles.technicalDesc" },
  { id: "opinion", labelKey: "create.blogStyles.opinion", descKey: "create.blogStyles.opinionDesc" },
  { id: "listicle", labelKey: "create.blogStyles.listicle", descKey: "create.blogStyles.listicleDesc" },
  { id: "case_study", labelKey: "create.blogStyles.caseStudy", descKey: "create.blogStyles.caseStudyDesc" },
];
const blogFrameworks = [
  { id: "answer_first", labelKey: "create.blogFrameworks.answerFirst", descKey: "create.blogFrameworks.answerFirstDesc" },
  { id: "pas", labelKey: "create.blogFrameworks.pas", descKey: "create.blogFrameworks.pasDesc" },
  { id: "aida", labelKey: "create.blogFrameworks.aida", descKey: "create.blogFrameworks.aidaDesc" },
  { id: "storytelling", labelKey: "create.blogFrameworks.storytelling", descKey: "create.blogFrameworks.storytellingDesc" },
];
const blogLevels = [
  { id: "quick", labelKey: "create.blogLevels.quickTake", descKey: "create.blogLevels.quickTakeDesc" },
  { id: "standard", labelKey: "create.blogLevels.standard", descKey: "create.blogLevels.standardDesc" },
  { id: "deep_dive", labelKey: "create.blogLevels.deepDive", descKey: "create.blogLevels.deepDiveDesc" },
  { id: "ultimate", labelKey: "create.blogLevels.ultimate", descKey: "create.blogLevels.ultimateDesc" },
];

function SettingsPopup({ open, onClose, settings, onSettingsChange, activeTab, activePlatform, onGenerate }) {
  const { t } = useTranslation();
  const [advOpen, setAdvOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 640);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 640);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  if (!open) return null;

  const isTwitter = activePlatform === "twitter";
  const currentLengths = activeTab === "reply" ? replyLengths : 
                         activeTab === "article" ? articleLengths : tweetLengths;

  // v2: Etki seçildiğinde smart defaults uygula
  const handleEtkiChange = (newEtki) => {
    const defaults = v2SmartDefaults[newEtki] || {};
    onSettingsChange({
      ...settings,
      etki: newEtki,
      karakter: defaults.karakter || settings.karakter,
      yapi: defaults.yapi || settings.yapi,
      uzunluk: defaults.uzunluk || settings.uzunluk,
      acilis: defaults.acilis || settings.acilis,
      bitis: defaults.bitis || settings.bitis,
      derinlik: defaults.derinlik || settings.derinlik,
    });
  };

  // v2: Uyumluluk kontrolü
  const isIncompat = isTwitter && v2KarakterYapiUyum[settings.karakter] && v2KarakterYapiUyum[settings.karakter][settings.yapi] === false;

  // Pill renderer: tekrar eden kod yerine helper
  const renderPills = (items, activeId, field, opts = {}) => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: isMobile ? "6px" : "8px" }}>
      {items.map((item) => {
        const id = item.id;
        const isActive = activeId === id;
        const isWarning = opts.checkCompat && id === "cesur" && v2KarakterYapiUyum[settings.karakter]?.[id] === false;
        return (
          <button
            key={id || "none"}
            onClick={() => onSettingsChange({ ...settings, [field]: id })}
            className="haptic-btn"
            style={{
              padding: isMobile ? "5px 11px" : "6px 14px",
              borderRadius: "999px",
              border: isActive ? "none" : isWarning ? "1px solid rgba(239,68,68,0.5)" : "1px solid var(--m-border)",
              background: isActive ? "var(--m-pill-active-bg)" : "transparent",
              color: isActive ? "var(--m-pill-active-text)" : isWarning ? "rgba(239,68,68,0.7)" : "var(--m-text-soft)",
              fontSize: isMobile ? "12px" : "13px",
              cursor: "pointer",
              transition: "all 0.2s ease",
              minHeight: "36px",
              display: "flex",
              alignItems: "center",
            }}
          >
            {t(item.labelKey)}{item.range ? <span style={{ opacity: 0.5, marginLeft: "4px" }}>{item.range}</span> : null}
          </button>
        );
      })}
    </div>
  );

  const renderDesc = (items, activeId) => {
    const found = items.find((i) => i.id === activeId);
    return found?.descKey ? (
      <p style={{ fontSize: "11px", color: "var(--m-text-faint)", marginTop: "4px" }}>{t(found.descKey)}</p>
    ) : null;
  };

  // Mobile: bottom sheet, Desktop: inline popup
  const settingsContent = (
    <>
      <div className="flex items-center justify-between mb-3">
        {isMobile && (
          <div style={{ width: "36px", height: "4px", borderRadius: "2px", background: "rgba(255,255,255,0.2)", position: "absolute", top: "8px", left: "50%", transform: "translateX(-50%)" }} />
        )}
        <span style={{ fontSize: isMobile ? "15px" : "13px", fontWeight: "600", color: "var(--m-text)" }}>
          {t('create.generationSettings')}
        </span>
        <button onClick={onClose} className="haptic-btn" style={{ background: "transparent", border: "none", color: "var(--m-text-muted)", cursor: "pointer", padding: "4px" }}>
          <X size={18} />
        </button>
      </div>

          {/* ══════ X PLATFORM: V2 SETTINGS ══════ */}
          {isTwitter && activeTab !== "article" ? (
            <>
              {/* Etki (smart defaults tetikleyen özel pills) */}
              <div className="mb-2.5">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.effect')}</label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {v2Etkiler.map((e) => (
                    <button
                      key={e.id}
                      onClick={() => handleEtkiChange(e.id)}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "999px",
                        border: settings.etki === e.id ? "none" : "1px solid var(--m-border)",
                        background: settings.etki === e.id ? "var(--m-pill-active-bg)" : "transparent",
                        color: settings.etki === e.id ? "var(--m-pill-active-text)" : "var(--m-text-soft)",
                        fontSize: "13px",
                        cursor: "pointer",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {t(e.labelKey)}
                    </button>
                  ))}
                </div>
                {renderDesc(v2Etkiler, settings.etki)}
              </div>

              {/* Karakter */}
              <div className="mb-2.5">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.character')}</label>
                {renderPills(v2Karakterler, settings.karakter, "karakter")}
                {renderDesc(v2Karakterler, settings.karakter)}
              </div>

              {/* Yapı */}
              <div className="mb-2.5">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.structure')}</label>
                {renderPills(v2Yapilar, settings.yapi, "yapi", { checkCompat: true })}
                {renderDesc(v2Yapilar, settings.yapi)}
                {isIncompat && (
                  <p style={{ fontSize: "11px", color: "rgba(239,68,68,0.8)", marginTop: "4px" }}>
                    {t('create.incompatibleWarning')}
                  </p>
                )}
              </div>

              {/* Uzunluk — shitpost'ta gizle */}
              {settings.etki !== "shitpost" && (
              <div className="mb-2.5">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.length')}</label>
                {renderPills(
                  activeTab === "reply" ? replyLengths : tweetLengths,
                  settings.uzunluk,
                  "uzunluk"
                )}
              </div>
              )}

              {/* Gelişmiş Ayarlar (collapsible) */}
              <button
                onClick={() => setAdvOpen(!advOpen)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "transparent",
                  border: "none",
                  color: "var(--m-text-muted)",
                  fontSize: "12px",
                  cursor: "pointer",
                  padding: "4px 0",
                  marginBottom: advOpen ? "8px" : "4px",
                }}
              >
                {advOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {t('create.advancedSettings')}
              </button>

              {advOpen && (
                <>
                  {/* Açılış */}
                  <div className="mb-2">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.opening')}</label>
                    {renderPills(v2Acilislar, settings.acilis, "acilis")}
                    {renderDesc(v2Acilislar, settings.acilis)}
                  </div>

                  {/* Bitiş */}
                  <div className="mb-2">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.ending')}</label>
                    {renderPills(v2Bitisler, settings.bitis, "bitis")}
                    {renderDesc(v2Bitisler, settings.bitis)}
                  </div>

                  {/* Derinlik */}
                  <div className="mb-2">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.depth')}</label>
                    {renderPills(v2Derinlikler, settings.derinlik, "derinlik")}
                    {renderDesc(v2Derinlikler, settings.derinlik)}
                  </div>

                  {/* Dil */}
                  <div className="mb-2">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.language')}</label>
                    {renderPills(languages, settings.language, "language")}
                  </div>
                </>
              )}

              {/* Reply Mode (reply tab'da) */}
              {activeTab === "reply" && (
                <div className="mb-2 mt-1">
                  <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.replyMode')}</label>
                  {renderPills(replyModes, settings.replyMode, "replyMode")}
                </div>
              )}
            </>
          ) : (
            /* ══════ OTHER PLATFORMS / ARTICLE: V1 SETTINGS ══════ */
            <>
              {/* Persona */}
              <div className="mb-2.5">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.persona')}</label>
                {renderPills(personas, settings.persona, "persona")}
                {renderDesc(personas, settings.persona)}
              </div>

              {/* Tone */}
              <div className="mb-2">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.tone')}</label>
                {renderPills(tones, settings.tone, "tone")}
                {renderDesc(tones, settings.tone)}
              </div>

              {/* Length — shitpost'ta gizle */}
              {settings.etki !== "shitpost" && (
              <div className="mb-2">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.length')}</label>
                {renderPills(currentLengths, settings.length, "length")}
              </div>
              )}

              {/* Knowledge */}
              <div className="mb-2">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.knowledgeMode')}</label>
                {renderPills(knowledgeModes, settings.knowledge, "knowledge")}
                {renderDesc(knowledgeModes, settings.knowledge)}
              </div>

              {/* Language */}
              <div className="mb-2">
                <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.language')}</label>
                {renderPills(languages, settings.language, "language")}
              </div>

              {/* LinkedIn-specific */}
              {activePlatform === "linkedin" && (
                <>
                  <div className="mb-2.5">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.linkedinPersona')}</label>
                    {renderPills(linkedinPersonas, settings.linkedinPersona, "linkedinPersona")}
                    {renderDesc(linkedinPersonas, settings.linkedinPersona)}
                  </div>
                  <div className="mb-2.5">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.linkedinFormat')}</label>
                    {renderPills(linkedinFormats, settings.linkedinFormat, "linkedinFormat")}
                    {renderDesc(linkedinFormats, settings.linkedinFormat)}
                  </div>
                </>
              )}

              {/* Blog-specific */}
              {activePlatform === "blog" && (
                <>
                  <div className="mb-2.5">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.blogStyle')}</label>
                    {renderPills(blogStyles, settings.blogStyle, "blogStyle")}
                    {renderDesc(blogStyles, settings.blogStyle)}
                  </div>
                  <div className="mb-2.5">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.blogFramework')}</label>
                    {renderPills(blogFrameworks, settings.blogFramework, "blogFramework")}
                    {renderDesc(blogFrameworks, settings.blogFramework)}
                  </div>
                  <div className="mb-2.5">
                    <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.blogLevel')}</label>
                    {renderPills(blogLevels, settings.blogLevel, "blogLevel")}
                    {renderDesc(blogLevels, settings.blogLevel)}
                  </div>
                </>
              )}

              {/* Reply Mode */}
              {activeTab === "reply" && (
                <div className="mb-2 mt-2">
                  <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.replyMode')}</label>
                  {renderPills(replyModes, settings.replyMode, "replyMode")}
                </div>
              )}

              {/* Article Style */}
              {activeTab === "article" && (
                <div className="mb-2 mt-2">
                  <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.articleStyle')}</label>
                  {renderPills(articleStyles, settings.articleStyle, "articleStyle")}
                </div>
              )}
            </>
          )}

          {/* Variant Count (her platformda) */}
          <div className="mb-2">
            <label style={{ fontSize: "12px", color: "var(--m-text-muted)", marginBottom: "4px", display: "block" }}>{t('create.variantCount')}</label>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button
                onClick={() => onSettingsChange({ ...settings, variants: Math.max(1, settings.variants - 1) })}
                style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  border: "1px solid var(--m-border)", background: "transparent",
                  color: "var(--m-text-soft)", display: "flex", alignItems: "center",
                  justifyContent: "center", cursor: "pointer",
                }}
              >
                <Minus size={14} />
              </button>
              <span style={{ fontSize: "18px", fontWeight: "600", color: "var(--m-text)", width: "24px", textAlign: "center" }}>
                {settings.variants}
              </span>
              <button
                onClick={() => onSettingsChange({ ...settings, variants: Math.min(5, settings.variants + 1) })}
                style={{
                  width: "36px", height: "36px", borderRadius: "50%",
                  border: "1px solid var(--m-border)", background: "transparent",
                  color: "var(--m-text-soft)", display: "flex", alignItems: "center",
                  justifyContent: "center", cursor: "pointer",
                }}
              >
                <Plus size={14} />
              </button>
            </div>
          </div>
    </>
  );

  if (isMobile) {
    return createPortal(
      <>
        <div className="mobile-sheet-overlay" onClick={onClose} />
        <div className="mobile-sheet-content" style={{ padding: "12px 16px 16px" }} onClick={(e) => e.stopPropagation()}>
          {/* Drag Handle */}
          <div onClick={onClose} style={{ display: "flex", justifyContent: "center", paddingBottom: "10px", cursor: "pointer" }}>
            <div style={{ width: "36px", height: "4px", borderRadius: "999px", background: "var(--m-text-muted)", opacity: 0.3 }} />
          </div>
          {settingsContent}
          {/* Generate button inside sheet */}
          {onGenerate && (
            <button
              onClick={() => { onClose(); onGenerate(); }}
              className="haptic-btn"
              style={{
                width: "100%",
                marginTop: "12px",
                padding: "14px",
                borderRadius: "14px",
                border: "none",
                background: "linear-gradient(135deg, #a855f7, #7c3aed)",
                color: "#fff",
                fontSize: "15px",
                fontWeight: "600",
                cursor: "pointer",
                letterSpacing: "0.01em",
              }}
            >
              ⚡ {t('common.generate')}
            </button>
          )}
        </div>
      </>,
      document.body
    );
  }

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        style={{ position: "relative", zIndex: 50, width: "100%", marginTop: "8px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            background: "var(--m-popup-bg)",
            border: "1px solid var(--m-border)",
            borderRadius: "16px",
            padding: "14px 16px",
            backdropFilter: "blur(20px)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
            display: "flex",
            flexDirection: "column",
            gap: "0",
            maxHeight: "70vh",
            overflowY: "auto",
          }}
        >
          {settingsContent}
        </div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════
// ONBOARDING TIP (Accordion)
// ══════════════════════════════════════════

function OnboardingTip({ isLoaded, hasStyleProfile }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(true);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem("typehype-onboard-dismissed") === "true");
  const navigate = useNavigate();

  const genCount = parseInt(localStorage.getItem("typehype-gen-count") || "0", 10);
  const hasTweeted = localStorage.getItem("typehype-onboard-tweet") === "true";

  const steps = [
    { label: t('create.onboarding.createAccount'), done: true, action: null },
    { label: t('create.onboarding.firstGeneration'), done: genCount >= 1, action: null },
    { label: t('create.onboarding.cloneStyle'), done: !!hasStyleProfile, action: () => navigate("/dashboard/style-lab") },
    { label: t('create.onboarding.firstTweet'), done: hasTweeted, action: null },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  const allDone = completedCount === steps.length;
  const progress = Math.round((completedCount / steps.length) * 100);

  if (dismissed) return null;
  if (allDone) {
    // Show success briefly then auto-dismiss
    if (!localStorage.getItem("typehype-onboard-complete-shown")) {
      localStorage.setItem("typehype-onboard-complete-shown", "true");
      setTimeout(() => {
        localStorage.setItem("typehype-onboard-dismissed", "true");
        setDismissed(true);
      }, 3000);
    } else {
      return null;
    }
  }

  const handleDismiss = () => {
    localStorage.setItem("typehype-onboard-dismissed", "true");
    setDismissed(true);
  };

  return (
    <div style={{ maxWidth: "680px", width: "100%", marginBottom: "16px" }}>
      <div
        style={{
          background: "rgba(168, 85, 247, 0.04)",
          border: "1px solid rgba(168, 85, 247, 0.12)",
          borderRadius: "12px",
          overflow: "hidden",
        }}
      >
        {/* Header - always visible */}
        <button
          onClick={() => setOpen(!open)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 14px",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          <span style={{ fontSize: "14px" }}>{allDone ? "🎉" : "🚀"}</span>
          <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--m-text)", flex: 1, textAlign: "left" }}>
            {allDone ? t('create.onboarding.congrats') : `${t('create.onboarding.quickStart')} (${completedCount}/${steps.length})`}
          </span>
          <span style={{ fontSize: "11px", color: "var(--m-text-muted)", marginRight: "4px" }}>%{progress}</span>
          <button
            onClick={(e) => { e.stopPropagation(); handleDismiss(); }}
            style={{ background: "transparent", border: "none", color: "var(--m-text-faint)", cursor: "pointer", padding: "2px" }}
          >
            <X size={14} />
          </button>
        </button>

        {/* Progress bar */}
        <div style={{ height: "3px", background: "rgba(255,255,255,0.05)", margin: "0 14px" }}>
          <div
            style={{
              height: "100%",
              width: `${progress}%`,
              background: "linear-gradient(90deg, #a855f7, #ec4899)",
              borderRadius: "2px",
              transition: "width 0.5s ease",
            }}
          />
        </div>

        {/* Steps - collapsible */}
        <div
          style={{
            maxHeight: open ? "200px" : "0",
            overflow: "hidden",
            transition: "max-height 0.3s ease",
          }}
        >
          <div style={{ padding: "10px 14px 12px", display: "flex", flexDirection: "column", gap: "6px" }}>
            {steps.map((step, i) => (
              <div
                key={i}
                onClick={() => step.action && step.action()}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "6px 8px",
                  borderRadius: "8px",
                  cursor: step.action ? "pointer" : "default",
                  transition: "background 0.15s ease",
                  background: step.action ? "transparent" : "transparent",
                }}
                onMouseEnter={(e) => { if (step.action) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{
                  width: "20px", height: "20px", borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "11px", flexShrink: 0,
                  background: step.done ? "rgba(34, 197, 94, 0.15)" : "rgba(255,255,255,0.05)",
                  color: step.done ? "#22c55e" : "var(--m-text-faint)",
                  border: step.done ? "1px solid rgba(34, 197, 94, 0.3)" : "1px solid var(--m-border)",
                }}>
                  {step.done ? "✓" : i + 1}
                </span>
                <span style={{
                  fontSize: "12px",
                  color: step.done ? "var(--m-text-muted)" : "var(--m-text-soft)",
                  textDecoration: step.done ? "line-through" : "none",
                  opacity: step.done ? 0.6 : 1,
                  flex: 1,
                }}>
                  {step.label}
                </span>
                {step.action && !step.done && (
                  <span style={{ fontSize: "10px", color: "var(--m-purple)", opacity: 0.7 }}>→</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════
// STYLE PROFILE BADGE (compact inline)
// ══════════════════════════════════════════

function StyleProfileBadge() {
  const { t } = useTranslation();
  const { profiles, activeProfile, activeProfileId, setActiveProfile, refreshProfiles } = useProfile();
  const [showDropdown, setShowDropdown] = useState(false);
  const navigate = useNavigate();
  const btnRef = useRef(null);
  const [dropPos, setDropPos] = useState(null);

  const openDropdown = () => {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setDropPos({
        top: rect.top - 8,
        left: rect.left + rect.width / 2,
      });
    }
    setShowDropdown(true);
  };

  if (!profiles || profiles.length === 0) return null;

  const profileItem = (profile) => (
    <button
      key={profile.id}
      onClick={() => { setActiveProfile(profile.id); setShowDropdown(false); }}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "8px 12px",
        borderRadius: "8px",
        border: "none",
        background: profile.id === activeProfileId ? "var(--m-purple-soft)" : "transparent",
        color: profile.id === activeProfileId ? "var(--m-purple)" : "var(--m-text-soft)",
        fontSize: "13px",
        cursor: "pointer",
        transition: "all 0.15s ease",
        textAlign: "left",
      }}
    >
      {(profile.avatar_url || profile.twitter_username) ? (
        <img
          src={profile.avatar_url || `https://unavatar.io/x/${profile.twitter_username}`}
          alt=""
          style={{ width: 24, height: 24, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
          onError={(e) => { e.target.onerror = null; e.target.src = ""; e.target.style.display = "none"; }}
        />
      ) : (
        <div style={{
          width: "24px", height: "24px", borderRadius: "50%",
          background: "linear-gradient(135deg, #a855f7, #ec4899)",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <span style={{ fontSize: "10px", fontWeight: "700", color: "var(--m-text)" }}>
            {profile.name?.charAt(0)?.toUpperCase() || "S"}
          </span>
        </div>
      )}
      <span style={{ flex: 1 }}>{profile.name}</span>
      {profile.id === activeProfileId && <Check size={14} />}
    </button>
  );

  return (
    <div style={{ position: "relative" }}>
      <button
        ref={btnRef}
        onClick={() => showDropdown ? setShowDropdown(false) : openDropdown()}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "6px 14px",
          borderRadius: "999px",
          border: activeProfile ? "1px solid var(--m-purple-border)" : "1px solid var(--m-border)",
          background: activeProfile ? "var(--m-purple-soft)" : "transparent",
          color: activeProfile ? "var(--m-purple)" : "var(--m-text-muted)",
          fontSize: "13px",
          cursor: "pointer",
          transition: "all 0.2s ease",
          whiteSpace: "nowrap",
        }}
      >
        {(activeProfile?.avatar_url || activeProfile?.twitter_username) ? (
          <img
            src={activeProfile.avatar_url || `https://unavatar.io/x/${activeProfile.twitter_username}`}
            alt=""
            style={{ width: 18, height: 18, borderRadius: "50%", objectFit: "cover" }}
            onError={(e) => { e.target.style.display = "none"; }}
          />
        ) : (
          <Dna size={14} />
        )}
        {activeProfile ? activeProfile.name.split(" ")[0] : t('create.style')}
        <ChevronDown size={12} style={{ opacity: 0.5 }} />
      </button>

      {showDropdown && dropPos && createPortal(
        <>
          {/* Backdrop */}
          <div
            onClick={() => setShowDropdown(false)}
            style={{ position: "fixed", inset: 0, zIndex: 99998 }}
          />
          {/* Dropdown (yukarı açılır, fixed pozisyon) */}
          <div
            style={{
              position: "fixed",
              bottom: `${window.innerHeight - dropPos.top}px`,
              left: `clamp(12px, ${dropPos.left}px, calc(100vw - 232px))`,
              transform: dropPos.left < 120 ? "none" : dropPos.left > window.innerWidth - 120 ? "none" : "translateX(-50%)",
              background: "var(--m-popup-bg)",
              border: "1px solid var(--m-border)",
              borderRadius: "12px",
              padding: "8px",
              minWidth: "220px",
              maxWidth: "calc(100vw - 24px)",
              maxHeight: "280px",
              overflowY: "auto",
              backdropFilter: "blur(20px)",
              zIndex: 99999,
              boxShadow: "0 -8px 32px rgba(0,0,0,0.4)",
              animation: "fadeIn 0.15s ease",
            }}
          >
            {profiles.map(profileItem)}

            <div style={{ borderTop: "1px solid var(--m-border-light)", margin: "4px 0", paddingTop: "4px" }}>
              <button
                onClick={() => { setActiveProfile(null); setShowDropdown(false); }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: "10px",
                  padding: "8px 12px", borderRadius: "8px", border: "none",
                  background: "transparent", color: "var(--m-text-muted)",
                  fontSize: "13px", cursor: "pointer",
                }}
              >
                <X size={14} />
                <span>{t('create.styleOff')}</span>
              </button>
              <button
                onClick={() => { navigate("/dashboard/style-lab"); setShowDropdown(false); }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: "10px",
                  padding: "8px 12px", borderRadius: "8px", border: "none",
                  background: "transparent", color: "var(--m-purple)",
                  fontSize: "13px", cursor: "pointer",
                }}
              >
                <Dna size={14} />
                <span>{t('create.styleLab')}</span>
              </button>
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// AI ANALYSIS DIALOG (preserved from original)
// ══════════════════════════════════════════

function AIAnalysisDialog({ open, onOpenChange, profileData }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  if (!profileData) return null;
  const fp = profileData.style_fingerprint || {};
  const aiAnalysis = fp.ai_analysis || "";
  const stylePrompt = profileData.style_prompt || "";

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(stylePrompt);
    setCopied(true);
    toast.success(t('styleLab.analysis.promptCopied'));
    setTimeout(() => setCopied(false), 2000);
  };

  const sections = [];
  if (aiAnalysis) {
    const parts = aiAnalysis.split(/\d+\.\s+\*\*/);
    for (const part of parts) {
      if (!part.trim()) continue;
      const titleEnd = part.indexOf("**");
      if (titleEnd > 0) {
        sections.push({
          title: part.substring(0, titleEnd).replace(/\*\*/g, "").trim(),
          content: part.substring(titleEnd + 2).replace(/^\s*:\s*/, "").trim(),
        });
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
            {t('create.aiAnalysis.title', { name: profileData.name })}
          </DialogTitle>
          <DialogDescription>
            {t('create.aiAnalysis.tweetsAnalyzed', { count: fp.tweet_count || 0 })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6 py-4">
          <div className="grid grid-cols-4 gap-3">
            {[
              { val: fp.tweet_count || 0, label: "Tweet", color: "sky" },
              { val: fp.avg_length || 0, label: t('create.aiAnalysis.avgCharacter'), color: "pink" },
              { val: fp.avg_engagement?.likes?.toFixed(0) || 0, label: t('create.aiAnalysis.avgLike'), color: "green" },
              { val: fp.emoji_usage?.toFixed(1) || 0, label: t('create.aiAnalysis.emojiPerTweet'), color: "purple" },
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
                  <Wand2 className="h-4 w-4 text-pink-400" /> {t('create.aiAnalysis.stylePrompt')}
                </h4>
                <Button variant="ghost" size="sm" onClick={handleCopyPrompt} className="h-8 text-xs">
                  {copied ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                  {copied ? t('common.copied') : t('common.copy')}
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
// TWEET PREVIEW CARD
// ══════════════════════════════════════════

function TweetPreviewCard({ tweet }) {
  if (!tweet) return null;
  const fmt = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return num?.toString() || "0";
  };

  return (
    <div style={{
      background: "var(--m-surface)",
      border: "1px solid var(--m-border-light)",
      borderRadius: "12px",
      padding: "14px 16px",
      marginBottom: "12px",
    }}>
      <div style={{ display: "flex", alignItems: "start", gap: "10px" }}>
        {tweet.author?.avatar && (
          <img src={tweet.author.avatar.replace("_normal", "_bigger")} alt="" 
            style={{ width: "36px", height: "36px", borderRadius: "50%" }} />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: "600", fontSize: "13px", color: "var(--m-text)" }}>{tweet.author?.name}</span>
            <span style={{ fontSize: "12px", color: "var(--m-text-muted)" }}>@{tweet.author?.username}</span>
          </div>
          <p style={{ fontSize: "13px", color: "var(--m-text-soft)", marginTop: "4px", whiteSpace: "pre-wrap", lineHeight: "1.5" }}>
            {tweet.text}
          </p>
          <div style={{ display: "flex", gap: "16px", marginTop: "8px", fontSize: "12px", color: "var(--m-text-faint)" }}>
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
// PROMO CARDS (Manus-style bottom carousel)
// ══════════════════════════════════════════

const promoCards = [
  { titleKey: "create.promoCards.styleCloning", descKey: "create.promoCards.styleCloningDesc", type: "style" },
  { titleKey: "create.promoCards.ultraMode", descKey: "create.promoCards.ultraModeDesc", type: "ultra" },
  { titleKey: "create.promoCards.threadPower", descKey: "create.promoCards.threadPowerDesc", type: "thread" },
];

// ══════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════

let jobIdCounter = 0;

export default function XAIModule() {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState("");
  const [activeTab, setActiveTab] = useState("tweet");
  const [activePlatform, setActivePlatform] = useState("twitter");
  const [isLoaded, setIsLoaded] = useState(false);
  const [activeCard, setActiveCard] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tweetUrl, setTweetUrl] = useState("");
  const [tweetData, setTweetData] = useState(null);
  const [fetching, setFetching] = useState(false);
  const [fetched, setFetched] = useState(false);
  const [fetchPhase, setFetchPhase] = useState("link"); // "link" | "prompt"
  const [imageUrl, setImageUrl] = useState(null);
  const [imageBase64, setImageBase64] = useState(null);
  const [trendContext, setTrendContext] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [repurposeModal, setRepurposeModal] = useState({ open: false, content: "", mode: "video" });
  const [imagePrompts, setImagePrompts] = useState({}); // unused, kept for compat
  const [generating, setGenerating] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { profiles, activeProfileId, activeProfile, setActiveProfile } = useProfile();

  // Connected account primary avatar (for generation cards)
  const [primaryAccountAvatar, setPrimaryAccountAvatar] = useState(null);
  useEffect(() => {
    api.get(`${API}/accounts`).then(res => {
      const primary = (res.data || []).find(a => a.is_primary);
      if (primary) {
        const platformAvatars = {
          twitter: (u) => `https://unavatar.io/x/${u}`,
          youtube: (u) => `https://unavatar.io/youtube/${u}`,
          tiktok: (u) => `https://unavatar.io/tiktok/${u}`,
        };
        const fn = platformAvatars[primary.platform];
        if (fn) setPrimaryAccountAvatar(fn(primary.username));
      }
    }).catch(() => {});
  }, []);

  const [settings, setSettings] = useState({
    mode: "classic",
    persona: "otorite",
    tone: "natural",
    length: "punch",
    knowledge: null,
    language: "auto",
    variants: 3,
    replyMode: "support",
    articleStyle: "authority",
    // LinkedIn-specific
    linkedinPersona: "thought_leader",
    linkedinFormat: "standard",
    // Blog-specific
    blogStyle: "informative",
    blogFramework: "answer_first",
    blogLevel: "standard",
    // v2 X settings
    etki: "patlassin",
    karakter: "uzman",
    yapi: "kurgulu",
    uzunluk: "punch",
    acilis: "otomatik",
    bitis: "otomatik",
    derinlik: "standart",
    isUltra: false,
  });

  // v2 gelişmiş ayarlar paneli açık/kapalı
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Draft bridge state (Creator Hub → /create)
  const [draftBridge, setDraftBridge] = useState(null); // { content, trend_topic, trend_summary, draft_id }

  // Initialize from URL params
  useEffect(() => {
    const draftId = searchParams.get("draft_id");
    if (draftId) {
      // Bridge: Creator Hub'dan gelen draft'ı API'den çek
      (async () => {
        try {
          const res = await api.get(`${API}/drafts/${draftId}`);
          const d = res.data?.draft;
          if (d) {
            setDraftBridge({ content: d.content, trend_topic: d.trend_topic, trend_summary: d.trend_summary, draft_id: d.id });
            if (d.trend_topic) setInputValue(d.trend_topic);
            if (d.trend_summary) setTrendContext(d.trend_summary);
            if (d.platform && ["twitter","youtube","instagram","tiktok","linkedin","blog"].includes(d.platform)) {
              setActivePlatform(d.platform);
            }
            // Status'ü "edited" yap (döngüyü kapat)
            api.put(`${API}/drafts/${draftId}`, { status: "edited" }).catch(() => {});
          }
        } catch { /* draft bulunamazsa sessizce devam */ }
      })();
      // URL'i temizle (draft_id param'ını kaldır)
      const next = new URLSearchParams(searchParams);
      next.delete("draft_id");
      setSearchParams(next, { replace: true });
      return; // Diğer param'ları okuma, draft her şeyi set etti
    }

    const topic = searchParams.get("topic") || "";
    const context = searchParams.get("trend_context") || "";
    const platformParam = searchParams.get("platform");
    const styleParam = searchParams.get("style");
    if (topic) setInputValue(topic);
    if (context) setTrendContext(context);
    if (platformParam && ["twitter","youtube","instagram","tiktok","linkedin","blog"].includes(platformParam)) {
      setActivePlatform(platformParam);
    }
    if (styleParam) {
      // Stil profilini aktif et (ProfileContext üzerinden)
      if (setActiveProfile) setActiveProfile(styleParam);
    }
    // Coach integration: persona, tone, length, hook URL params
    const urlPersona = searchParams.get("persona");
    const urlTone = searchParams.get("tone");
    const urlLength = searchParams.get("length");
    const urlHook = searchParams.get("hook");
    if (urlPersona) setSettings(s => ({ ...s, persona: urlPersona }));
    if (urlTone) setSettings(s => ({ ...s, tone: urlTone }));
    if (urlLength) setSettings(s => ({ ...s, length: urlLength }));
    if (urlHook && !topic) setInputValue(urlHook);
  }, [searchParams]);

  useEffect(() => {
    setIsLoaded(true);
    const interval = setInterval(() => {
      setActiveCard((prev) => (prev + 1) % promoCards.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch generation history
  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await api.get(`${API}/generations/history`, { params: { limit: 20 } });
      setHistory(res.data || []);
    } catch (e) {
      // silent fail
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Refresh history after generation completes
  useEffect(() => {
    if (jobs.some((j) => j.status === "completed")) {
      fetchHistory();
    }
  }, [jobs, fetchHistory]);

  const handleTextareaInput = (e) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + "px";
    }
  };

  // Fetch tweet for quote/reply
  const handleFetchTweet = async () => {
    const url = inputValue.trim();
    if (!url.match(/x\.com|twitter\.com/)) {
      toast.error(t('create.enterTweetLink'));
      return;
    }
    setFetching(true);
    try {
      const response = await api.get(`${API}/tweet/fetch`, { params: { url } });
      if (response.data.success) {
        setTweetData(response.data.tweet);
        setTweetUrl(url);
        setFetched(true);
        setFetchPhase("prompt");
        setInputValue("");
        toast.success(t('create.tweetFetched'));
      } else {
        toast.error(t('create.tweetFetchFailed'));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || t('create.tweetFetchFailed'));
    } finally {
      setFetching(false);
    }
  };

  // Image handling
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { toast.error(t('create.maxFileSize')); return; }
      setImageUrl(URL.createObjectURL(file));
      const reader = new FileReader();
      reader.onloadend = () => setImageBase64(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const updateJob = useCallback((jobId, updates) => {
    setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, ...updates } : j)));
  }, []);

  const dismissJob = useCallback((jobId) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
  }, []);

  // GENERATE
  const handleGenerate = useCallback(async () => {
    const input = inputValue.trim();
    if (!input && activeTab !== "quote" && activeTab !== "reply") {
      toast.error(t('create.writeSomething'));
      return;
    }

    // For quote/reply, need fetched tweet
    if ((activeTab === "quote" || activeTab === "reply") && !fetched && fetchPhase === "link") {
      // Try to fetch first
      if (input.match(/x\.com|twitter\.com/)) {
        await handleFetchTweet();
        return; // Input will clear, user writes direction then sends
      }
      toast.error(t('create.pasteTweetFirst'));
      return;
    }

    const jobId = `job-${++jobIdCounter}`;
    const type = activeTab === "thread" ? "tweet" : activeTab;
    const newJob = {
      id: jobId,
      type,
      status: "generating",
      startedAt: Date.now(),
      topic: input.slice(0, 60) + (input.length > 60 ? "..." : ""),
      persona: activePlatform === "twitter" ? settings.karakter : settings.persona,
      personaLabel: activePlatform === "twitter"
        ? tl(v2Karakterler, settings.karakter)
        : tl(personas, settings.persona),
      toneLabel: activePlatform === "twitter"
        ? tl(v2Yapilar, settings.yapi)
        : tl(tones, settings.tone),
      lengthLabel: tl(activeTab === "reply" ? replyLengths : activeTab === "article" ? articleLengths : tweetLengths,
        activePlatform === "twitter" ? settings.uzunluk : settings.length),
      knowledgeLabel: activePlatform === "twitter"
        ? (settings.etki ? tl(v2Etkiler, settings.etki) : null)
        : (settings.knowledge ? tl(knowledgeModes, settings.knowledge) : null),
      variantCount: settings.variants,
      variants: null,
    };

    setJobs((prev) => [newJob, ...prev]);
    setGenerating(true);

    try {
      let endpoint, body;

      if (activePlatform === "linkedin") {
        endpoint = `${API}/generate/linkedin`;
        body = {
          topic: input,
          format: settings.linkedinFormat,
          persona: settings.linkedinPersona,
          language: settings.language,
          additional_context: null,
          variants: settings.variants,
        };
      } else if (activePlatform === "blog") {
        endpoint = `${API}/generate/blog/full`;
        body = {
          topic: input,
          style: settings.blogStyle,
          framework: settings.blogFramework,
          level: settings.blogLevel,
          language: settings.language,
          additional_context: null,
        };
      } else if (activePlatform === "instagram") {
        const igConfig = {
          "caption": { endpoint: "/generate/instagram/caption", body: { topic: input, format: "standard", language: settings.language, variants: settings.variants } },
          "reel-script": { endpoint: "/generate/instagram/reel-script", body: { topic: input, duration: 30, language: settings.language } },
          "story": { endpoint: "/generate/instagram/story-ideas", body: { topic: input, count: 5, language: settings.language } },
        };
        const cfg = igConfig[activeTab] || igConfig["caption"];
        endpoint = `${API}${cfg.endpoint}`;
        body = cfg.body;
      } else if (activePlatform === "tiktok") {
        const tkConfig = {
          "hook": { endpoint: "/generate/tiktok/script", body: { topic: input, duration: 15, language: settings.language } },
          "script": { endpoint: "/generate/tiktok/script", body: { topic: input, duration: 30, language: settings.language } },
          "caption": { endpoint: "/generate/tiktok/caption", body: { topic: input, language: settings.language } },
        };
        const cfg = tkConfig[activeTab] || tkConfig["script"];
        endpoint = `${API}${cfg.endpoint}`;
        body = cfg.body;
      } else if (activePlatform === "youtube") {
        const ytConfig = {
          "video-script": { endpoint: "/generate/youtube/script", body: { topic: input, duration_minutes: 10, style: "educational", language: settings.language } },
          "title-desc": { endpoint: "/generate/youtube/title", body: { topic: input, count: 5, language: settings.language } },
          "shorts-script": { endpoint: "/generate/youtube/script", body: { topic: input, duration_minutes: 1, style: "shorts", language: settings.language } },
        };
        const cfg = ytConfig[activeTab] || ytConfig["video-script"];
        endpoint = `${API}${cfg.endpoint}`;
        body = cfg.body;
      } else if (type === "tweet") {
        // X platformu: v2 endpoint
        endpoint = `${API}/v2/generate/tweet`;
        body = {
          topic: input,
          etki: settings.etki,
          karakter: settings.karakter,
          yapi: settings.yapi,
          uzunluk: activeTab === "thread" ? "thread" : settings.uzunluk,
          acilis: settings.acilis,
          bitis: settings.bitis,
          derinlik: settings.derinlik,
          language: settings.language,
          is_ultra: settings.isUltra,
          variants: settings.variants,
          additional_context: null,
          trend_context: trendContext || null,
          style_profile_id: activeProfileId || null,
          image_base64: imageBase64 || null,
        };
      } else if (type === "quote") {
        // X platformu: v2 endpoint
        endpoint = `${API}/v2/generate/quote`;
        body = {
          tweet_url: tweetUrl,
          tweet_content: tweetData?.text || "",
          direction: input || null,
          etki: settings.etki,
          karakter: settings.karakter,
          yapi: settings.yapi,
          uzunluk: settings.uzunluk,
          acilis: settings.acilis,
          bitis: settings.bitis,
          derinlik: settings.derinlik,
          language: settings.language,
          is_ultra: settings.isUltra,
          variants: settings.variants,
          additional_context: null,
          style_profile_id: activeProfileId || null,
          trend_context: trendContext || null,
          image_base64: imageBase64 || null,
        };
      } else if (type === "reply") {
        // X platformu: v2 endpoint
        endpoint = `${API}/v2/generate/reply`;
        body = {
          tweet_url: tweetUrl,
          tweet_content: tweetData?.text || "",
          direction: input || null,
          reply_mode: settings.replyMode,
          etki: settings.etki,
          karakter: settings.karakter,
          yapi: settings.yapi,
          uzunluk: settings.uzunluk,
          acilis: settings.acilis,
          bitis: settings.bitis,
          derinlik: settings.derinlik,
          language: settings.language,
          is_ultra: settings.isUltra,
          variants: settings.variants,
          additional_context: null,
          style_profile_id: activeProfileId || null,
          trend_context: trendContext || null,
          image_base64: imageBase64 || null,
        };
      } else if (type === "article") {
        endpoint = `${API}/generate/article`;
        body = {
          topic: input,
          title: null,
          length: settings.length,
          style: settings.articleStyle,
          language: settings.language,
          variants: 1,
          persona: "otorite",
          reference_links: [],
          additional_context: null,
        };
      }

      const response = await api.post(endpoint, body);

      if (response.data.success) {
        updateJob(jobId, {
          status: "completed",
          variants: response.data.variants,
          generationId: response.data.generation_id,
        });
        toast.success(t('create.contentGenerated'));
        // Increment generation counter for onboarding tip
        const gc = parseInt(localStorage.getItem("typehype-gen-count") || "0", 10);
        localStorage.setItem("typehype-gen-count", String(gc + 1));
      } else {
        updateJob(jobId, { status: "error" });
        toast.error(response.data.error || t('create.generationFailed'));
      }
    } catch (error) {
      updateJob(jobId, { status: "error" });
      toast.error(error.response?.data?.detail || t('create.errorOccurred'));
    } finally {
      setGenerating(false);
    }
  }, [inputValue, activeTab, settings, fetched, fetchPhase, tweetUrl, tweetData, activeProfileId, imageUrl, imageBase64, trendContext, updateJob]);

  // Handle evolve
  const handleEvolve = async ({ parentGenerationId, selectedVariantIndices, feedback, quickTags, variantCount }) => {
    try {
      const res = await api.post(`${API}/evolve`, {
        parent_generation_id: parentGenerationId,
        selected_variant_indices: selectedVariantIndices,
        feedback,
        quick_tags: quickTags,
        variant_count: variantCount,
      });

      if (res.data.success) {
        toast.success(t('evolve.evolve') + ' ✨');
        return res.data; // Return to caller (GenerationCard) for inline threading
      }
    } catch (e) {
      const detail = e.response?.data?.detail || t('evolve.error');
      toast.error(detail);
      throw e;
    }
  };



  // Placeholder based on active tab
  const basePlaceholderKeys = PLATFORM_PLACEHOLDER_KEYS[activePlatform] || PLATFORM_PLACEHOLDER_KEYS.twitter;
  const resolvedPlaceholders = {};
  for (const [key, val] of Object.entries(basePlaceholderKeys)) {
    resolvedPlaceholders[key] = t(val);
  }
  const placeholders = {
    ...resolvedPlaceholders,
    ...(fetchPhase === "prompt" && {
      quote: t('create.placeholders.quoteTweet'),
      reply: t('create.placeholders.replyTweet'),
    }),
  };

  const needsUrl = activeTab === "quote" || activeTab === "reply";
  const isUrlInput = needsUrl && inputValue.match(/x\.com|twitter\.com/);
  const tl = (items, id) => { const f = items.find((i) => i.id === id); return f?.labelKey ? t(f.labelKey) : ""; };
  const settingsSummary = activePlatform === "linkedin"
    ? `${tl(linkedinPersonas, settings.linkedinPersona)} · ${tl(linkedinFormats, settings.linkedinFormat)} · ${settings.variants}x`
    : activePlatform === "blog"
    ? `${tl(blogStyles, settings.blogStyle)} · ${tl(blogFrameworks, settings.blogFramework)} · ${tl(blogLevels, settings.blogLevel)}`
    : activePlatform === "twitter"
    ? `${tl(v2Etkiler, settings.etki)} · ${tl(v2Karakterler, settings.karakter)} · ${tl(v2Yapilar, settings.yapi)} · ${settings.variants}x${settings.isUltra ? " · Ultra" : ""}`
    : `${tl(personas, settings.persona)} · ${tl(tones, settings.tone)} · ${settings.variants}x`;

  return (
    <div
      style={{
        minHeight: "calc(100vh - 80px)",
        background: "var(--m-bg)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
        color: "var(--m-text)",
        padding: window.innerWidth < 640 ? "12px 12px" : "24px 16px",
        position: "relative",
        overflow: "hidden",
        transition: "background 0.35s ease, color 0.35s ease, border-color 0.35s ease",
      }}
    >
      {/* Subtle background grain */}
      <div
        style={{
          position: "fixed",
          inset: 0,
          background: "var(--m-grain)",
          pointerEvents: "none",
        }}
      />

      {/* Vertical spacer - pushes content toward center */}
      <div style={{ height: window.innerWidth < 640 ? "4vh" : "15vh", flexShrink: 0 }} />

      {/* Style Profile Badge (top) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0",
          background: "var(--m-border-light)",
          borderRadius: "999px",
          padding: "6px 4px",
          marginBottom: window.innerWidth < 640 ? "16px" : "32px",
          border: "1px solid var(--m-border-light)",
          opacity: isLoaded ? 1 : 0,
          transform: isLoaded ? "translateY(0)" : "translateY(-8px)",
          transition: "all 0.5s ease 0.1s",
        }}
      >
        <StyleProfileBadge />
        <span
          style={{
            width: "1px",
            height: "14px",
            background: "var(--m-border)",
          }}
        />
        <span
          style={{
            fontSize: "13px",
            color: "var(--m-text-muted)",
            padding: "4px 14px",
            letterSpacing: "0.01em",
          }}
        >
          {settingsSummary}
        </span>
      </div>
      {activePlatform === "style-transfer" ? (
        <StyleTransferMode onEvolve={handleEvolve} />
      ) : (
      <>
      {/* Onboarding */}
      <OnboardingTip isLoaded={isLoaded} hasStyleProfile={profiles?.length > 0} />

      {/* Main Heading */}
      <h1
        style={{
          fontSize: "clamp(20px, 5vw, 42px)",
          fontWeight: "400",
          fontFamily: "'Georgia', 'Times New Roman', 'Noto Serif', serif",
          textAlign: "center",
          marginBottom: window.innerWidth < 640 ? "20px" : "36px",
          letterSpacing: "-0.01em",
          lineHeight: "1.25",
          fontStyle: "italic",
          opacity: isLoaded ? 1 : 0,
          transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.2s",
        }}
      >
        {t(PLATFORM_HEADING_KEYS[activePlatform] || 'create.platformHeadings.twitter')}
      </h1>

      {/* Fetched Tweet Preview */}
      {fetched && tweetData && (
        <div style={{ width: "100%", maxWidth: "680px", marginBottom: "12px" }}>
          <TweetPreviewCard tweet={tweetData} />
          <button
            onClick={() => {
              setFetched(false);
              setFetchPhase("link");
              setTweetData(null);
              setTweetUrl("");
              setInputValue("");
            }}
            style={{
              marginTop: "8px",
              padding: "6px 14px",
              borderRadius: "999px",
              border: "1px solid var(--m-border)",
              background: "transparent",
              color: "var(--m-text-muted)",
              fontSize: "12px",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            ← {t('create.differentTweet')}
          </button>

          {/* Direction Pills */}
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap" style={{ gap: "6px", marginTop: "10px" }}>
            {[
              { id: "support", label: `👍 ${t('create.directions.support')}`, color: "#22c55e" },
              { id: "oppose", label: `⚔️ ${t('create.directions.oppose')}`, color: "#ef4444" },
              { id: "add", label: `💡 ${t('create.directions.add')}`, color: "#3b82f6" },
              { id: "roast", label: `🔥 ${t('create.directions.roast')}`, color: "#f59e0b" },
            ].map(d => (
              <button
                key={d.id}
                onClick={() => setInputValue(prev => prev === d.id ? "" : d.id)}
                className="haptic-btn"
                style={{
                  padding: "6px 10px",
                  borderRadius: "999px",
                  border: inputValue === d.id ? `1px solid ${d.color}` : "1px solid var(--m-border)",
                  background: inputValue === d.id ? `${d.color}15` : "transparent",
                  color: inputValue === d.id ? d.color : "var(--m-text-muted)",
                  fontSize: "12px",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                  minHeight: "36px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {d.label}
              </button>
            ))}
            <span style={{ fontSize: "10px", color: "var(--m-text-muted)", alignSelf: "center", marginLeft: "2px" }}>
              {t('create.orTypeBelow')}
            </span>
          </div>
        </div>
      )}

      {/* Chat Input Container */}
      <div
        style={{
          width: "100%",
          maxWidth: "680px",
          marginBottom: "20px",
          opacity: isLoaded ? 1 : 0,
          transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.3s",
        }}
      >
        {/* Ultra glow wrapper */}
        <div
          className={settings.isUltra ? "ultra-glow-border" : ""}
          style={{
            borderRadius: "18px",
            position: "relative",
          }}
        >
        <div
          style={{
            background: "var(--m-input-bg)",
            border: "1px solid var(--m-input-border)",
            borderRadius: "16px",
            padding: window.innerWidth < 640 ? "12px 14px 10px" : "16px 18px 12px",
            position: "relative",
            boxShadow: "var(--m-shadow)",
            transition: "background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease",
          }}
        >
          {/* Image Preview */}
          {imageUrl && (
            <div style={{ marginBottom: "12px", position: "relative", display: "inline-block" }}>
              <img
                src={imageUrl}
                alt=""
                style={{ maxHeight: "80px", borderRadius: "8px" }}
              />
              <button
                onClick={() => { setImageUrl(null); setImageBase64(null); }}
                style={{
                  position: "absolute",
                  top: "-6px",
                  right: "-6px",
                  width: "20px",
                  height: "20px",
                  borderRadius: "50%",
                  background: "#ef4444",
                  border: "none",
                  color: "var(--m-text)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
              >
                <X size={12} />
              </button>
            </div>
          )}

          {/* Draft Bridge Banner */}
          {draftBridge && (
            <div className="mb-3 p-3 rounded-lg" style={{ background: "rgba(139,92,246,0.08)", border: "1px solid rgba(139,92,246,0.15)" }}>
              <div className="flex items-start gap-3">
                <span className="text-base mt-0.5">✨</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <p className="text-[11px] font-medium text-violet-400">DNA Taslağın Hazır</p>
                    {draftBridge.trend_topic && (
                      <button onClick={() => navigate("/dashboard/trends")}
                        className="text-[9px] px-2 py-0.5 rounded-full bg-fuchsia-500/10 text-fuchsia-400 border border-fuchsia-500/15 truncate max-w-[240px] hover:bg-fuchsia-500/20 transition-colors cursor-pointer">
                        📰 {draftBridge.trend_topic}
                      </button>
                    )}
                  </div>
                  <p className="text-[13px] text-white/80 leading-relaxed whitespace-pre-wrap">{draftBridge.content}</p>
                  {draftBridge.trend_summary && (
                    <p className="text-[10px] text-zinc-500 mt-2 leading-relaxed italic">
                      💡 Neden bu konu: {draftBridge.trend_summary}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2.5">
                    <button onClick={() => {
                      navigator.clipboard.writeText(draftBridge.content);
                      toast.success("Panoya kopyalandı!");
                      if (draftBridge.draft_id) api.put(`${API}/drafts/${draftBridge.draft_id}`, { status: "published" }).catch(() => {});
                    }} className="text-[10px] px-2 py-1 rounded-md bg-violet-600/20 text-violet-300 hover:bg-violet-600/30 transition-colors">
                      Kopyala
                    </button>
                    <button onClick={() => {
                      const text = encodeURIComponent(draftBridge.content);
                      window.open(`https://twitter.com/intent/tweet?text=${text}`, "_blank");
                      if (draftBridge.draft_id) api.put(`${API}/drafts/${draftBridge.draft_id}`, { status: "published" }).catch(() => {});
                    }} className="text-[10px] px-2 py-1 rounded-md bg-violet-600/20 text-violet-300 hover:bg-violet-600/30 transition-colors">
                      X'te Paylaş
                    </button>
                    <button onClick={() => navigate("/dashboard/trends")} className="text-[10px] px-2 py-1 rounded-md text-fuchsia-400/70 hover:text-fuchsia-300 hover:bg-fuchsia-500/10 transition-colors">
                      Trendlere Bak →
                    </button>
                    <button onClick={() => setDraftBridge(null)} className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors ml-auto">
                      Kapat
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleTextareaInput}
            placeholder={placeholders[activeTab]}
            rows={3}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleGenerate();
              }
            }}
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              outline: "none",
              color: "var(--m-text)",
              fontSize: "16px",
              lineHeight: "1.55",
              resize: "none",
              fontFamily: "inherit",
              padding: "0",
              marginBottom: "14px",
              caretColor: "var(--m-caret)",
            }}
          />

          {/* Toolbar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            {/* Left Icons */}
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              {/* Link (for fetch tweet) */}
              {needsUrl && (
                <button
                  onClick={handleFetchTweet}
                  disabled={fetching}
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "50%",
                    border: fetched ? "1px solid var(--m-green-border)" : "1px solid var(--m-border)",
                    background: fetched ? "var(--m-green-soft)" : "transparent",
                    color: fetched ? "var(--m-green)" : "var(--m-text-muted)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                  title={t('create.fetchTweet')}
                >
                  {fetching ? <Loader2 size={18} className="animate-spin" /> : <Link size={18} />}
                </button>
              )}

              {/* Ultra Mode Toggle (Zap icon) */}
              <button
                onClick={() => setSettings((s) => ({ ...s, isUltra: !s.isUltra }))}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  border: settings.isUltra ? "1px solid rgba(168,85,247,0.4)" : "1px solid var(--m-icon-btn-border)",
                  background: settings.isUltra ? "rgba(168,85,247,0.12)" : "transparent",
                  color: settings.isUltra ? "rgba(168,85,247,1)" : "var(--m-icon-color)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  transition: "all 0.3s ease",
                  boxShadow: settings.isUltra ? "0 0 12px rgba(168,85,247,0.2)" : "none",
                }}
                title={settings.isUltra ? t('create.ultraActive') : t('create.ultraSwitch')}
              >
                <Zap size={18} style={{ fill: settings.isUltra ? "rgba(168,85,247,1)" : "none" }} />
              </button>

              {/* Settings */}
              <button
                onClick={() => setSettingsOpen(true)}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  border: "1px solid var(--m-icon-btn-border)",
                  background: settingsOpen ? "var(--m-surface-hover)" : "transparent",
                  color: "var(--m-icon-color)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
                title={t('common.settings')}
              >
                <Settings2 size={18} />
              </button>
            </div>

            {/* Right: Send Button */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              {/* Send Button */}
              <button
                onClick={handleGenerate}
                disabled={generating}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  border: "none",
                  background: inputValue.trim() || fetched
                    ? "var(--m-send-bg)"
                    : "var(--m-send-bg-idle)",
                  color: inputValue.trim() || fetched
                    ? "var(--m-send-text)"
                    : "var(--m-send-text-idle)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: inputValue.trim() || fetched ? "pointer" : "default",
                  transition: "all 0.25s ease",
                }}
              >
                {generating ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path
                      d="M12 2L12 22M12 2L5 9M12 2L19 9"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      fill="none"
                    />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Platform Selection Bar (Manus-style "Connect your tools") */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderTop: "1px solid var(--m-border-light)",
              paddingTop: "10px",
              marginTop: "10px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--m-text-faint)" }}>
                <path d="M15 7h3a5 5 0 0 1 5 5 5 5 0 0 1-5 5h-3m-6 0H6a5 5 0 0 1-5-5 5 5 0 0 1 5-5h3" /><line x1="8" y1="12" x2="16" y2="12" />
              </svg>
              <span style={{ fontSize: "12px", color: "var(--m-text-faint)", whiteSpace: "nowrap" }}>{t('create.selectPlatform')}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              {[
                { id: "twitter", color: "#000", darkColor: "#fff", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg> },
                { id: "youtube", color: "#FF0000", darkColor: "#FF0000", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg> },
                { id: "instagram", color: "#E4405F", darkColor: "#E4405F", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z"/></svg> },
                { id: "tiktok", color: "#010101", darkColor: "#fff", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg> },
                { id: "linkedin", color: "#0A66C2", darkColor: "#0A66C2", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg> },
                { id: "blog", color: "#6366F1", darkColor: "#818CF8", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><line x1="6" y1="8" x2="18" y2="8"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="6" y1="16" x2="14" y2="16"/></svg> },
                { id: "style-transfer", color: "#8B5CF6", darkColor: "#A78BFA", icon: <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> },
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    if (p.id === "style-transfer") {
                      navigate("/dashboard/persona-lab");
                      return;
                    }
                    setActivePlatform(p.id);
                    if (PLATFORM_CONTENT_TYPES_DATA[p.id]) setActiveTab(PLATFORM_CONTENT_TYPES_DATA[p.id][0].id);
                    setFetched(false);
                    setFetchPhase("link");
                    setTweetData(null);
                    setTweetUrl("");
                    // Navbar sync: URL'deki platform parametresini güncelle
                    setSearchParams((prev) => {
                      const next = new URLSearchParams(prev);
                      next.set("platform", p.id);
                      return next;
                    }, { replace: true });
                  }}
                  style={{
                    width: "26px",
                    height: "26px",
                    borderRadius: "50%",
                    border: activePlatform === p.id ? "2px solid var(--m-text-muted)" : "1.5px solid var(--m-border)",
                    background: "transparent",
                    color: activePlatform === p.id ? p.color : "var(--m-text-faint)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    opacity: activePlatform === p.id ? 1 : 0.45,
                    transition: "all 0.2s ease",
                    transform: activePlatform === p.id ? "scale(1.1)" : "scale(1)",
                  }}
                  title={p.id}
                >
                  {p.icon}
                </button>
              ))}
            </div>
          </div>

        </div>
        </div>

        {/* Settings Popup - below input */}
        <SettingsPopup
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          settings={settings}
          onSettingsChange={setSettings}
          activeTab={activeTab}
          activePlatform={activePlatform}
          onGenerate={handleGenerate}
        />
      </div>

      {/* Quick Action Chips (Content Type Tabs) */}
      <div
        className="scrollbar-hide"
        style={{
          display: "flex",
          flexWrap: "nowrap",
          gap: "8px",
          justifyContent: "center",
          maxWidth: "680px",
          width: "100%",
          overflowX: "auto",
          WebkitOverflowScrolling: "touch",
          marginBottom: jobs.length > 0 ? "24px" : "80px",
          opacity: isLoaded ? 1 : 0,
          transform: isLoaded ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.6s ease 0.45s",
        }}
      >
        {(PLATFORM_CONTENT_TYPES_DATA[activePlatform] || PLATFORM_CONTENT_TYPES_DATA.twitter).map((ct) => {
          const Icon = ct.icon;
          const isActive = activeTab === ct.id;
          return (
            <button
              key={ct.id}
              onClick={() => {
                setActiveTab(ct.id);
                setFetched(false);
                setFetchPhase("link");
                setTweetData(null);
                setTweetUrl("");
                if (ct.id === "thread") {
                  setSettings((s) => ({ ...s, length: "thread" }));
                } else if (ct.id === "reply") {
                  setSettings((s) => ({ ...s, length: "punch" }));
                } else {
                  setSettings((s) => ({ ...s, length: "punch" }));
                }
              }}
              className="haptic-btn"
              style={{
                display: "flex",
                alignItems: "center",
                gap: window.innerWidth < 640 ? "5px" : "8px",
                padding: window.innerWidth < 640 ? "7px 13px" : "9px 18px",
                borderRadius: "999px",
                border: isActive
                  ? "1px solid var(--m-text-faint)"
                  : "1px solid var(--m-border)",
                background: isActive ? "var(--m-surface-hover)" : "transparent",
                color: isActive
                  ? "var(--m-text)"
                  : "var(--m-text-soft)",
                fontSize: window.innerWidth < 640 ? "12px" : "13.5px",
                cursor: "pointer",
                transition: "all 0.2s ease",
                fontFamily: "inherit",
                whiteSpace: "nowrap",
                flexShrink: 0,
                letterSpacing: "0.01em",
                fontWeight: isActive ? "500" : "400",
              }}
            >
              <Icon size={16} style={{ opacity: isActive ? 0.9 : 0.65 }} />
              {t(ct.labelKey)}
            </button>
          );
        })}
        {/* Makale butonu kaldırıldı */}
      </div>

      {/* Generation Results */}
      {jobs.length > 0 && (
        <div
          style={{
            width: "100%",
            maxWidth: "680px",
            marginBottom: "80px",
          }}
        >

          <div style={{ display: "flex", flexDirection: "column", gap: window.innerWidth < 640 ? "10px" : "16px" }}>
            {jobs.map((job) => (
              <GenerationCard
                key={job.id}
                job={job}
                onEvolve={handleEvolve}
                avatarUrl={primaryAccountAvatar}
              />
            ))}
          </div>
        </div>
      )}

      {/* Generation History */}
      <div
        style={{
          width: "100%",
          maxWidth: "680px",
          marginBottom: "80px",
        }}
      >
        {/* Collapsible Header */}
        <button
          onClick={() => setHistoryOpen((p) => !p)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            width: "100%",
            padding: "12px 0",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            color: "var(--m-text-soft)",
            fontSize: "14px",
            fontWeight: "600",
            fontFamily: "inherit",
          }}
        >
          {historyOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          {t('common.history')}
          {history.length > 0 && (
            <span style={{ fontSize: "12px", color: "var(--m-text-muted)", fontWeight: "400" }}>
              ({history.length})
            </span>
          )}
        </button>

        {historyOpen && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {historyLoading && history.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px", color: "var(--m-text-muted)", fontSize: "13px" }}>
                {t('common.loading')}
              </div>
            )}
            {!historyLoading && history.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px", color: "var(--m-text-muted)", fontSize: "13px" }}>
                {t('create.noHistory')}
              </div>
            )}
            {history.map((gen) => (
              <GenerationCard
                key={gen.id}
                job={{
                  generationId: gen.id,
                  topic: gen.topic || '',
                  persona: gen.persona || 'expert',
                  personaLabel: gen.persona || '',
                  toneLabel: gen.tone || '',
                  lengthLabel: gen.length || '',
                  type: gen.type || 'tweet',
                  status: 'completed',
                  variants: (gen.variants || []).map((v, i) => ({
                    ...v,
                    variant_index: v.variant_index ?? i,
                    character_count: v.character_count || v.content?.length || 0,
                  })),
                  variantCount: gen.variants?.length || 0,
                  evolutionDepth: gen.evolution_depth || 0,
                  style_scores: gen.style_scores || null,
                }}
                onEvolve={handleEvolve}
                showDate={true}
                createdAt={gen.created_at}
                tweetContent={gen.tweet_content}
                tweetUrl={gen.tweet_url}
                initialFavorites={gen.favorited_variants}
                avatarUrl={primaryAccountAvatar}
              />
            ))}
          </div>
        )}
      </div>

      </>
      )}

      {/* Floating Queue */}
      <FloatingQueue jobs={jobs} onDismiss={dismissJob} />
      <RepurposeModal
        open={repurposeModal.open}
        onClose={() => setRepurposeModal(prev => ({ ...prev, open: false }))}
        content={repurposeModal.content}
        mode={repurposeModal.mode}
        api={api}
        API={API}
      />

      {/* Bottom Promo Card */}
      {/* Promo cards removed - saved for landing page */}
      {false && (
        <div>
          {/* placeholder */}
          <div
            style={{
              background: "var(--m-card-bg)",
              border: "1px solid var(--m-border-light)",
              borderRadius: "14px",
              padding: "20px 24px",
              display: "flex",
              alignItems: "center",
              gap: "20px",
              maxWidth: "440px",
              width: "max-content",
              cursor: "pointer",
              boxShadow: "var(--m-shadow)",
              transition: "background 0.35s ease, border-color 0.35s ease, box-shadow 0.35s ease",
            }}
          >
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: "15px",
                  fontWeight: "600",
                  marginBottom: "5px",
                  color: "var(--m-text)",
                }}
              >
                {t(promoCards[activeCard].titleKey)}
              </div>
              <div
                style={{
                  fontSize: "13px",
                  color: "var(--m-text-muted)",
                  lineHeight: "1.45",
                }}
              >
                {t(promoCards[activeCard].descKey)}
              </div>
            </div>
            {/* Mini Preview */}
            <div
              style={{
                width: "90px",
                height: "64px",
                background: "rgba(0,0,0,0.4)",
                borderRadius: "8px",
                border: "1px solid var(--m-border-light)",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  height: "14px",
                  background: "var(--m-surface)",
                  display: "flex",
                  alignItems: "center",
                  gap: "3px",
                  padding: "0 5px",
                }}
              >
                <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#FF5F57" }} />
                <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#FEBC2E" }} />
                <span style={{ width: "4px", height: "4px", borderRadius: "50%", background: "#28C840" }} />
                <span style={{ marginLeft: "6px", width: "30px", height: "3px", background: "var(--m-border)", borderRadius: "2px" }} />
              </div>
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <TypeHypeLogo />
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
                  borderRadius: "50%",
                  border: "none",
                  background: i === activeCard ? "var(--m-text-soft)" : "var(--m-border)",
                  cursor: "pointer",
                  padding: 0,
                  transition: "all 0.3s ease",
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Global Styles */}
      <style>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }
        ::placeholder { color: var(--m-text-faint); }
        textarea:focus { outline: none !important; box-shadow: none !important; border-color: transparent !important; ring: none !important; }
        textarea::-webkit-scrollbar { width: 4px; }
        textarea::-webkit-scrollbar-track { background: transparent; }
        textarea::-webkit-scrollbar-thumb { background: var(--m-scrollbar); border-radius: 4px; }
        button:hover { filter: brightness(var(--m-hover-brightness)); }
        @media (max-width: 640px) {
          h1 { font-size: 26px !important; }
        }
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
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
            #a855f7,
            #3b82f6,
            #06b6d4,
            #ec4899,
            #ef4444,
            #f97316,
            #a855f7
          );
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          animation: ultra-rotate 6s linear infinite;
          pointer-events: none;
        }
        /* glow removed - border only */
      `}</style>
    </div>
  );
}
