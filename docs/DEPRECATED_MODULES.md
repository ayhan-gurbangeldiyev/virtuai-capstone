# Kullanılmayan / Deprecated Modüller — Repo Haritası

> **Amaç:** Bu repo klonlanıp otomatik bir AI raporu hazırlanırken, neyin **aktif** neyin
> **ölü (kullanılmıyor)** olduğunu doğru göstermek. Aşağıdaki dosyalar repoda **referans için**
> tutuluyor ama aktif uygulama akışının parçası **DEĞİL**. Kod dosyalarının başında da
> `@deprecated KULLANILMIYOR` işareti vardır.
>
> **Tarih:** 2026-06-14 · **Yöntem:** statik + fonksiyon-içi (lazy) import + systemd
> (`deploy/*.service|*.timer`) + GitHub Actions + dinamik dispatch çapraz-kontrolü; her aday
> **tüm repoda** doğrulandı (cross-dir `hype_crew→backend` import'ları dahil).
> **Güven:** Yüksek (import grafiği deterministik). Şüpheli olanlar ayrı bölümde, işaretlenmedi.

---

## 1. Siteden kaldırılan sayfalar (route + menü silindi, dosya @deprecated)
Frontend, 2026-06-14. Route `App.js`'ten, menü `DashboardLayout.jsx` / `ControlChrome.jsx`'ten kaldırıldı.
Dosyalar `frontend/src/pages/` altında duruyor ama erişilemez.

| Sayfa | Eski route | Dosya |
|---|---|---|
| Kalite Denetimi | /dashboard/quality-audit | `QualityAuditPage.jsx` |
| Otonomi Skoru | /dashboard/autonomy-score | `AutonomyScorePage.jsx` |
| Düzenleme Önerileri | /dashboard/edit-elevations | `EditElevationsPage.jsx` |
| Sistem Sağlığı | /dashboard/system-health | `SystemHealthPage.jsx` |
| Sistem (huni paneli) | /dashboard/sistem | `SystemFunnelPage.jsx` |

> Not: i18n etiketleri (`nav.qualityAudit`, `nav.autonomyScore`, `nav.editElevations`,
> `nav.systemHealth` + `qualityAudit.*` / `autonomyScore.*` / `editElevations.*` / `systemHealth.*`
> ad alanları) `locales/tr.json` + `en.json`'da artık **kullanılmıyor** (silinmedi).

---

## 2. Kesin kullanılmayan dosyalar (doğrulandı — 0 import/çağrı, @deprecated işaretli)

### Frontend — orphan sayfalar (`frontend/src/pages/`)
Hiçbir yerden import edilmiyor, route/nav yok, lazy import yok (eski modül sürümleri):
`BlogArchitectModule.jsx`, `CreateHub.jsx`, `InstaFlowModule.jsx`, `LinkShareModule.jsx`,
`TikTrendModule.jsx`, `XAIModuleV2.jsx`, `XAIModuleV3.jsx`, `XAIModuleV4.jsx`, `YouTubeModule.jsx`

### Frontend — orphan component'ler (`frontend/src/components/`)
`DashboardLayout.sidebar.jsx` (eski sidebar), `ProfileSwitcher.jsx`, `StyleSelector.jsx`, `SidebarLayout.jsx`

### Backend (`backend/`)
- **Fine-tune kümesi (kayıtsız):** `routes/finetune.py` (server.py'de `include_router` YOK → erişilemez) +
  `services/together_finetune.py` (yalnız finetune.py kullanıyor).
- **Servisler:** `services/account_analyzer.py`, `services/tweet_collector.py` (sıfır çağrı).
- **Prompt'lar:** `prompts/builder_v2_lite.py`, `prompts/skeleton_strip.py`, `prompts/hooks.py`.
- **Scriptler (systemd/workflow'a bağlı değil):** `scripts/collect_apify.py`, `scripts/collect_apify_topics.py`,
  `scripts/collect_apify_topics_v2.py`, `scripts/collect_viral_tweets.py`, `scripts/prepare_finetune_data.py`,
  `scripts/home_composer_sample_run.py`.

### hype_crew (`hype_crew/tools/`)
- `wiro_whisper_client.py` (yalnız fal_whisper_client yorumunda anılıyor; instance yok).
- `video_caption_writer.py` (`build_video_captions()` hiç çağrılmıyor; içinde LiteLLM wiring var ama
  fonksiyonun kendisi flow/pipeline'dan çağrılmadığı için ölü).

### Kök
- `content_factory.py` (eski n8n webhook pipeline; `.github/workflows/run.yml` → `if: false`).

---

## 3. Dormant (ölü DEĞİL — yalnızca manuel tetik)
- **`rss_fetcher.py`** — `.github/workflows/rss-fetcher.yml` ile **manuel** (`workflow_dispatch`) çalışır.
  RSS cron'u 2026-04-07'de XQuik batch + Radar lehine kapatıldı, ama script operasyonel — **silinmedi,
  @deprecated işaretlenmedi.**

---

## 4. ⚠️ "Ölü sanılıp aslında AKTİF" olanlar (yanlış-pozitif — DOKUNULMADI)
Statik grep bunları "0 import" gösterdi ama `hype_crew→backend` cross-dir / lazy import'la **canlılar**:
- `backend/services/editors_desk.py` — `hype_crew/flow.py:1179` `from backend.services.editors_desk import select_lead, persist_judgment` (editor's-desk / re-lead).
- `backend/prompts/brand_visual_brief_builder.py` — `hype_crew/flow.py:346` import ediyor.
- `hype_crew/tools/llm_router.py` + LiteLLM-bağlı gate'ler (visual_decision, news_headline, clarity_gate,
  curated_photo_selector, pronunciation_resolver, tts_quality_gate, voice_tools, video_topic_guard,
  video_script_writer, faithfulness_gate, image_text_check, compliance/llm_judge) — fonksiyon-içi lazy +
  flag-gated (`HYPE_LITELLM_ROUTER_ENABLED`). **AKTİF.**

---

## 5. Ölü / kırık wiring (bilgi — düzeltme bu işin kapsamında değil)
- `backend/server.py` — `trends_router` ve `account_analysis_router` **çift kayıtlı** (iki kez import +
  `include_router`); `account_analysis` için fazladan kullanılmayan import.
- `backend/routes/mcp.py:999` — `trend_engine.refresh_all(include_twitter_search=True)` çağrısı **kırık**
  (fonksiyon imzası argümansız → çağrıldığında TypeError). Aynı hata `backend/routes/trends.py:341`'de de var.

---

## 6. Aktif giriş noktaları (rapor-AI için: BUNLAR ÇALIŞIYOR)
- **Pipeline:** `hype_crew/runner.py` → `flow.py` → `crew_factory.py` (+ `lg/*` LangGraph) — `hype-crew.service` (saatlik).
- **C-suite daemon:** `hype_exec/main.py` (graph/scheduler/listener/worker) — `hype-exec.service` (sürekli).
- **Backend API:** `backend/server.py` (FastAPI) — `contentfactory.service`.
- **Cron scriptleri:** `backend/scripts/run_trend_fetch.py` (`hype-trend-fetch`), `run_supply_health_check.py`
  (`hype-trend-supply`), + diğer `deploy/*.timer` wired script'ler.
- **Frontend:** `frontend/` (React, Vercel → typehype.io). Aktif `/control/*` (Home, Sağlık, Seçimler,
  Lifecycle) + `/dashboard/*` (create, trends, crew-flow, social, auto-drafts vb.).
