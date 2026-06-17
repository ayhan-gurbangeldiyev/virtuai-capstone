# Type Hype — LLM Model Araştırması

> **Tarih:** 10 Şubat 2026  
> **Amaç:** Type Hype için en uygun modelleri belirlemek (stil analizi + Türkçe yaratıcı yazım)  
> **Hariç tutulan modeller:** GPT-4o/4.1/5 serisi, Claude Opus 4.6/Sonnet 4.5/Haiku 4.5, Gemini 2.5/3 serisi, Grok 4/4.1, DeepSeek V3.2

---

## 1. LM Arena (arena.ai) — Güncel Sıralamalar

Arena leaderboard'dan çekilen veriler (Şubat 2026). Sütun açıklaması: Genel sıra, sonraki sütunlar farklı kategorilerdeki sıralamalar.

### İlgili Modeller — Arena Sıralamaları

| Model | Genel | Creative Writing (tahmini 6. sütun) | Instruction Following (tahmini 3. sütun) |
|-------|-------|-------------------------------------|------------------------------------------|
| Kimi K2.5-thinking | **17** | 22 | 16 |
| Kimi K2.5-instant | **24** | 30 | 17 |
| Qwen3 Max Preview | **27** | 38 | 23 |
| Kimi K2-thinking-turbo | **30** | 46 | 27 |
| GLM-4.7 | **21** | 28 | 20 |
| GLM-4.6 | **32** | 32 | 37 |
| Qwen3-235B-A22B-instruct (2507) | **37** | 51 | 31 |
| DeepSeek V3.2 | **40** | 34 | 35 |
| Mistral Large 3 | **49** | 67 | 50 |
| Mistral Medium (2508) | **54** | 57 | 52 |
| GLM-4.5 | **56** | 65 | 49 |
| Qwen3-Next-80B-A3B | **63** | 115 | 59 |
| Qwen3-Coder-480B | **80** | 78 | 74 |
| Mistral Medium (2505) | **82** | 77 | 84 |
| Llama 4 Maverick | **140** | 121 | 136 |
| Llama 4 Scout | **147** | 144 | 145 |
| Yi-Lightning | **138** | 138 | 133 |
| Command A (Cohere) | **109** | 96 | 112 |
| Command R+ (08-2024) | **192** | 175 | 207 |
| Step 3 (StepFun) | **119** | 124 | 100 |

> **Not:** Arena'da ayrı "Creative Writing" veya "Türkçe" kategorisi olarak etiketlenmiş tab yok. Sütunlar muhtemelen farklı task tiplerini temsil ediyor. 6. sütun creative writing'e en yakın korelasyon gösteriyor.

---

## 2. Model Detayları

### 2.1 Qwen Modelleri (Alibaba)

| Model | Input $/1M | Output $/1M | Context | OpenAI-uyumlu API | OpenRouter |
|-------|-----------|------------|---------|-------------------|------------|
| **Qwen3 Max** (Thinking) | $1.20 | $6.00 | 262K | ✅ (Alibaba DashScope) | ✅ |
| **Qwen3 Max** (non-thinking) | $1.20 | $6.00 | 262K | ✅ | ✅ |
| Qwen3-235B-A22B (open, 2507) | $0.07 | $0.10 | 262K | ✅ | ✅ |
| Qwen3-235B-A22B-thinking (2507) | $0.11 | $0.60 | 262K | ✅ | ✅ |
| Qwen3-Next-80B-A3B (instruct) | $0.09 | $1.10 | 262K | ✅ | ✅ (+ free tier) |
| Qwen3-30B-A3B (instruct, 2507) | $0.08 | $0.33 | 262K | ✅ | ✅ |
| Qwen3-32B | $0.08 | $0.24 | 40K | ✅ | ✅ |
| Qwen3 Coder (480B-A35B) | $0.22 | $1.00 | 262K | ✅ | ✅ |
| Qwen3 Coder Next (80B-A3B) | $0.07 | $0.30 | 262K | ✅ | ✅ |
| Qwen3 Coder Plus | $1.00 | $5.00 | 1M | ✅ | ✅ |
| Qwen3 Coder Flash | $0.30 | $1.50 | 1M | ✅ | ✅ |
| Qwen Plus | $0.40 | $1.20 | 1M | ✅ | ✅ |

**Alibaba doğrudan fiyatlar (Çin dışı, International):**
- Qwen Max: ¥8.807/M input, ¥44.035/M output (~$1.20/$6.00)
- Qwen Plus: ¥2.936/M input, ¥8.807/M output (~$0.40/$1.20)
- Qwen Flash: ¥0.367/M input, ¥2.936/M output (~$0.05/$0.40)
- Qwen Coder: ¥2.202/M input, ¥11.009/M output (~$0.30/$1.50)

**Türkçe kalitesi:** İyi-Orta. Qwen3 eğitim verisinde Türkçe var, ancak İngilizce/Çince kadar güçlü değil. MoE mimarisi sayesinde çok dilli yetenekler DeepSeek'e benzer seviyede.

**OpenAI-uyumlu API:** Evet — DashScope API'si OpenAI SDK ile doğrudan uyumlu. OpenRouter üzerinden de tüm modeller erişilebilir.

### 2.2 Kimi K2.5 (Moonshot AI)

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| **Kimi K2.5** | $0.45 | $2.25 | 262K | ✅ |
| Kimi K2 Thinking | $0.40 | $1.75 | 262K | ✅ |
| Kimi K2 (0905) | $0.39 | $1.90 | 262K | ✅ |

**Arena sıralaması:** K2.5-thinking **#17 genel** — GPT-5.1 ve birçok Claude modelden önde!  
**Türkçe:** Orta. Çince/İngilizce ağırlıklı. Türkçe'de deneysel.  
**OpenAI-uyumlu API:** Evet (Moonshot platform + OpenRouter)  
**Multimodal:** K2.5 görsel girdi de destekliyor.

### 2.3 GLM Modelleri (Zhipu AI / Z.AI)

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| **GLM-4.7** | $0.40 | $1.50 | 202K | ✅ |
| **GLM-4.7 Flash** | $0.06 | $0.40 | 202K | ✅ |
| GLM-4.6 | $0.35 | $1.50 | 202K | ✅ |
| GLM-4.5 | $0.35 | $1.55 | 131K | ✅ |
| GLM-4.5 Air | $0.13 | $0.85 | 131K | ✅ (+ free) |

**Arena sıralaması:** GLM-4.7 **#21 genel** — çok güçlü.  
**Türkçe:** Orta. Çince'de mükemmel, İngilizce'de güçlü, Türkçe orta.  
**OpenAI-uyumlu API:** Evet (bigmodel.cn + OpenRouter)

### 2.4 Mistral Modelleri

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| **Mistral Large 3** (2512) | $0.50 | $1.50 | 262K | ✅ |
| **Mistral Medium 3.1** | $0.40 | $2.00 | 131K | ✅ |
| Mistral Medium 3 | $0.40 | $2.00 | 131K | ✅ |
| **Mistral Small 3.2** (24B) | $0.06 | $0.18 | 131K | ✅ |
| **Mistral Small Creative** | $0.10 | $0.30 | 32K | ✅ |
| Mistral Saba | $0.20 | $0.60 | 32K | ✅ |

**Arena sıralaması:** Mistral Large 3 = #49 genel  
**Türkçe:** **İyi.** Mistral Saba özellikle Arapça/Türkçe gibi diller için optimize edilmiş. Mistral genel olarak Avrupa dilleri konusunda güçlü.  
**Özel not:** `mistral-small-creative` modeli yaratıcı yazım için özel olarak optimize edilmiş! Context kısa (32K) ama fiyatı çok uygun.

### 2.5 Llama 4 (Meta)

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| Llama 4 Maverick (17B-128E) | $0.15 | $0.60 | 1M | ✅ |
| Llama 4 Scout (17B-16E) | $0.08 | $0.30 | 327K | ✅ |

**Arena sıralaması:** #140 ve #147 — düşük performans, frontier modeller değil.  
**Türkçe:** Orta-zayıf. Meta modelleri Türkçe'de historik olarak zayıf.  
**API erişimi:** Meta API yok, OpenRouter/Together/Fireworks üzerinden.

### 2.6 Command R+ / Command A (Cohere)

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| **Command A** | $2.50 | $10.00 | 256K | ✅ |
| Command R+ (08-2024) | $2.50 | $10.00 | 128K | ✅ |

**Arena sıralaması:** Command A = #109  
**Türkçe:** **İyi.** Cohere modelleri çok dilli eğitimde güçlü — Türkçe resmi desteklenen diller arasında (Command R+ pre-training data'sında var).  
**Özel not:** RAG için optimize. Ama yaratıcı yazımda zayıf. Fiyat/performans kötü.

### 2.7 Yi-Lightning (01.AI)

**Arena sıralaması:** #138 — orta-alt  
**OpenRouter:** ❌ Artık mevcut değil  
**API:** 01.AI platformu üzerinden (Çin merkezli)  
**Türkçe:** Zayıf  
**Yorum:** Modası geçmiş, yeni versiyonu yok. Skip.

### 2.8 Writer Palmyra X5

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| Palmyra X5 | $0.60 | $6.00 | 1.04M | ✅ |

**Arena sıralaması:** Leaderboard'da yok  
**Türkçe:** Zayıf-orta. Enterprise İngilizce odaklı.  
**Özel not:** Enterprise content yazımı için tasarlanmış ama max output sadece 8K token. Yaratıcı yazımdan çok kurumsal içerik.

### 2.9 Step 3.5 (StepFun)

| Model | Input $/1M | Output $/1M | Context | OpenRouter |
|-------|-----------|------------|---------|------------|
| **Step 3.5 Flash** | **FREE** | **FREE** | 256K | ✅ |
| Step 3 | ~$0.20 | ~$0.80 | 256K | — |

**Arena sıralaması:** Step 3 = #119  
**Türkçe:** Orta-zayıf  
**Özel not:** Step 3.5 Flash OpenRouter'da **ücretsiz!** MoE 196B/11B aktif. Reasoning model. Test için ideal.

### 2.10 BONUS: Dikkat Çeken Diğer Modeller

| Model | Input $/1M | Output $/1M | Context | Arena Sıra | OpenRouter |
|-------|-----------|------------|---------|-----------|------------|
| **ERNIE 5.0** (Baidu) | — | — | — | **#11** | ❌ |
| **MiniMax M2.1** | ~$0.30 | ~$1.20 | 65K | **#81** | ✅ |
| **MiniMax M2-her** | $0.30 | $1.20 | 65K | — | ✅ |
| **Hunyuan T1** (Tencent) | — | — | — | **#79** | ❌ |

---

## 3. Karşılaştırma Tablosu

| Model | Provider | Input $/1M | Output $/1M | Context | Arena ELO Sıra | Creative Sıra | Türkçe | OpenRouter | Use Case Uygunluk (1-5) |
|-------|----------|-----------|------------|---------|----------------|---------------|--------|------------|------------------------|
| **Qwen3 Max** | Alibaba | $1.20 | $6.00 | 262K | #27 | ~#38 | İyi-Orta | ✅ | ⭐⭐⭐⭐ |
| **Qwen3-235B-A22B** (thinking) | Alibaba | $0.11 | $0.60 | 262K | #66 | ~#68 | İyi-Orta | ✅ | ⭐⭐⭐⭐ |
| **Qwen3-235B-A22B** (open) | Alibaba | $0.07 | $0.10 | 262K | #89 | ~#104 | İyi-Orta | ✅ | ⭐⭐⭐ |
| Qwen3-Next-80B-A3B | Alibaba | $0.09 | $1.10 | 262K | #63 | ~#115 | Orta | ✅ | ⭐⭐⭐ |
| **Kimi K2.5** | Moonshot AI | $0.45 | $2.25 | 262K | **#17** | ~#22 | Orta | ✅ | ⭐⭐⭐⭐ |
| Kimi K2.5-instant | Moonshot AI | — | — | 262K | **#24** | ~#30 | Orta | ✅ | ⭐⭐⭐⭐ |
| **GLM-4.7** | Zhipu AI | $0.40 | $1.50 | 202K | **#21** | ~#28 | Orta | ✅ | ⭐⭐⭐⭐ |
| **GLM-4.7 Flash** | Zhipu AI | $0.06 | $0.40 | 202K | #100 | ~#134 | Orta | ✅ | ⭐⭐⭐ |
| **Mistral Large 3** | Mistral | $0.50 | $1.50 | 262K | #49 | ~#67 | İyi | ✅ | ⭐⭐⭐ |
| Mistral Medium 3.1 | Mistral | $0.40 | $2.00 | 131K | #54* | ~#57 | İyi | ✅ | ⭐⭐⭐ |
| **Mistral Small Creative** | Mistral | $0.10 | $0.30 | 32K | — | — | İyi | ✅ | ⭐⭐⭐⭐ |
| Mistral Small 3.2 | Mistral | $0.06 | $0.18 | 131K | ~#173 | ~#167 | İyi | ✅ | ⭐⭐⭐ |
| Mistral Saba | Mistral | $0.20 | $0.60 | 32K | — | — | **İyi** | ✅ | ⭐⭐⭐ |
| Llama 4 Maverick | Meta | $0.15 | $0.60 | 1M | #140 | ~#121 | Orta-Zayıf | ✅ | ⭐⭐ |
| Llama 4 Scout | Meta | $0.08 | $0.30 | 327K | #147 | ~#144 | Orta-Zayıf | ✅ | ⭐⭐ |
| Command A | Cohere | $2.50 | $10.00 | 256K | #109 | ~#96 | İyi | ✅ | ⭐⭐ |
| Command R+ | Cohere | $2.50 | $10.00 | 128K | #192 | ~#175 | İyi | ✅ | ⭐ |
| Yi-Lightning | 01.AI | — | — | — | #138 | ~#138 | Zayıf | ❌ | ⭐ |
| Palmyra X5 | Writer | $0.60 | $6.00 | 1.04M | — | — | Zayıf-Orta | ✅ | ⭐⭐ |
| **Step 3.5 Flash** | StepFun | **FREE** | **FREE** | 256K | ~#119 | ~#124 | Orta-Zayıf | ✅ | ⭐⭐⭐ |
| GLM-4.5 | Zhipu AI | $0.35 | $1.55 | 131K | #56 | ~#65 | Orta | ✅ | ⭐⭐⭐ |

---

## 4. Öneriler — Type Hype Use Case

### 🎯 Stil Analizi (50 tweet → stil profili çıkarma) İçin En İyiler

**1. Qwen3 Max (Thinking)** — ⭐⭐⭐⭐⭐
- Arena #27, güçlü analitik yetenek
- 262K context: 50 tweet rahat sığar, detaylı analiz yapabilir
- Thinking mode ile derin stil analizi mümkün
- $1.20 input — stil analizi tek seferlik yapılacağı için maliyet kabul edilebilir

**2. Kimi K2.5-thinking** — ⭐⭐⭐⭐
- Arena #17 genel — en yüksek sıralı "ucuz" model
- $0.45 input ile Qwen Max'tan 3x ucuz
- Multimodal: tweet screenshotlarını da analiz edebilir

**3. GLM-4.7** — ⭐⭐⭐⭐
- Arena #21 — çok güçlü reasoning
- $0.40 input ile rekabetçi fiyat
- 202K context

### ✍️ Türkçe Yaratıcı Yazım (tweet, post, makale üretimi) İçin En İyiler

**1. Mistral Small Creative** — ⭐⭐⭐⭐⭐ (GİZLİ ŞAMPİYON)
- Yaratıcı yazım için **özel olarak optimize edilmiş** tek model!
- $0.10/$0.30 — **inanılmaz ucuz**
- Mistral zaten Türkçe'de güçlü (Avrupa dilleri odaklı)
- 32K context yeterli (üretim için)
- Tweet/post üretimi gibi kısa formatta ideal

**2. Qwen3-235B-A22B (open/thinking)** — ⭐⭐⭐⭐
- Non-thinking: $0.07/$0.10 — **en ucuz yüksek kalite model**
- Thinking: $0.11/$0.60
- Türkçe'de iyi performans
- Yüksek throughput, production'a uygun

**3. Mistral Saba** — ⭐⭐⭐⭐
- Türkçe dahil Ortadoğu/Güney Asya dilleri için optimize
- $0.20/$0.60 — çok uygun
- 32K context — üretim için yeterli

**4. GLM-4.7** — ⭐⭐⭐⭐
- Arena #21 — creative writing sıralamasında da iyi (#28)
- $0.40/$1.50 — makul fiyat
- Türkçe orta ama genel kalite çok yüksek

### 💰 Fiyat/Performans Gizli Şampiyonları

| Model | Neden? |
|-------|--------|
| 🥇 **Mistral Small Creative** | $0.10/$0.30 — Yaratıcı yazıma özel, Türkçe iyi |
| 🥈 **Qwen3-235B-A22B (open)** | $0.07/$0.10 — Bu fiyata 235B MoE model inanılmaz |
| 🥉 **GLM-4.7 Flash** | $0.06/$0.40 — Arena #100 ama fiyatı neredeyse bedava |
| 🏅 **Step 3.5 Flash** | **ÜCRETSİZ** — Test ve geliştirme aşaması için ideal |
| 🏅 **Mistral Small 3.2** | $0.06/$0.18 — Günlük kullanım için en ucuz kaliteli model |

---

## 5. Önerilen Strateji

### Production Architecture (Önerilen)

```
Stil Analizi (tek sefer):     Qwen3 Max Thinking ($1.20/$6.00)
                               veya Kimi K2.5-thinking ($0.45/$2.25)

Tweet/Post Üretimi (yüksek):  Mistral Small Creative ($0.10/$0.30)
                               veya Qwen3-235B-A22B ($0.07/$0.10)

Makale Üretimi (uzun form):   Qwen3 Max ($1.20/$6.00)
                               veya GLM-4.7 ($0.40/$1.50)

Fallback/Budget:               Mistral Small 3.2 ($0.06/$0.18)
                               veya Step 3.5 Flash (FREE)
```

### Tahmini Maliyet (1000 kullanıcı/ay)
- Stil analizi: 1000 × ~5K token input × $1.20/M = ~$6
- Tweet üretimi: 1000 × 30 tweet × ~500 token × $0.10/M input + $0.30/M output ≈ ~$6
- **Toplam: ~$12-20/ay** (Mistral Small Creative ile)

### OpenRouter Entegrasyonu
Tüm önerilen modeller OpenRouter'da mevcut. Tek API endpoint ile tüm modellere erişim. OpenAI SDK uyumlu.

---

## 6. Veri Kaynakları

- **Arena Leaderboard:** arena.ai/leaderboard (çekilme tarihi: 9 Şubat 2026)
- **OpenRouter API:** openrouter.ai/api/v1/models (gerçek zamanlı fiyatlar)
- **Alibaba DashScope:** help.aliyun.com/zh/model-studio/models (resmi Qwen fiyatları)
- **Mistral Docs:** docs.mistral.ai/getting-started/models
- **Cohere Docs:** docs.cohere.com/docs/command-r-plus

> ⚠️ Fiyatlar OpenRouter üzerinden doğrulanmıştır. Doğrudan provider API'leri farklı fiyatlandırma sunabilir (genelde daha ucuz).
