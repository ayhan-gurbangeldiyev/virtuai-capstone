/**
 * Phase 28.H — Human collaborator identity mapping.
 *
 * Cansu workspace shu an 3 kisi: Berkay (owner), Ayhan, Didem.
 * Backend hype_feedback.user_id -> auth.users.email resolve ediyor;
 * frontend email'i bu tablodan isim + avatar + renge cevirir.
 *
 * Eklemek icin: workspace_collaborators tablosuna invite + bu dosyaya bir satir.
 */

export const COLLABORATORS = {
  "berkayaltunel123@gmail.com": {
    name: "Berkay",
    role: "owner",
    avatar: "👨‍💻",
    color: "indigo",
  },
  "ayhan.gurbangeldiyev.tm@gmail.com": {
    name: "Ayhan",
    role: "editor",
    avatar: "🧑‍💼",
    color: "sky",
  },
  "dozipekk@gmail.com": {
    name: "Didem",
    role: "editor",
    avatar: "👩‍🎨",
    color: "pink",
  },
};

const COLOR_CLASSES = {
  indigo: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border-indigo-500/30",
  sky:    "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/30",
  pink:   "bg-pink-500/10 text-pink-700 dark:text-pink-300 border-pink-500/30",
  slate:  "bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/30",
};

/**
 * Resolve a feedback event's user_email -> persona object.
 * Bilinmiyorsa email'in @-oncesi part'ini name olarak gosterir + slate renk.
 */
export function resolveCollaborator(email) {
  if (!email) return { name: "—", avatar: "·", color: "slate", classes: COLOR_CLASSES.slate };
  const found = COLLABORATORS[email.toLowerCase()];
  if (found) {
    return {
      ...found,
      classes: COLOR_CLASSES[found.color] || COLOR_CLASSES.slate,
    };
  }
  return {
    name: email.split("@")[0],
    role: "guest",
    avatar: "👤",
    color: "slate",
    classes: COLOR_CLASSES.slate,
  };
}

/**
 * "5 dk once" gibi human-readable timestamp.
 */
export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return "az önce";
  const min = Math.floor(diffSec / 60);
  if (min < 60) return `${min} dk önce`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} sa önce`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} g önce`;
  return new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

/**
 * Translate raw feedback action -> Turkish verb.
 */
export const ACTION_LABELS = {
  approved: "onayladı",
  rejected: "reddetti",
  edited: "düzenledi",
  expired: "süresi geçti",
};

/**
 * Reject category enum -> short Turkish label (matches RejectDialog).
 */
export const REJECT_CATEGORY_LABELS = {
  too_long: "Çok uzun",
  too_short: "Çok kısa",
  tone_off: "Ton uymadı",
  wrong_topic: "Yanlış konu",
  inaccurate: "Hatalı bilgi",
  already_posted: "Zaten paylaşıldı",
  low_quality: "Düşük kalite",
  off_brand: "Marka dışı",
  other: "Diğer",
};

/**
 * Image rejection reason enum (Phase 28).
 */
export const IMAGE_REJECTION_LABELS = {
  deformed_hand: "Bozuk el/parmak",
  fake_logo: "Sahte marka logosu",
  off_brand: "Cansu'ya benzemiyor",
  ai_obvious: "AI olduğu çok belli",
  inappropriate: "Uygunsuz içerik",
  low_quality: "Düşük kalite",
  other: "Diğer",
};
