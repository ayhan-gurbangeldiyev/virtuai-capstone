# Fine-Tuning Model Araştırması: Viral Sosyal Medya İçerik Üretimi

**Tarih**: 11 Şubat 2026
**Proje**: Type Hype / ContentFactory
**Amaç**: Viral tweet, thread, quote üretimi için en uygun fine-tuning stratejisi

---

## 1. Executive Summary

### 🥇 Düşük Bütçe (Önerilen Başlangıç): GPT-4.1-nano Fine-tuning
- **Training**: $1.50/1M token | **Inference**: $0.20 input, $0.80 output /1M token
- 500 tweet ile başla, OpenAI API üzerinden 10 dakikada fine-tune et
- Toplam başlangıç maliyeti: ~$2-5 (ilk fine-tune)
- **Neden**: En düşük maliyet, sıfır infra, anında başla, Türkçe kalitesi yeterli

### 🥈 Orta Bütçe (En İyi Değer): Qwen3-8B + Unsloth (LoRA) via Together AI
- **Training**: $0.48/1M token (Together AI) veya ücretsiz (Colab + Unsloth)
- **Inference**: $0.18/1M token (Together AI serverless)
- Açık kaynak, kendi adapter'ını eğit, istediğin yerde çalıştır
- **Neden**: Mükemmel Türkçe, yaratıcı yazıda güçlü, esnek hosting

### 🥉 Yüksek Bütçe (Maksimum Kalite): GPT-4.1-mini Fine-tuning
- **Training**: $5.00/1M token | **Inference**: $0.80 input, $3.20 output /1M token
- Daha büyük model kapasitesi, daha iyi stil yakalama
- **Neden**: OpenAI ekosistemi, en iyi genel kalite, production-ready

---

## 2. Detaylı Model Karşılaştırma Tablosu

### 2.1 API Tabanlı (Managed Fine-tuning)

| Model | Boyut | FT Yöntemi | Training $/1M tok | Inference $/1M tok (in/out) | Min Veri | Türkçe (1-5) | Yaratıcı (1-5) | Hosting | Açık Kaynak |
|-------|-------|-----------|-------------------|---------------------------|----------|-------------|----------------|---------|-------------|
| GPT-4.1-nano | ~küçük | SFT | $1.50 | $0.20 / $0.80 | 10 örnek | 3.5 | 3.5 | API | Hayır |
| GPT-4.1-mini | ~orta | SFT | $5.00 | $0.80 / $3.20 | 10 örnek | 4 | 4.5 | API | Hayır |
| GPT-4.1 | ~büyük | SFT | $25.00 | $3.00 / $12.00 | 10 örnek | 4.5 | 5 | API | Hayır |
| Mistral Small/7B | 7B | SFT (LoRA) | ~$4 min ücret | API fiyatı değişken | 50+ örnek | 3 | 3.5 | API | Kısmen |
| Gemini (tuning) | değişken | SFT | Ücretsiz (sınırlı) | Gemini API fiyatları | 20+ örnek | 4 | 4 | API | Hayır |

### 2.2 Açık Kaynak + Platform (Together AI / Fireworks)

| Model | Boyut | FT Yöntemi | Training $/1M tok | Inference $/1M tok (in/out) | Min Veri | Türkçe (1-5) | Yaratıcı (1-5) | Hosting | Platform |
|-------|-------|-----------|-------------------|---------------------------|----------|-------------|----------------|---------|----------|
| Qwen3-8B | 8B | LoRA/Full | $0.48 (Together LoRA) | $0.18 / $0.18 | 50+ | 4.5 | 4 | Both | Together/Fireworks |
| Qwen3-4B | 4B | LoRA/Full | $0.48 (Together LoRA) | ~$0.10 / $0.10 | 50+ | 4 | 3.5 | Both | Together/Fireworks |
| Qwen3-30B-A3B (MoE) | 30B (3B aktif) | LoRA | $0.48 | $0.15 / $1.50 | 50+ | 5 | 4.5 | Both | Together |
| Llama 3.1-8B | 8B | LoRA/Full | $0.48 / $0.54 | $0.18 / $0.18 | 50+ | 3 | 3.5 | Both | Together/Fireworks |
| Llama 3.2-3B | 3B | LoRA/Full | $0.48 / $0.54 | $0.06 / $0.06 | 50+ | 2.5 | 3 | Both | Together |
| Gemma 3-4B | 4B | LoRA/Full | $0.48 / $0.54 | $0.10 / $0.10 | 50+ | 3.5 | 3.5 | Both | Together/Fireworks |
| Gemma 3-12B | 12B | LoRA/Full | $0.48 | $0.20 / $0.20 | 50+ | 4 | 4 | Both | Together/Fireworks |
| Mistral 7B v0.2 | 7B | LoRA/Full | $0.48 / $0.54 | $0.20 / $0.20 | 50+ | 3 | 3.5 | Both | Together/Fireworks |
| DeepSeek-V3.1 | 671B MoE | LoRA | $10.00 | $0.60 / $1.70 | 100+ | 4.5 | 4.5 | API | Together ($20 min) |
| gpt-oss-20B | 20B | LoRA/Full | $0.48 (16B altı) | $0.05 / $0.20 | 50+ | 3.5 | 4 | Both | Together/Fireworks |

### 2.3 Self-Host (Unsloth + Kendi GPU)

| Model | Boyut | FT Yöntemi | Training Maliyeti | Inference Maliyeti | Min VRAM | Türkçe (1-5) | Yaratıcı (1-5) | Not |
|-------|-------|-----------|-------------------|-------------------|----------|-------------|----------------|-----|
| Qwen3-8B | 8B | QLoRA (Unsloth) | Ücretsiz (Colab) | Ücretsiz (local) | 6GB (4bit) | 4.5 | 4 | Colab T4 yeterli |
| Qwen3-4B | 4B | QLoRA (Unsloth) | Ücretsiz (Colab) | Ücretsiz (local) | 4GB (4bit) | 4 | 3.5 | En hafif seçenek |
| Llama 3.1-8B | 8B | QLoRA (Unsloth) | Ücretsiz (Colab) | Ücretsiz (local) | 6GB (4bit) | 3 | 3.5 | İngilizce güçlü |
| Gemma 3-4B | 4B | QLoRA (Unsloth) | Ücretsiz (Colab) | Ücretsiz (local) | 4GB (4bit) | 3.5 | 3.5 | Google kalitesi |
| gpt-oss-20B | 20B | QLoRA (Unsloth) | Ücretsiz (Colab) | ~$0.05-0.10/1M | 12GB (4bit) | 3.5 | 4 | Yeni, umut vaat eden |
| Phi-4 | 14B | QLoRA (Unsloth) | Ücretsiz (Colab) | Ücretsiz (local) | 8GB (4bit) | 3 | 3 | Reasoning güçlü, yaratıcı orta |

---

## 3. Model Bazlı Pros/Cons

### GPT-4.1-nano (OpenAI)
**Pros**: En düşük API maliyeti, sıfır infra, hızlı fine-tune, iyi Türkçe desteği, anında production-ready
**Cons**: Kapalı kaynak, veri OpenAI'a gider, model küçük olduğu için karmaşık stilleri kaçırabilir, vendor lock-in

### GPT-4.1-mini (OpenAI)
**Pros**: Çok iyi kalite/fiyat oranı, güçlü yaratıcı yazı, mükemmel instruction following
**Cons**: nano'dan 3x pahalı inference, kapalı kaynak, veri gizliliği endişesi

### GPT-4.1 (OpenAI)
**Pros**: En yüksek kalite, en iyi stil yakalama, 1M context window
**Cons**: Çok pahalı ($25/1M training, $12/1M output), bütçe aşımı riski yüksek

### Qwen3-8B (Alibaba)
**Pros**: Mükemmel Türkçe (çok dilli eğitim), açık kaynak, Apache 2.0, Unsloth ile ücretsiz eğitim, Together AI'da ucuz inference, thinking/non-thinking mode
**Cons**: Çince ağırlıklı pre-training (bazen Çince sızıntı olabilir), self-host gerekebilir

### Qwen3-30B-A3B (MoE)
**Pros**: 30B kapasitesi 3B aktif parametre maliyetiyle, çok iyi Türkçe, inference'da hızlı
**Cons**: MoE modeller fine-tune'da trickier olabilir, Together AI'da yeni

### Llama 3.1-8B / 3.3-70B (Meta)
**Pros**: Devasa community, tonlarca fine-tune deneyimi, iyi dokümantasyon, her platformda desteklenir
**Cons**: Türkçe orta seviye (İngilizce ağırlıklı), 70B pahalı

### Gemma 3-4B/12B (Google)
**Pros**: Küçük ama kaliteli, Google'ın eğitim verisi kalitesi, iyi çok dilli destek
**Cons**: Gemma lisansı (bazı kısıtlamalar), community Llama/Qwen kadar büyük değil

### DeepSeek-V3.1
**Pros**: 671B MoE, çok güçlü, Türkçe iyi
**Cons**: Fine-tune çok pahalı ($10/1M + $20 minimum), Çin veri endişeleri, büyük model

### Mistral 7B
**Pros**: Avrupa yapımı, iyi İngilizce/Fransızca, hızlı
**Cons**: Türkçe zayıf (Avrupa dilleri odaklı), fine-tune minimum $4

### gpt-oss-20B (OpenAI Açık Kaynak)
**Pros**: OpenAI kalitesi açık kaynak olarak, 20B güçlü boyut, Unsloth desteği, Together/Fireworks'te ucuz
**Cons**: Çok yeni (Şubat 2026), community deneyimi az, lisans detayları kontrol edilmeli

### Phi-4 (Microsoft)
**Pros**: Boyutuna göre çok güçlü reasoning, MIT lisansı
**Cons**: Yaratıcı yazıda orta, Türkçe zayıf, daha çok kod/mantık odaklı

### Gemini Tuning (Google)
**Pros**: Ücretsiz fine-tuning (sınırlı), iyi Türkçe, Google ekosistemi
**Cons**: Sınırlı kontrol, kapalı kaynak, tuning seçenekleri kısıtlı, rate limitleri var

---

## 4. Maliyet Senaryoları

### Hesaplama Varsayımları
- 1 tweet ≈ 150 token (input prompt + output)
- Fine-tune veri seti: her tweet = ~300 token (system + user + assistant mesajları)
- Epoch sayısı: 3 (standart)
- Generation: her tweet üretimi ≈ 200 token input + 100 token output

### Senaryo A: 1K tweet fine-tune + ayda 10K generation

| Çözüm | Training Maliyeti | Aylık Inference | Toplam İlk Ay | Devam Eden Ay |
|-------|------------------|-----------------|---------------|---------------|
| GPT-4.1-nano | $1.35 (300K tok × 3 epoch × $1.50) | $2.00 input + $0.80 output = $2.80 | $4.15 | $2.80 |
| GPT-4.1-mini | $4.50 | $1.60 + $3.20 = $4.80 | $9.30 | $4.80 |
| Qwen3-8B (Together LoRA) | $0.43 | $0.36 + $0.18 = $0.54 | $0.97 | $0.54 |
| Qwen3-8B (Unsloth + Colab) | $0 | Self-host: $0 (veya Together: $0.54) | $0 - $0.54 | $0 - $0.54 |
| Llama 3.1-8B (Together) | $0.43 | $0.36 + $0.18 = $0.54 | $0.97 | $0.54 |

### Senaryo B: 5K tweet fine-tune + ayda 50K generation

| Çözüm | Training Maliyeti | Aylık Inference | Toplam İlk Ay | Devam Eden Ay |
|-------|------------------|-----------------|---------------|---------------|
| GPT-4.1-nano | $6.75 | $14.00 | $20.75 | $14.00 |
| GPT-4.1-mini | $22.50 | $24.00 | $46.50 | $24.00 |
| Qwen3-8B (Together LoRA) | $2.16 | $2.70 | $4.86 | $2.70 |
| Qwen3-8B (Unsloth + Colab) | $0 | Self-host: ~$0 | ~$0 | ~$0 |

### Senaryo C: 10K tweet fine-tune + ayda 100K generation

| Çözüm | Training Maliyeti | Aylık Inference | Toplam İlk Ay | Devam Eden Ay |
|-------|------------------|-----------------|---------------|---------------|
| GPT-4.1-nano | $13.50 | $28.00 | $41.50 | $28.00 |
| GPT-4.1-mini | $45.00 | $48.00 | $93.00 | $48.00 |
| Qwen3-8B (Together LoRA) | $4.32 | $5.40 | $9.72 | $5.40 |
| Qwen3-8B (Unsloth, Colab Pro) | ~$10/ay Colab | Self-host veya Together | $10-15 | $5-10 |
| gpt-oss-20B (Together) | $4.32 | $1.00 + $2.00 = $3.00 | $7.32 | $3.00 |

---

## 5. Önerilen Strateji (Adım Adım)

### Faz 1: Hızlı MVP (Hafta 1-2) → GPT-4.1-nano
1. **Mevcut 500 tweet verisini** JSONL formatına çevir (system/user/assistant)
2. OpenAI fine-tuning API ile **GPT-4.1-nano** fine-tune et (~$1-2)
3. Kaliteyi değerlendir: 50 tweet üret, manuel olarak puanla
4. Bu baseline olacak, diğer modelleri bununla karşılaştır

### Faz 2: Açık Kaynak Alternatif (Hafta 2-3) → Qwen3-8B + Unsloth
1. Google Colab Pro ($10/ay) al
2. **Unsloth** ile Qwen3-8B'yi QLoRA ile fine-tune et (ücretsiz notebook'lar var)
3. Aynı veri setini kullan, sonuçları GPT-4.1-nano ile karşılaştır
4. Adapter'ı kaydet, Together AI veya Fireworks'e yükle

### Faz 3: Veri Toplama ve İyileştirme (Hafta 3-8)
1. Veri setini **500 → 2000+** tweet'e çıkar
2. Veri çeşitliliğini artır: farklı tonlar, konular, formatlar
3. **DPO (Direct Preference Optimization)** dene: iyi tweet vs kötü tweet çiftleri
4. Her iki modeli yeniden fine-tune et, karşılaştır

### Faz 4: Ölçeklendirme (Ay 2+)
1. Kazanan modeli production'a al
2. Eğer açık kaynak kazandıysa: Together AI serverless veya kendi GPU
3. Eğer GPT-4.1-nano kazandıysa: batch API ile maliyet %50 düşür
4. Veri setini sürekli büyüt (10K+ hedefi)
5. A/B testing ile gerçek engagement verisi topla

### Önemli İpuçları
- **Veri kalitesi > veri miktarı**: 500 mükemmel tweet > 5000 vasat tweet
- **System prompt'u fine-tune'a dahil et**: Stil, ton, kişilik tanımını system message olarak koy
- **Çift dil stratejisi**: Türkçe ve İngilizce tweetleri ayrı ayrı etiketle, modele dil bilgisi ver
- **Evaluation framework kur**: BLEU/ROUGE yerine, viral metrikler (engagement tahmin skoru) kullan
- **OpenAI Batch API**: Toplu üretimde %50 indirim, 24 saat içinde teslim

---

## 6. Platform Karşılaştırması

| Platform | Fine-tune Desteği | Inference | Avantaj | Dezavantaj |
|----------|------------------|-----------|---------|-----------|
| **OpenAI API** | GPT-4.1 serisi SFT | Serverless | En kolay, en hızlı, batch API | Kapalı kaynak, vendor lock-in |
| **Together AI** | 100+ model, LoRA/Full/DPO | Serverless + Dedicated | En geniş model seçimi, ucuz | Bazı modellerde minimum ücret |
| **Fireworks AI** | 80+ model, SFT/DPO | Serverless + On-demand | Hızlı inference, basit fiyatlandırma | Model seçimi Together'dan az |
| **Unsloth** | Tüm açık kaynak modeller | Yok (sadece training) | Ücretsiz, 2x hız, %70 az VRAM | Inference ayrıca çözülmeli |
| **Hugging Face AutoTrain** | Birçok model | Inference Endpoints | Kolay UI, Spaces | Fiyat karışık |
| **Replicate** | Sınırlı | Serverless | Basit API | Fine-tune desteği sınırlı |
| **Google AI Studio** | Gemini tuning | API | Ücretsiz tuning | Kısıtlı kontrol |
| **Mistral Platform** | Mistral modelleri | API | Avrupa veri güvenliği | Pahalı ($4 min), Türkçe zayıf |

---

## 7. Türkçe Dil Kalitesi Notları

Türkçe için en iyi sonuç veren modeller (sırasıyla):
1. **Qwen3 serisi**: Alibaba'nın çok dilli eğitim verisi Türkçe'yi iyi kapsıyor
2. **GPT-4.1 serisi**: OpenAI'ın genel kalitesi Türkçe'de de iyi yansıyor
3. **Gemma 3**: Google'ın çok dilli verisi güçlü
4. **DeepSeek V3**: Geniş veri seti, Türkçe düzgün
5. **Llama 3.x**: İngilizce ağırlıklı, Türkçe orta
6. **Mistral**: Avrupa dilleri güçlü ama Türkçe zayıf

**Not**: Fine-tuning ile tüm modellerin Türkçe kalitesi önemli ölçüde artırılabilir. 500+ Türkçe tweet ile eğitim, zayıf modelleri bile kabul edilebilir seviyeye çeker.

---

## 8. Sonuç ve Tavsiye

**Başlangıç için GPT-4.1-nano + Qwen3-8B ikili stratejisi** öneriyorum:

1. **GPT-4.1-nano** ile hızlı başla (maliyet: $5 altı)
2. **Qwen3-8B + Unsloth** ile paralel dene (maliyet: $0)
3. Hangisi daha iyi tweet üretiyorsa onu scale et
4. Veri setini büyüttükçe her ikisini de yeniden eğit

Bu yaklaşım:
- Toplam başlangıç maliyeti: **$5 altı**
- Risk: **Düşük** (iki farklı strateji paralel)
- Production'a geçiş: **1-2 hafta**
- Ölçeklenebilirlik: **Yüksek** (her iki yolda da)

---

## 9. Kaynaklar

- OpenAI Pricing: https://openai.com/api/pricing/
- Together AI Pricing: https://www.together.ai/pricing
- Together AI Fine-tuning Models: https://docs.together.ai/docs/fine-tuning-models
- Fireworks AI Pricing: https://fireworks.ai/pricing
- Mistral Fine-tuning Docs: https://docs.mistral.ai/capabilities/finetuning/
- Unsloth GitHub: https://github.com/unslothai/unsloth
- Unsloth Docs: https://unsloth.ai/docs
- Google Gemini Tuning: https://ai.google.dev/gemini-api/docs/tuning
- Replicate Pricing: https://replicate.com/pricing

**Not**: Fiyatlar 11 Şubat 2026 itibarıyla günceldir. AI fiyatları hızla düşmektedir, karar vermeden önce güncel fiyatları kontrol edin.
