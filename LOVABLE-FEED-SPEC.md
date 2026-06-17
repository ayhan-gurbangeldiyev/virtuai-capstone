# TypeHype Feed UI — Lovable Geliştirme Dokümanı

## Overview

TypeHype bir tweet feed + içerik üretim platformu. Backend'de 21 X/Twitter hesabından + 7 Radar kaynağından (Google Trends, Hacker News, Reddit, GitHub, Polymarket, TrustMRR, Wikipedia) otomatik tweet/sinyal topluyoruz. Bu sinyaller `tweet_feed` tablosunda 48 saatlik pencerede tutuluyor.

Lovable ile yapılacak: Bu feed verisini gösteren bir UI + seçilen tweet'ten yeni tweet oluşturma (compose) akışı.

**Mevcut frontend stack:** React 19 + Tailwind CSS + Radix UI + Lucide Icons + Supabase Auth
**API Base URL:** `https://api.typehype.io`
**Auth:** Feed okuma için auth gerekmez (public). Compose ve kullanıcı işlemleri Supabase JWT ile.

---

## Bölüm 1: Feed Sayfası

### 1.1 Sayfa Yapısı

```
┌─────────────────────────────────────────────────────┐
│  TypeHype Feed                          [Sort Toggle]│
├─────────────────────────────────────────────────────┤
│  [Tümü] [AI/Tech] [Haber] [Spor] [Radar]           │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ [Avatar] @OpenAI · OpenAI · 2s önce         │    │
│  │                                              │    │
│  │ We are excited to announce our latest        │    │
│  │ model GPT-5, featuring breakthrough...       │    │
│  │                                              │    │
│  │ ❤️ 12.4K  🔁 3.2K  💬 892  👁 1.2M          │    │
│  │                                              │    │
│  │ [Tweet Yaz]  [X'te Aç]                      │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ [Avatar] @AnthropicAI · Anthropic · 5s önce │    │
│  │                                              │    │
│  │ Claude 4.5 Haiku is now available...         │    │
│  │                                              │    │
│  │ ❤️ 8.7K  🔁 2.1K  💬 456  👁 890K           │    │
│  │                                              │    │
│  │ [Tweet Yaz]  [X'te Aç]                      │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  ... (infinite scroll)                               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 1.2 Feed API

**Endpoint:** `GET /api/feed`

**Query Parametreleri:**

| Param | Tip | Default | Açıklama |
|-------|-----|---------|----------|
| `batch_type` | string | `null` (tümü) | `ai_tech`, `tr_haber`, `spor`, `monitor`, `radar` |
| `limit` | integer | 20 | Sayfa başına sonuç (max 200) |
| `offset` | integer | 0 | Pagination offset |
| `sort` | string | `"recent"` | `recent` (zamana göre) veya `popular` (beğeniye göre) |
| `hours` | integer | 48 | Son kaç saat (max 168 = 7 gün) |

**Örnek İstek:**
```
GET https://api.typehype.io/api/feed?batch_type=ai_tech&sort=recent&limit=20&offset=0
```

**Response:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "tweet_id": "1234567890123456789",
      "username": "OpenAI",
      "display_name": "OpenAI",
      "avatar_url": "https://pbs.twimg.com/profile_images/xxxxx/xxxxx_400x400.jpg",
      "content": "We are excited to announce our latest model GPT-5...",
      "likes": 12400,
      "retweets": 3200,
      "replies": 892,
      "views": 1200000,
      "tweet_url": "https://x.com/OpenAI/status/1234567890123456789",
      "batch_type": "ai_tech",
      "source_detail": "OpenAI",
      "tweet_created_at": "2026-04-08T10:30:00+00:00",
      "collected_at": "2026-04-08T10:35:00+00:00"
    }
  ],
  "total": 134,
  "has_more": true,
  "limit": 20,
  "offset": 0
}
```

**Auth:** Gerekmez (public endpoint).
**Rate Limit:** 100 req/dakika.

### 1.3 Kategori Tabları

| Tab Label | batch_type Değeri | Açıklama | Ikon |
|-----------|-------------------|----------|------|
| Tümü | `null` (parametre gönderme) | Tüm kaynaklar | Globe |
| AI/Tech | `ai_tech` | AI lab'lar + TR tech siteleri | Brain |
| Haber | `tr_haber` | Türk haber kaynakları | Newspaper |
| Spor | `spor` | Spor haberleri | Trophy |
| Radar | `radar` | Google Trends, HN, Reddit, GitHub vb. | Radar |

`monitor` kategorisi ayrı tab olarak gösterilmez — "Tümü" içinde gelir.

### 1.4 Sıralama Toggle

İki mod:
- **Son Eklenenler** (`sort=recent`) — `tweet_created_at` DESC (default)
- **En Popüler** (`sort=popular`) — `likes` DESC

UI: İki butonlu toggle veya dropdown.

### 1.5 Tweet Kartı Bileşeni

Her kart şu bilgileri gösterir:

```
┌──────────────────────────────────────────────────┐
│ [48px Avatar]  @username · Display Name · Zaman  │
│                                                   │
│ Tweet içeriği burada görünür. Maksimum 280        │
│ karakter. Uzun tweetler expand ile açılabilir.    │
│                                                   │
│ ❤️ 12.4K   🔁 3.2K   💬 892   👁 1.2M            │
│                                                   │
│ [🖊 Tweet Yaz]              [↗ X'te Aç]          │
│                                                   │
│ [ai_tech badge]                                   │
└──────────────────────────────────────────────────┘
```

**Avatar:**
- `avatar_url` alanından geliyor
- 400x400 çözünürlük
- Rounded-full (circular)
- Fallback: İlk harf avatar (username[0])
- `null` olabilir (radar kaynaklarında genelde yok)

**Zaman Gösterimi:**
- `tweet_created_at` alanından relative time:
  - < 1 dakika: "az önce"
  - < 60 dakika: "12dk önce"
  - < 24 saat: "5s önce"
  - < 7 gün: "3g önce"
  - > 7 gün: "8 Nis" (tarih)

**Engagement Metrikleri:**
- `likes`: ❤️ ikon + sayı
- `retweets`: 🔁 ikon + sayı
- `replies`: 💬 ikon + sayı
- `views`: 👁 ikon + sayı
- Sayı formatı: 1000 → "1K", 1200000 → "1.2M"
- 0 olan metrikler gösterilmesin veya gri olsun

**Aksiyon Butonları:**
1. **"Tweet Yaz"** — Bu tweet'ten ilham alarak yeni tweet compose etme. Compose modalını açar (Bölüm 2).
2. **"X'te Aç"** — `tweet_url` linkini yeni sekmede açar.

**Batch Type Badge:**
- Kartın alt köşesinde küçük badge
- ai_tech → mavi, tr_haber → kırmızı, spor → yeşil, radar → mor, monitor → turuncu

### 1.6 Radar Kartları (Özel)

Radar kaynaklı öğeler tweet değil, trend sinyali. Farklar:
- `avatar_url` genelde `null` — kaynak ikonu kullan
- `username` = kaynak adı (ör. "Radar:hacker_news_global_tech")
- `content` = trend başlığı + açıklama
- `likes` = skor (0-10000 arası)
- `retweets`, `replies`, `views` = 0
- `tweet_url` = kaynak URL'i (HN post, Reddit thread, GitHub repo vb.)
- Badge: "Radar" + kaynak adı

### 1.7 Pagination — Infinite Scroll

- İlk yükleme: `limit=20&offset=0`
- Kullanıcı aşağı scroll edince: `offset += 20` ile yeni sayfa çek
- `has_more: false` gelene kadar devam et
- Loading spinner: Altta skeleton kartlar göster
- Pull-to-refresh: Sayfayı başa çekince `offset=0` ile yeniden yükle

### 1.8 Boş ve Loading State'leri

**Loading:** 3-4 skeleton tweet kartı (avatar placeholder + text shimmer)
**Boş:** "Bu kategoride henüz tweet yok." + "Veriler her birkaç saatte güncellenir."
**Hata:** "Feed yüklenirken bir hata oluştu." + [Tekrar Dene] butonu

### 1.9 Auto-Refresh

- Feed her 5 dakikada kendini güncellesin (background polling)
- Yeni tweet geldiğinde kartın üstüne "X yeni tweet" bildirimi göster
- Tıklanınca scroll yukarı ve yeni tweetleri göster

---

## Bölüm 2: Tweet Compose Akışı

Feed'deki bir tweet'e "Tweet Yaz" butonuna basıldığında açılan modal.

### 2.1 Compose Modal Yapısı

```
┌─────────────────────────────────────────────────────┐
│  Tweet Oluştur                              [X Kapat]│
├─────────────────────────────────────────────────────┤
│                                                      │
│  İlham Tweet:                                        │
│  ┌─────────────────────────────────────────────┐    │
│  │ @OpenAI: We are excited to announce...       │    │
│  └─────────────────────────────────────────────┘    │
│                                                      │
│  Hedef:  [Engagement ▾]    Ton:  [Profesyonel ▾]   │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │ Tweet metnini buraya yaz...                  │    │
│  │                                              │    │
│  └─────────────────────────────────────────────┘    │
│  245/280 karakter                                    │
│                                                      │
│  [📊 Skorla]  [✨ İyileştir]  [📋 Kopyala]          │
│                                                      │
│  ─── Skor Sonucu ───                                │
│  Genel Skor: 87/100  ████████░░                     │
│  ✅ Call to action var                               │
│  ✅ Emoji kullanımı uygun                            │
│  ❌ Hashtag eksik → "2-3 hashtag ekle"              │
│                                                      │
│  ─── İyileştirme Önerisi ───                        │
│  "Check out this..." → "Discover this ground..."    │
│  Sebep: Power word engagement artırır               │
│  [Öneriyi Uygula]                                    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 2.2 Compose API'ları (Tümü ÜCRETSİZ)

#### A. Tweet Skorla
```
POST https://api.typehype.io/api/compose/score
Body: { "draft": "Bu harika bir gelişme! AI dünyasında..." }

Response:
{
  "checklist": [
    {"factor": "call_to_action", "passed": true, "score": 9, "suggestion": null},
    {"factor": "emoji_usage", "passed": false, "score": 4, "suggestion": "1-2 emoji ekle"},
    {"factor": "hashtag", "passed": false, "score": 2, "suggestion": "2-3 hashtag ekle"}
  ],
  "summary": "İyi engagement potansiyeli. Emoji ve hashtag ekle.",
  "totalScore": 72
}
```

#### B. Tweet İyileştir
```
POST https://api.typehype.io/api/compose/refine
Body: {
  "draft": "Bu harika bir gelişme!",
  "topic": "AI advancement",
  "goal": "engagement",
  "tone": "professional"
}

Response:
{
  "suggestions": [
    {
      "original": "Bu harika bir gelişme!",
      "refined": "AI'da çığır açan bir gelişme! İşte detaylar 🧵👇",
      "reason": "Power word + CTA + emoji = daha yüksek engagement",
      "impact": "high"
    }
  ],
  "refinedDraft": "AI'da çığır açan bir gelişme! İşte detaylar 🧵👇",
  "expectedImprovementScore": 15
}
```

### 2.3 Goal ve Tone Seçenekleri

**Goal (Hedef):** engagement, followers, authority, conversation
**Tone (Ton):** professional, casual, witty, bold

### 2.4 Skor Gösterimi

- 0-40: Kırmızı (zayıf)
- 41-70: Sarı (orta)
- 71-100: Yeşil (güçlü)

Checklist: ✅ passed / ❌ failed + suggestion

---

## Bölüm 3: Veri Modeli

### FeedItem Alanları

| Alan | Tip | Nullable | Açıklama |
|------|-----|----------|----------|
| `id` | UUID | Hayır | Benzersiz kayıt ID'si |
| `tweet_id` | string | Hayır | X/Twitter tweet ID'si |
| `username` | string | Hayır | @kullanıcıadı (@ olmadan) |
| `display_name` | string | Evet | Görünen isim |
| `avatar_url` | string | Evet | Profil fotoğrafı URL (400x400) |
| `content` | string | Hayır | Tweet metni |
| `likes` | integer | Hayır | Beğeni sayısı |
| `retweets` | integer | Hayır | RT sayısı |
| `replies` | integer | Hayır | Yanıt sayısı |
| `views` | integer | Hayır | Görüntülenme sayısı |
| `tweet_url` | string | Evet | Tweet linki |
| `batch_type` | string | Hayır | Kategori |
| `source_detail` | string | Evet | Kaynak detayı |
| `tweet_created_at` | ISO8601 | Evet | Tweet zamanı |
| `collected_at` | ISO8601 | Evet | Toplama zamanı |

---

## Bölüm 4: UI/UX Detayları

### 4.1 Badge Renkleri

| batch_type | Renk | Ikon |
|-----------|------|------|
| `ai_tech` | Mavi (#3B82F6) | Brain |
| `tr_haber` | Kırmızı (#EF4444) | Newspaper |
| `spor` | Yeşil (#22C55E) | Trophy |
| `radar` | Mor (#A855F7) | Radar |
| `monitor` | Turuncu (#F97316) | Bell |

### 4.2 Radar Kaynak İkonları

| source_detail İçeriği | Ikon | Renk |
|-----------------------|------|------|
| "google_trends" | Google "G" | #4285F4 |
| "hacker_news" | "Y" (YC) | #FF6600 |
| "reddit" | Reddit alien | #FF4500 |
| "github" | Octocat | #333333 |
| "polymarket" | "P" | #0066FF |
| "trustmrr" | "T" | #6366F1 |
| "wikipedia" | "W" | #636363 |

### 4.3 Sayı Formatlama

```
< 1000       → "892"
< 10000      → "1.2K"
< 1000000    → "45K"
< 10000000   → "1.2M"
>= 10000000  → "12M"
```

### 4.4 Responsive

- Desktop (>1024px): Kartlar max-width 680px, ortalanmış
- Tablet (768-1024px): Kartlar tam genişlik
- Mobil (<768px): Kartlar tam genişlik, metrikler küçültülmüş

### 4.5 Dark Mode

Dark mode desteklenmeli. Tailwind `dark:` prefix'i ile.

---

## Bölüm 5: TypeScript Tipleri

```typescript
const API_BASE = "https://api.typehype.io/api";

// ─── Feed Types ───

interface FeedParams {
  batch_type?: "ai_tech" | "tr_haber" | "spor" | "monitor" | "radar";
  limit?: number;
  offset?: number;
  sort?: "recent" | "popular";
  hours?: number;
}

interface FeedResponse {
  items: FeedItem[];
  total: number;
  has_more: boolean;
  limit: number;
  offset: number;
}

interface FeedItem {
  id: string;
  tweet_id: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  content: string;
  likes: number;
  retweets: number;
  replies: number;
  views: number;
  tweet_url: string | null;
  batch_type: string;
  source_detail: string | null;
  tweet_created_at: string | null;
  collected_at: string | null;
}

// ─── Compose Types ───

interface ScoreRequest {
  draft: string;
}

interface ScoreResponse {
  checklist: ChecklistItem[];
  summary: string;
  totalScore: number;
}

interface ChecklistItem {
  factor: string;
  passed: boolean;
  score: number;
  suggestion: string | null;
}

interface RefineRequest {
  draft: string;
  topic: string;
  goal: "engagement" | "followers" | "authority" | "conversation";
  tone: "professional" | "casual" | "witty" | "bold";
}

interface RefineResponse {
  suggestions: Suggestion[];
  refinedDraft: string;
  expectedImprovementScore: number;
}

interface Suggestion {
  original: string;
  refined: string;
  reason: string;
  impact: "high" | "medium" | "low";
}
```

---

## Bölüm 6: Öncelik Sırası

### Faz 1 (İlk Versiyon)
1. Feed sayfası + tweet kartları
2. Kategori tabları
3. Sıralama toggle
4. Infinite scroll
5. Avatar, engagement, relative time
6. "X'te Aç" butonu
7. Radar kartları için kaynak ikonları
8. Loading/empty/error state'leri
9. Responsive + Dark mode

### Faz 2 (Sonra)
1. "Tweet Yaz" + Compose modal
2. Skor gösterimi
3. İyileştirme önerileri
4. Goal/Tone seçenekleri

---

## Test

Aşağıdaki URL'ler canlı API'dan veri döner:

```
GET https://api.typehype.io/api/feed
GET https://api.typehype.io/api/feed?batch_type=ai_tech
GET https://api.typehype.io/api/feed?sort=popular&hours=24
GET https://api.typehype.io/api/feed?limit=20&offset=20
```

---

## Örnek Kullanım (JavaScript)

```javascript
// Fetch AI Tech tweets, most popular first
const res = await fetch('https://api.typehype.io/api/feed?batch_type=ai_tech&sort=popular&limit=20');
const data = await res.json();
// data.items = FeedItem[]
// data.total = number
// data.has_more = boolean

// Paginate
const page2 = await fetch('https://api.typehype.io/api/feed?limit=20&offset=20');

// Score a tweet draft
const scoreRes = await fetch('https://api.typehype.io/api/compose/score', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ draft: "Bu harika bir gelişme!" })
});
const scoreData = await scoreRes.json();

// Refine a tweet
const refineRes = await fetch('https://api.typehype.io/api/compose/refine', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    draft: "Bu harika bir gelişme!",
    topic: "AI advancement",
    goal: "engagement",
    tone: "professional"
  })
});
const refineData = await refineRes.json();
```
