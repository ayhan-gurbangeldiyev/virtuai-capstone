# AI Coach v2 — Mega Spec

> Tarih: 2026-02-23
> Hedef: En güçlü AI Coach, 4 sütun birleşik
> Durum: Berkay onayı bekleniyor

---

## Mimari Özet

Sayfa açıldığında kullanıcıyı **dinamik kart feed'i** karşılar. Sıkıcı tablo yok, uzun paragraf yok. Her kart actionable, dismiss edilebilir, "Yaz" butonuyla direkt XAIModule'e yönlendirir.

```
┌─────────────────────────────────────┐
│  🧠 AI Coach                        │
│  "Günaydın Berkay, bugün 3 fırsat"  │
├─────────────────────────────────────┤
│  🚨 FIRSAT KARTI (Trend Hijacking)  │
│  "OpenAI yeni model çıkardı..."     │
│  [Hemen Yaz →]  [Kapat ✕]          │
├─────────────────────────────────────┤
│  🔥 ROAST KARTI                     │
│  "Son 10 üretiminde hep aynı..."    │
│  [Bunu Dene →]                      │
├─────────────────────────────────────┤
│  🎯 GÜNLÜK HEDEF                    │
│  "Bugün hiç üretmedin. İşte taslak" │
│  [Yaz →]  [Geç]                     │
├─────────────────────────────────────┤
│  ♻️ REPURPOSE                        │
│  "3 hafta önceki favori tweetin..."  │
│  [Yeniden Yaz →]                    │
├─────────────────────────────────────┤
│  📅 HAFTALIK PLAN                    │
│  Pazartesi: Tech trend analizi...   │
│  [Yaz →]                            │
├─────────────────────────────────────┤
│  📈 GELİŞİM KARTI                   │
│  "Bu hafta %40 daha çok ürettin"    │
│  [Harika! ✨]                        │
├─────────────────────────────────────┤
│  ⏰ OPTİMAL SAAT                     │
│  Heatmap + "Şimdi iyi zaman!"      │
└─────────────────────────────────────┘
```

---

## Sütun 1: Roast & Toast (Veri Tabanlı)

X API olmadan, kullanıcının **üretim verileriyle** kişiselleştirilmiş analiz.

### Veri Kaynağı
```sql
-- Son 50 generation
SELECT persona, tone, length, content_type, platform,
       created_at, is_favorite, character_count, evolution_depth
FROM generations
WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
```

### Roast Örnekleri (Gerçek Veriden)
- "Son 15 üretiminde hep `otorite` persona kullandın. Tekdüze olmaya başlıyorsun. Bugün `saf` veya `mentalist` dene."
- "Bu hafta 8 tweet ürettin ama hiçbirini favorilere eklemedin. Kalite düşüyor olabilir."
- "Son 5 tweetin ortalama 280+ karakter. Twitter'da kısa içerik daha çok etkileşim alır. `micro` uzunluğu dene."
- "3 gündür hiç üretim yapmadın. Tutarlılık kaybediyorsun."

### Toast Örnekleri
- "Bu hafta 12 üretim yaptın, geçen haftaya göre %60 artış! 🔥"
- "Son 5 üretiminin 3'ünü favorilere ekledin. Kalite artıyor."
- "İlk kez `thread` formatı denedin. Çeşitlilik harika!"
- "3 farklı persona kullandın bu hafta. Çok yönlülük artıyor."

### Backend: `GET /coach/feed` → Roast/Toast Kartları
```python
def generate_roast_toast(generations):
    cards = []
    
    # Persona çeşitliliği analizi
    personas = [g['persona'] for g in generations[-15:]]
    unique = len(set(personas))
    if unique == 1:
        cards.append({
            "type": "roast",
            "title": f"Hep aynı karakter: {personas[0]}",
            "description": f"Son 15 üretiminde sadece '{personas[0]}' kullandın. Monotonlaşıyorsun.",
            "action": {"label": "Farklı Dene", "persona": random_other_persona, "tone": "raw"},
            "priority": 8
        })
    elif unique >= 4:
        cards.append({
            "type": "toast",
            "title": "Çok yönlü performans! 🎭",
            "description": f"Son 15 üretiminde {unique} farklı karakter kullandın. Harika çeşitlilik.",
            "priority": 3
        })
    
    # Favori oranı analizi
    recent = generations[-20:]
    fav_rate = sum(1 for g in recent if g.get('is_favorite')) / max(len(recent), 1)
    if fav_rate < 0.1:
        cards.append({
            "type": "roast",
            "title": "Favorilerin boş 😬",
            "description": "Son 20 üretiminin %10'undan azını beğendin. Prompt'larını geliştirmeyi dene.",
            "priority": 7
        })
    elif fav_rate > 0.4:
        cards.append({
            "type": "toast",
            "title": "Kalite patlaması! 💎",
            "description": f"Son 20 üretiminin %{int(fav_rate*100)}'ini favorilere ekledin. Üst düzey.",
            "priority": 4
        })
    
    # Uzunluk analizi
    avg_chars = sum(g.get('character_count', 0) for g in recent) / max(len(recent), 1)
    if avg_chars > 250:
        cards.append({
            "type": "roast",
            "title": "Tweet'lerin çok uzun",
            "description": f"Ortalama {int(avg_chars)} karakter. Twitter'da 100-200 arası daha çok etkileşim alır.",
            "action": {"label": "Kısa Dene", "length": "micro"},
            "priority": 6
        })
    
    # Üretim sıklığı
    # ... (gün bazlı analiz, streak hesaplama)
    
    return sorted(cards, key=lambda c: c['priority'], reverse=True)
```

---

## Sütun 2: Trend Hijacking (Proaktif Fırsat)

### Veri Kaynağı
```sql
-- En taze, en yüksek skorlu trendler
SELECT title, summary, score, source, keywords, key_angles, suggested_hooks
FROM trends
WHERE score >= 70 AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY score DESC LIMIT 3
```

### Kart Yapısı
```json
{
  "type": "opportunity",
  "title": "🚨 OpenAI GPT-5.1 duyuruldu",
  "description": "Senin kitlen bu konuyu tartışıyor. Geç kalmadan pozisyon al.",
  "trend_score": 92,
  "freshness": "2 saat önce",
  "action": {
    "label": "Hemen Yaz →",
    "platform": "twitter",
    "topic": "OpenAI GPT-5.1 duyuruldu: ...",
    "persona": "insider",
    "tone": "raw",
    "suggested_hook": "Herkes GPT-5.1'in özelliklerini konuşuyor ama asıl dikkat edilmesi gereken..."
  },
  "priority": 10
}
```

### Zero-Friction: "Hemen Yaz" tıklandığında
```
/dashboard/create?platform=twitter&topic={encoded_topic}&persona=insider&tone=raw&hook={encoded_hook}
```
XAIModule açılır → textarea'da topic + suggested hook hazır, persona + tone seçili.

---

## Sütun 3: Dinamik Kartlar (Gamified Feed)

### Kart Tipleri

#### 🎯 Günlük Hedef
```python
# Bugün üretim yapılmış mı?
today_count = count_generations_today(user_id)
if today_count == 0:
    card = {
        "type": "daily_goal",
        "title": "Bugün henüz bir şey üretmedin",
        "description": "Tutarlılık büyümenin anahtarı. İşte sana bir başlangıç noktası.",
        "action": {"label": "Yaz →", "topic": random_topic_from_niche},
        "priority": 7
    }
elif today_count >= 3:
    card = {
        "type": "daily_complete",
        "title": "Bugünkü hedefini aştın! 🎉",
        "description": f"Bugün {today_count} içerik ürettin. Harika tempo.",
        "dismissable": True,
        "priority": 2
    }
```

#### ♻️ Repurpose (Geri Dönüşüm)
```python
# 2+ hafta önceki favorilerden öner
old_favorites = get_old_favorites(user_id, min_age_days=14)
if old_favorites:
    fav = random.choice(old_favorites)
    card = {
        "type": "repurpose",
        "title": "Bu favorini hatırlıyor musun?",
        "description": f'"{fav.content[:80]}..." — Bunu farklı bir tonda yeniden yazalım mı?',
        "original_content": fav.content,
        "action": {
            "label": "Yeniden Yaz →",
            "topic": fav.content,
            "persona": different_persona,
            "tone": different_tone
        },
        "priority": 5
    }
```

#### 📈 Gelişim (Progress)
```python
# Haftalık karşılaştırma
this_week = count_generations_this_week(user_id)
last_week = count_generations_last_week(user_id)
change = ((this_week - last_week) / max(last_week, 1)) * 100

if change > 20:
    card = {
        "type": "progress",
        "title": f"Bu hafta %{int(change)} artış! 📈",
        "description": f"Geçen hafta {last_week}, bu hafta {this_week} üretim.",
        "priority": 3
    }
elif change < -30:
    card = {
        "type": "progress_down",
        "title": "Tempo düşüyor ⚠️",
        "description": f"Geçen hafta {last_week} üretim vardı, bu hafta henüz {this_week}.",
        "action": {"label": "Hemen Başla →"},
        "priority": 6
    }
```

#### 🏆 Streak
```python
# Kaç gün üst üste üretim yapılmış
streak = calculate_streak(user_id)
if streak >= 3:
    card = {
        "type": "streak",
        "title": f"🔥 {streak} gün üst üste!",
        "description": "Seriyi bozmamak için bugün de bir şeyler üret.",
        "priority": 4
    }
```

### Kart UI
- Framer Motion: swipe-to-dismiss (sola kaydır = kapat)
- Dismiss animasyonu: kart yukarı uçar + confetti/sparkle
- Renk kodlaması: 
  - 🚨 Fırsat: kırmızı/turuncu gradient border
  - 🔥 Roast: kırmızı/pembe
  - 🎉 Toast: yeşil/emerald
  - 🎯 Hedef: mavi/cyan
  - ♻️ Repurpose: mor/fuchsia
  - 📈 Gelişim: yeşil
  - 🏆 Streak: turuncu/amber

---

## Sütun 4: Inline Feedback (v2.3, Sonra)

Bu en karmaşık olanı. Şimdilik **Coach Feed'deki kartlar** aynı işi görür. XAIModule'de üretim yaparken coach önerileri göstermek v2.3'te yapılır.

Ama şimdi basit bir versiyon yapabiliriz: XAIModule'de prompt kısa ise (< 20 karakter) altında minik bir coach notu:
"💡 Daha detaylı prompt = daha iyi sonuç. Konu, ton ve hedef kitleyi belirt."

---

## DB Tabloları

### 1. `coach_weekly_plans` (Yeni)
```sql
CREATE TABLE coach_weekly_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    week_start DATE NOT NULL,
    niche TEXT DEFAULT 'tech',
    plan JSONB NOT NULL,
    weekly_goal TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, week_start)
);
ALTER TABLE coach_weekly_plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own plans" ON coach_weekly_plans FOR ALL USING (auth.uid() = user_id);
```

### 2. `coach_dismissed_cards` (Yeni)
```sql
CREATE TABLE coach_dismissed_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    card_key TEXT NOT NULL,
    dismissed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, card_key)
);
ALTER TABLE coach_dismissed_cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users see own dismissals" ON coach_dismissed_cards FOR ALL USING (auth.uid() = user_id);
```

Dismissed card key örnekleri: `roast_persona_2026-02-23`, `opportunity_trend_abc123`, `repurpose_fav_xyz`

---

## Backend API

### `GET /coach/feed`
Ana endpoint. Tüm kartları hesaplayıp priority sırasıyla döndürür.

```python
@router.get("/feed")
async def get_coach_feed(user=Depends(require_auth)):
    cards = []
    
    # 1. Trend Hijacking (en yüksek priority)
    cards += await get_opportunity_cards(user.id)
    
    # 2. Roast & Toast (üretim analizi)
    cards += await get_roast_toast_cards(user.id)
    
    # 3. Günlük hedef
    cards += await get_daily_goal_cards(user.id)
    
    # 4. Repurpose önerileri
    cards += await get_repurpose_cards(user.id)
    
    # 5. Streak & Progress
    cards += await get_progress_cards(user.id)
    
    # Dismissed kartları filtrele
    dismissed = await get_dismissed_keys(user.id)
    cards = [c for c in cards if c.get('key') not in dismissed]
    
    # Priority sırasıyla döndür
    cards.sort(key=lambda c: c.get('priority', 0), reverse=True)
    
    return {"cards": cards[:10]}  # Max 10 kart
```

### `POST /coach/dismiss`
```python
@router.post("/dismiss")
async def dismiss_card(card_key: str, user=Depends(require_auth)):
    # DB'ye kaydet, bir daha gösterme
```

### `GET /coach/weekly-plan` (Güncelleme)
```python
# Önce DB'ye bak, yoksa null döndür
```

### `POST /coach/weekly-plan` (Yeni)
```python
# GPT ile üret, DB'ye kaydet
```

---

## Frontend: CoachPage.jsx (Tamamen Yeniden)

### Yapı
```jsx
export default function CoachPage() {
  const [cards, setCards] = useState([]);
  const [weeklyPlan, setWeeklyPlan] = useState(null);
  
  useEffect(() => {
    // Paralel fetch
    Promise.all([
      api.get('/coach/feed'),
      api.get('/coach/weekly-plan'),
      api.get('/posting-times/heatmap'),
    ]).then(([feedRes, planRes, heatmapRes]) => {
      setCards(feedRes.data.cards);
      setWeeklyPlan(planRes.data);
      // ...
    });
  }, []);
  
  return (
    <div>
      {/* Header: "Günaydın Berkay, bugün X fırsat var" */}
      <CoachHeader cardCount={cards.length} />
      
      {/* Dinamik Kart Feed */}
      <AnimatePresence>
        {cards.map(card => (
          <CoachCard key={card.key} card={card} onDismiss={handleDismiss} onAction={handleAction} />
        ))}
      </AnimatePresence>
      
      {/* Haftalık Plan */}
      <WeeklyPlanSection plan={weeklyPlan} onGenerate={generatePlan} />
      
      {/* Optimal Saatler (mevcut, kalıyor) */}
      <PostingHeatmapSection />
    </div>
  );
}
```

### CoachCard Component
```jsx
function CoachCard({ card, onDismiss, onAction }) {
  const cardStyles = {
    opportunity: "border-red-500/30 bg-gradient-to-r from-red-500/10 to-orange-500/10",
    roast: "border-pink-500/30 bg-gradient-to-r from-pink-500/10 to-red-500/10",
    toast: "border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 to-green-500/10",
    daily_goal: "border-blue-500/30 bg-gradient-to-r from-blue-500/10 to-cyan-500/10",
    repurpose: "border-purple-500/30 bg-gradient-to-r from-purple-500/10 to-fuchsia-500/10",
    progress: "border-emerald-500/30 bg-emerald-500/5",
    streak: "border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-orange-500/10",
  };
  
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -300, transition: { duration: 0.3 } }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={(_, info) => {
        if (info.offset.x < -100) onDismiss(card.key);
      }}
      className={cn("rounded-xl border p-4 mb-3 cursor-grab", cardStyles[card.type])}
    >
      {/* Kart içeriği */}
    </motion.div>
  );
}
```

---

## XAIModule URL Param Desteği (Güncelleme)

Mevcut: `topic`, `trend_context` destekleniyor.
Eklenecek: `persona`, `tone`, `hook`

```jsx
// XAIModule.jsx useEffect içinde
const urlPersona = searchParams.get('persona');
const urlTone = searchParams.get('tone');
const urlHook = searchParams.get('hook');

if (urlPersona) setSettings(s => ({...s, persona: urlPersona}));
if (urlTone) setSettings(s => ({...s, tone: urlTone}));
if (urlHook && !topic) setTopic(urlHook);
```

---

## Implementation Sırası

| Adım | İş | Dosya | Effort |
|------|-----|-------|--------|
| 1 | DB tabloları oluştur | Supabase SQL | 10 dk |
| 2 | Backend: `/coach/feed` (roast/toast + daily goal + progress + streak) | routes/coach.py | 1.5 saat |
| 3 | Backend: Trend hijacking kartları (trends tablodan) | routes/coach.py | 30 dk |
| 4 | Backend: Repurpose kartları (eski favoriler) | routes/coach.py | 20 dk |
| 5 | Backend: Persistent weekly plan (GET DB + POST GPT) | routes/coach.py | 30 dk |
| 6 | Backend: Dismiss endpoint | routes/coach.py | 10 dk |
| 7 | Frontend: CoachCard component (swipeable, renk kodlu) | components/CoachCard.jsx | 1 saat |
| 8 | Frontend: CoachPage yeniden yazım (feed + plan + heatmap) | pages/CoachPage.jsx | 1.5 saat |
| 9 | Frontend: XAIModule persona/tone/hook URL param | pages/XAIModule.jsx | 15 dk |
| 10 | i18n | locales/tr.json, en.json | 20 dk |
| 11 | Test + deploy | | 30 dk |

**Toplam: ~6-7 saat**

## Rollback Planı
- Backend: Eski coach.py'yi geri koy
- Frontend: Eski CoachPage.jsx'i geri koy
- DB: Tabloları drop et (veri kaybı minimal, yeni tablolar)
