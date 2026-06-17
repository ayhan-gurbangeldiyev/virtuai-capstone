# Cansu Voice Samples v2 — Post Engineer-Frame Perde Cure (2026-06-08)

**Context**: The first pass (commit `0c47a11`) killed the contrarian perde but the Semih-DNA path produced a NEW perde — 8/9 drafts opened with "mühendis olarak / mühendis gözüyle bakınca" (engineer-frame) + several added "asıl ilginç olan şu" / "asıl önemli olan" (reveal-template). The engineering being **announced** is itself a perde, same class as the contrarian frame.

**This pass**: kill the engineer-frame perde without restoring any of the contrarian content.

**State on prod**:
- `hype_account_config.active_style_profile_id = NULL` for both Cansu accounts (`4f13b200…` + `2b731bf7…`)
- v2 profile row `fd2c092a-64d8-4d9a-9532-a6395f7ad25a` stays in `style_profiles` for audit (no longer read)
- Writer: `anthropic/claude-sonnet-4.6` via `model_override` (gate/editor/dedup stay on Gemini Flash)
- Handle normalization + source_tweets union + gate over-block fixes all KEPT
- All `0c47a11` strippings stay GONE (contrarian_shock, mystery_reveal, perde_arkasi, otorite, insider personas, _VARIETY_SHAPES)

**Audit**: 0 banned-phrase hits across 9 drafts (extended 27-entry ban list + self-ref opener regex). 0 retries needed — directive + persona cleanup made the LLM stop producing the perde naturally.

**Cost**: $0.4994 for 9 drafts (59,456 tokens, Sonnet 4.6 @ $8.40/Mtok blended).

---

## STORY 1 — Claude coding-leap (AnthropicAI)

### Twitter
```
Claude'un açık uçlu kodlama sorularındaki başarı oranı 6 ayda 26%'dan 76%'ya çıktı.

50 puanlık bir sıçrama bu.
```
*[111 chars, 4,476 tokens, 0 violations]*

### LinkedIn
```
Anthropic, Claude'un açık uçlu kodlama problemlerindeki başarı oranının 6 ayda 26%'dan 76%'ya çıktığını açıkladı.

50 puanlık artış sadece hız değil, belirsiz problemlerde doğru karar verme kapasitesi anlamına geliyor.

Araştırma yargısı henüz net değil ama bu ivme devam ederse tablo çok farklı görünecek.
```
*[306 chars, 5,259 tokens, 0 violations]*

### YouTube (TTS-safe narrative)
```
Altı ayda elli puanlık sıçrama kolay görünmüyor. Claude'un açık uçlu kodlama problemlerindeki başarı oranı yüzde yetmiş altıya ulaştı. Mayıs iki bin yirmi beş itibarıyla ortalama hız artışı yaklaşık üç kat. Bir modelin araştırma kararlarını — hangi problemi çalışmaya değer bulduğunu — henüz tam olarak verip veremediği belirsiz. Bu fark, araştırma sürecinin hangi adımında insan yargısının zorunlu kaldığını doğrudan sorgulatıyor.
```
*[431 chars, 9,986 tokens, 0 violations]*

---

## STORY 2 — Perplexity SBA $25M (perplexity_ai)

### Twitter
```
Perplexity, ABD Küçük İşletmeler İdaresi ile ortaklaşarak 100.000 şirkete toplam 25 milyon dolarlık kredi dağıtıyor.

Şirket başına 250 dolar — küçük görünüyor ama bu kadar geniş ölçekte ilk kez böyle bir şey yapılıyor.
```
*[219 chars, 4,481 tokens, 0 violations]*

### LinkedIn
```
Perplexity, ABD Küçük İşletmeler İdaresi ile ortaklaşarak 100.000 şirkete toplam 25 milyon dolarlık kredi taahhüt etti — şirket başına 250 dolar.

Büyük oyuncuların AI'a erişimi çoktan var. Bu program tam da ortadaki boşluğu kapatmaya çalışıyor.
```
*[245 chars, 5,200 tokens, 0 violations]*

### YouTube
```
Perplexity, ABD Küçük İşletmeler İdaresi ile ortaklaşa Main Street AI Accelerator programını başlattı. Yirmi beş milyon dolarlık kredi taahhüdü var. Yüz bin şirkete, her birine iki yüz elli dolar bilgisayar kredisi verilecek. Aynı zamanda Perplexity'nin Pro ve Max aboneleri artık Nvidia'nın yeni açık modeli Nemotron üç Ultra'ya erişebiliyor. Model uzun süreli ajan görevleri için tasarlandı. Küçük işletme sahibiyseniz bu program fena bir başlangıç noktası.
```
*[459 chars, 9,954 tokens, 0 violations]*

---

## STORY 3 — Cloudflare bots-vs-humans (webtekno)

### Twitter
```
İnternetin trafiğinin %57,4'ü artık botlardan geliyor.

Cloudflare verisi bu — ilk kez insanlar azınlıkta kaldı.
```
*[112 chars, 4,613 tokens, 0 violations]*

### LinkedIn
```
İnternetin trafiğinin yarısından fazlası artık insan değil.

Cloudflare verilerine göre %57,4'ü botlardan geliyor. İnsan trafiği %42,6'da kaldı.

Web analitiğine bakan herkesin bunu hesaba katması gerekiyor — "ziyaretçi" sayısının yarısından fazlası gerçek bir insan değil.
```
*[273 chars, 5,384 tokens, 0 violations]*

### YouTube
```
Cloudflare'in verilerine göre internet trafiğinde botlar insanları ilk kez geçti. Trafiğin yüzde elli yedi nokta dördü botlardan geliyor. İnsan kaynaklı trafik yüzde kırk iki nokta altıda kaldı. Yani internette gezinen her on bağlantının altısı artık insan değil. Bu rakamlar benim için soyut değil; arama sıralamaları, içerik tüketimi, site analitiği hepsini yeniden okumak gerekiyor.
```
*[385 chars, 10,103 tokens, 0 violations]*

---

## Observations: v1 → v2 voice comparison

| Aspect | v1 (with Semih DNA, post-0c47a11) | v2 (perde-killed, post-this-commit) |
|---|---|---|
| Engineer-frame opener | **8/9 leaked**: "Mühendis olarak söyleyeyim", "Mühendis gözüyle bakınca" | **0/9** leaked |
| Reveal template | **4/9 leaked**: "asıl ilginç olan şu", "asıl önemli olan kısım" | **0/9** leaked |
| Contrarian opener | 0/9 (already killed in 0c47a11) | 0/9 (stays killed) |
| Substance-direct openers | Mixed | **Consistent**: "Claude'un başarı oranı… çıktı", "İnternetin trafiğinin %57,4'ü…", "Perplexity… 100.000 şirkete…" |
| Engineering shows via | Self-tag ("as an engineer") | **What Cansu notices**: "belirsiz problemlerde doğru karar verme kapasitesi", "ortadaki boşluğu kapatmaya çalışıyor", "arama sıralamaları, içerik tüketimi, site analitiği hepsini yeniden okumak" |
| Question/CTA close | 0/9 (gone since 0c47a11) | 0/9 (stays gone) |
| Cost per draft | $0.063 | $0.055 (slightly down — shorter, no retry needed) |

---

## What was removed / kept / NOT-restored

### Removed (this pass)
- DB: `UPDATE hype_account_config SET active_style_profile_id = NULL` for both Cansu accounts
- `hype_crew/flow.py`: rewritten `cansu_directive` (no more `"hafif mühendis görüşü ('mühendis olarak beni heyecanlandıran şu')"` instruction; replaced with explicit ❌/✅ examples)
- `backend/prompts/personas.py` `uzman` entry: identity no longer starts with `"Sen konunun mühendisisin"`; writing_rules dropped `"Mühendis olarak / bence işin altında şu var"`; voice_characteristics dropped `"Hafif teknik görüş — 'mühendis olarak şu' kadar"`
- `_CANNED_PHRASES_GLOBAL_BAN` in flow.py: 10 → 27 entries (engineer-frame + reveal-template additions)
- `_violates_variety` extended to scan WHOLE text (not just opener), with self-ref regex against every paragraph

### Kept (do NOT touch)
- Sonnet 4.6 writer routing: `hype_crew/config.py`, `hype_crew/tools/typehype_client.py`, `backend/server.py` `get_model_config(model_override=...)`, `backend/routes/hype_internal.py` (forwards override), `hype_crew/callbacks/supabase_logger.py` (Sonnet rate)
- Handle normalization: `backend/routes/hype_internal.py:_normalize_source_handles`
- Source-tweets union: writer-side in `hype_crew/flow.py` (`_trend_raw_content_cache`), gate-side in `backend/routes/hype.py` (commit `a96e9e3`)
- Gate over-block fixes: `hype_crew/tools/faithfulness_gate.py` `_URL_ACCOUNT_TO_ENTITY` + acronym aliases + numeric symmetry

### NOT-restored (stays gone from `0c47a11`)
- `backend/prompts/hooks.py` `contrarian_shock` + `mystery_reveal`
- `backend/prompts/derinlik.py` `perde_arkasi`
- `backend/prompts/personas.py` `otorite` + `insider`
- `hype_crew/flow.py` `_VARIETY_SHAPES`, `_CONTRARIAN_SHAPE_KEY`, `_RECENT_OPENER_SIGNATURES`, `_OVERUSED_OPERATIONAL_PHRASES`
- Old cansu_directive opener-shape menu + "operasyonel olarak / iş akışı" word list

**Both perdes (contrarian + engineer-frame) stay killed.**

Auto-publish stays OFF. POSTIZ_PUBLISH_ALLOW_NON_UI not set in prod.
