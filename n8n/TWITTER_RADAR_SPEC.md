# Type Hype - Twitter Radar n8n Workflow Specification

## Amaç

X (Twitter) ve Xquik API kullanarak AI/tech trendlerini topla, Supabase `raw_signals` tablosuna yaz, sonra FastAPI'yi tetikleyerek AI analiz + scoring yaptır.

## Çalışma Zamanı

Günde 5 kez: **04:00, 08:00, 12:00, 16:00, 20:00 UTC** (Türkiye: 07, 11, 15, 19, 23)

## Gerekli Environment Variables (n8n'de tanımlı)

| Değişken | Değer |
|----------|-------|
| `SUPABASE_URL` | `https://awlsmfhxcsifabyanwfv.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase service role JWT |
| `XQUIK_API_KEY` | Xquik API anahtarı |
| `CRON_SECRET` | *(set in environment; never commit the live value — rotated 2026-06-07)* |

---

## Workflow Topolojisi

```
Schedule ──→ Fetch Accounts ──→ Prepare Groups ──┬──→ VIP Search ──────┐
                                                  ├──→ TR Search ──────┤──→ Merge ──→ Normalize ──→ IF ──→ Insert ──→ Trigger ──→ Summary
                                                  └──→ Keyword Search ─┘                              └──→ No Data (end)
```

**Toplam**: ~14 node

---

## Adımlar

### ADIM 1: Schedule Trigger

- **Node type**: `n8n-nodes-base.scheduleTrigger`
- **Cron**: `0 4,8,12,16,20 * * *`
- Hiçbir data üretmez, sadece workflow'u başlatır

---

### ADIM 2: Fetch Watch Accounts (HTTP Request)

- **Node type**: `n8n-nodes-base.httpRequest`
- **Method**: GET
- **URL**: `{{ $env.SUPABASE_URL }}/rest/v1/twitter_watch_accounts`
- **Query params**: `select=*&active=eq.true`
- **Headers**:
  - `apikey`: `{{ $env.SUPABASE_SERVICE_KEY }}`
  - `Authorization`: `Bearer {{ $env.SUPABASE_SERVICE_KEY }}`
- **Çıktı**: Tüm aktif hesapların listesi
- **Örnek data**: `[{username: "OpenAI", tier: 1, niche: "ai", category: "ai_lab", region: "en"}, ...]`
- Supabase'de şu an **56 hesap** var (19 EN VIP + 13 TR haber + 24 keyword/diğer)

---

### ADIM 3: Prepare Search Groups (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items

Gelen hesap listesini 3 gruba ayırır:

```javascript
const accounts = $input.first().json;

// Tier 1+2: VIP accounts (EN) — from:user1 OR from:user2 formatında
const vipAccounts = accounts.filter(a => [1, 2].includes(a.tier) && a.region !== 'tr');
const vipQuery = vipAccounts.map(a => `from:${a.username}`).join(' OR ');

// TR haber hesapları — from:user1 OR from:user2 formatında
const trAccounts = accounts.filter(a => a.region === 'tr');
const trQuery = trAccounts.map(a => `from:${a.username}`).join(' OR ');

// Keyword search queries (sabit)
const keywordQueries = [
  '"just released" (AI OR LLM OR model) min_faves:500',
  '"open source" (model OR LLM OR AI) min_faves:500',
  '"announcing" (from:AnthropicAI OR from:OpenAI OR from:GoogleDeepMind OR from:MistralAI OR from:MetaAI)',
  '"state of the art" (benchmark OR SOTA) min_faves:300',
  '(API OR SDK) launch (AI OR LLM) min_faves:500'
];

return [{
  json: {
    vipQuery,
    vipCount: vipAccounts.length,
    trQuery,
    trCount: trAccounts.length,
    keywordQueries,
    accountMap: Object.fromEntries(accounts.map(a => [a.username.toLowerCase(), a]))
  }
}];
```

**Çıktı**: Tek bir obje — 3 search query grubu + account metadata map

---

### ADIM 4A: Xquik VIP Search (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items
- **onError**: continueRegularOutput (hata olursa workflow durmasın)

Xquik API'ye async extraction job başlatır, sonuç gelene kadar poll eder:

```javascript
const { vipQuery, vipCount } = $input.first().json;

if (!vipQuery || vipCount === 0) {
  return [{ json: { tweets: [], source: 'vip', error: null } }];
}

const apiKey = $env.XQUIK_API_KEY;
const baseUrl = 'https://xquik.com/api/v1';

try {
  // 1. Extraction job başlat
  const startResp = await $helpers.httpRequest({
    method: 'POST',
    url: `${baseUrl}/extractions`,
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: {
      type: 'tweet_search_extractor',
      query: vipQuery,
      max_results: 200
    },
    returnFullResponse: false
  });

  const extractionId = startResp.id;
  if (!extractionId) {
    return [{ json: { tweets: [], source: 'vip', error: 'No extraction ID' } }];
  }

  // 2. Poll — her 2 saniyede bir, max 60 saniye
  let status = 'running';
  let attempts = 0;
  while (status === 'running' && attempts < 30) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const checkResp = await $helpers.httpRequest({
      method: 'GET',
      url: `${baseUrl}/extractions/${extractionId}`,
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    status = checkResp.status;
    attempts++;
  }

  if (status !== 'completed') {
    return [{ json: { tweets: [], source: 'vip', error: `Status: ${status}` } }];
  }

  // 3. Sonuçları çek (pagination)
  let allResults = [];
  let cursor = null;
  do {
    const params = cursor ? `?cursor=${cursor}` : '';
    const resultResp = await $helpers.httpRequest({
      method: 'GET',
      url: `${baseUrl}/extractions/${extractionId}/results${params}`,
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const items = resultResp.data || resultResp.results || [];
    allResults = allResults.concat(items);
    cursor = resultResp.next_cursor || null;
  } while (cursor);

  return [{ json: { tweets: allResults, source: 'vip', error: null } }];

} catch (err) {
  return [{ json: { tweets: [], source: 'vip', error: err.message } }];
}
```

**Çıktı**: `{ tweets: [...raw xquik tweet objeler...], source: "vip", error: null }`

---

### ADIM 4B: Xquik TR Search (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items
- **onError**: continueRegularOutput

VIP Search ile **aynı yapı**, farklılıklar:
- `trQuery` kullanır (`vipQuery` yerine)
- `source: 'tr'`
- `max_results: 100`

```javascript
const { trQuery, trCount } = $input.first().json;

if (!trQuery || trCount === 0) {
  return [{ json: { tweets: [], source: 'tr', error: null } }];
}

const apiKey = $env.XQUIK_API_KEY;
const baseUrl = 'https://xquik.com/api/v1';

try {
  const startResp = await $helpers.httpRequest({
    method: 'POST',
    url: `${baseUrl}/extractions`,
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: {
      type: 'tweet_search_extractor',
      query: trQuery,
      max_results: 100
    }
  });

  const extractionId = startResp.id;
  if (!extractionId) {
    return [{ json: { tweets: [], source: 'tr', error: 'No extraction ID' } }];
  }

  let status = 'running';
  let attempts = 0;
  while (status === 'running' && attempts < 30) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const checkResp = await $helpers.httpRequest({
      method: 'GET',
      url: `${baseUrl}/extractions/${extractionId}`,
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    status = checkResp.status;
    attempts++;
  }

  if (status !== 'completed') {
    return [{ json: { tweets: [], source: 'tr', error: `Status: ${status}` } }];
  }

  let allResults = [];
  let cursor = null;
  do {
    const params = cursor ? `?cursor=${cursor}` : '';
    const resultResp = await $helpers.httpRequest({
      method: 'GET',
      url: `${baseUrl}/extractions/${extractionId}/results${params}`,
      headers: { 'Authorization': `Bearer ${apiKey}` }
    });
    const items = resultResp.data || resultResp.results || [];
    allResults = allResults.concat(items);
    cursor = resultResp.next_cursor || null;
  } while (cursor);

  return [{ json: { tweets: allResults, source: 'tr', error: null } }];

} catch (err) {
  return [{ json: { tweets: [], source: 'tr', error: err.message } }];
}
```

---

### ADIM 4C: Xquik Keyword Search (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items
- **onError**: continueRegularOutput

5 keyword query'yi sırayla çalıştırır (aralarında 2sn bekleme):

```javascript
const { keywordQueries } = $input.first().json;
const apiKey = $env.XQUIK_API_KEY;
const baseUrl = 'https://xquik.com/api/v1';
let allTweets = [];

for (const query of keywordQueries) {
  try {
    // Start extraction
    const startResp = await $helpers.httpRequest({
      method: 'POST',
      url: `${baseUrl}/extractions`,
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: { type: 'tweet_search_extractor', query, max_results: 15 }
    });

    const extractionId = startResp.id;
    if (!extractionId) continue;

    // Poll
    let status = 'running';
    let attempts = 0;
    while (status === 'running' && attempts < 30) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      const checkResp = await $helpers.httpRequest({
        method: 'GET',
        url: `${baseUrl}/extractions/${extractionId}`,
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      status = checkResp.status;
      attempts++;
    }

    if (status === 'completed') {
      const resultResp = await $helpers.httpRequest({
        method: 'GET',
        url: `${baseUrl}/extractions/${extractionId}/results`,
        headers: { 'Authorization': `Bearer ${apiKey}` }
      });
      const items = resultResp.data || resultResp.results || [];
      allTweets = allTweets.concat(items);
    }

    // Rate limit — queries arası 2sn bekle
    await new Promise(resolve => setTimeout(resolve, 2000));
  } catch (err) {
    // Tek query fail ederse diğerleri devam etsin
    continue;
  }
}

return [{ json: { tweets: allTweets, source: 'keyword', error: null } }];
```

---

### ADIM 5: Merge

- **Node type**: `n8n-nodes-base.merge`
- **Mode**: Append
- 3 paralel branch'in çıktılarını birleştirir (VIP + TR + Keyword)
- n8n'de 3 branch merge etmek için 2 Merge node gerekebilir:
  - **Merge 1**: VIP + TR
  - **Merge 2**: Merge 1 çıktısı + Keyword
- **Çıktı**: 3 item (her biri `{tweets: [...], source: "vip"|"tr"|"keyword"}`)

---

### ADIM 6: Normalize + Dedup (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items

Tüm kaynakların raw tweet datalarını `raw_signals` formatına dönüştürür ve dedup yapar:

```javascript
const inputs = $input.all();
const now = new Date().toISOString();
const cutoffMs = Date.now() - (72 * 60 * 60 * 1000); // 72 saat önce

// accountMap'i bul (Prepare Groups node'undan geliyor)
let accountMap = {};
for (const input of inputs) {
  if (input.json.accountMap) {
    accountMap = input.json.accountMap;
    break;
  }
}

const seen = new Set();
const signals = [];

for (const input of inputs) {
  const tweets = input.json.tweets || [];
  const source = input.json.source || 'unknown';

  for (const tweet of tweets) {
    const tweetId = String(tweet.tweetId || tweet.id || '');
    const text = tweet.tweetText || tweet.text || '';
    const username = tweet.xUsername || tweet.username || '';

    // RT filtrele
    if (text.startsWith('RT @')) continue;

    // Dedup — aynı tweet ID'yi iki kez ekleme
    if (seen.has(tweetId)) continue;
    seen.add(tweetId);

    // Tarih parse + 72h filtre
    const rawDate = tweet.tweetCreatedAt || tweet.created_at || '';
    let tweetDate = null;
    if (rawDate) {
      try {
        tweetDate = new Date(rawDate.replace('Z', '+00:00'));
        if (tweetDate.getTime() < cutoffMs) continue; // 72h'den eski
      } catch(e) {}
    }

    // Account metadata
    const acc = accountMap[username.toLowerCase()] || {};
    const tier = acc.tier || (source === 'keyword' ? 3 : 0);
    const niche = acc.niche || 'ai';
    const category = acc.category || (source === 'keyword' ? 'community' : 'unknown');

    // Engagement metrikleri
    const likes = tweet.likeCount || tweet.likes || 0;
    const retweets = tweet.retweetCount || tweet.retweets || 0;
    const replies = tweet.replyCount || tweet.replies || 0;
    const views = tweet.viewCount || tweet.views || 0;

    const url = `https://x.com/${username}/status/${tweetId}`;

    signals.push({
      source_type: 'twitter',
      source_name: username,
      niche: niche,
      title: text.substring(0, 200),
      url: url,
      description: text,
      raw_data: {
        tweet_id: tweetId,
        username: username,
        text: text,
        likes: likes,
        retweets: retweets,
        replies: replies,
        views: views,
        tier: tier,
        category: category,
        source_branch: source
      },
      status: 'pending',
      published_at: tweetDate ? tweetDate.toISOString() : now,
      batch_id: `twitter-${now.split('T')[0]}-${now.split('T')[1].substring(0,5)}`
    });
  }
}

return [{ json: { signals, count: signals.length } }];
```

**Çıktı**: `{ signals: [...normalized signal objeler...], count: 47 }`

---

### ADIM 7: IF Has Signals?

- **Node type**: `n8n-nodes-base.if`
- **Koşul**: `{{ $json.count }}` greater than `0`
- **True branch**: → Supabase Insert
- **False branch**: → No Data summary (workflow biter)

---

### ADIM 8: Supabase Batch Insert (Code Node)

- **Node type**: `n8n-nodes-base.code`
- **Mode**: Run Once for All Items

```javascript
const { signals } = $input.first().json;

if (!signals || signals.length === 0) {
  return [{ json: { inserted: 0, total: 0, error: null } }];
}

const supabaseUrl = $env.SUPABASE_URL;
const supabaseKey = $env.SUPABASE_SERVICE_KEY;

try {
  // Batch insert — URL UNIQUE constraint ile duplicate'ler ignore edilir
  const resp = await $helpers.httpRequest({
    method: 'POST',
    url: `${supabaseUrl}/rest/v1/raw_signals`,
    headers: {
      'apikey': supabaseKey,
      'Authorization': `Bearer ${supabaseKey}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=ignore-duplicates,return=representation'
    },
    body: signals,
    returnFullResponse: true
  });

  const inserted = Array.isArray(resp.body) ? resp.body.length : 0;

  return [{ json: { inserted, total: signals.length, error: null } }];
} catch (err) {
  return [{ json: { inserted: 0, total: signals.length, error: err.message } }];
}
```

**Önemli**: `Prefer: resolution=ignore-duplicates` header'ı sayesinde URL'si zaten var olan sinyaller sessizce atlanır, hata vermez.

---

### ADIM 9: Trigger Process Signals (HTTP Request)

- **Node type**: `n8n-nodes-base.httpRequest`
- **Method**: POST
- **URL**: `https://api.typehype.io/api/trends/process-signals`
- **Headers**:
  - `X-Cron-Secret`: `{{ $env.CRON_SECRET }}`
  - `Content-Type`: `application/json`
- **Body**: `{}`
- **Options**: Continue on fail = true (FastAPI down olsa bile workflow crash olmasın)

Bu endpoint FastAPI'deki `process_raw_signals()` fonksiyonunu çağırır:
1. `raw_signals` tablosundan `status=pending` olanları çeker
2. GPT-4o-mini ile her sinyali analiz eder (başlık, özet, niche, skor)
3. Entity-based clustering yapar (aynı konudaki sinyalleri gruplar)
4. `trends` tablosuna upsert eder
5. Skor >= 80 olan trendler için `content_drafts` oluşturur (LinkedIn, Twitter, Blog)
6. İşlenen sinyallerin status'unu `done` yapar

---

### ADIM 10: Summary (Set Node)

- **Node type**: `n8n-nodes-base.set`
- Workflow sonucu loglamak için:
  - `inserted`: `{{ $json.inserted }}`
  - `total`: `{{ $json.total }}`
  - `timestamp`: `{{ $now }}`

### ADIM 10B: No Data (Set Node)

- IF false branch'ından gelir
- Sadece log: `"No signals found this run"`

---

## Node Settings

| Node | Özel Ayar |
|------|-----------|
| Tüm Code node'ları | **Run Once for All Items** mode |
| VIP Search | `onError: continueRegularOutput` |
| TR Search | `onError: continueRegularOutput` |
| Keyword Search | `onError: continueRegularOutput` |
| Trigger Process Signals | `continueOnFail: true` |

---

## Xquik API Detayları

| Özellik | Değer |
|---------|-------|
| Base URL | `https://xquik.com/api/v1` |
| Auth | `Authorization: Bearer {API_KEY}` |
| Rate limit | 10 req/s |
| Poll interval | 2 saniye |
| Max poll | 30 deneme (60 saniye timeout) |

### Extraction Akışı

```
1. POST /extractions
   Body: { type: "tweet_search_extractor", query: "...", max_results: N }
   Response: { id: "extraction-uuid" }

2. GET /extractions/{id}  (her 2sn poll)
   Response: { status: "running" | "completed" | "failed" }

3. GET /extractions/{id}/results  (status=completed olunca)
   Response: { data: [...tweets], next_cursor: "..." | null }
   → next_cursor varsa tekrar çağır (pagination)
```

### Xquik Tweet Objesi

```json
{
  "tweetId": "1234567890",
  "xUsername": "OpenAI",
  "tweetText": "We're releasing GPT-5...",
  "likeCount": 15000,
  "retweetCount": 3000,
  "replyCount": 800,
  "viewCount": 2000000,
  "tweetCreatedAt": "2026-03-15T10:30:00Z"
}
```

---

## raw_signals Tablo Şeması

```sql
CREATE TABLE raw_signals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  source_type TEXT NOT NULL,        -- 'twitter', 'rss'
  source_name TEXT,                 -- username veya feed adı
  niche TEXT DEFAULT 'ai',          -- 'ai', 'crypto', 'startup'
  title TEXT NOT NULL,              -- tweet'in ilk 200 karakteri
  url TEXT NOT NULL UNIQUE,         -- https://x.com/user/status/id
  description TEXT,                 -- tam tweet metni
  raw_data JSONB,                   -- tüm metadata (likes, views, tier, category...)
  status TEXT DEFAULT 'pending',    -- 'pending', 'processing', 'done', 'error'
  batch_id TEXT,                    -- 'twitter-2026-03-15-14:00'
  published_at TIMESTAMPTZ,        -- tweet tarihi
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Bağlantı Haritası (connections)

```
Schedule (5x/day)
  └──→ Fetch Watch Accounts
        └──→ Prepare Search Groups
              ├──→ Xquik VIP Search ────────────┐
              ├──→ Xquik TR Search ─────────────┤──→ Merge (VIP+TR)
              │                                  │        │
              └──→ Xquik Keyword Search ────────┤────────┘
                                                 │
                                          Merge (All) ──→ Normalize + Dedup
                                                              │
                                                        IF Has Signals?
                                                        ├─ true ──→ Supabase Insert ──→ Trigger Process Signals ──→ Summary
                                                        └─ false ──→ No Data
```

---

## Filtreleme Kuralları

1. **RT filtresi**: `text.startsWith('RT @')` → atla
2. **Yaş filtresi**: 72 saatten eski tweetler → atla
3. **Dedup**: Aynı `tweetId` → sadece ilkini al
4. **URL UNIQUE**: Supabase'de aynı URL'ye sahip sinyal varsa → ignore (PostgREST `resolution=ignore-duplicates`)
