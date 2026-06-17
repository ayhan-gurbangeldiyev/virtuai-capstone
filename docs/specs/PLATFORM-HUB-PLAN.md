# 🚀 Platform Hub: Manus-Style Unified Content Creator

## Vizyon
Manus.im'deki gibi tek bir akıllı input alanı. Kullanıcı platformu seçer, konu yazar, içerik üretilir. 6 ayrı sayfa yerine tek bir güçlü ekran.

## Mevcut Durum Analizi

### Frontend (6 ayrı modül sayfası)
| Modül | Dosya | Satır | Durum |
|-------|-------|-------|-------|
| X/Twitter | XAIModule.jsx | ~1860 | ✅ Manus UI, tam fonksiyonel |
| YouTube | YouTubeModule.jsx | 362 | ⚠️ Eski UI, tab yapısı |
| Instagram | InstaFlowModule.jsx | 461 | ⚠️ Eski UI |
| TikTok | TikTrendModule.jsx | 351 | ⚠️ Eski UI |
| LinkedIn | LinkShareModule.jsx | 925 | ⚠️ Eski UI |
| Blog | BlogArchitectModule.jsx | 723 | ⚠️ Eski UI |

### Backend (Tamamı hazır!)
| Platform | Route dosyası | Endpoint'ler |
|----------|--------------|-------------|
| X/Twitter | server.py | `/generate/tweet`, `/generate/quote`, `/generate/reply`, `/generate/article` |
| LinkedIn | routes/linkedin.py | `/generate/linkedin`, `/generate/linkedin/carousel`, `/generate/linkedin/hooks` |
| Instagram | routes/instagram.py | `/generate/instagram/caption`, `/generate/instagram/reel-script`, `/generate/instagram/hashtags` |
| YouTube | routes/youtube.py | `/generate/youtube/idea`, `/generate/youtube/script`, `/generate/youtube/title`, `/generate/youtube/description` |
| TikTok | routes/tiktok.py | `/generate/tiktok/script`, `/generate/tiktok/caption` |
| Blog | routes/blog.py | `/generate/blog/outline`, `/generate/blog/full`, `/generate/blog/seo-optimize` |

### Prompt Sistemi (Tamamı hazır!)
- `prompts/builder.py` → `build_final_prompt()` zaten `content_type` parametresi ile platform bazlı çalışıyor
- Her platform için ayrı system prompt: `linkedin.py`, `instagram.py`, `youtube.py`, `tiktok.py`, `blog.py`
- Platform task definition'ları `TASK_DEFINITIONS` dict'inde mevcut

---

## Mimari Karar: Unified Component

**XAIModule.jsx'i genişletmek yerine yeni `CreateHub.jsx` component'i oluşturuyoruz.**

Neden:
- XAIModule 1860 satır, Twitter'a spesifik logic çok fazla
- Temiz başlamak, Manus pattern'ini doğru uygulamak daha sağlıklı
- XAIModule yedek olarak kalır (v1 route)
- Yeni component modüler: platform config'leri ayrı dosyalarda

---

## Platform Konfigürasyonu

Her platform için bir config objesi:

```js
const PLATFORMS = {
  twitter: {
    id: "twitter",
    label: "𝕏",
    icon: FaXTwitter,
    color: "#000000",
    contentTypes: [
      { id: "tweet", label: "Tweet", icon: MessageSquare },
      { id: "quote", label: "Alıntı", icon: Quote, needsUrl: true },
      { id: "reply", label: "Yanıt", icon: Reply, needsUrl: true },
      { id: "thread", label: "Thread", icon: FileText },
    ],
    settings: {
      personas: true,        // Karakter seçimi
      tones: true,           // Ton seçimi  
      lengths: "tweet",      // Uzunluk grubu
      knowledge: true,       // Knowledge mode
      replyModes: true,      // Reply modunda
      styleProfile: true,    // RAG stil klonlama
      ultraMode: true,       // Ultra/APEX mode
    },
    endpoint: "/generate/tweet",  // Ana endpoint
    placeholder: "Ne hakkında tweet atmak istiyorsun?",
  },
  
  linkedin: {
    id: "linkedin",
    label: "LinkedIn",
    icon: FaLinkedinIn,
    color: "#0A66C2",
    contentTypes: [
      { id: "post", label: "Post", icon: FileText },
      { id: "carousel", label: "Carousel", icon: Layers },
      { id: "hooks", label: "Hook", icon: Sparkles },
    ],
    settings: {
      personas: "linkedin",  // LinkedIn-specific personalar
      tones: true,
      lengths: "linkedin",
      knowledge: true,
      styleProfile: true,
      ultraMode: true,
    },
    endpoint: "/generate/linkedin",
    placeholder: "Hangi konuda LinkedIn post'u yazmak istiyorsun?",
  },
  
  instagram: {
    id: "instagram",
    label: "Instagram", 
    icon: FaInstagram,
    color: "#E4405F",
    contentTypes: [
      { id: "caption", label: "Caption", icon: MessageSquare },
      { id: "reel-script", label: "Reel Script", icon: Film },
      { id: "story", label: "Story", icon: Image },
      { id: "hashtags", label: "Hashtag", icon: Hash },
    ],
    settings: {
      personas: true,
      tones: true,
      lengths: "instagram",
      knowledge: false,
      styleProfile: true,
      ultraMode: true,
    },
    endpoint: "/generate/instagram/caption",
    placeholder: "Instagram için ne paylaşmak istiyorsun?",
  },
  
  youtube: {
    id: "youtube",
    label: "YouTube",
    icon: FaYoutube,
    color: "#FF0000",
    contentTypes: [
      { id: "idea", label: "Fikir", icon: Lightbulb },
      { id: "script", label: "Script", icon: FileText },
      { id: "title", label: "Başlık", icon: Type },
      { id: "description", label: "Açıklama", icon: AlignLeft },
    ],
    settings: {
      personas: true,
      tones: true,
      lengths: "youtube",
      knowledge: false,
      styleProfile: false,
      ultraMode: true,
    },
    endpoint: "/generate/youtube/script",
    placeholder: "Hangi konuda video çekmek istiyorsun?",
  },
  
  tiktok: {
    id: "tiktok",
    label: "TikTok",
    icon: FaTiktok,
    color: "#000000",
    contentTypes: [
      { id: "script", label: "Script", icon: Film },
      { id: "caption", label: "Caption", icon: MessageSquare },
    ],
    settings: {
      personas: true,
      tones: true,
      lengths: "tiktok",
      knowledge: false,
      styleProfile: false,
      ultraMode: true,
    },
    endpoint: "/generate/tiktok/script",
    placeholder: "TikTok için ne çekmek istiyorsun?",
  },
  
  blog: {
    id: "blog",
    label: "Blog",
    icon: HiDocumentText,
    color: "#4A90D9",
    contentTypes: [
      { id: "outline", label: "Taslak", icon: List },
      { id: "full", label: "Tam Yazı", icon: FileText },
      { id: "seo", label: "SEO", icon: Search },
    ],
    settings: {
      personas: true,
      tones: true,
      lengths: "blog",
      knowledge: true,
      styleProfile: true,
      ultraMode: true,
    },
    endpoint: "/generate/blog/full",
    placeholder: "Hangi konuda blog yazısı yazmak istiyorsun?",
  },
};
```

---

## Detaylı Checklist

### FAZ 1: Core Hub UI (Öncelik: YÜKSEK)

#### 1.1 CreateHub.jsx Component Oluştur
- [ ] Yeni dosya: `frontend/src/pages/CreateHub.jsx`
- [ ] Manus layout'u: Hero başlık + input alanı + platform bar + quick action pills
- [ ] Platform config objelerini tanımla (`PLATFORMS` dict)
- [ ] CSS variables kullan (mevcut `--m-*` sistemi)
- [ ] Dark/Light mode uyumlu (DESIGN_SYSTEM.md kuralları)

#### 1.2 Platform Icon Bar (Input İçi)
- [ ] Input kutusunun alt satırında renkli platform ikonları (Manus "Araçlarınızı bağlayın" satırı)
- [ ] 𝕏 · YouTube · Instagram · TikTok · LinkedIn · Blog
- [ ] Seçili platform highlight (border-bottom veya filled bg)
- [ ] Platform değiştirince smooth transition (content types değişir)
- [ ] Default: Twitter seçili (mevcut kullanıcı davranışı korunur)

#### 1.3 Quick Action Pills (Input Altı)
- [ ] Seçili platforma göre dinamik pill'ler
- [ ] Twitter: `Tweet yaz` · `Alıntı` · `Yanıt` · `Thread`
- [ ] LinkedIn: `Post yaz` · `Carousel` · `Hook üret`
- [ ] Instagram: `Caption` · `Reel Script` · `Story` · `Hashtag`
- [ ] YouTube: `Fikir` · `Script` · `Başlık` · `Açıklama`
- [ ] TikTok: `Script` · `Caption`
- [ ] Blog: `Taslak` · `Tam Yazı` · `SEO`
- [ ] Pill'e tıklayınca content type seçilir, placeholder güncellenir

#### 1.4 Başlık Dinamikleştirme
- [ ] Platform seçilmeden: "Ne yazmak istiyorsun?"
- [ ] Twitter seçili: "𝕏'te ne paylaşmak istiyorsun?"
- [ ] LinkedIn seçili: "LinkedIn'de ne paylaşmak istiyorsun?"
- [ ] vs.

#### 1.5 Settings Popup Adaptasyonu
- [ ] Mevcut SettingsPopup component'ini genelleştir
- [ ] Platform config'e göre hangi ayarlar görünür
- [ ] Twitter: personas + tones + lengths + knowledge + replyModes + language + variants
- [ ] LinkedIn: linkedin_personas + tones + lengths + language + variants
- [ ] Instagram: tones + lengths + language + variants (persona yok)
- [ ] YouTube: duration (5/10/15/20 dk) + language + variants
- [ ] TikTok: duration (15/30/60 sn) + language + variants
- [ ] Blog: style + framework + lengths + language

#### 1.6 Ultra Mode (⚡) Genelleştirme
- [ ] Tüm platformlarda Ultra mode çalışır
- [ ] Rotating gradient border efekti korunur
- [ ] Backend'e `is_apex: true` gider (mevcut yapı)

#### 1.7 Toolbar Ikonları
- [ ] Sol: ⚙️ Settings · ⚡ Ultra toggle
- [ ] Sağ: 🎤 (gelecek) · 😊 (gelecek) · ➡️ Gönder butonu
- [ ] Manus layout korunur

---

### FAZ 2: Generation & History Entegrasyonu

#### 2.1 Platform-Aware Generation
- [ ] Her platform için doğru endpoint'e istek at
- [ ] Twitter: mevcut `/generate/tweet` etc. (değişmez)
- [ ] LinkedIn: `/generate/linkedin` (routes/linkedin.py)
- [ ] Instagram: `/generate/instagram/caption` etc.
- [ ] YouTube: `/generate/youtube/script` etc.
- [ ] TikTok: `/generate/tiktok/script` etc.
- [ ] Blog: `/generate/blog/full` etc.
- [ ] Request body'yi platform'a göre oluştur (her endpoint farklı model bekliyor)

#### 2.2 Unified Response Handler
- [ ] Tüm platform response'ları aynı `GenerationCard` component'inde render
- [ ] Platform badge'i göster (hangi platformdan geldi)
- [ ] Copy butonu platform'a göre format (Twitter: 280 char uyarı, Blog: markdown)
- [ ] Favoriye ekleme tüm platformlarda çalışır

#### 2.3 Inline Generation History
- [ ] Mevcut inline history yapısı tüm platformlarda çalışır
- [ ] Platform filtresi: "Sadece Twitter" / "Sadece LinkedIn" vs.
- [ ] GenerationCard'da platform ikonu göster

#### 2.4 RAG/Style Integration
- [ ] Twitter: mevcut RAG (similar-tweets) aynen çalışır
- [ ] Diğer platformlar: style_prompt (stil profili) gider ama example_tweets yok (henüz)
- [ ] StyleProfileBadge tüm platformlarda görünür (varsa)

---

### FAZ 3: Routing & Navigation Değişiklikleri

#### 3.1 Route Yapısı
- [ ] Yeni route: `/dashboard/create` → `CreateHub.jsx`
- [ ] DashboardLayout navbar: Platform linkleri kaldır, tek "Oluştur" butonu
- [ ] Veya: Navbar'da platform ikonları kalır ama hepsi `/dashboard/create?platform=x` gibi query param ile
- [ ] Eski route'lar redirect: `/dashboard/x-ai` → `/dashboard/create?platform=twitter`
- [ ] Home page (DashboardHome) "Oluştur" CTA'sı → `/dashboard/create`

#### 3.2 Navbar Sadeleştirme
- [ ] Seçenek A: `Home` · `Oluştur` · `Trendler` · `...` (minimal)
- [ ] Seçenek B: Navbar'da platform ikonları kalır, tıklayınca create hub'a gider (mevcut yapıya yakın)
- [ ] **Berkay karar verecek**

#### 3.3 Deep Link Desteği
- [ ] URL: `/dashboard/create?platform=twitter&type=tweet`
- [ ] Trends'ten "Hızlı Üret" → `/dashboard/create?platform=twitter&topic=...&trend_context=...`
- [ ] Home bento kartlarından → ilgili platforma deep link

---

### FAZ 4: Backend Harmonizasyon

#### 4.1 Unified Generation Response
- [ ] Tüm platform endpoint'lerinin response formatını `GenerationResponse` ile uyumlu hale getir
- [ ] Her response'a `platform` field'ı ekle
- [ ] `generations` tablosuna `platform` kolonu ekle (şu an `content_type` var)

#### 4.2 Supabase Schema Güncelleme
- [ ] `generations` tablosu: `platform` VARCHAR ekle (twitter, linkedin, instagram, youtube, tiktok, blog)
- [ ] Mevcut kayıtlar: platform = 'twitter' (default migration)
- [ ] Index: `idx_generations_platform` 

#### 4.3 Meta Endpoint'leri Birleştir
- [ ] `/api/meta/platforms` → Tüm platform config'lerini tek endpoint'ten döndür
- [ ] Frontend bu endpoint'i kullanarak platformları ve content type'ları dinamik yükleyebilir
- [ ] Gelecekte yeni platform eklemek: sadece backend config + prompt dosyası

---

### FAZ 5: Polish & UX

#### 5.1 Onboarding
- [ ] İlk kullanımda platform seçim rehberi
- [ ] "Hangi platformda içerik üretmek istiyorsun?" wizard
- [ ] Favori platform kaydetme (localStorage veya Supabase)

#### 5.2 Animasyonlar
- [ ] Platform değiştirme: pill'ler slide-in/out
- [ ] Content type seçme: smooth morph
- [ ] Generation: mevcut loading animasyonları korunur

#### 5.3 Keyboard Shortcuts
- [ ] `Cmd+1` → Twitter, `Cmd+2` → LinkedIn, vs.
- [ ] `Cmd+Enter` → Generate
- [ ] `Tab` → Platform arası geçiş

#### 5.4 Mobile Responsive
- [ ] Platform icon bar yatay scroll (6 ikon sığmazsa)
- [ ] Settings popup bottom sheet olur
- [ ] Quick action pills wrap

---

## Dosya Yapısı (Yeni)

```
frontend/src/
├── pages/
│   ├── CreateHub.jsx          ← YENİ: Ana hub component
│   ├── XAIModule.jsx          ← KALIR: Backup / v1
│   └── ...eski modüller...    ← KALIR: Redirect veya silinir
├── config/
│   └── platforms.js           ← YENİ: Platform konfigürasyonları
├── components/
│   └── create/
│       ├── PlatformBar.jsx    ← YENİ: Platform icon satırı
│       ├── QuickActions.jsx   ← YENİ: Dinamik pill'ler
│       ├── HubSettings.jsx    ← YENİ: Genelleştirilmiş settings popup
│       └── HubToolbar.jsx     ← YENİ: Input toolbar (⚙️ ⚡ 🎤 ➡️)
```

---

## Risk Analizi

| Risk | Olasılık | Etki | Çözüm |
|------|----------|------|-------|
| XAIModule'deki UX kalitesi düşer | Düşük | Yüksek | XAIModule yedek kalır, CreateHub ayrı dosya |
| Backend endpoint format uyumsuzluğu | Orta | Orta | Adapter pattern: her platform için request builder |
| Dark mode bozulması | Düşük | Yüksek | CSS variables sistemi aynen kullanılır |
| Performance (tek sayfada çok logic) | Düşük | Orta | Lazy loading, platform config'ler ayrı dosyada |
| RAG sadece Twitter'da çalışıyor | Beklenen | Düşük | Faz 1'de sadece Twitter'da RAG, diğerleri style_prompt |

---

## Uygulama Sırası

**Bugün (Faz 1.1 + 1.2 + 1.3):**
1. `platforms.js` config dosyası oluştur
2. `CreateHub.jsx` iskelet: başlık + input + platform bar + pills
3. Twitter tam fonksiyonel (mevcut XAIModule logic'i taşı)
4. Diğer platformlar seçilebilir ama "Yakında" badge'i

**Yarın (Faz 1.4 + 1.5 + 2.1):**
5. Settings popup adaptasyonu
6. LinkedIn ve Instagram generation bağlantısı
7. Route değişiklikleri

**Sonraki günler (Faz 2-5):**
8. Tüm platformlar tam fonksiyonel
9. History/favorites entegrasyonu
10. Supabase schema güncellemesi
11. Polish ve animasyonlar
