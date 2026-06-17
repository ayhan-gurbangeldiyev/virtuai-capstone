/**
 * Phase 27 — DB enum → human-readable Turkish/English helpers.
 *
 * Goal: a non-technical user opening the Executive Board should never
 * see raw status enums, technical decision_types, or JSON-stringified
 * diffs. These helpers map them to plain language.
 */

// ─── status (executive_decisions.status) ───────────────────────────────────

export const STATUS_TR = {
  awaiting_approval: { label: "Senin onayını bekliyor", color: "amber", icon: "⏳" },
  approved_pending_resume: { label: "Onaylandı, uygulanıyor…", color: "blue", icon: "⚡" },
  rejected_pending_resume: { label: "Reddedildi, sonuçlanıyor…", color: "rose", icon: "⚡" },
  auto_executed: { label: "Otomatik yapıldı", color: "emerald", icon: "✓" },
  executed: { label: "Senin onayınla yapıldı", color: "emerald", icon: "✓" },
  rejected: { label: "Reddedildi", color: "rose", icon: "✕" },
  reverted: { label: "Geri alındı", color: "muted", icon: "↶" },
  expired: { label: "Süresi geçti", color: "muted", icon: "⌛" },
  failed: { label: "Hata oldu", color: "rose", icon: "⚠" },
};

export function humanizeStatus(status) {
  return STATUS_TR[status] || { label: status || "—", color: "muted", icon: "·" };
}

// ─── decision_type (executive_decisions.decision_type) ─────────────────────

export const DECISION_TYPE_TR = {
  noop: "Yorum yok, gözlem paylaştı",
  observation: "Gözlem",
  strategy_observation: "Strateji notu paylaştı",
  weekly_review_directive: "Haftalık strateji direktifi",

  cost_cap_adjust: "Günlük harcama limitini değiştir",
  cost_alert: "Maliyet uyarısı",
  model_downgrade_recommend: "Daha ekonomik modele geç",

  model_swap: "AI modelini değiştir",
  pipeline_freeze: "Otomatik üretimi durdur",
  pipeline_unfreeze: "Otomatik üretimi tekrar başlat",
  retry_policy_change: "Hata sonrası tekrar deneme politikası",
  cadence_adjust: "Yayın sıklığını değiştir",
  executive_freeze_toggle: "Sistem kilidini aç/kapa",

  content_type_weight_adjust: "İçerik türü ağırlığı ayarla",
  visual_mode_distribution_adjust: "Görsel mod karışımını değiştir",
  scene_rotation_update: "Sahne rotasyonunu güncelle",
  voice_drift_alert: "Marka tonu sapma uyarısı",

  forbidden_topic_add: "Yasaklı konu listesine ekle",
  forbidden_topic_remove: "Yasaklı konu listesinden çıkar",
  post_takedown: "Bu içeriği kaldır",
  compliance_halt: "Acil durdur (uyumsuzluk)",
  cro_auto_freeze_toggle: "Otomatik güvenlik kilidini aç/kapa",

  persona_create: "Yeni persona aç",
  persona_retire: "Persona'yı emekli et",
};

export function humanizeDecisionType(decisionType) {
  return DECISION_TYPE_TR[decisionType] || (decisionType ? decisionType.replace(/_/g, " ") : "—");
}

// ─── meeting_kind (executive_meetings.kind) ────────────────────────────────

export const MEETING_KIND_TR = {
  hourly_heartbeat: { label: "Saatlik kontrol", emoji: "⏰" },
  daily_standup: { label: "Günlük toplantı", emoji: "☀️" },
  weekly_review: { label: "Haftalık strateji", emoji: "📊" },
  event_triggered: { label: "Olay tetiklemesi", emoji: "⚡" },
};

export function humanizeMeetingKind(kind) {
  return MEETING_KIND_TR[kind] || { label: kind || "Toplantı", emoji: "📅" };
}

// ─── memo_kind (executive_memos.kind) ──────────────────────────────────────

export const MEMO_KIND_TR = {
  strategy: { label: "Strateji", color: "purple", icon: "🎯" },
  observation: { label: "Gözlem", color: "blue", icon: "📝" },
  dissent: { label: "Karşı görüş", color: "amber", icon: "⚠️" },
  alert: { label: "Uyarı", color: "rose", icon: "🚨" },
};

export function humanizeMemoKind(kind) {
  return MEMO_KIND_TR[kind] || { label: kind || "Not", color: "muted", icon: "💬" };
}

// ─── config field label translator ─────────────────────────────────────────
// Friendly names for hype_account_config / personas / etc. keys

export const FIELD_LABEL_TR = {
  daily_cost_cap_usd: "Günlük harcama limiti",
  daily_post_quota: "Günlük yayın sayısı",
  dry_run_mode: "Test modu",
  auto_publish_enabled: "Otomatik yayın",
  executive_freeze: "Sistem kilidi",
  cro_auto_freeze_on_violation: "Otomatik güvenlik kilidi",
  active_style_profile_id: "Aktif marka tonu profili",
  voice_description: "Marka tonu açıklaması",
  topics_focus: "Odak konular",
  forbidden_topics: "Yasaklı konular",
  watch_accounts: "Takip edilen hesaplar",
  reactive_enabled: "Tepkisel içerik",
  posting_cadence: "Yayın sıklığı",
  follower_goal: "Takipçi hedefi",
  identity_card: "Persona kimlik kartı",

  // Hype Crew config-like
  HYPE_MODEL_FAST: "Hızlı AI modeli",
  HYPE_MODEL_SMART: "Akıllı AI modeli",
  hype_model_fast: "Hızlı AI modeli",
  hype_model_smart: "Akıllı AI modeli",
  model: "AI modeli",

  // Persona-level
  visual_enabled: "Görsel üretimi",
  video_enabled: "Video üretimi",
  is_active: "Aktif durumu",

  // Generic
  status: "Durum",
};

export function humanizeFieldName(key) {
  if (!key) return "—";
  return FIELD_LABEL_TR[key] || key.replace(/_/g, " ");
}

// ─── value formatter for diff display ──────────────────────────────────────

export function formatFieldValue(value) {
  if (value === null || value === undefined) return "—";
  if (value === true) return "Açık";
  if (value === false) return "Kapalı";
  if (Array.isArray(value)) {
    if (value.length === 0) return "(boş)";
    return value.slice(0, 5).map(String).join(", ") + (value.length > 5 ? ", …" : "");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value).slice(0, 80);
    } catch {
      return "—";
    }
  }
  if (typeof value === "number") {
    // Dollar amounts on cost fields
    return String(value);
  }
  return String(value);
}

/**
 * humanizeChange — turn (old_value, new_value) into an array of plain-language
 * change items. Filters keys whose values are equal. Used by DecisionCard
 * "Değişecek olan" block.
 *
 * Returns: [{key, label, oldDisplay, newDisplay}]
 */
export function humanizeChange(oldValue, newValue) {
  const oldObj = oldValue && typeof oldValue === "object" ? oldValue : {};
  const newObj = newValue && typeof newValue === "object" ? newValue : {};
  const keys = Array.from(new Set([...Object.keys(oldObj), ...Object.keys(newObj)]));
  const changes = [];
  for (const k of keys) {
    const o = oldObj[k];
    const n = newObj[k];
    if (JSON.stringify(o) === JSON.stringify(n)) continue;
    changes.push({
      key: k,
      label: humanizeFieldName(k),
      oldDisplay: formatFieldValue(o),
      newDisplay: formatFieldValue(n),
    });
  }
  return changes;
}

// ─── threshold_breach reason renderer ──────────────────────────────────────

export function humanizeBreachReason(breach) {
  if (!breach || typeof breach !== "object") return null;
  // Common shapes the daemon emits:
  // { field: "...", current: N, threshold: N }
  // { field: "action_type", current: "model_swap", threshold: "always_review" }
  // { action: "model_swap", impact: "free-text impact line" }
  if (breach.impact) return breach.impact;
  if (breach.field === "action_type") {
    return "Bu aksiyon kategorisi her zaman insan onayı gerektirir.";
  }
  if (breach.field === "daily_cost_cap_usd") {
    return `Önerilen limit ${breach.current} — güvenlik için $${breach.threshold} üstü onayını gerektiriyor.`;
  }
  if (breach.field === "daily_cost_cap_usd_delta") {
    return `Limit değişimi mevcut bütçenin %${Math.round((breach.current || 0) * 100)}'i kadar — büyük sapmalar için onayın gerek.`;
  }
  if (breach.field && (breach.current !== undefined || breach.threshold !== undefined)) {
    return `${humanizeFieldName(breach.field)}: mevcut ${formatFieldValue(breach.current)} → sınır ${formatFieldValue(breach.threshold)}`;
  }
  // Fallback
  try {
    return Object.entries(breach)
      .map(([k, v]) => `${humanizeFieldName(k)}: ${formatFieldValue(v)}`)
      .join(" · ");
  } catch {
    return null;
  }
}

// ─── relative time helper ──────────────────────────────────────────────────

export function relativeTime(iso) {
  if (!iso) return "";
  const now = Date.now();
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return "az önce";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} dk önce`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} saat önce`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} gün önce`;
  return new Date(iso).toLocaleDateString("tr-TR");
}

export function timeUntilNextHour() {
  const now = new Date();
  const next = new Date(now);
  next.setUTCHours(next.getUTCHours() + 1, 0, 0, 0);
  const diff = Math.max(0, next.getTime() - now.getTime());
  const minutes = Math.round(diff / 60000);
  if (minutes <= 1) return "1 dk";
  if (minutes < 60) return `${minutes} dk`;
  return "1 saatten az";
}
