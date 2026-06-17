# AI Coach v2 — Detaylı Implementation Checklist

> Tarih: 2026-02-23
> Durum: Berkay onayı bekleniyor
> Tahmini süre: ~6-7 saat
> Referans spec: AI-COACH-V2-MEGA-SPEC.md

---

## FAZ 1: Veritabanı (10 dk)

### 1.1 `coach_weekly_plans` tablosu
- [ ] Supabase SQL editörde tablo oluştur:
  ```
  id, user_id, week_start (DATE), niche, plan (JSONB), weekly_goal (TEXT), 
  created_at, updated_at, UNIQUE(user_id, week_start)
  ```
- [ ] RLS policy ekle: `auth.uid() = user_id`
- [ ] Service role erişimi için anon policy (backend service key kullanıyor)

### 1.2 `coach_dismissed_cards` tablosu
- [ ] Supabase SQL editörde tablo oluştur:
  ```
  id, user_id, card_key (TEXT), dismissed_at, UNIQUE(user_id, card_key)
  ```
- [ ] RLS policy ekle
- [ ] card_key formatı: `{type}_{identifier}_{date}` (örn: `roast_persona_2026-02-23`)

### 1.3 Doğrulama
- [ ] Her iki tablo Supabase dashboard'da görünüyor mu?
- [ ] Service key ile CRUD test (curl)

---

## FAZ 2: Backend — Feed Engine (2.5 saat)

### 2.1 Dosya yapısı oluştur
- [ ] `backend/services/coach_engine.py` → Tüm kart üretim mantığı
- [ ] `backend/routes/coach.py` → Mevcut dosyayı güncelle (endpoint'ler)

### 2.2 Coach Engine: Roast & Toast kartları
- [ ] `get_roast_toast_cards(user_id, supabase)` fonksiyonu yaz
- [ ] Generations tablosundan son 50 üretimi çek:
  ```python
  supabase.table("generations")
    .select("persona, tone, length, content_type, platform, created_at, character_count, evolution_depth")
    .eq("user_id", user_id)
    .order("created_at", desc=True)
    .limit(50)
  ```
- [ ] Favorites tablosundan favori sayısı/oranı çek:
  ```python
  supabase.table("favorites")
    .select("id, generation_id, created_at")
    .eq("user_id", user_id)
    .is_("deleted_at", "null")
  ```
- [ ] **Persona çeşitliliği analizi:**
  - Son 15 üretimde kaç farklı persona kullanılmış?
  - 1 tane → Roast: "Hep aynı karakter: {persona}. Monotonlaşıyorsun."
  - 4+ tane → Toast: "Çok yönlü performans! {count} farklı karakter."
  - Action: farklı persona önerisi
- [ ] **Tone çeşitliliği analizi:**
  - Son 15 üretimde kaç farklı tone?
  - Aynı mantık, roast/toast
- [ ] **Favori oranı analizi:**
  - Son 20 üretimin kaçı favorilerde?
  - < %10 → Roast: "Son 20 üretiminin %X'ini beğendin. Kalite düşüyor."
  - > %40 → Toast: "Kalite patlaması! %X favori oranı."
- [ ] **Uzunluk analizi:**
  - Ortalama karakter sayısı
  - > 250 → Roast: "Tweet'lerin çok uzun. Ortalama {avg} karakter."
  - Action: length=micro önerisi
- [ ] **Format çeşitliliği:**
  - content_type dağılımı (tweet/thread/quote/reply)
  - Hep aynı → Roast: "Hep {type} üretiyorsun. Thread veya quote dene."
- [ ] **Üretim sıklığı analizi:**
  - Son 7 günde kaç gün üretim yapılmış?
  - 7/7 → Toast: "Her gün ürettin! Muhteşem disiplin."
  - < 3/7 → Roast: "Bu hafta sadece {count} gün üretim yaptın."
- [ ] **Evolution kullanımı:**
  - evolution_depth > 0 olanlar var mı?
  - Hiç yok → Roast: "Geliştir özelliğini hiç kullanmadın. İlk üretimi rafine etmek kaliteyi artırır."
- [ ] Her kart için `key` oluştur: `roast_persona_2026-02-23`
- [ ] Her kart için `priority` (1-10) ata

### 2.3 Coach Engine: Trend Hijacking kartları
- [ ] `get_opportunity_cards(user_id, supabase)` fonksiyonu yaz
- [ ] Trends tablosundan son 24 saatin en yüksek skorlu 3 trendini çek:
  ```python
  supabase.table("trends")
    .select("id, title, summary, score, source, keywords, key_angles, suggested_hooks")
    .gte("created_at", twenty_four_hours_ago)
    .gte("score", 70)
    .order("score", desc=True)
    .limit(3)
  ```
- [ ] Her trend için kart oluştur:
  - type: "opportunity"
  - title: "🚨 {trend.title}"
  - description: trend.summary (ilk 150 karakter)
  - trend_score badge
  - freshness: "X saat önce"
  - action: platform=twitter, topic={title + summary}, persona=insider, tone=raw
  - suggested_hook: key_angles[0] veya suggested_hooks[0]
- [ ] Priority: 10 (en yüksek, her zaman üstte)
- [ ] Key: `opportunity_{trend_id}`

### 2.4 Coach Engine: Günlük Hedef kartları
- [ ] `get_daily_goal_cards(user_id, supabase)` fonksiyonu yaz
- [ ] Bugün kaç üretim yapılmış kontrol et:
  ```python
  supabase.table("generations")
    .select("id", count="exact")
    .eq("user_id", user_id)
    .gte("created_at", today_start_utc)
  ```
- [ ] 0 üretim → Kart: "Bugün henüz bir şey üretmedin. Tutarlılık büyümenin anahtarı."
  - Action: rastgele trend topic veya niche topic öner
  - Priority: 7
- [ ] 3+ üretim → Kart: "Bugünkü hedefini aştın! 🎉 {count} üretim."
  - Dismissable, priority: 2
- [ ] Key: `daily_goal_2026-02-23`

### 2.5 Coach Engine: Repurpose kartları
- [ ] `get_repurpose_cards(user_id, supabase)` fonksiyonu yaz
- [ ] 14+ gün önceki favorileri çek:
  ```python
  supabase.table("favorites")
    .select("id, content, created_at")
    .eq("user_id", user_id)
    .is_("deleted_at", "null")
    .lte("created_at", fourteen_days_ago)
    .order("created_at", desc=True)
    .limit(10)
  ```
- [ ] Rastgele 1-2 tane seç
- [ ] Her biri için kart:
  - type: "repurpose"
  - title: "Bu favorini hatırlıyor musun?"
  - description: content[:100] + "..."
  - original_content: tam metin
  - action: topic=content, persona=farklı persona, tone=farklı tone
  - Priority: 5
- [ ] Key: `repurpose_{favorite_id}`

### 2.6 Coach Engine: Progress & Streak kartları
- [ ] `get_progress_cards(user_id, supabase)` fonksiyonu yaz
- [ ] **Haftalık karşılaştırma:**
  - Bu hafta vs geçen hafta üretim sayısı
  - > %20 artış → Toast: "Bu hafta %X artış! 📈"
  - > %30 düşüş → Uyarı: "Tempo düşüyor ⚠️"
  - Priority: 3-6 (duruma göre)
- [ ] **Streak hesaplama:**
  - Kaç gün üst üste en az 1 üretim yapılmış?
  - Bugünden geriye doğru say
  - 3+ gün → Kart: "🔥 {streak} gün üst üste!"
  - Priority: 4
- [ ] Key: `progress_week_2026-W08`, `streak_2026-02-23`

### 2.7 Ana Feed Endpoint
- [ ] `GET /coach/feed` endpoint'ini yaz:
  ```python
  @router.get("/feed")
  async def get_coach_feed(user=Depends(require_auth)):
      sb = get_supabase()
      cards = []
      cards += await get_opportunity_cards(user.id, sb)
      cards += await get_roast_toast_cards(user.id, sb)
      cards += await get_daily_goal_cards(user.id, sb)
      cards += await get_repurpose_cards(user.id, sb)
      cards += await get_progress_cards(user.id, sb)
      
      # Dismissed kartları filtrele
      dismissed = sb.table("coach_dismissed_cards")
        .select("card_key")
        .eq("user_id", user.id)
        .execute()
      dismissed_keys = {d["card_key"] for d in (dismissed.data or [])}
      cards = [c for c in cards if c.get("key") not in dismissed_keys]
      
      # Priority sırasıyla, max 10
      cards.sort(key=lambda c: c.get("priority", 0), reverse=True)
      return {"cards": cards[:10]}
  ```

### 2.8 Dismiss Endpoint
- [ ] `POST /coach/dismiss` endpoint'ini yaz:
  ```python
  @router.post("/dismiss")
  async def dismiss_card(body: DismissRequest, user=Depends(require_auth)):
      sb.table("coach_dismissed_cards").upsert({
          "user_id": user.id,
          "card_key": body.card_key,
          "dismissed_at": now
      }).execute()
      return {"success": True}
  ```
- [ ] Pydantic model: `class DismissRequest(BaseModel): card_key: str`

### 2.9 Persistent Weekly Plan
- [ ] `GET /coach/weekly-plan` güncelle:
  - Bu haftanın Pazartesi tarihini hesapla
  - DB'den plan çek: `coach_weekly_plans WHERE user_id = ? AND week_start = ?`
  - Varsa döndür: `{"plan": ..., "weekly_goal": ..., "cached": true, "created_at": "..."}`
  - Yoksa döndür: `{"plan": null, "has_plan": false}`
- [ ] `POST /coach/weekly-plan` yeni endpoint:
  - GPT ile 7 günlük plan üret (mevcut mantık)
  - DB'ye kaydet (upsert: aynı hafta varsa güncelle)
  - Döndür: `{"plan": ..., "weekly_goal": ..., "cached": false}`
- [ ] GPT prompt'a kullanıcının üretim geçmişini ekle (en çok kullandığı persona/tone, favori oranı)

### 2.10 Backend Test
- [ ] `/coach/feed` curl test — kartlar dönüyor mu?
- [ ] `/coach/weekly-plan` GET — plan yokken null dönüyor mu?
- [ ] `/coach/weekly-plan` POST — plan üretip DB'ye kaydediyor mu?
- [ ] `/coach/weekly-plan` GET tekrar — cache'den dönüyor mu?
- [ ] `/coach/dismiss` POST — kart dismiss ediliyor mu?
- [ ] `/coach/feed` tekrar — dismiss edilen kart filtreleniyor mu?

---

## FAZ 3: Frontend — CoachCard Component (1 saat)

### 3.1 CoachCard.jsx oluştur
- [ ] `frontend/src/components/coach/CoachCard.jsx` dosyası oluştur
- [ ] Framer Motion import: `motion, AnimatePresence, useMotionValue, useTransform`
- [ ] Kart tiplerine göre renk şeması:
  ```
  opportunity → border-red-500/30, bg-gradient from-red-500/10 to-orange-500/10
  roast      → border-pink-500/30, bg-gradient from-pink-500/10 to-red-500/10
  toast      → border-emerald-500/30, bg-gradient from-emerald-500/10 to-green-500/10
  daily_goal → border-blue-500/30, bg-gradient from-blue-500/10 to-cyan-500/10
  daily_complete → border-emerald-500/30, bg-emerald-500/5
  repurpose  → border-purple-500/30, bg-gradient from-purple-500/10 to-fuchsia-500/10
  progress   → border-emerald-500/30, bg-emerald-500/5
  progress_down → border-yellow-500/30, bg-yellow-500/5
  streak     → border-amber-500/30, bg-gradient from-amber-500/10 to-orange-500/10
  ```
- [ ] Kart tiplerine göre ikon:
  ```
  opportunity → AlertTriangle (kırmızı)
  roast → Flame (pembe)
  toast → PartyPopper (yeşil)
  daily_goal → Target (mavi)
  daily_complete → CheckCircle (yeşil)
  repurpose → RefreshCw (mor)
  progress → TrendingUp (yeşil)
  progress_down → TrendingDown (sarı)
  streak → Flame (turuncu)
  ```
- [ ] Kart yapısı:
  ```jsx
  <motion.div drag="x" ...>
    <div className="flex items-start gap-3">
      <Icon />
      <div className="flex-1">
        <h4>{card.title}</h4>
        <p>{card.description}</p>
        {card.original_content && <blockquote>"{card.original_content.slice(0,100)}..."</blockquote>}
      </div>
      <button onClick={onDismiss}>✕</button>
    </div>
    {card.action && (
      <div className="mt-3 flex gap-2">
        <Button onClick={() => onAction(card.action)}>{card.action.label}</Button>
      </div>
    )}
    {card.trend_score && <Badge>{card.trend_score} skor</Badge>}
    {card.freshness && <span className="text-xs">{card.freshness}</span>}
  </motion.div>
  ```
- [ ] Swipe-to-dismiss:
  - `drag="x"`, `dragConstraints={{ left: -200, right: 0 }}`
  - `onDragEnd`: offset.x < -100 ise dismiss
  - Exit animasyonu: `x: -300, opacity: 0`
- [ ] Dismiss animasyonu: layout animasyonu ile alt kartlar yukarı kayar

### 3.2 CoachHeader.jsx oluştur
- [ ] `frontend/src/components/coach/CoachHeader.jsx`
- [ ] Saate göre selamlama: "Günaydın" / "İyi günler" / "İyi akşamlar"
- [ ] Kart sayısı badge: "Bugün {count} önerim var"
- [ ] Brain ikonu + gradient background

### 3.3 WeeklyPlanSection.jsx oluştur
- [ ] `frontend/src/components/coach/WeeklyPlanSection.jsx`
- [ ] Plan varsa: 7 günlük kart listesi
  - Her gün: gün adı, saat, konu, persona badge, tone badge, "Yaz →" butonu
  - Bugünün kartı highlight (border-purple)
- [ ] Plan yoksa: Empty state + "✨ Bu Haftanın Planını Oluştur" butonu
  - Butona basınca: loading skeleton → POST /coach/weekly-plan → göster
- [ ] Cache badge: "Bu plan {X} gün önce oluşturuldu" + "Yeniden Oluştur" butonu
- [ ] "Yaz →" butonu doğru URL: `/dashboard/create?platform=twitter&topic={encoded}&persona={p}&tone={t}`

---

## FAZ 4: Frontend — CoachPage Yeniden Yazım (1.5 saat)

### 4.1 CoachPage.jsx tamamen yeniden yaz
- [ ] Mevcut CoachPage.jsx'i yedekle: `CoachPage.old.jsx`
- [ ] Yeni yapı:
  ```jsx
  export default function CoachPage() {
    const [cards, setCards] = useState([]);
    const [weeklyPlan, setWeeklyPlan] = useState(null);
    const [planCached, setPlanCached] = useState(false);
    const [planCreatedAt, setPlanCreatedAt] = useState(null);
    const [postingData, setPostingData] = useState(null);
    const [bestNow, setBestNow] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    
    useEffect(() => {
      Promise.all([
        api.get(`${API}/coach/feed`),
        api.get(`${API}/coach/weekly-plan`),
        api.get(`${API}/posting-times/heatmap`),
        api.get(`${API}/posting-times/best-now`),
      ]).then(([feedRes, planRes, heatmapRes, bestNowRes]) => {
        setCards(feedRes.data.cards || []);
        if (planRes.data.plan) {
          setWeeklyPlan(planRes.data);
          setPlanCached(planRes.data.cached || false);
          setPlanCreatedAt(planRes.data.created_at);
        }
        setPostingData(heatmapRes.data);
        setBestNow(bestNowRes.data);
        setLoading(false);
      }).catch(() => setLoading(false));
    }, []);
    
    const handleDismiss = async (cardKey) => {
      setCards(prev => prev.filter(c => c.key !== cardKey));
      await api.post(`${API}/coach/dismiss`, { card_key: cardKey });
    };
    
    const handleAction = (action) => {
      const params = new URLSearchParams();
      params.set("platform", action.platform || "twitter");
      if (action.topic) params.set("topic", action.topic);
      if (action.persona) params.set("persona", action.persona);
      if (action.tone) params.set("tone", action.tone);
      if (action.hook) params.set("hook", action.hook);
      if (action.length) params.set("length", action.length);
      navigate(`/dashboard/create?${params.toString()}`);
    };
    
    // render...
  }
  ```

### 4.2 Sayfa yapısı (yukarıdan aşağıya)
- [ ] **Loading state**: Skeleton kartlar (3 adet placeholder)
- [ ] **CoachHeader**: Selamlama + kart sayısı
- [ ] **Kart Feed**: `<AnimatePresence>` içinde CoachCard'lar
  - Layout animasyonu: bir kart dismiss edilince diğerleri yukarı kayar
  - Boş state: tüm kartlar dismiss edilmişse "Bugünlük bu kadar! 🎉"
- [ ] **Haftalık Plan Section**: WeeklyPlanSection component
- [ ] **Optimal Saatler Section**: Mevcut PostingHeatmap (kalıyor, değişmez)
- [ ] **İstatistikler Section**: Mevcut Stats + Distribution (kalıyor ama aşağıya taşınıyor)

### 4.3 Sayfa tasarım detayları
- [ ] Max width: `max-w-2xl` (dar, mobil-first, feed hissi)
- [ ] Kartlar arası boşluk: `gap-3`
- [ ] Her section arası: `mb-8` + başlık
- [ ] Genel renk tonu: dark, mor/neon vurgular (Account Analysis ile uyumlu)

---

## FAZ 5: XAIModule URL Param Desteği (15 dk)

### 5.1 Yeni URL parametreleri
- [ ] `persona` param'ını oku → `settings.persona` set et
- [ ] `tone` param'ını oku → `settings.tone` set et
- [ ] `length` param'ını oku → `settings.length` set et
- [ ] `hook` param'ını oku → topic yoksa textarea'ya yaz
- [ ] XAIModule.jsx'te ilgili useEffect'e ekle:
  ```jsx
  useEffect(() => {
    const urlPersona = searchParams.get('persona');
    const urlTone = searchParams.get('tone');
    const urlLength = searchParams.get('length');
    const urlHook = searchParams.get('hook');
    
    if (urlPersona) setSettings(s => ({...s, persona: urlPersona}));
    if (urlTone) setSettings(s => ({...s, tone: urlTone}));
    if (urlLength) setSettings(s => ({...s, length: urlLength}));
    if (urlHook) setTopic(prev => prev || urlHook);
  }, []);
  ```

### 5.2 Test
- [ ] URL'den persona/tone/hook geçince XAIModule'de doğru seçili mi?
- [ ] Coach "Yaz →" butonundan geçince çalışıyor mu?

---

## FAZ 6: i18n (20 dk)

### 6.1 Türkçe (tr.json)
- [ ] `coach.greeting.morning`: "Günaydın"
- [ ] `coach.greeting.afternoon`: "İyi günler"
- [ ] `coach.greeting.evening`: "İyi akşamlar"
- [ ] `coach.cardCount`: "Bugün {{count}} önerim var"
- [ ] `coach.noCards`: "Bugünlük bu kadar! 🎉"
- [ ] `coach.opportunity.title`: "🚨 Fırsat"
- [ ] `coach.opportunity.freshness`: "{{hours}} saat önce"
- [ ] `coach.opportunity.action`: "Hemen Yaz →"
- [ ] `coach.roast.personaMono`: "Hep aynı karakter: {{persona}}"
- [ ] `coach.toast.personaDiverse`: "Çok yönlü performans! 🎭"
- [ ] `coach.roast.lowFavorites`: "Son {{count}} üretiminin %{{rate}}'ini beğendin"
- [ ] `coach.toast.highFavorites`: "Kalite patlaması! 💎"
- [ ] `coach.roast.tooLong`: "Tweet'lerin çok uzun"
- [ ] `coach.dailyGoal.none`: "Bugün henüz bir şey üretmedin"
- [ ] `coach.dailyGoal.complete`: "Bugünkü hedefini aştın! 🎉"
- [ ] `coach.repurpose.title`: "Bu favorini hatırlıyor musun?"
- [ ] `coach.repurpose.action`: "Yeniden Yaz →"
- [ ] `coach.progress.up`: "Bu hafta %{{change}} artış! 📈"
- [ ] `coach.progress.down`: "Tempo düşüyor ⚠️"
- [ ] `coach.streak.title`: "🔥 {{count}} gün üst üste!"
- [ ] `coach.plan.empty`: "Bu hafta için henüz plan yok"
- [ ] `coach.plan.create`: "✨ Bu Haftanın Planını Oluştur"
- [ ] `coach.plan.recreate`: "Yeniden Oluştur"
- [ ] `coach.plan.cached`: "Bu plan {{days}} gün önce oluşturuldu"
- [ ] `coach.plan.write`: "Yaz →"
- [ ] `coach.plan.today`: "Bugün"

### 6.2 İngilizce (en.json)
- [ ] Tüm yukarıdaki key'lerin İngilizce karşılıkları

---

## FAZ 7: Backend Deploy + Test (30 dk)

### 7.1 Backend deploy
- [ ] `coach_engine.py` → Hetzner'e SCP
- [ ] `routes/coach.py` → Hetzner'e SCP
- [ ] `systemctl restart contentfactory`
- [ ] Service active kontrolü

### 7.2 Frontend deploy
- [ ] `npx craco build` — hata yok mu?
- [ ] `bash deploy.sh` — Vercel deploy
- [ ] typehype.io erişim kontrolü

### 7.3 End-to-end test
- [ ] Coach sayfası açılıyor mu? Loading skeleton görünüyor mu?
- [ ] Kart feed yükleniyor mu? En az 1 kart var mı?
- [ ] Opportunity kartı: trend varsa görünüyor mu?
- [ ] Roast/Toast kartı: üretim geçmişine göre doğru mu?
- [ ] Günlük hedef kartı: bugünkü üretim sayısına göre doğru mu?
- [ ] Repurpose kartı: eski favori varsa görünüyor mu?
- [ ] Progress kartı: haftalık karşılaştırma doğru mu?
- [ ] Streak kartı: ardışık gün sayısı doğru mu?
- [ ] Kart dismiss: swipe veya ✕ ile kapanıyor mu?
- [ ] Dismiss animasyonu çalışıyor mu? (kart uçar, altları kayar)
- [ ] Dismiss edilen kart sayfa yenilenince geri gelmiyor mu?
- [ ] "Yaz →" butonu: XAIModule'e doğru parametrelerle yönlendiriyor mu?
- [ ] XAIModule'de persona/tone/topic doğru seçili mi?
- [ ] Haftalık plan: ilk açılışta empty state mi?
- [ ] "Planını Oluştur" butonu: GPT çağrısı + DB kayıt + gösterim?
- [ ] Sayfa yenilenince plan hala duruyor mu? (DB'den)
- [ ] Cache badge: "X gün önce oluşturuldu" görünüyor mu?
- [ ] "Yeniden Oluştur" butonu çalışıyor mu?
- [ ] Plan "Yaz →" butonları doğru URL oluşturuyor mu?
- [ ] Optimal saatler heatmap hala çalışıyor mu?
- [ ] Mobil görünüm: kartlar düzgün mü? Swipe çalışıyor mu?

---

## FAZ 8: Git Commit + Memory Güncelle (10 dk)

### 8.1 Git
- [ ] `git add -A`
- [ ] `git commit -m "feat: AI Coach v2 — dynamic card feed, trend hijacking, roast/toast, persistent weekly plan"`
- [ ] `git push origin main`

### 8.2 Memory
- [ ] `MEMORY.md` güncelle: AI Coach v2 tamamlandı notları
- [ ] `QUEUE.md` güncelle: TH-005 tamamlandı
- [ ] `AI-COACH-V2-CHECKLIST.md` tüm checkbox'lar ✅

---

## Rollback Planı

| Sorun | Aksiyon |
|-------|---------|
| Backend çöküyor | Eski coach.py'yi geri koy, restart |
| Frontend bozuk | Vercel'de önceki deploy'a rollback |
| DB sorunu | Yeni tabloları DROP, eski endpoint'ler zaten eskisi gibi çalışır |
| Kartlar yanlış veri gösteriyor | /coach/feed'i devre dışı bırak, eski insights'a dön |

---

## Bağımlılık Grafiği

```
FAZ 1 (DB) ──────┐
                  ├──→ FAZ 2 (Backend) ──→ FAZ 7 (Deploy+Test)
FAZ 5 (XAI URL) ─┘          │
                             ↓
                  FAZ 3 (CoachCard) ──→ FAZ 4 (CoachPage) ──→ FAZ 7
                                                   │
                                            FAZ 6 (i18n) ──→ FAZ 7
```

FAZ 1 + FAZ 5 paralel yapılabilir.
FAZ 3 + FAZ 2 paralel yapılabilir (arayüz bağımsız).
FAZ 4, FAZ 2 + FAZ 3'e bağımlı.
FAZ 7, her şeye bağımlı.
