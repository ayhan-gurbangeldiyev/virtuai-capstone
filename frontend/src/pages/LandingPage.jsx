import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import {
  Sparkles, ArrowRight, Zap, Target, Users, ChevronDown,
  BarChart3, Palette, MessageSquare, BookOpen,
  Check, Star, Monitor, Flame, Brain, Eye, Shield,
  Clock, Send, ChevronRight, Plus, X as XIcon,
  Wand2, TrendingUp, Lock, Layers, Globe, Play,
  CheckCircle2, XCircle, Minus,
  Pen,
} from 'lucide-react';
import { FaXTwitter, FaYoutube, FaInstagram, FaTiktok, FaLinkedinIn } from 'react-icons/fa6';
import { HiDocumentText } from 'react-icons/hi2';

/* ═══════════════════════════════════════════
   PART 1: DESIGN SYSTEM
   Satoshi font, tryholo.ai spacing & typography
   ═══════════════════════════════════════════ */

const satoshiFont = "'Satoshi', 'Inter', system-ui, sans-serif";
const clashFont = "'Clash Display', 'Satoshi', system-ui, sans-serif";

/* Animations */
const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] } }
};

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.5 } }
};

const scaleIn = {
  hidden: { opacity: 0, scale: 0.92 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] } }
};

const slideLeft = {
  hidden: { opacity: 0, x: -40 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.6, ease: 'easeOut' } }
};

const slideRight = {
  hidden: { opacity: 0, x: 40 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.6, ease: 'easeOut' } }
};

const stagger = {
  visible: { transition: { staggerChildren: 0.08 } }
};

const staggerSlow = {
  visible: { transition: { staggerChildren: 0.12 } }
};

/* Animated counter hook */
function useCounter(end, duration = 2000, startOnView = true) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (!inView && startOnView) return;
    let start = 0;
    const increment = end / (duration / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [inView, end, duration, startOnView]);

  return [count, ref];
}

/* ── Reusable Design System Components ── */

function MascotVideo({ className = '', style = {} }) {
  return (
    <video
      autoPlay
      loop
      muted
      playsInline
      className={className}
      style={style}
      src="/maskotvideo-loop.mp4"
    />
  );
}

function SectionWrapper({ children, className = '', bg = 'bg-[#fbfbfb]', id }) {
  return (
    <section id={id} className={`${bg} ${className}`} style={{ fontFamily: satoshiFont }}>
      <div className="max-w-[1200px] mx-auto px-6" style={{ paddingTop: 140, paddingBottom: 60 }}>
        {children}
      </div>
    </section>
  );
}

function SectionBadge({ children }) {
  return (
    <span className="inline-flex items-center px-4 py-1.5 rounded-full text-[13px] font-semibold bg-gradient-to-r from-violet-500/10 to-fuchsia-500/10 text-violet-600 border border-violet-200/40" style={{ fontFamily: satoshiFont }}>
      {children}
    </span>
  );
}

function SectionTitle({ children, className = '' }) {
  return (
    <h2
      className={`text-[32px] md:text-[40px] font-bold text-[#1d1d1f] leading-[1.15] tracking-[-0.02em] ${className}`}
      style={{ fontFamily: satoshiFont, fontWeight: 700 }}
    >
      {children}
    </h2>
  );
}

function SectionDescription({ children, className = '' }) {
  return (
    <p
      className={`text-[16px] md:text-[18px] text-gray-400 leading-[1.65] max-w-xl mx-auto ${className}`}
      style={{ fontFamily: satoshiFont, fontWeight: 500 }}
    >
      {children}
    </p>
  );
}

function HoloButton({ children, to = '/login', variant = 'gradient-border', className = '' }) {
  if (variant === 'gradient-border') {
    return (
      <Link
        to={to}
        className={`shrink-0 group inline-block hover:shadow-lg hover:shadow-violet-500/15 hover:-translate-y-0.5 active:scale-95 ${className}`}
        style={{
          padding: 2,
          borderRadius: 100,
          background: 'linear-gradient(107deg, #7c3aed 0%, #a855f7 25%, #d946ef 50%, #ec4899 75%, #f43f5e 100%)',
          transition: 'transform 0.3s, box-shadow 0.3s',
        }}
      >
        <div
          className="flex items-center justify-center gap-2 group-hover:bg-gray-50/90 transition-colors duration-200"
          style={{ background: '#fbfbfb', borderRadius: 100, padding: '13px 28px' }}
        >
          <span className="text-[16px] md:text-[18px] font-bold text-[#1d1d1f] tracking-tight" style={{ fontFamily: satoshiFont, fontWeight: 700 }}>
            {children}
          </span>
        </div>
      </Link>
    );
  }
  return (
    <Link
      to={to}
      className={`inline-flex items-center gap-2 px-8 py-3.5 bg-gradient-to-r from-violet-600 to-fuchsia-500 text-white rounded-full text-[16px] font-semibold hover:shadow-xl hover:shadow-violet-500/25 transition-all duration-300 hover:-translate-y-0.5 ${className}`}
      style={{ fontFamily: satoshiFont }}
    >
      {children}
    </Link>
  );
}

function HoloCard({ children, className = '' }) {
  return (
    <div
      className={`bg-white rounded-[20px] p-5 border border-gray-100/80 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 ${className}`}
    >
      {children}
    </div>
  );
}

/* ── Browser Frame Component ── */
function BrowserFrame({ children, url = 'typehype.io', className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-[#E5E7EB] shadow-lg overflow-hidden ${className}`}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/50">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
          <div className="w-3 h-3 rounded-full bg-[#FEBC2E]" />
          <div className="w-3 h-3 rounded-full bg-[#28C840]" />
        </div>
        <div className="flex-1 mx-3">
          <div className="bg-white rounded-md border border-gray-200 px-3 py-1.5 text-[12px] text-gray-400 text-center font-medium">
            {url}
          </div>
        </div>
      </div>
      <div>{children}</div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   NAVBAR — Holo tab bar (DOKUNMA)
   ═══════════════════════════════════════════ */

const glassStyle = {
  background: 'rgba(251, 251, 251, 0.92)',
  backdropFilter: 'blur(14px)',
  WebkitBackdropFilter: 'blur(14px)',
  border: '1px solid rgba(230, 230, 231, 0.7)',
  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(0, 0, 0, 0.02)',
};

const holoEase = [0.4, 0, 0.2, 1];
const holoTransition = { duration: 0.65, ease: holoEase };

function Navbar() {
  const { t, i18n } = useTranslation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 60);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  const navLinks = [
    { label: t('landing.navbar.howItWorks'), href: '#how-it-works' },
    { label: t('landing.navbar.features'), href: '#features' },
    { label: t('landing.navbar.platforms'), href: '#platforms' },
    { label: t('landing.navbar.faq'), href: '#faq' },
  ];

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="fixed top-0 left-0 right-0 z-50 px-5 pt-4"
    >
      <div
        className="flex items-center w-full transition-[padding] duration-700"
        style={{
          justifyContent: scrolled ? 'space-between' : 'center',
          gap: scrolled ? 0 : 10,
          padding: scrolled ? '0 4px' : '0',
        }}
      >
        <motion.div layout transition={{ layout: holoTransition }}>
          <Link
            to="/"
            className="shrink-0 flex items-center justify-center hover:scale-105 active:scale-95"
            style={{ transition: 'transform 0.2s' }}
          >
            <img src="/logo.png" alt="Type Hype" className="w-14 h-14 object-contain" />
          </Link>
        </motion.div>

        <motion.div layout transition={{ layout: holoTransition }} className="hidden md:block">
          <motion.div
            className="flex items-center overflow-hidden"
            animate={{
              opacity: scrolled ? 0 : 1,
              maxWidth: scrolled ? 0 : 520,
              paddingLeft: scrolled ? 0 : 22,
              paddingRight: scrolled ? 0 : 22,
              borderWidth: scrolled ? 0 : 1,
            }}
            transition={{ duration: 0.5, ease: holoEase }}
            style={{
              height: 52,
              borderRadius: 26,
              background: scrolled ? 'transparent' : 'rgba(251, 251, 251, 0.92)',
              backdropFilter: scrolled ? 'none' : 'blur(14px)',
              WebkitBackdropFilter: scrolled ? 'none' : 'blur(14px)',
              borderStyle: 'solid',
              borderColor: 'rgba(230, 230, 231, 0.7)',
              boxShadow: scrolled ? 'none' : '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.02)',
              gap: 6,
              pointerEvents: scrolled ? 'none' : 'auto',
              whiteSpace: 'nowrap',
              fontFamily: satoshiFont,
            }}
          >
            {navLinks.map((item) =>
              item.isRoute ? (
                <Link key={item.label} to={item.href} className="px-3 py-1.5 text-[14px] font-medium text-gray-500 hover:text-gray-900 hover:bg-gray-100/70 rounded-full transition-all duration-200">
                  {item.label}
                </Link>
              ) : (
                <a key={item.label} href={item.href} className="px-3 py-1.5 text-[14px] font-medium text-gray-500 hover:text-gray-900 hover:bg-gray-100/70 rounded-full transition-all duration-200">
                  {item.label}
                </a>
              )
            )}
          </motion.div>
        </motion.div>

        {/* Language Toggle */}
        <motion.div layout transition={{ layout: holoTransition }}>
          <button
            onClick={() => i18n.changeLanguage(i18n.language === 'tr' ? 'en' : 'tr')}
            className="px-3 py-1.5 text-[14px] font-medium text-gray-500 hover:text-gray-900 hover:bg-gray-100/70 rounded-full transition-all duration-200"
          >
            {i18n.language === 'tr' ? '🇬🇧 EN' : '🇹🇷 TR'}
          </button>
        </motion.div>

        <motion.div layout transition={{ layout: holoTransition }}>
          <Link
            to="/login"
            className="shrink-0 group block hover:shadow-lg hover:shadow-violet-500/15 hover:-translate-y-0.5 active:scale-95"
            style={{
              padding: 2,
              borderRadius: 100,
              background: 'linear-gradient(107deg, #7c3aed 0%, #a855f7 25%, #d946ef 50%, #ec4899 75%, #f43f5e 100%)',
              transition: 'transform 0.3s, box-shadow 0.3s',
            }}
          >
            <div
              className="flex items-center justify-center group-hover:bg-gray-50/90 transition-colors duration-200"
              style={{ background: 'rgb(251, 251, 251)', borderRadius: 100, padding: '13px 22px' }}
            >
              <span className="text-[15px] font-bold text-gray-900 tracking-tight" style={{ fontFamily: satoshiFont }}>
                {t('landing.navbar.getStarted')}
              </span>
            </div>
          </Link>
        </motion.div>
      </div>

      <div
        className="md:hidden flex items-center justify-center mt-2 transition-all duration-500"
        style={{ opacity: scrolled ? 0 : 1, maxHeight: scrolled ? 0 : 48, overflow: 'hidden' }}
      >
        <div className="flex items-center gap-1 px-3" style={{ height: 44, borderRadius: 22, ...glassStyle }}>
          {[
            { label: t('landing.navbar.features'), href: '#features' },
            { label: t('landing.navbar.faq'), href: '#faq' },
          ].map((item) => (
            <a key={item.label} href={item.href} className="px-3 py-1 text-[13px] font-medium text-gray-500 hover:text-gray-900 rounded-full transition-colors">
              {item.label}
            </a>
          ))}
          <Link to="/login" className="px-3 py-1 text-[13px] font-medium text-gray-500 hover:text-gray-900 rounded-full transition-colors">
            {t('landing.navbar.login')}
          </Link>
        </div>
      </div>
    </motion.nav>
  );
}

/* ═══════════════════════════════════════════
   S2: VALUE STATEMENTS — Soro word-by-word reveal
   ═══════════════════════════════════════════ */

function WordReveal({ children, delay = 0, inView }) {
  return (
    <span
      className="transition-opacity duration-500"
      style={{
        opacity: inView ? 1 : 0.15,
        transitionDelay: inView ? `${delay}ms` : '0ms',
      }}
    >
      {children}
    </span>
  );
}

function InlineVideo({ src, className = '' }) {
  return (
    <video
      autoPlay
      loop
      muted
      playsInline
      className={`inline-block align-middle mx-1.5 md:mx-3 ${className}`}
      style={{ mixBlendMode: 'multiply' }}
      src={src}
    />
  );
}

function ValueStatements() {
  const { t } = useTranslation();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  const line1 = t('landing.valueStatements.line1');
  const line2 = t('landing.valueStatements.line2');
  const line3 = t('landing.valueStatements.line3');

  // Split lines around the video insertion points (approximate word boundaries)
  const lines = [
    {
      segments: [
        { type: 'text', content: line1.split('yazım')[0] },
        { type: 'video', src: '/glass-boomerang.webm' },
        { type: 'text', content: 'yazım' + (line1.split('yazım')[1] || '') },
      ],
    },
    {
      segments: [
        { type: 'text', content: line2.split('ayırt')[0] || line2.substring(0, 6) },
        { type: 'video', src: '/pencil-boomerang.webm' },
        { type: 'text', content: line2.includes('ayırt') ? ('ayırt' + line2.split('ayırt')[1]) : line2.substring(6) },
      ],
    },
    {
      segments: [
        { type: 'text', content: line3 },
      ],
    },
  ];

  let wordIndex = 0;

  return (
    <section ref={ref} style={{ background: '#ffffff', paddingTop: 100, paddingBottom: 100 }}>
      <div className="max-w-[740px] mx-auto text-center px-6 space-y-12">
        {lines.map((line, li) => {
          const lineElements = [];
          line.segments.forEach((seg, si) => {
            if (seg.type === 'video') {
              const d = wordIndex * 80;
              wordIndex++;
              lineElements.push(
                <WordReveal key={`${li}-vid-${si}`} delay={d} inView={inView}>
                  <InlineVideo src={seg.src} className="w-14 h-14 md:w-20 md:h-20" />
                </WordReveal>
              );
            } else {
              const words = seg.content.split(' ');
              words.forEach((word, wi) => {
                const d = wordIndex * 80;
                wordIndex++;
                lineElements.push(
                  <WordReveal key={`${li}-${si}-${wi}`} delay={d} inView={inView}>
                    {word}{' '}
                  </WordReveal>
                );
              });
            }
          });
          return (
            <p
              key={li}
              className="text-[26px] sm:text-[32px] md:text-[44px] text-[#1d1d1f]"
              style={{
                fontWeight: 600,
                lineHeight: 1.35,
                fontFamily: clashFont,
              }}
            >
              {lineElements}
            </p>
          );
        })}
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S3: HERO — "Hype ile tanış."
   Marketing: Pain → Promise → Proof → CTA
   Psychology: JTBD, Loss Aversion, Social Proof
   ═══════════════════════════════════════════ */
function Hero() {
  const { t } = useTranslation();
  return (
    <section className="relative overflow-hidden" style={{ background: '#fbfbfb', paddingTop: 130, paddingBottom: 60, fontFamily: satoshiFont }}>
      {/* Subtle ambient glow */}
      <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-gradient-to-br from-violet-100/30 via-fuchsia-100/20 to-transparent rounded-full blur-[120px] -z-10" />

      <motion.div className="max-w-[1200px] mx-auto text-center px-6" initial="hidden" animate="visible" variants={stagger}>
        {/* Eyebrow badge */}
        <motion.div variants={fadeUp} className="flex justify-center mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-violet-50/80 rounded-full border border-violet-100/60">
            <Sparkles className="w-3.5 h-3.5 text-violet-500" />
            <span className="text-[13px] text-violet-600 font-medium">{t('landing.hero.badge')}</span>
          </div>
        </motion.div>

        {/* Main headline — Clash Display for impact */}
        <motion.h1
          variants={fadeUp}
          className="text-[36px] sm:text-[48px] md:text-[64px] lg:text-[72px] text-[#1d1d1f] leading-[1.05] tracking-[-0.03em] max-w-[850px] mx-auto"
          style={{ fontFamily: clashFont, fontWeight: 600 }}
        >
          {t('landing.hero.title')}{' '}
          <span className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-transparent">
            {t('landing.hero.titleHighlight')}
          </span>
        </motion.h1>

        {/* Sub-headline — emotional hook */}
        <motion.p
          variants={fadeUp}
          className="mt-5 text-[18px] sm:text-[22px] md:text-[28px] text-gray-400 max-w-[600px] mx-auto leading-[1.4] tracking-[-0.01em]"
          style={{ fontFamily: satoshiFont, fontWeight: 500 }}
        >
          {t('landing.hero.subtitle')}
        </motion.p>

        {/* CTA — action-oriented, specific */}
        <motion.div variants={fadeUp} className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <HoloButton to="/login">
            {t('landing.hero.cta')} <ArrowRight className="w-4 h-4 inline ml-1" />
          </HoloButton>
          <span className="text-[13px] text-gray-300 font-medium">{t('landing.hero.noCreditCard')}</span>
        </motion.div>

        {/* Social proof strip */}
        <motion.div variants={fadeUp} className="mt-10 flex flex-wrap items-center justify-center gap-8 text-[13px] text-gray-400">
          <div className="flex items-center gap-2.5">
            <div className="flex -space-x-1.5">
              {['bg-violet-400', 'bg-fuchsia-400', 'bg-pink-400', 'bg-amber-400', 'bg-emerald-400'].map((bg, i) => (
                <div key={i} className={`w-7 h-7 rounded-full ${bg} border-2 border-white`} />
              ))}
            </div>
            <span className="font-medium">{t('landing.hero.socialProof')}</span>
          </div>
          <div className="flex items-center gap-1.5">
            {[...Array(5)].map((_, i) => (
              <Star key={i} className="w-4 h-4 text-amber-400 fill-amber-400" />
            ))}
            <span className="ml-1 font-medium">{t('landing.hero.rating')}</span>
          </div>
        </motion.div>

        {/* Browser Frame + Mascot Video — the product reveal */}
        <motion.div variants={scaleIn} className="mt-16 max-w-[1040px] mx-auto">
          <BrowserFrame>
            <MascotVideo className="w-full" />
          </BrowserFrame>
        </motion.div>
      </motion.div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S4: HOW IT WORKS — 3 Steps
   ═══════════════════════════════════════════ */
function HowItWorks() {
  const { t } = useTranslation();
  const steps = [
    { num: '01', title: t('landing.howItWorks.step1Title'), desc: t('landing.howItWorks.step1Desc') },
    { num: '02', title: t('landing.howItWorks.step2Title'), desc: t('landing.howItWorks.step2Desc') },
    { num: '03', title: t('landing.howItWorks.step3Title'), desc: t('landing.howItWorks.step3Desc') },
  ];

  return (
    <section id="how-it-works" style={{ background: '#fbfbfb', fontFamily: satoshiFont, paddingTop: 140, paddingBottom: 60 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <motion.div className="text-center mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
          <SectionTitle className="text-center">{t('landing.howItWorks.title')}</SectionTitle>
        </motion.div>

        <motion.div
          className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={stagger}
        >
          {steps.map((step, i) => (
            <motion.div
              key={i}
              variants={fadeUp}
              className="text-center"
              style={{ transitionDelay: `${i * 100}ms` }}
            >
              <div
                className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-500 flex items-center justify-center mx-auto mb-5"
              >
                <span className="text-[20px] text-white" style={{ fontWeight: 800, fontFamily: satoshiFont }}>{step.num}</span>
              </div>
              <h3 className="text-[18px] md:text-[20px] text-[#1d1d1f] mb-2" style={{ fontWeight: 700, fontFamily: satoshiFont }}>{step.title}</h3>
              <p className="text-[14px] md:text-[16px] text-gray-400 leading-[1.65] max-w-[280px] mx-auto" style={{ fontWeight: 500 }}>{step.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S5: BRAND DNA FEATURES — 3 Big Cards
   ═══════════════════════════════════════════ */
function BrandDNAFeatures() {
  const { t } = useTranslation();
  const features = [
    {
      icon: <Brain className="w-7 h-7 text-white" />,
      title: t('landing.features.styleCloning'),
      desc: t('landing.features.styleCloningDesc'),
    },
    {
      icon: <Wand2 className="w-7 h-7 text-white" />,
      title: t('landing.features.aiCharacters'),
      desc: t('landing.features.aiCharactersDesc'),
    },
    {
      icon: <Flame className="w-7 h-7 text-white" />,
      title: t('landing.features.apexMode'),
      desc: t('landing.features.apexModeDesc'),
    },
  ];

  return (
    <section id="features" style={{ background: '#f8f8f8', fontFamily: satoshiFont, paddingTop: 140, paddingBottom: 60 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <motion.div className="text-center mb-16" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
          <SectionTitle className="text-center">{t('landing.features.title')}</SectionTitle>
          <SectionDescription className="mt-4">{t('landing.features.subtitle')}</SectionDescription>
        </motion.div>

        <motion.div
          className="grid md:grid-cols-3 gap-6"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-40px' }}
          variants={stagger}
        >
          {features.map((f, i) => (
            <motion.div key={i} variants={fadeUp}>
              <div className="bg-white rounded-[20px] border border-gray-100 p-8 hover:shadow-xl hover:-translate-y-2 transition-all duration-300 h-full">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-fuchsia-500 flex items-center justify-center mb-6">
                  {f.icon}
                </div>
                <h3 className="text-[18px] md:text-[20px] text-[#1d1d1f] mb-3" style={{ fontWeight: 700, fontFamily: satoshiFont }}>{f.title}</h3>
                <p className="text-[14px] md:text-[16px] text-gray-400 leading-[1.65]" style={{ fontWeight: 500 }}>{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S6: STYLE SHOWCASE (Brand DNA — preserved)
   ═══════════════════════════════════════════ */
function StyleShowcase() {
  const { t } = useTranslation();
  const dimensions = [
    { name: t('landing.styleShowcase.wordChoice'), score: 72 },
    { name: t('landing.styleShowcase.sentenceFlow'), score: 65 },
    { name: t('landing.styleShowcase.humorLevel'), score: 95 },
    { name: t('landing.styleShowcase.emojiUsage'), score: 78 },
    { name: t('landing.styleShowcase.engagementPower'), score: 97 },
    { name: t('landing.styleShowcase.provocativeness'), score: 92 },
  ];

  return (
    <section style={{ background: '#fbfbfb', fontFamily: satoshiFont, paddingTop: 180, paddingBottom: 60 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-16 items-center">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={scaleIn}>
            <div className="bg-white rounded-[20px] shadow-2xl shadow-gray-200/50 border border-gray-100 p-7">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-11 h-11 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-full flex items-center justify-center text-white text-[13px] font-bold">SK</div>
                <div className="flex-1">
                  <div className="text-[14px] font-semibold text-[#1d1d1f]">@semihdev</div>
                  <div className="text-[12px] text-gray-400">{t('landing.styleShowcase.profileActive')}</div>
                </div>
                <div className="px-3 py-1 bg-green-50 text-green-600 rounded-full text-[11px] font-medium flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                  {t('landing.styleShowcase.analyzed')}
                </div>
              </div>
              <div className="space-y-3.5">
                {dimensions.map((d) => (
                  <div key={d.name} className="flex items-center gap-3">
                    <span className="text-[12px] text-gray-400 w-[110px] shrink-0" style={{ fontWeight: 500 }}>{d.name}</span>
                    <div className="flex-1 h-[6px] bg-gray-100 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full"
                        initial={{ width: 0 }}
                        whileInView={{ width: `${d.score}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 1.2, delay: 0.3, ease: 'easeOut' }}
                      />
                    </div>
                    <span className="text-[12px] font-semibold text-gray-600 w-[32px] text-right">{d.score}%</span>
                  </div>
                ))}
              </div>
              <div className="mt-6 p-4 bg-violet-50/60 rounded-xl border border-violet-100/60">
                <p className="text-[12px] text-violet-600 leading-[1.6]" style={{ fontWeight: 500 }}>
                  {t('landing.styleShowcase.tip')}
                </p>
              </div>
            </div>
          </motion.div>

          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={staggerSlow}>
            <motion.div variants={fadeUp}><SectionBadge>{t('landing.styleShowcase.badge')}</SectionBadge></motion.div>
            <motion.div variants={fadeUp}>
              <SectionTitle className="mt-5 whitespace-pre-line">
                {t('landing.styleShowcase.title')}
              </SectionTitle>
            </motion.div>
            <motion.p variants={fadeUp} className="mt-5 text-[16px] md:text-[18px] text-gray-400 leading-[1.7] max-w-[420px]" style={{ fontWeight: 500 }}>
              {t('landing.styleShowcase.subtitle')}
            </motion.p>
            <motion.div variants={fadeUp} className="mt-8 space-y-3.5">
              {[
                t('landing.styleShowcase.bullet1'),
                t('landing.styleShowcase.bullet2'),
                t('landing.styleShowcase.bullet3'),
                t('landing.styleShowcase.bullet4'),
              ].map((text, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-5 h-5 bg-gradient-to-br from-violet-500 to-fuchsia-500 rounded-full flex items-center justify-center shrink-0">
                    <Check className="w-3 h-3 text-white" />
                  </div>
                  <span className="text-[14px] text-gray-500" style={{ fontWeight: 500 }}>{text}</span>
                </div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S7: STATS — Full-width, no cards
   ═══════════════════════════════════════════ */
function StatsSection() {
  const { t } = useTranslation();
  const [count1, ref1] = useCounter(50, 1500);
  const [count2, ref2] = useCounter(6, 800);
  const [count3, ref3] = useCounter(9, 800);
  const [count4, ref4] = useCounter(500, 1800);

  const stats = [
    { value: `${count1}K+`, label: t('landing.stats.contentGenerated'), ref: ref1 },
    { value: count2.toString(), label: t('landing.stats.platformSupport'), ref: ref2 },
    { value: count3.toString(), label: t('landing.stats.styleDimensions'), ref: ref3 },
    { value: `${count4}+`, label: t('landing.stats.activeUsers'), ref: ref4 },
  ];

  return (
    <section style={{ background: '#f8f8f8', fontFamily: satoshiFont, paddingTop: 120, paddingBottom: 120 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="flex flex-wrap items-center justify-center">
          {stats.map((s, i) => (
            <div key={i} className="flex items-center">
              <div ref={s.ref} className="text-center px-8 md:px-12 py-4">
                <div
                  className="text-[48px] md:text-[72px] leading-tight bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent"
                  style={{ fontWeight: 900, fontFamily: satoshiFont }}
                >
                  {s.value}
                </div>
                <div className="text-[14px] text-gray-400 mt-1" style={{ fontWeight: 500 }}>{s.label}</div>
              </div>
              {i < stats.length - 1 && (
                <div className="hidden md:block w-px bg-gray-200" style={{ height: 60 }} />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S8: PLATFORM SUPPORT
   ═══════════════════════════════════════════ */
function PlatformSupport() {
  const { t } = useTranslation();
  const platforms = [
    { name: t('landing.platforms.twitter'), icon: <FaXTwitter className="w-7 h-7" />, desc: t('landing.platforms.twitterDesc'), color: 'text-gray-800', bg: 'bg-gray-50' },
    { name: t('landing.platforms.instagram'), icon: <FaInstagram className="w-7 h-7" />, desc: t('landing.platforms.instagramDesc'), color: 'text-pink-500', bg: 'bg-pink-50' },
    { name: t('landing.platforms.tiktok'), icon: <FaTiktok className="w-7 h-7" />, desc: t('landing.platforms.tiktokDesc'), color: 'text-gray-800', bg: 'bg-gray-50' },
    { name: t('landing.platforms.youtube'), icon: <FaYoutube className="w-7 h-7" />, desc: t('landing.platforms.youtubeDesc'), color: 'text-red-500', bg: 'bg-red-50' },
    { name: t('landing.platforms.linkedin'), icon: <FaLinkedinIn className="w-7 h-7" />, desc: t('landing.platforms.linkedinDesc'), color: 'text-blue-600', bg: 'bg-blue-50' },
    { name: t('landing.platforms.blog'), icon: <HiDocumentText className="w-7 h-7" />, desc: t('landing.platforms.blogDesc'), color: 'text-emerald-500', bg: 'bg-emerald-50' },
  ];

  return (
    <section id="platforms" style={{ background: '#fbfbfb', fontFamily: satoshiFont, paddingTop: 140, paddingBottom: 60 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <motion.div className="text-center mb-14" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
          <SectionBadge>{t('landing.platforms.badge')}</SectionBadge>
          <SectionTitle className="mt-5 text-center">{t('landing.platforms.title')}</SectionTitle>
          <SectionDescription className="mt-4">{t('landing.platforms.subtitle')}</SectionDescription>
        </motion.div>

        <motion.div className="grid grid-cols-2 md:grid-cols-3 gap-5" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger}>
          {platforms.map((p, i) => (
            <motion.div key={i} variants={fadeUp}>
              <HoloCard className="group p-8 h-full">
                <div className={`w-16 h-16 ${p.bg} rounded-[20px] flex items-center justify-center mb-4 ${p.color} group-hover:scale-110 transition-transform duration-300`}>
                  {p.icon}
                </div>
                <h3 className="text-[16px] font-bold text-[#1d1d1f] mb-1" style={{ fontWeight: 700 }}>{p.name}</h3>
                <p className="text-[13px] text-gray-400 leading-[1.5]" style={{ fontWeight: 500 }}>{p.desc}</p>
              </HoloCard>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S9: COST COMPARISON — Grid table
   ═══════════════════════════════════════════ */
function CostComparison() {
  const { t } = useTranslation();
  const rows = [
    t('landing.costComparison.styleCloning'),
    t('landing.costComparison.aiCharacters'),
    t('landing.costComparison.apexMode'),
    t('landing.costComparison.platformSupport'),
    t('landing.costComparison.trendTracking'),
    t('landing.costComparison.alwaysOn'),
  ];

  return (
    <section style={{ background: '#f8f8f8', fontFamily: satoshiFont, paddingTop: 140, paddingBottom: 60 }}>
      <div className="max-w-[900px] mx-auto px-6">
        <motion.div className="text-center mb-14" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
          <SectionTitle className="text-center">{t('landing.costComparison.title')}</SectionTitle>
          <SectionDescription className="mt-4">{t('landing.costComparison.subtitle')}</SectionDescription>
        </motion.div>

        <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={scaleIn}>
          <div className="bg-white rounded-[20px] border border-gray-100 overflow-hidden">
            {/* Header */}
            <div className="grid grid-cols-3 border-b border-gray-100">
              <div className="px-6 py-4 text-[13px] font-semibold text-gray-400" style={{ fontWeight: 600 }}>{t('landing.costComparison.feature')}</div>
              <div className="px-6 py-4 text-center text-[13px] font-semibold text-gray-400" style={{ fontWeight: 600 }}>{t('landing.costComparison.otherTools')}</div>
              <div className="px-6 py-4 text-center text-[13px] font-bold text-white bg-gradient-to-r from-violet-600 to-fuchsia-500" style={{ fontWeight: 700 }}>Type Hype</div>
            </div>
            {/* Rows */}
            {rows.map((feature, i) => (
              <div key={i} className={`grid grid-cols-3 ${i < rows.length - 1 ? 'border-b border-gray-50' : ''}`}>
                <div className="px-6 py-4 text-[14px] text-gray-700" style={{ fontWeight: 500 }}>{feature}</div>
                <div className="px-6 py-4 flex items-center justify-center">
                  <div className="w-7 h-7 rounded-full bg-red-50 flex items-center justify-center">
                    <XIcon className="w-3.5 h-3.5 text-red-400" />
                  </div>
                </div>
                <div className="px-6 py-4 flex items-center justify-center bg-violet-50/30">
                  <div className="w-7 h-7 rounded-full bg-green-50 flex items-center justify-center">
                    <Check className="w-3.5 h-3.5 text-green-500" />
                  </div>
                </div>
              </div>
            ))}
            {/* Price row */}
            <div className="grid grid-cols-3 border-t border-gray-100 bg-gray-50/30">
              <div className="px-6 py-5 text-[14px] text-[#1d1d1f]" style={{ fontWeight: 700 }}>{t('landing.costComparison.monthlyCost')}</div>
              <div className="px-6 py-5 text-center">
                <span className="text-[20px] text-red-500 line-through" style={{ fontWeight: 700 }}>$142+/ay</span>
              </div>
              <div className="px-6 py-5 text-center bg-violet-50/30">
                <span className="text-[20px] bg-gradient-to-r from-violet-600 to-fuchsia-500 bg-clip-text text-transparent" style={{ fontWeight: 900 }}>$0/ay</span>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S10: PRIVACY & SECURITY
   ═══════════════════════════════════════════ */
function PrivacySecurity() {
  const { t } = useTranslation();
  return (
    <section style={{ background: '#fbfbfb', fontFamily: satoshiFont, paddingTop: 180, paddingBottom: 60 }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="grid md:grid-cols-2 gap-14 items-center">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={staggerSlow}>
            <motion.div variants={fadeUp}><SectionBadge>{t('landing.privacy.badge')}</SectionBadge></motion.div>
            <motion.div variants={fadeUp}>
              <SectionTitle className="mt-5 whitespace-pre-line">{t('landing.privacy.title')}</SectionTitle>
            </motion.div>
            <motion.p variants={fadeUp} className="mt-5 text-[16px] md:text-[18px] text-gray-400 leading-[1.7] max-w-[400px]" style={{ fontWeight: 500 }}>
              {t('landing.privacy.subtitle')}
            </motion.p>
            <motion.div variants={fadeUp} className="mt-8 space-y-4">
              {[
                { icon: <Lock className="w-4 h-4" />, text: t('landing.privacy.encryption') },
                { icon: <Shield className="w-4 h-4" />, text: t('landing.privacy.noSharing') },
                { icon: <Eye className="w-4 h-4" />, text: t('landing.privacy.fullControl') },
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-violet-50 rounded-lg flex items-center justify-center text-violet-500">{item.icon}</div>
                  <span className="text-[14px] text-gray-600" style={{ fontWeight: 500 }}>{item.text}</span>
                </div>
              ))}
            </motion.div>
            <motion.div variants={fadeUp} className="mt-8">
              <Link
                to="/aydinlatma"
                className="inline-flex items-center gap-2 px-5 py-2.5 border border-violet-200 text-violet-600 rounded-full text-[13px] font-semibold hover:bg-violet-50 transition-colors"
              >
                <Shield className="w-3.5 h-3.5" />
                {t('landing.privacy.readNotice')}
              </Link>
            </motion.div>
          </motion.div>

          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={slideRight} className="flex justify-center">
            <div className="relative">
              <MascotVideo className="w-full max-w-[350px] rounded-3xl" />
              <motion.div
                className="absolute -bottom-4 -right-4 w-16 h-16 bg-white rounded-[20px] shadow-xl flex items-center justify-center"
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <Shield className="w-7 h-7 text-violet-500" />
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S11: FAQ
   ═══════════════════════════════════════════ */
function FAQ() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(0);
  const items = [
    { q: t('landing.faq.q1'), a: t('landing.faq.a1') },
    { q: t('landing.faq.q2'), a: t('landing.faq.a2') },
    { q: t('landing.faq.q3'), a: t('landing.faq.a3') },
    { q: t('landing.faq.q4'), a: t('landing.faq.a4') },
    { q: t('landing.faq.q5'), a: t('landing.faq.a5') },
    { q: t('landing.faq.q6'), a: t('landing.faq.a6') },
  ];

  return (
    <section id="faq" style={{ background: '#f8f8f8', fontFamily: satoshiFont, paddingTop: 180, paddingBottom: 60 }}>
      <div className="max-w-[800px] mx-auto px-6">
        <motion.div className="text-center mb-14" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeUp}>
          <SectionBadge>{t('landing.faq.badge')}</SectionBadge>
          <SectionTitle className="mt-5 text-center">{t('landing.faq.title')}</SectionTitle>
        </motion.div>

        <motion.div className="space-y-3" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger}>
          {items.map((item, i) => (
            <motion.div key={i} variants={fadeUp} className="bg-white border border-gray-100 rounded-[20px] overflow-hidden">
              <button onClick={() => setOpen(open === i ? -1 : i)} className="w-full flex items-center justify-between p-5 text-left hover:bg-gray-50/50 transition-colors">
                <span className="text-[15px] font-medium text-[#1d1d1f] pr-4" style={{ fontWeight: 500 }}>{item.q}</span>
                <div className="w-7 h-7 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-center shrink-0">
                  {open === i ? <Minus className="w-3.5 h-3.5 text-gray-400" /> : <Plus className="w-3.5 h-3.5 text-gray-400" />}
                </div>
              </button>
              <AnimatePresence>
                {open === i && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25, ease: 'easeOut' }} className="overflow-hidden">
                    <div className="px-5 pb-5 -mt-1">
                      <p className="text-[14px] text-gray-500 leading-[1.7]" style={{ fontWeight: 500 }}>{item.a}</p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S12: FINAL CTA
   ═══════════════════════════════════════════ */
function FinalCTA() {
  const { t } = useTranslation();
  return (
    <section className="relative overflow-hidden" style={{ background: '#fbfbfb', fontFamily: satoshiFont, paddingTop: 120, paddingBottom: 120 }}>
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-gradient-to-r from-violet-100/60 via-fuchsia-100/40 to-pink-100/60 rounded-full blur-[100px]" />
      </div>

      <motion.div className="max-w-[700px] mx-auto text-center px-6" initial="hidden" whileInView="visible" viewport={{ once: true }} variants={stagger}>
        <motion.div variants={scaleIn} className="flex justify-center mb-8">
          <MascotVideo className="w-[140px] h-[140px] rounded-full object-cover" style={{ objectFit: 'cover' }} />
        </motion.div>

        <motion.h2 variants={fadeUp} className="text-[36px] md:text-[56px] text-[#1d1d1f] leading-[1.05] tracking-[-0.03em]" style={{ fontWeight: 900 }}>
          {t('landing.finalCta.title')}<br />
          <span className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-transparent">
            {t('landing.finalCta.titleHighlight')}
          </span>
        </motion.h2>

        <motion.p variants={fadeUp} className="mt-5 text-[16px] md:text-[18px] text-gray-400 max-w-[450px] mx-auto leading-[1.65]" style={{ fontWeight: 500 }}>
          {t('landing.finalCta.subtitle')}
        </motion.p>

        <motion.div variants={fadeUp} className="mt-9 flex flex-col items-center gap-4">
          <HoloButton to="/login">
            {t('landing.finalCta.cta')} <ArrowRight className="w-4 h-4 inline ml-1" />
          </HoloButton>
          <p className="text-[13px] text-gray-400" style={{ fontWeight: 500 }}>{t('landing.finalCta.noCreditCard')}</p>
        </motion.div>
      </motion.div>
    </section>
  );
}

/* ═══════════════════════════════════════════
   S13: FOOTER
   ═══════════════════════════════════════════ */
function Footer() {
  const { t } = useTranslation();
  const columns = [
    { title: t('landing.footer.product'), links: [t('landing.footer.featuresLink'), t('landing.footer.platformsLink'), t('landing.footer.styleLabLink'), t('landing.footer.pricingLink')] },
    { title: t('landing.footer.characters'), links: [t('landing.footer.authority'), t('landing.footer.insider'), t('landing.footer.mentalist'), t('landing.footer.saf'), t('landing.footer.news')] },
    { title: t('landing.footer.technology'), links: [t('landing.footer.apexMode'), t('landing.footer.styleCloning'), t('landing.footer.trendEngine')] },
    { title: t('landing.footer.resources'), links: [t('landing.footer.blogLink'), t('landing.footer.changelog'), t('landing.footer.docs')] },
  ];

  return (
    <footer className="border-t border-gray-200/60" style={{ background: '#f8f8f8', fontFamily: satoshiFont, padding: '56px 24px' }}>
      <div className="max-w-[1200px] mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-7 gap-8">
          <div className="col-span-2">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-600 to-fuchsia-500 flex items-center justify-center">
                <Sparkles className="w-3.5 h-3.5 text-white" />
              </div>
              <span className="text-[17px] text-[#1d1d1f]" style={{ fontWeight: 700 }}>Type Hype</span>
            </div>
            <p className="text-[12px] text-gray-400 leading-[1.6] whitespace-pre-line" style={{ fontWeight: 500 }}>
              {t('landing.footer.copyright')}
            </p>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <div className="text-[13px] text-[#1d1d1f] mb-4" style={{ fontWeight: 700 }}>{col.title}</div>
              <div className="space-y-2.5">
                {col.links.map((link) => (
                  <div key={link} className="text-[13px] text-gray-400 hover:text-gray-600 cursor-pointer transition-colors" style={{ fontWeight: 500 }}>{link}</div>
                ))}
              </div>
            </div>
          ))}

          <div>
            <div className="text-[13px] text-[#1d1d1f] mb-4" style={{ fontWeight: 700 }}>{t('landing.footer.followUs')}</div>
            <div className="flex gap-3 mb-4">
              {[
                { icon: <FaXTwitter className="w-4 h-4" />, color: 'text-gray-600' },
                { icon: <FaInstagram className="w-4 h-4" />, color: 'text-pink-500' },
                { icon: <FaLinkedinIn className="w-4 h-4" />, color: 'text-blue-600' },
              ].map((s, i) => (
                <div key={i} className={`w-9 h-9 bg-white border border-gray-100 rounded-xl flex items-center justify-center ${s.color} hover:bg-gray-50 cursor-pointer transition-colors`}>
                  {s.icon}
                </div>
              ))}
            </div>
            <a href="mailto:hello@typehype.io" className="inline-flex items-center px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg text-[12px] font-medium hover:bg-gray-100 transition-colors">
              {t('landing.footer.contact')}
            </a>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-gray-200/60 flex flex-col sm:flex-row justify-between items-center text-[12px] text-gray-400">
          <span>{t('landing.footer.builtWithAi')}</span>
          <div className="flex gap-6 mt-2 sm:mt-0">
            <Link to="/aydinlatma" className="hover:text-gray-600 cursor-pointer">{t('landing.footer.privacyPolicy')}</Link>
            <span className="hover:text-gray-600 cursor-pointer">{t('landing.footer.termsOfService')}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

/* ═══════════════════════════════════════════
   MAIN LANDING PAGE
   ═══════════════════════════════════════════ */
export default function LandingPage() {
  return (
    <div className="min-h-screen overflow-x-hidden" style={{ background: '#fbfbfb', fontFamily: satoshiFont }}>
      <Navbar />
      <Hero />
      <ValueStatements />
      <HowItWorks />
      <BrandDNAFeatures />
      <StyleShowcase />
      <StatsSection />
      <PlatformSupport />
      <CostComparison />
      <PrivacySecurity />
      <FAQ />
      <FinalCTA />
      <Footer />
    </div>
  );
}
