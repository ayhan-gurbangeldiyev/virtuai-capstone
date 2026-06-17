# Multi-Account Support — Mimari Tasarım

> Tarih: 2026-02-23
> Durum: **Berkay onayladı**, Faz 1'e hazır
> Revizyon: v2 (5 kırmızı çizgi eklendi)

## Problem

Şu an TypeHype tek bir Twitter hesabıyla çalışıyor (`connected_accounts` tablosunda `is_primary` ile).
Kullanıcı birden fazla hesap yönetmek istediğinde (kişisel + marka, farklı niche'ler) sistemi sıfırdan
kurmak yerine, hesaplar arası geçiş yapabilmeli.

## Temel Karar: "Aktif Hesap" Paradigması

Her şeyi `user_id` yerine `user_id + active_account_id` ile scope'luyoruz.
Kullanıcı hesap değiştirdiğinde, tüm ekranlar o hesabın verileriyle yenileniyor.

### Etkilenen Alanlar

| Alan | Şu An | Çoklu Hesap |
|------|-------|-------------|
| Üretimler (generations) | user_id | user_id + account_id |
| Favoriler | user_id | user_id + account_id |
| Stil Profili | user_id | account_id'ye bağlı |
| AI Coach kartları | user_id | account_id bazlı istatistik |
| Haftalık Plan | user_id + week_start | user_id + account_id + week_start |
| Posting Times Heatmap | Sabit data | account_id bazlı hesaplama |
| Trend'ler | Global | Global (hesap bağımsız) |
| Account Analysis | Bağımsız | Bağımsız (herhangi hesap analiz edilebilir) |

---

## 🚨 5 Kırmızı Çizgi (Kritik Edge Case'ler)

### 1. Null Migration — Veri Sızıntısı Önleme

**Problem:** Eski data `account_id = NULL` olursa, yeni eklenen marka hesabının
History/Coach'unda kişisel tweetler görünür. Bu kabul edilemez bir bağlam kopukluğu.

**Çözüm: İlk Hesap Ataması (First Account Assignment)**
```sql
-- Kullanıcı ikinci hesabını eklediğinde tetiklenen migration:
-- Tüm NULL kayıtları İLK (primary) hesaba ata
UPDATE generations SET account_id = :first_account_id
  WHERE user_id = :user_id AND account_id IS NULL;

UPDATE favorites SET account_id = :first_account_id
  WHERE user_id = :user_id AND account_id IS NULL;

UPDATE coach_weekly_plans SET account_id = :first_account_id
  WHERE user_id = :user_id AND account_id IS NULL;

UPDATE coach_dismissed_cards SET account_id = :first_account_id
  WHERE user_id = :user_id AND account_id IS NULL;
```

**Tetikleme zamanı:** İkinci hesap eklendiğinde (PUT /accounts/{platform}), backend
otomatik olarak null migration çalıştırır. Tek hesaplı kullanıcılar etkilenmez.

**Sonuç:** Yeni hesap sıfır kilometre ile açılır. Eski data ilk hesaba aittir.

### 2. Aktif Hesap Görünürlüğü — "Hangi Hesaptayım?" Sorunu

**Problem:** Navbar'da sadece "Berkay" yazarsa, kullanıcı hangi X hesabında
olduğunu unutur. Yanlış hesaptan shitpost üretebilir.

**Çözüm: Navbar'da aktif hesap avatarı + badge**
```
┌─────────────────────────────────────────────────────────┐
│ 🔵 TypeHype  🏠  𝕏  ▶  📷  🎵  in  📝  ⚙  [ 🐦▾ ]  │
│                                               @berkay.. │
└─────────────────────────────────────────────────────────┘
```

- Navbar avatarı = **aktif hesabın Twitter avatarı** (auth user avatarı değil)
- Avatarın altında veya yanında `@username` kısaltılmış gösterimi
- Tek hesaplı kullanıcılar: mevcut davranış (avatar + "Berkay")
- Çok hesaplı kullanıcılar: aktif hesap avatarı + `@handle`
- Hesap değişince avatar crossfade animasyonu

### 3. Varlık İzolasyonu — Persona & Stil Profilleri

**Karar: Personalar ve stiller account_id'ye scope'lu**

| Varlık | Scope | Açıklama |
|--------|-------|----------|
| Stil Profilleri (style_profiles) | account_id | Her hesabın kendi klonlanmış stili |
| Özel Personalar (varsa) | account_id | Marka dili ≠ kişisel dil |
| Sistem Personaları (otorite, insider...) | Global | 5 default persona herkese açık |
| Trend'ler | Global | Tüm hesaplardan erişilebilir |
| Account Analysis | Global | Herhangi hesap analiz edilebilir |

**DB değişikliği:**
```sql
ALTER TABLE style_profiles ADD COLUMN account_id UUID REFERENCES connected_accounts(id);

-- Mevcut profilleri ilk hesaba ata (null migration ile birlikte)
UPDATE style_profiles SET account_id = :first_account_id
  WHERE user_id = :user_id AND account_id IS NULL;
```

**Style Lab:** Hesap değişince farklı stil profilleri yüklenir. Marka hesabında
kişisel hesabın "Semih Kışlar" stili görünmez.

### 4. Kredi & Kota — Billing Scope

**Karar: Cüzdan tek (user_id), harcama noktaları çoklu (account_id)**

```
┌──────────────────────────────────┐
│       User: Berkay (100 kredi)   │
│  ┌──────────┐  ┌──────────────┐  │
│  │ @berkay   │  │ @typehype_io │  │
│  │ 67 kredi  │  │ 33 kredi     │  │
│  │ harcandı  │  │ harcandı     │  │
│  └──────────┘  └──────────────┘  │
│       Kalan: 0 kredi             │
└──────────────────────────────────┘
```

- `generations` tablosundaki mevcut `user_id` ile quota kontrol (değişmez)
- Per-account harcama takibi: `account_id` ile raporlama (hangi hesap ne kadar harcadı)
- Limit aşıldığında tüm hesaplar etkilenir (global limit)
- Şu an billing yok ama gelecekte eklendiğinde hazır olacak

### 5. Token/Bağlantı Kopması — Hesap Sağlık Durumu

**Problem:** Twitter cookie/token expire olursa hesap bozuk kalır.

**Çözüm: Hesap sağlık durumu UI**
```
┌────────────────────┐
│ ✅ @berkayaltunel   │  ← Aktif, sağlıklı
│    Kişisel Hesap    │
│ ──────────────────  │
│ ⚠️ @typehype_io    │  ← Token expired
│    Yeniden bağla →  │
└────────────────────┘
```

**DB:**
```sql
ALTER TABLE connected_accounts ADD COLUMN status TEXT DEFAULT 'active';
-- status: 'active' | 'token_expired' | 'suspended' | 'rate_limited'
ALTER TABLE connected_accounts ADD COLUMN last_verified_at TIMESTAMPTZ;
```

**Backend:**
- Periyodik sağlık kontrolü (cron, her 6 saat): hesabın hala erişilebilir olduğunu doğrula
- Hata durumunda `status = 'token_expired'` set et
- Kullanıcı "Yeniden bağla" tıklayınca → ayarlara yönlendir

**Frontend:**
- Dropdown'da sağlık badge'i (✅ / ⚠️)
- Bozuk hesaba geçildiğinde: uyarı banner + "Yeniden Bağla" CTA
- Bozuk hesapta üretim engellenmez ama uyarı gösterilir (scraping çalışmayabilir)

---

## Veritabanı Değişiklikleri (Tam Liste)

### Mevcut `connected_accounts` tablosuna eklenenler
```sql
ALTER TABLE connected_accounts ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE connected_accounts ADD COLUMN last_verified_at TIMESTAMPTZ;
```

### `user_settings` tablosuna eklenenler
```sql
ALTER TABLE user_settings ADD COLUMN active_account_id UUID REFERENCES connected_accounts(id);
```

### Mevcut tablolara `account_id` ekleme
```sql
ALTER TABLE generations ADD COLUMN account_id UUID REFERENCES connected_accounts(id);
ALTER TABLE favorites ADD COLUMN account_id UUID REFERENCES connected_accounts(id);
ALTER TABLE style_profiles ADD COLUMN account_id UUID REFERENCES connected_accounts(id);
ALTER TABLE coach_weekly_plans ADD COLUMN account_id UUID REFERENCES connected_accounts(id);
ALTER TABLE coach_dismissed_cards ADD COLUMN account_id UUID REFERENCES connected_accounts(id);

CREATE INDEX idx_generations_account ON generations(account_id) WHERE account_id IS NOT NULL;
CREATE INDEX idx_favorites_account ON favorites(account_id) WHERE account_id IS NOT NULL;
CREATE INDEX idx_style_profiles_account ON style_profiles(account_id) WHERE account_id IS NOT NULL;
```

### Null Migration (ikinci hesap eklendiğinde çalışır)
```sql
-- Tüm NULL kayıtları kullanıcının ilk (primary) hesabına ata
UPDATE generations SET account_id = :first_id WHERE user_id = :uid AND account_id IS NULL;
UPDATE favorites SET account_id = :first_id WHERE user_id = :uid AND account_id IS NULL;
UPDATE style_profiles SET account_id = :first_id WHERE user_id = :uid AND account_id IS NULL;
UPDATE coach_weekly_plans SET account_id = :first_id WHERE user_id = :uid AND account_id IS NULL;
UPDATE coach_dismissed_cards SET account_id = :first_id WHERE user_id = :uid AND account_id IS NULL;
```

---

## Frontend Mimari

### Account Switcher: Navbar Avatar Dropdown

**Tek hesap (mevcut davranış):**
```
[👤 Berkay ▾] → Ayarlar, Çıkış
```

**Çok hesap:**
```
[ 🐦 @berkay.. ▾] → Hesap listesi + Ayarlar + Çıkış
```

Aktif hesap değişince navbar avatarı = o hesabın Twitter profil fotoğrafı.

### AccountContext (React Context)

```jsx
{
  accounts: [...],            // Tüm connected_accounts (status dahil)
  activeAccount: {...},       // Aktif hesap objesi (avatar, username, status)
  activeAccountId: "uuid",
  switchAccount: (id) => {},  // Hesap değiştir + tüm data refetch
  addAccount: () => {},       // Ayarlara yönlendir
  isMultiAccount: boolean,    // 2+ hesap var mı
  isLoading: boolean,
}
```

### Hesap Değişim Akışı

1. Dropdown'dan hesap seçimi
2. `switchAccount(id)` → backend PATCH + localStorage güncelle
3. Navbar avatarı crossfade
4. Tüm sayfa data'sı fade-out → skeleton → fade-in (300ms)
5. Coach, History, Favorites, Style Lab yenilenir

### Geçiş Animasyonu
- Avatar: 200ms crossfade
- Sayfa: 300ms fade + skeleton
- Toast: "📱 @typehype_io hesabına geçildi"

---

## Backend Değişiklikleri

### Middleware: Active Account Injection

```python
async def get_active_account(user=Depends(require_auth)):
    """Her request'e aktif hesap ID'si inject et."""
    sb = get_supabase()
    res = sb.table("user_settings") \
        .select("active_account_id") \
        .eq("user_id", user.id) \
        .limit(1) \
        .execute()
    return res.data[0]["active_account_id"] if res.data and res.data[0].get("active_account_id") else None
```

### Null Migration Trigger

```python
async def run_null_migration(user_id: str, first_account_id: str, sb):
    """İkinci hesap eklendiğinde tüm NULL dataları ilk hesaba ata."""
    tables = ["generations", "favorites", "style_profiles",
              "coach_weekly_plans", "coach_dismissed_cards"]
    for table in tables:
        sb.table(table) \
            .update({"account_id": first_account_id}) \
            .eq("user_id", user_id) \
            .is_("account_id", "null") \
            .execute()
    logger.info(f"Null migration completed for user {user_id} → account {first_account_id}")
```

### Etkilenen Endpoint'ler

| Endpoint | Değişiklik |
|----------|-----------|
| PUT /accounts/{platform} | İkinci hesapta null migration tetikle |
| POST /generate | `account_id` kaydet |
| GET /generations | `WHERE account_id = :active` |
| GET /favorites | `WHERE account_id = :active` |
| GET /styles/list | `WHERE account_id = :active` |
| GET /coach/feed | account_id bazlı istatistik |
| GET /coach/insights | account_id bazlı |
| GET/POST /coach/weekly-plan | account_id scope |
| POST /coach/dismiss | account_id scope |
| GET /posting-times/* | account_id bazlı |

---

## Uygulama Fazları

### Faz 1: Altyapı (Backend + DB) [~2 gün]
1. DB migration SQL'leri hazırla (Berkay çalıştıracak)
2. Backend middleware: `get_active_account` dependency
3. Null migration fonksiyonu
4. PUT /accounts güncelle (ikinci hesapta migration tetikle)
5. PATCH /settings güncelle (active_account_id)
6. Test: tek hesaplı kullanıcılar etkilenmemeli

### Faz 2: Frontend Switcher [~1.5 gün]
1. AccountContext oluştur
2. Navbar dropdown redesign (hesap listesi + status badge)
3. Aktif hesap avatarı navbar'da
4. switchAccount + data refetch mekanizması
5. Geçiş animasyonu (crossfade + skeleton)

### Faz 3: Data Scoping [~2 gün]
1. Generation endpoint + XAIModule: account_id gönder/filtrele
2. Favorites + History: account_id filtre
3. Style Lab: account_id scope
4. Coach: account_id bazlı feed/insights/plan
5. Posting Times: account_id bazlı

### Faz 4: Polish [~1 gün]
1. Bozuk hesap uyarı UI (⚠️ banner)
2. "Tüm Hesaplar" görünümü (isteğe bağlı, v2.1)
3. Per-account default persona/tone
4. Hesap silme (cascade soft-delete)
5. Sağlık kontrolü cron (6 saatte bir)

---

---

## 🚨 Ek Kırmızı Çizgiler (v2.1)

### 6. Ghost Account → Gerçek Hesap Merge

**Senaryo:** `platform='default'` hesabı olan kullanıcı gerçek Twitter hesabı bağlıyor.

**Akış:**
1. Kullanıcı PUT /accounts/twitter ile gerçek hesap ekliyor
2. Backend: "Bu kullanıcının `platform='default'` hesabı var mı?" kontrol
3. Varsa → **Merge**: Tüm tablolarda `account_id = default_id` olan kayıtları `account_id = new_real_id` olarak güncelle
4. Default hesabı sil (`DELETE FROM connected_accounts WHERE id = default_id`)
5. Yeni hesabı `is_primary = true` yap
6. Log: "Ghost account merged: default → @berkayaltunel"

```python
async def merge_ghost_account(user_id: str, new_account_id: str, sb):
    """Default hesaptaki tüm veriyi gerçek hesaba aktar ve default'u sil."""
    # Default hesabı bul
    default = sb.table("connected_accounts") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("platform", "default") \
        .limit(1).execute()

    if not default.data:
        return  # Ghost account yok, normal akış

    old_id = default.data[0]["id"]
    tables = ["generations", "favorites", "style_profiles",
              "coach_weekly_plans", "coach_dismissed_cards"]

    for table in tables:
        sb.table(table) \
            .update({"account_id": new_account_id}) \
            .eq("account_id", old_id) \
            .execute()

    # Default hesabı sil
    sb.table("connected_accounts").delete().eq("id", old_id).execute()
    logger.info(f"Ghost merge: {old_id} → {new_account_id} for user {user_id}")
```

**Sonuç:** Orphan data yok, kullanıcı verisi korunuyor, default hesap temizleniyor.

### 7. Default Hesap UI Fallback

**Navbar'da `platform='default'` hesap aktifken:**
- Avatar: Anonim silüet (generic user icon)
- İsim: "Hesabım"
- Dropdown'da: "📱 Hesap bağla" CTA belirgin

**Frontend kontrolü:**
```jsx
const isGhostAccount = activeAccount?.platform === 'default';
const displayName = isGhostAccount ? 'Hesabım' : `@${activeAccount.username}`;
const avatarUrl = isGhostAccount ? null : getAvatarUrl(activeAccount);
// null avatar → letter initial fallback (mevcut davranış)
```

---

## 💰 Monetization: Pro Özellik Olarak Multi-Account

### Tier Yapısı

| Tier | Hesap Limiti | Fiyat |
|------|-------------|-------|
| Free | 1 hesap | $0 |
| Pro | 5 hesap | TBD |
| Agency | Sınırsız | TBD |

### DB: Subscription Tracking

```sql
-- user_settings'e tier bilgisi
ALTER TABLE user_settings ADD COLUMN subscription_tier TEXT DEFAULT 'free';
-- 'free' | 'pro' | 'agency'

ALTER TABLE user_settings ADD COLUMN account_limit INT DEFAULT 1;
```

### Backend: Hesap Limit Kontrolü

```python
# PUT /accounts/{platform} endpoint'inde
async def upsert_account(...):
    # Mevcut hesap sayısı
    existing = sb.table("connected_accounts") \
        .select("id", count="exact") \
        .eq("user_id", user.id) \
        .neq("platform", "default") \  # Ghost hesap saymaz
        .execute()
    current_count = existing.count or 0

    # Limit kontrolü
    settings = sb.table("user_settings") \
        .select("account_limit, subscription_tier") \
        .eq("user_id", user.id).single().execute()
    limit = settings.data.get("account_limit", 1) if settings.data else 1

    if current_count >= limit and not existing_account:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACCOUNT_LIMIT",
                "message": "Hesap limitine ulaştın",
                "current": current_count,
                "limit": limit,
                "upgrade_url": "/pricing"
            }
        )
```

### Frontend: Paywall Modal

```
➕ Hesap Ekle → (Free kullanıcı) →

┌─────────────────────────────────────┐
│          🔒 Pro Özellik             │
│                                     │
│  Birden fazla hesap yönetmek için   │
│  Pro plana geçin.                   │
│                                     │
│  ✓ 5 hesap yönetimi                │
│  ✓ Hesap bazlı AI Coach            │
│  ✓ Hesap bazlı stil profili        │
│  ✓ Öncelikli destek                │
│                                     │
│  [ Pro'ya Geç → ]                   │
│                                     │
│  Şu an: Free (1/1 hesap)           │
└─────────────────────────────────────┘
```

### Uygulama Planı

- **Faz 1 (DB):** `subscription_tier` + `account_limit` kolonlarını migration'a ekle
- **Faz 2 (Backend):** Limit kontrolünü endpoint'e koy
- **Faz 2 (Frontend):** Paywall modal component
- **Faz 4 (Polish):** Stripe/LemonSqueezy entegrasyonu (ödeme altyapısı)

---

## Kararlar Özeti

| Karar | Sonuç |
|-------|-------|
| NULL data stratejisi | İlk hesaba ata, yeni hesap sıfır km |
| Navbar görünürlük | Aktif hesap avatarı + @username |
| Persona/Stil scope | account_id'ye bağlı |
| Billing scope | user_id (global cüzdan) |
| Token kopması | Status kolonu + UI badge + uyarı banner |
| Trend'ler | Global (hesap bağımsız) |
| Account Analysis | Global (herhangi hesap analiz edilebilir) |
| URL state | Yok (global context) |
| Ghost → Real merge | Otomatik data transfer + default hesap silme |
| Default hesap UI | Anonim silüet + "Hesabım" + "Hesap bağla" CTA |
| Monetization | Free=1, Pro=5, Agency=sınırsız |
| Billing scope | user_id (global cüzdan, tier bazlı limit) |
