import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Shield,
  Database,
  Eye,
  Clock,
  Users,
  Scale,
  Cookie,
  Mail,
  ChevronUp,
  ArrowLeft,
} from "lucide-react";

const satoshiFont = "'Satoshi', 'Inter', system-ui, sans-serif";
const clashFont = "'Clash Display', 'Satoshi', system-ui, sans-serif";

const fadeIn = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" },
  },
};

const stagger = {
  visible: { transition: { staggerChildren: 0.06 } },
};

const SECTIONS = [
  { id: "data-controller", icon: Shield, key: "dataController" },
  { id: "personal-data", icon: Database, key: "personalData" },
  { id: "purposes", icon: Eye, key: "purposes" },
  { id: "retention", icon: Clock, key: "retention" },
  { id: "third-parties", icon: Users, key: "thirdParties" },
  { id: "user-rights", icon: Scale, key: "userRights" },
  { id: "cookie-policy", icon: Cookie, key: "cookiePolicy" },
  { id: "contact", icon: Mail, key: "contact" },
];

function TableOfContents({ activeSection, t }) {
  return (
    <nav className="hidden lg:block sticky top-8 self-start">
      <p
        className="text-[13px] font-semibold text-muted-foreground uppercase tracking-wider mb-3"
        style={{ fontFamily: satoshiFont }}
      >
        {t("aydinlatma.toc")}
      </p>
      <div className="space-y-1">
        {SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className={`block text-[13px] py-1.5 px-3 rounded-lg transition-colors ${
              activeSection === s.id
                ? "text-violet-400 bg-violet-500/10 font-medium"
                : "text-muted-foreground hover:text-foreground/70"
            }`}
            style={{ fontFamily: satoshiFont }}
          >
            {t(`aydinlatma.${s.key}.title`)}
          </a>
        ))}
      </div>
    </nav>
  );
}

function SectionCard({ id, icon: Icon, sectionKey, t }) {
  const body = t(`aydinlatma.${sectionKey}.body`, { returnObjects: true });
  const items = t(`aydinlatma.${sectionKey}.items`, {
    returnObjects: true,
    defaultValue: [],
  });
  const notice = t(`aydinlatma.${sectionKey}.notice`, { defaultValue: "" });

  return (
    <motion.section id={id} variants={fadeIn} className="scroll-mt-8">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500/10 to-fuchsia-500/10 flex items-center justify-center">
          <Icon className="w-[18px] h-[18px] text-violet-400" />
        </div>
        <h2
          className="text-[20px] md:text-[22px] font-bold text-foreground"
          style={{ fontFamily: clashFont }}
        >
          {t(`aydinlatma.${sectionKey}.title`)}
        </h2>
      </div>
      <div
        className="text-[14px] md:text-[15px] text-muted-foreground leading-[1.8] space-y-3"
        style={{ fontFamily: satoshiFont, fontWeight: 500 }}
      >
        {Array.isArray(body) &&
          body.map((p, i) => <p key={i}>{p}</p>)}
        {Array.isArray(items) && items.length > 0 && (
          <ul className="list-disc list-inside space-y-1.5 ml-1">
            {items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        )}
        {notice && <p className="mt-2 text-[13px] text-muted-foreground/70 italic">{notice}</p>}
      </div>
    </motion.section>
  );
}

function ScrollToTopButton() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = () => setVisible(window.scrollY > 400);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  if (!visible) return null;

  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className="fixed bottom-6 right-6 w-10 h-10 rounded-full bg-violet-500 text-white shadow-lg flex items-center justify-center hover:bg-violet-600 transition-colors z-50"
    >
      <ChevronUp className="w-5 h-5" />
    </button>
  );
}

export default function AydinlatmaPage() {
  const { t } = useTranslation();
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id);

  useEffect(() => {
    document.title = t("aydinlatma.pageTitle") + " | TypeHype";
  }, [t]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 }
    );

    SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <main
      className="max-w-4xl mx-auto px-4 py-12"
      style={{ fontFamily: satoshiFont }}
    >
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground hover:text-violet-400 transition-colors mb-8"
        style={{ fontFamily: satoshiFont, fontWeight: 500 }}
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        {t("aydinlatma.backToHome")}
      </Link>

      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h1
          variants={fadeIn}
          className="text-[32px] md:text-[40px] font-bold text-foreground leading-[1.1] tracking-[-0.02em]"
          style={{ fontFamily: clashFont }}
        >
          {t("aydinlatma.pageTitle")}
        </motion.h1>
        <motion.p
          variants={fadeIn}
          className="mt-3 text-[14px] text-muted-foreground"
          style={{ fontFamily: satoshiFont, fontWeight: 500 }}
        >
          {t("aydinlatma.lastUpdated")}
        </motion.p>
      </motion.div>

      <div className="mt-10 grid lg:grid-cols-[200px_1fr] gap-10">
        <TableOfContents activeSection={activeSection} t={t} />

        <motion.div
          initial="hidden"
          animate="visible"
          variants={stagger}
          className="space-y-10"
        >
          {SECTIONS.map((section) => (
            <SectionCard
              key={section.id}
              id={section.id}
              icon={section.icon}
              sectionKey={section.key}
              t={t}
            />
          ))}
        </motion.div>
      </div>

      <ScrollToTopButton />
    </main>
  );
}
