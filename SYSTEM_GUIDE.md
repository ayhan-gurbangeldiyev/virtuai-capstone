# ContentFactory — Sistem Kullanım Kılavuzu

> **Amaç:** Bu repo "Cansu" (@cansubuilds) adlı persona için **otonom AI-haber sosyal medya
> pipeline'ı** içerir. Trend yakalar → haber/kart yazar → kalite kapılarından geçirir →
> Twitter/dev.to/LinkedIn/Instagram/YouTube'a yayınlar. Bu doküman; sistemin ne olduğunu,
> hangi dosyanın ne yaptığını, hangi dosyaların LLM kullandığını, çalışma akışını ve
> altyapıyı **tek yerde** anlatır. Repo dağınık olduğu için bir LLM'in (veya yeni bir
> geliştiricinin) sistemi çözebilmesi için referans noktasıdır.
>
> **Son güncelleme:** 2026-06-14 · **Repo kökü:** `/Users/berkay/.openclaw/workspace/ContentFactory`
> · Dosya referansları repo köküne görelidir (`path:line`).

---

## 1. Genel Bakış (30 saniyede sistem)

- **Ürün:** Otonom içerik fabrikası. Bir persona (Cansu) adına AI-haberlerini takip edip
  Gen-Z diliyle, ölçülü bir sesle çok platforma yayınlar.
- **Üç katman:**
  1. **Frontend (Vercel)** — `typehype.io`, React 19 SPA. Operatör paneli + içerik gözden geçirme.
  2. **Backend API (Hetzner)** — `api.typehype.io`, FastAPI. Veri çekme, trend motoru, yazar API'si, gözden geçirme/onay.
  3. **Hype Crew (Hetzner)** — CrewAI otonom pipeline (cron). Asıl içerik üretimini yapan ajan sistemi.
- **Veri:** Supabase (Postgres + pgvector). Tüm trend/draft/run/config tabloları + LangGraph checkpoint şeması.
- **Kritik gerçek:** Sistem **iki ayrı Python venv** kullanır (backend + hype_crew). Bazı modüller
  (prompt'lar, faithfulness_gate) iki taraftan da kullanılır → deploy ederken ikisini de düşün.

---

## 2. Yüksek Seviye Mimari

```
  [X/Twitter kaynak listesi]            [RSS (legacy, manuel)]
            │ XQuik (ücretli)
            ▼
  hype-trend-fetch  (cron, 4 saatte bir)  ──►  Supabase: trends / tweet_feed / trend_x_sources
            │                                          │
            │ (LangGraph ingest kabuğu, flag ON)       │
            ▼                                          ▼
  hype-crew (cron, SAATLİK)  ── runner.py ── flow.py (CrewAI Flow)
     │
     ├─ TrendScout (lead seçimi, rubrik)        ── LLM: gemini-3-flash-preview (model_fast)
     ├─ Planner (açı/ses/uzunluk)               ── LLM: gemini-3-flash-preview (model_smart)
     ├─ Writer  → TypeHype API /generate-tweet  ── LLM: claude-sonnet-4.6 (writer_model)
     ├─ Compliance (dedup/forbidden/hard rules)
     ├─ Faithfulness gate (T0 NER / T1 / T2)    ── LLM: gemini-3-flash-preview
     ├─ Clarity gate                            ── LLM: gemini-3-flash-preview
     ├─ Visual (opsiyonel)  → Wiro              ── LLM: gemini-flash (sahne) + Wiro (görsel)
     ├─ Video (opsiyonel)   → HeyGen + MiniMax  ── LLM: claude-sonnet (script)
     ▼
  daily_drafts  ──(auto_publish_enabled?)──►  Postiz  ──►  Twitter/devto/linkedin/instagram/youtube
     │  false → pending_review (operatör onayı)
     │  true  → otomatik Postiz schedule
     ▼
  hype-cards (cron, GÜNLÜK 05:00) → kurak-gün SÖZLÜK/SENCE kartları
  (+ haber-sonrası "companion" kartlar flow içinden)

  [hype-exec daemon → Executive Board (CEO/CPO/CBPO/CFO/CRO)]  ⚠️ ŞU AN KAPALI (inactive+disabled, son aktivite 2026-05-29)
```

---

## 3. Prod Topolojisi, venv'ler ve Deploy

### 3.1 Topoloji
| Katman | Nerede | Yol / Adres | Deploy |
|---|---|---|---|
| Frontend | Vercel | `typehype.io` | Repo kökünden `vercel --prod` (veya `frontend/deploy.sh`). **NOT:** Hetzner'daki frontend build LEGACY — kullanıcı ORAYA bakmıyor. |
| Backend API | Hetzner `46.225.27.85` | `/opt/contentfactory/backend` (servis: `contentfactory.service`) | `scp` + drift-check + `systemctl restart contentfactory` |
| Hype Crew | Hetzner `46.225.27.85` | `/opt/hype-crew` | `scp` → oneshot servisler bir sonraki run'da taze okur (restart gerekmez) |
| Executive daemon | Hetzner `46.225.27.85` | `/opt/hype-exec` (servis: `hype-exec.service`) — **şu an inactive + disabled** | bkz. [hype_exec/DEPLOY.md](hype_exec/DEPLOY.md) |
| DB | Supabase | Postgres + pgvector | migration dosyaları `backend/migrations/*.sql` |

### 3.2 İki venv gerçeği (ÇOK ÖNEMLİ)
| venv | Yol | Rolü | Ayırt edici paketler |
|---|---|---|---|
| **backend** | `/opt/contentfactory/backend/venv` | FastAPI API + trend-fetch + supply-health | `fastapi`, `uvicorn`, `xquik`, `psycopg2`, `tenacity`, `langgraph` (ingest için), `gliner` |
| **hype_crew** | `/opt/hype-crew/venv` | CrewAI runner + kartlar + gate'ler | `crewai`, `langgraph`, `psycopg` (v3), `gliner`, `sentence-transformers` |

- Backend hype_crew'dan import etmez; ortak mantık (örn. `faithfulness_gate`) her iki tarafta da bulunur/erişilir.
- Writer prompt'ları (`backend/prompts/style_prompt_v2.py`, `voice_modes.py`) **backend'de** çalışır
  (crew, TypeHype API'sini çağırır → o da contentfactory.service içinde). Yani bu dosyaları
  değiştirince **contentfactory.service restart** gerekir.

### 3.3 Deploy prosedürü (özet)
1. **Drift-check:** prod dosya md5 == git HEAD mi? (`ssh ... md5sum` vs `git show HEAD:...`). Eşleşmiyorsa
   prod elle değişmiş → önce diff'i incele/backport et, sonra deploy.
2. **Yedek:** prod dosyasını `/root/*-pre-*.tgz` veya `.py` olarak yedekle.
3. **scp** → ilgili `/opt/...` yoluna.
4. **md5 doğrula** (local working-tree == prod).
5. **Restart:** backend dosyası ise `systemctl restart contentfactory`; hype_crew dosyası ise
   oneshot servisler taze okur (restart gerekmez) — ama backend de o dosyayı import ediyorsa
   contentfactory restart.
6. **Drift monitor:** `hype-deploy-drift` timer prod==git HEAD karşılaştırır → commit/push ile kapanır.

> Detaylı runbook: [deploy/FAZ2_DEPLOY_RUNBOOK.md](deploy/FAZ2_DEPLOY_RUNBOOK.md)

---

## 4. Servisler ve Cron Takvimi

systemd unit dosyaları `deploy/` dizininde. **Doğrulanmış kilit zamanlamalar:**

| Servis | Tip | Zamanlama | Ne yapar |
|---|---|---|---|
| `contentfactory.service` | sürekli | — | FastAPI API (uvicorn), yazar endpoint'i, onay/gözden geçirme, /control panelleri |
| `hype-crew` | oneshot+timer | **SAATLİK** (`OnCalendar=hourly`) | İçerik pipeline (runner.py → flow.py) |
| `hype-trend-fetch` | oneshot+timer | **4 saatte bir** (`00,04,08,12,16,20:30 UTC`) | XQuik ile X kaynak listesini çek (ücretli) |
| `hype-cards` | oneshot+timer | **GÜNLÜK 05:00 UTC** | Kurak-gün SÖZLÜK/SENCE kartları |
| `hype-exec` | sürekli daemon | **KAPALI** (inactive+disabled; 2026-05-29'dan beri durmuş) | Executive board (LangGraph, insan onayı) — şu an çalışmıyor |
| `hype-trend-supply` | timer | `05:15 UTC` günlük | 24s AI supply sağlık denetimi |
| `hype-engagement` | timer | `00,06,12,18:00` (6 saatte bir) | Yayınlanan içerik etkileşim metrikleri |
| `hype-image-regen` | timer | `OnUnitActiveSec=30` (+OnBoot 60s) | Görsel yeniden-üretim kuyruğu işçisi |
| `hype-regen-watchdog` | timer | `OnUnitActiveSec=60` | Takılı regen draft kurtarma |
| `hype-checkpoint-gc` | timer | `03:30 UTC` günlük | LangGraph checkpoint temizliği (bloat kontrolü) |
| `hype-exec-cleanup` | timer | `weekly` | Executive checkpoint temizliği (>30g) |
| `hype-autonomy-gates` | timer | `03:00 UTC` günlük | Otonomi kapı kontrolü + edit elevation tarama |
| `hype-deploy-drift` | timer | `OnUnitActiveSec=5min` | prod md5 vs git HEAD drift alarmı |
| `hype-quality-check` | timer | `*:00` saatlik | Kalite eşik kontrolü |
| `hype-quality-digest` | timer | `07:00 UTC` günlük | Günlük kalite özeti |
| `hype-quality-audit` | timer | `*-*-01 09:00` aylık | Aylık kalite denetimi |
| `faithfulness-monitor` | timer | `03:30 UTC` günlük | Faithfulness σ-bant metrik izleme |
| `shadow-graduation` | timer | `*:15` ve `*:45` (saatte 2×) | Shadow-mode mezuniyet + devre kesici |

> Tüm zamanlamalar `deploy/*.timer` dosyalarından birebir okundu (2026-06-14). Saatler aksi
> belirtilmedikçe UTC.

---

## 5. İçerik Üretim Akışı (uçtan uca)

**Giriş:** `hype_crew/runner.py` (`run_for_account`). **Orkestrasyon:** `hype_crew/flow.py` (CrewAI Flow).

### 5.1 Pre-flight kontroller (LLM'den ÖNCE — `runner.py`)
Sıra (şiddet): **executive_freeze** (skip, $0) → **daily cost cap** (skip, $0) → **reaper** (>2s takılı
run'ları failed yap) → **stale-scheduling alarm** → **failure-streak alarm** → flow başlat.
- `dry_run_mode` / `auto_publish_enabled` precedence: **DB (`hype_account_config`) kazanır.**

### 5.2 Flow node sırası (`flow.py`)
1. **initialize** — `hype_runs` satırı, dry_run çöz.
2. **run_crew** —
   - **Lever A (deterministik):** `query_trends()` → persona-gate + dedup. **Sıfır aday → `no_candidates`,
     LLM çağrısı YOK** (kuraklıkta sistem burada sessizce durur, çöp basmaz).
   - **Editor's Desk:** `backend/services/editors_desk.select_lead()` — son 3 günü exclude (re-lead memory),
     gelişme marker'ı (kaldırıldı/geri çekildi/çöktü) varsa exclusion düşer.
   - **TrendScout** (LLM): 12-nokta rubrik, content_type, `video_worthy`, `passed`.
   - **Curator override:** `is_curator=true` haber rubrikten elenirse `passed=true` (news-bar kaçış yolu).
   - **URL pre-gate dedup:** kaynak URL 7 gün içinde kullanıldıysa skip (re-share önleme).
   - **Planner** (LLM): `voice_mode`, etki/karakter/uzunluk, brief.
3. **write_via_typehype** — Çok platform paralel üretim. Her platform için `voice_mode` (twitter/instagram →
   first_person_witty; linkedin/devto/blog/youtube → hybrid). **Twitter önce** üretilir, açılışı diğerlerine
   "bu açılışı kullanma" diye yasaklanır (aynı-açılış önleme). Sonra variety-lint + gerekiyorsa 1 retry.
   Sanitize: em-dash→virgül, hashtag/emoji/AI-disclosure strip.
4. **run_compliance** — dedup / forbidden topics / hard rules (HARD blok) + brand-voice skoru (advisory).
   Hard ihlalde CRO auto-freeze tetiklenebilir.
5. **faithfulness_gate** + **clarity_gate** (aşağıda Bölüm 6.2).
6. **visual_branch** (opsiyonel, `persona.visual_enabled`) — Wiro görsel + 4 katman görsel kapısı. NON-FATAL.
7. **video_branch** (opsiyonel, `persona.video_enabled` + video hedefi + trend video-worthy/skor) —
   HeyGen + MiniMax TTS. Script faithfulness + konu-uyumu guard'ı; günlük video bütçesi ($5). NON-FATAL.
8. **publish_branch vs dry_run_branch:**
   - `auto_publish_enabled=false` → `daily_drafts` satırı **`pending_review`**, Postiz YOK (operatör onayı:
     `/hype/drafts/:id/approve`).
   - `auto_publish_enabled=true` → Postiz schedule (medya tek upload, platformlar paylaşır), modality
     unlock + platform allowlist enforce, `GuardedPostizClient.assert_publishable()`.
   - Yayından sonra **companion kartlar** zamanlanır (Bölüm 11).

### 5.3 Yayın durum kodları (`daily_drafts.status`)
`pending` (üretildi) · `pending_review` (operatör onayı bekliyor) · `auto_scheduled` (Postiz'e verildi) ·
`auto_published` (yayınlandı).

---

## 6. Ajanlar, Kapılar (Gates) ve Ses Sistemi

### 6.1 CrewAI Ajanları
| Ajan | Dosya | LLM | Rolü |
|---|---|---|---|
| **TrendScout** | [hype_crew/agents/trendscout.py](hype_crew/agents/trendscout.py) · prompt [trendscout_prompt.py](hype_crew/prompts/trendscout_prompt.py) | `model_fast` = **gemini-3-flash-preview** (prod .env doğrulandı) | Lead trend seçimi, 12-nokta rubrik, VIP marka tanıma, politika-komşu reddi |
| **Planner** | [hype_crew/agents/planner.py](hype_crew/agents/planner.py) · prompt [planner_prompt.py](hype_crew/prompts/planner_prompt.py) | `model_smart` = **gemini-3-flash-preview** (prod .env doğrulandı) | Açı/brief + `voice_mode` haritalama (hafıza-güdümlü) |
| **Visual Director** | [hype_crew/agents/visual_director.py](hype_crew/agents/visual_director.py) | `model_smart` | Sahne/mood/kıyafet + Wiro tetik (opsiyonel) |
| **Writer** | *ajan DEĞİL* → [hype_crew/tools/typehype_client.py](hype_crew/tools/typehype_client.py) | **claude-sonnet-4.6** (`writer_model` config default; env override yok) | Taslak yazımı backend `/api/internal/generate-tweet`'e devredilmiş; sadece writer adımı Sonnet, gate/editor/dedup gemini-flash'ta kalır |

### 6.2 Kalite Kapıları (hepsi fail-closed: şüphede REDDET → pending_review)
| Kapı | Dosya | Model | Ne yapar |
|---|---|---|---|
| **Faithfulness** | [hype_crew/tools/faithfulness_gate.py](hype_crew/tools/faithfulness_gate.py) | GLiNER (lokal) + `gemini-3-flash-preview` | **T0:** NER grounding — GLiNER threshold `0.45`, fuzzy eşleşme `≥85`, eksik entity → HARD_BLOCK. **T1:** claim entailment — grounding oranı `< 0.9` (`claim_grounding_floor`) → blok. **T2:** "uydurma tez/yeni-entity/nedensel iddia" hakimi (gri-bölge). **Arbiter:** blok temyizi — sayısal eşik YOK, LLM ihlali `fp`/`minor`/`fabrication` diye sınıflar; fp/minor → blok kalkar, fabrication → kalır, hata → fail-closed (blok korunur). **Soft (2026-06-14):** politik/pazar spekülasyonu için `speculative` WARN — block ETMEZ, sadece loglar. |
| **Clarity** | [hype_crew/tools/clarity_gate.py](hype_crew/tools/clarity_gate.py) | `gemini-3-flash-preview` | Net/doğal Türkçe mi, jargon/AI-dili var mı; "siz" → "sen" sadeleştirme. fail-open. |
| **Card gates** | [hype_crew/tools/card_gates.py](hype_crew/tools/card_gates.py) | `gemini-3-flash-preview` | SÖZLÜK: correct+clear+voice+**curiosity**; SENCE: ai_related+open_opinion+appropriate+**evocative** (4'ü AND). |
| **Compliance** | [hype_crew/tools/compliance_tools.py](hype_crew/tools/compliance_tools.py) | deterministik | dedup (pgvector/Jaccard 7g), forbidden topics, hard rules |

### 6.3 Ses / Prompt sistemi (Cansu "ölçülü beat" sesi)
- **`backend/prompts/style_prompt_v2.py`** — Cansu DNA (`_build_ghost_writer_identity`). `voice_mode !=
  third_person_neutral` ise aktif. **2026-06-14 düzeltmesi:** zorunlu kontrast-opener + zorunlu maxim
  KALDIRILDI → "tek somut beat / kontrast ancak kaynakta gerçekse / maxim yok / spekülasyon yok".
- **`backend/prompts/voice_modes.py`** — Tonal çerçeve: `first_person_witty` (Cansu 1. şahıs), `hybrid`
  (3. şahıs haber + 1. şahıs ölçülü kapanış), `third_person_neutral` (Cansu için YASAK). Ayrıca TTS video
  kuralları, tekrar-yasağı, grounding kuralları.
- **`hype_crew/tools/cansu_voice.py`** — `build_cansu_directive`: kimlik + kesin yasaklar (em-dash, hashtag,
  emoji, reveal açılışı, maxim kapanış, 3. şahıs ajans tonu, **politik/jeopolitik/pazar spekülasyonu**,
  uydurma). Görüş bütçesi DÜŞÜK.

---

## 7. Dış Servisler ve LLM Kullanım Haritası ⭐

> Bu bölüm "hangi dosya LLM kullanıyor, hangi servis ne işe yarıyor" sorusunun cevabıdır.

### 7.1 Dış servis kataloğu
| Servis | Ne işe yarar | Dosya(lar) | Maliyet modeli | Env anahtarı (DEĞER yok) |
|---|---|---|---|---|
| **XQuik** | X/Twitter veri çekme (extraction + lookup + account) | [backend/services/xquik_client.py](backend/services/xquik_client.py) | Kredi-tabanlı; extraction=hesap-başı, lookup=tweet-başı, **radar ÜCRETSİZ**, /account ÜCRETSİZ | `XQUIK_API_KEY` |
| **Quota Manager** | XQuik kalan kredi + degradasyon | [backend/services/quota_manager.py](backend/services/quota_manager.py) | ücretsiz (10dk cache) | `QUOTA_BALANCE_NORMAL/REDUCED/MINIMAL` |
| **TypeHype** | Writer (taslak üretimi) | [hype_crew/tools/typehype_client.py](hype_crew/tools/typehype_client.py) | ~$0.001-0.01/çağrı | `TYPEHYPE_API_URL`, `CRON_SECRET` |
| **OpenRouter** | LLM broker (gemini/claude/gpt) | [hype_crew/tools/llm_router.py](hype_crew/tools/llm_router.py), gate'ler | model-spesifik | `OPENROUTER_API_KEY` |
| **OpenAI** | embedding, trend enrichment | `backend/embed_tweets.py`, `backend/services/trend_enrichment.py` | usage | `OPENAI_API_KEY` |
| **Wiro** | Görsel üretimi (i2i) | `hype_crew/tools/wiro_client.py`, `framed_news_image.py` | generation başına | `WIRO_API_KEY/SECRET` |
| **HeyGen** | Avatar video | `hype_crew/tools/heygen_client.py` | video başına | `HEYGEN_API_KEY` |
| **MiniMax** | Türkçe TTS (Cansu sesi) | `hype_crew/config.py` | karakter başına | `MINIMAX_*` |
| **Postiz** | Çok platform yayın | `hype_crew/tools/postiz_client.py`, `guarded_postiz.py` | 30 req/saat | `POSTIZ_API_KEY` |
| **Supabase** | Veri + checkpoint | her yerde | abonelik | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |
| **GLiNER** | NER (faithfulness T0) | [faithfulness_gate.py](hype_crew/tools/faithfulness_gate.py) | lokal CPU, ücretsiz | `FAITHFULNESS_NER_REQUIRED` |

### 7.2 LLM çağrısı yapan dosyalar (tablo)
| Dosya | Adım | Model | Çağrı yolu |
|---|---|---|---|
| `hype_crew/agents/trendscout.py` | TrendScout | gemini-3-flash-preview (`settings.model_fast`) | CrewAI |
| `hype_crew/agents/planner.py` | Planner | gemini-3-flash-preview (`settings.model_smart`) | CrewAI |
| `hype_crew/tools/typehype_client.py` | Writer | claude-sonnet-4.6 (`settings.writer_model`) | TypeHype API |
| `hype_crew/tools/card_gates.py` | Kart kalite | google/gemini-3-flash-preview | OpenRouter / LiteLLM Router |
| `hype_crew/tools/faithfulness_gate.py` | T1/T2/Arbiter | google/gemini-3-flash-preview | OpenRouter / LiteLLM Router |
| `hype_crew/tools/dictionary_card.py`, `question_card.py` | Kart üretimi | google/gemini-3-flash-preview | OpenRouter |
| `hype_crew/tools/clarity_gate.py` | Netlik | google/gemini-3-flash-preview | OpenRouter |
| `hype_crew/tools/video_script_writer.py`, `video_caption_writer.py` | Video script | claude-sonnet | OpenRouter (model="writer") |
| `hype_crew/tools/visual_director_tools.py`, `visual_decision.py` | Görsel strateji/brief | gemini-flash | OpenRouter |
| `backend/services/editors_desk.py` | Lead sıralama | claude-sonnet | httpx (OpenRouter) |
| `backend/services/home_composer.py` | Home hero cümle | claude-sonnet | httpx (OpenRouter) |
| `backend/services/trend_enrichment.py` | Trend zenginleştirme | gpt-4o-mini | OpenAI |
| `hype_exec/*` | Executive board | gemini-3-flash / gemini-pro | Google Gemini / OpenRouter |

> **Model adları config/env ile değişir.** Kod sabitleri: gate/kart dosyalarında
> `_MODEL = "google/gemini-3-flash-preview"`. Crew ajanları `settings.model_fast/model_smart`.

### 7.3 LiteLLM Router
- Flag: `HYPE_LITELLM_ROUTER_ENABLED` (**bu oturumda CANLI/ON**). Açıkken gate/tool LLM çağrıları
  uniform timeout+retry+cooldown katmanından geçer; kapalıyken çıplak httpx/CrewAI yolu.
- Model alias'ları: `gate-fast`, `writer` (claude-sonnet), `vision`. Dosya:
  [hype_crew/tools/llm_router.py](hype_crew/tools/llm_router.py).

### 7.4 XQuik maliyet modeli (sık karıştırılır)
- `twitter_items=159` = **dönen tweet sayısı, API çağrısı DEĞİL.**
- Gerçek tüketim/run ≈ **~24 extraction** (aktif hesap-başı: ai_core 13 + ai_news_en 6 + ai_tech 2 +
  ai_news_tr 2) + **~10 lookup** (enrichment-skip AÇIK, normalde ~150; ~%94 kısık) ≈ ~34 çağrı.
- **4 saatte bir × ~34 ≈ ~200 çağrı/gün.** "~335K kredi bütçe" bir KOD YORUMU
  ([twitter_trend_fetcher.py:447](backend/services/twitter_trend_fetcher.py)), ölçülen değer DEĞİL.
  **Gerçek kalan kredi henüz ölçülmedi** — kota telemetrisi 2026-06-14'e kadar kördü (yanlış alan
  okuyordu); fix sonrası ilk fetch `api_cache.quota:status`'a gerçek `creditInfo.balance`'ı yazacak.
  O görülene kadar "runway" tahmini spekülatiftir.
- enrichment-skip flag: `TREND_ENRICH_SKIP_ENABLED=1` (zaten enrich'li tweet'i 48s TTL içinde lookup'tan çıkar).
- Kota okuma: `/account` → `creditInfo.balance` (**2026-06-14 fix**: eskiden olmayan `quotaRemaining`
  alanını okuyup hep "%0/normal" görüyordu = kör; artık gerçek balance + fail-loud).

---

## 8. LangGraph ve Dayanıklılık

| Katman | Dosya | Flag | Durum |
|---|---|---|---|
| **X-Ingestion** | [backend/lg/ingest_graph.py](backend/lg/ingest_graph.py), [backend/lg/checkpointer.py](backend/lg/checkpointer.py) | `TREND_INGEST_LANGGRAPH_ENABLED` | **CANLI (ON).** Her trend fetch graph kabuğundan geçer; checkpoint Supabase `langgraph` şemasına. |
| **İçerik pipeline** | [hype_crew/lg/graph.py](hype_crew/lg/graph.py), `card_graph.py`, `checkpointer.py` | `HYPE_LANGGRAPH_ENABLED` (+ per-account `hype_account_config.langgraph_enabled`) | **CANLI** (prod .env `HYPE_LANGGRAPH_ENABLED=true` doğrulandı; run logları `via=langgraph`). LangGraph dayanıklılık sarmalı aktif; CrewAI ajanları (TrendScout/Planner) bu sarmalın İÇİNDE çalışır. (Config default OFF'tur ama prod ON.) |
| **Executive** | [hype_exec/graph.py](hype_exec/graph.py) | (daemon) | **ŞU AN KAPALI** (hype-exec.service inactive+disabled; son DB aktivitesi 2026-05-29). Çalıştığında: insan-onayı interrupt'lı LangGraph daemon. |

- **Checkpointer:** prod=AsyncPostgresSaver (Supabase `langgraph` şeması, `search_path` izole,
  `prepare_threshold=0` pooler uyumu); dev=SQLite fallback.
- **Idempotency:** `migrations/025_langgraph_resume.sql` — `uq_daily_drafts_run_platform_ctype`,
  `uq_hype_stages_run_order` (resume'da çift yazım yok).
- **Node-state binding (içerik flow):** [hype_crew/lg/graph.py](hype_crew/lg/graph.py) `flow.py`'nin
  AYNI node/edge'lerini sarar (`StateGraph(HypeFlowState)` — pydantic, sıralı, reducer yok). Node'lar:
  initialize → run_crew → write → compliance → visual → video → publish/dry_run/skip/fail. Node
  metotlarında `asyncio.run()` adaları olduğu için **sync** `graph.invoke` + `sync_checkpointer`
  kullanılır (ainvoke değil). Her node'dan sonra checkpoint yazılır (crash-safe). Resume `thread_id =
  run_id` ile; **poison-run koruması** (MED-4): bir run belirli sayıda resume edilip hâlâ
  tamamlanamıyorsa sonsuz döngü kesilir.

---

## 9. Supabase Şema Kataloğu (kilit tablolar)
| Tablo | Amaç | Kilit kolonlar |
|---|---|---|
| `trends` | Trend kaynakları (lead havuzu) | topic, category, score, url, raw_content, full_source_text, is_curator, is_vip, cluster_id, key_angles, suggested_hooks, source_tweets (PK=`id`; daily_drafts.trend_id buna bakar) |
| `daily_drafts` | Üretilen taslaklar/kartlar | status, platform, content, **voice_mode**, **content_type**, trend_id, scheduled_at, postiz_post_id, source_url, rejection_reason |
| `hype_account_config` | Hesap ayarları | **auto_publish_enabled**, **dry_run_mode**, **executive_freeze**, **langgraph_enabled**, allowed_publish_platforms, daily_post_quota, forbidden_topics |
| `personas` | Persona ayarları (DB tablosu) | **video_enabled**, video_autonomy_unlocked, **daily_video_budget_usd**, video_min_trend_score, primary_account_id |
| `trend_x_sources` | XQuik kaynak hesapları | batch_type (ai_core/ai_news_en/ai_news_tr/ai_tech/ai_curator), username, is_active |
| `trend_fetch_runs` | Fetch tetik/sonuç telemetrisi | status, triggered_by, twitter_items, trends_saved, started_at/finished_at |
| `trend_fetch_batch_stats` | Per-batch fetch istatistiği | run_id, batch_type, username, tweets_fetched, attempts |
| `card_history` | Kart dedup geçmişi | account_id, card_kind, key_text |
| `api_cache` | L2 cache (kota vb.) | cache_key (`quota:status`), data (jsonb), expires_at |
| `hype_runs` / `hype_stages` | Run + ajan adım telemetrisi (Crew Akışı paneli) | hype_runs: status, dry_run, flow_state(jsonb), draft_content, daily_draft_id, postiz_post_id, scheduled_at, total_tokens, total_cost_usd, resume_attempts · hype_stages: run_id, agent_name, stage_order, input/output(jsonb), model_used, tokens_used, guardrail_retries, status |
| `image_render_log` / `video_render_log` | Görsel/video write-ahead defteri (maliyet koruması) | image: persona_id, prompt_sha, slug, image_url, status, est_cost_usd, run_id, consumed_at · video: pipeline, script_sha, heygen_video_id, narration_url, status, est_cost_usd, duration_sec |
| `executive_decisions` / `_meetings` / `_memos` | Executive board kayıtları | decisions: role_responsible, decision_type, decision_text, target_table/id, old/new_value, status, threshold_breach, rationale_memo, approved_by · meetings: kind, attendees, agenda, transcript, decisions_made_ids · memos: author_role, kind, content, visibility |

---

## 10. Operatör / Executive (hype_exec) ve Kontrol Paneli
- **hype_exec** = ayrı LangGraph daemon (5 rol: CEO/CPO/CBPO/CFO/CRO). ⚠️ **ŞU AN ÇALIŞMIYOR** —
  `hype-exec.service` inactive + disabled, son DB aktivitesi **2026-05-29** (291 toplantı / 258 karar /
  369 memo geçmişi var ama ~16 gündür durgun; boot'ta da açılmaz). Aşağıdaki davranış *çalıştığında*
  geçerlidir. Tekrar açmak: `systemctl enable --now hype-exec.service`. Çalışırken: 5 rol saatlik/günlük/haftalık
  toplanır, eşik aşımında **insan onayı** ister (`executive_decisions.status=awaiting_approval`),
  Supabase'e karar/memo/transcript yazar. Giriş: [hype_exec/main.py](hype_exec/main.py),
  graph [hype_exec/graph.py](hype_exec/graph.py).
- **Backend API:** [backend/routes/exec.py](backend/routes/exec.py) — `/exec/decisions` (approve/reject/revert),
  `/exec/memos`, `/exec/meetings`. Frontend bunları operatöre gösterir.
- **Kill-switch:** `hype_account_config.executive_freeze=true` → tüm content run'ları skip (daemon
  çalışmaya devam eder ama karar execute etmez).
- **Operatör panelleri (frontend):** `/control/sistem` (teknik), `/control/health` (özet), Crew Akışı
  (hype_runs/hype_stages görselleştirme), draft onay kuyruğu.
- **"OpenClaw" ne demek:** Özel bir entegrasyon DEĞİL — kod ve dokümanlarda ([docs/SYSTEM_DOCUMENTATION.md:140](docs/SYSTEM_DOCUMENTATION.md))
  "OpenClaw Cron" sadece **harici bir HTTP cron** (belirli saatlerde `X-Cron-Secret` ile endpoint'i
  dürten herhangi bir zamanlayıcı) anlamında geçer; servise bağımlılık yok. Tetikleme bugün aslında
  **systemd timer'ları** ile yapılıyor. `hype_exec` daemon'u çalıştığında systemd (`hype-exec.service`)
  + Supabase **`realtime_listener`** ([hype_exec/main.py:68](hype_exec/main.py), `listener.realtime_listener`)
  ile tetiklenir (saatlik/günlük/haftalık loop + olay dinleyici) — ama **şu an servis kapalı.**

---

## 11. SÖZLÜK / SENCE Kart Sistemi
- **Amaç:** Kuraklık-dolgusu (AI haberi yokken) ve haber-sonrası tamamlayıcı içerik.
- **Üreticiler:** [hype_crew/tools/dictionary_card.py](hype_crew/tools/dictionary_card.py) (SÖZLÜK = gerçek
  AI terimi + sade açıklama), [hype_crew/tools/question_card.py](hype_crew/tools/question_card.py) (SENCE =
  hafif, tek cümle, anında-çağrışımlı soru). Kapı: [card_gates.py](hype_crew/tools/card_gates.py).
- **Zamanlayıcı:** [hype_crew/tools/card_scheduler.py](hype_crew/tools/card_scheduler.py)
  - **Kurak gün** (`schedule_drought_cards`): günde 4 kart, alternatif tip, İstanbul prime saatleri
    (`has_recent_news` false ise). `hype-cards` cron'u (05:00) tetikler.
  - **Companion** (`schedule_companion_cards`): haber-sonrası 1 SÖZLÜK + 1 SENCE, haberin slot'undan sonra.
  - **Çift-çift fix (2026-06-14):** `assign_kinds_chronological` — birleşik zaman çizelgesinde her slot
    komşusunun ZIDDI atanır; companion kuyruğun SONUNA çapalanır → asla iki aynı tip arka arkaya.

---

## 12. Flag'ler ve Env Anahtarları (sadece isim)
| Flag / Anahtar | Etki |
|---|---|
| `auto_publish_enabled` (DB) | false → pending_review; true → Postiz canlı yayın |
| `dry_run_mode` (DB) | true → sadece log/draft |
| `executive_freeze` (DB) | run'ları durdur (kill-switch) |
| `langgraph_enabled` (DB) / `HYPE_LANGGRAPH_ENABLED` | içerik pipeline LangGraph sarmalı — **prod=true (CANLI)** |
| `TREND_INGEST_LANGGRAPH_ENABLED` | X-ingestion LangGraph — **prod=1 (CANLI)** |
| `HYPE_LITELLM_ROUTER_ENABLED` | LiteLLM Router (CANLI) |
| `TREND_ENRICH_SKIP_ENABLED` (+`_TTL_HOURS`) | XQuik enrichment-skip (CANLI) |
| `FAITHFULNESS_NER_REQUIRED` | GLiNER zorunlu (prod true) |
| `QUOTA_BALANCE_NORMAL/REDUCED/MINIMAL` | kota degradasyon eşikleri (50K/20K/5K) |
| `CANSU_VIDEO_V2_ENABLED`, `CANSU_FRAME_I2I_ENABLED`, `CANSU_CARDS_PUBLISH_ENABLED` | video/görsel/kart yayın bayrakları |

> Gizli değerler `backend/.env` ve `hype_crew/.env` içinde (git'te DEĞİL). Bu dosyalara değer yazma/echo etme.

---

## 13. Güncel Notlar ve Doğrulama
- **2026-06-14 bu oturumda canlıya alınanlar:** ölçülü haber sesi (DNA çelişkisi çözüldü),
  SÖZLÜK/SENCE kart kalite çıtası, kart tip rotasyonu (çift-çift fix), XQuik kota parse fix (kör nokta).
- **Drift:** Tüm değişiklikler git'e commit+push edildi (main). Prod==git HEAD olmalı.
- **2026-06-14 denetim düzeltmeleri (prod .env'e karşı doğrulandı):** Model haritası düzeltildi —
  TrendScout/Planner/Visual = `gemini-3-flash-preview` (gpt-4o DEĞİL), Writer = `claude-sonnet-4.6`.
  İçerik-pipeline LangGraph **prod'da CANLI** (`HYPE_LANGGRAPH_ENABLED=true`), "dormant" değil. "335K
  bütçe" bir kod yorumu; gerçek kalan kredi henüz ölçülmedi. Bayat `crew_factory.py` docstring'i
  (gpt-4o) düzeltildi. **Executive/CEO daemon (hype_exec) ŞU AN KAPALI** — `hype-exec.service`
  inactive+disabled, son aktivite 2026-05-29; önceki sürüm "24/7 CANLI" diyordu, yanlıştı.
- **Doğrulama kaynakları (bu kılavuzdaki tüm iddialar şunlara karşı kontrol edildi):** prod `.env`
  (model + flag değerleri), Supabase `information_schema` (tablo + kolonlar), `deploy/*.timer` (tüm
  zamanlamalar), canlı run logları (`via=langgraph`), `api_cache` (kota durumu) ve kaynak kod
  (`config.py`, `flow.py`, `lg/graph.py`, gate'ler). Her satır yer-gerçeğinden onaylıdır.

---

*Tüm iddialar 2026-06-14'te yer-gerçeğine (prod .env, Supabase information_schema, deploy/*.timer,
canlı loglar, kaynak kod) karşı doğrulandı. Sistem değiştikçe güncel tutulmalı — özellikle Bölüm 4
(cron), 7 (LLM haritası) ve 12 (flag'ler).*
