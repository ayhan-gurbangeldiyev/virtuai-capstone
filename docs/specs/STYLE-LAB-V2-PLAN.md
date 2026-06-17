# Style Lab v2: Hibrit Stil Klonlama + Algoritma Entegrasyonu

## Vizyon
Kullanıcının Twitter stilini "tıpa tıp" klonlayan, X algoritmasını bilen, 
en viral tweet formatlarını üreten tam otomatik sistem.

**Mevcut:** 50 tweet → soyut AI analizi → genel stil prompt → tek variant
**Hedef:** 500+ tweet → mikro-dilbilim + AI DNA + algoritma skoru → akıllı RAG → Maverick fine-tuned → 5 variant → ranking → en iyi 2-3

---

## Sprint Planı

### Sprint 0: Veri Toplama Güçlendirmesi (0.5 gün)
**Amaç:** 50 tweet yerine 500+ tweet çekmek

**Görevler:**
- [ ] `services/tweet_collector.py` oluştur (Apify entegrasyonu)
- [ ] Apify `apidojo/tweet-scraper` ile kullanıcı tweet'lerini çek
  - `from:handle -filter:retweets min_faves:10` (düşük eşik, tüm karakteristik tweet'ler)
  - `from:handle filter:replies` (reply stilini de al)
  - `from:handle filter:quote` (quote tweet stilini de al)
- [ ] Limit: 500 tweet (ana) + 100 reply + 100 quote = **700 tweet**
- [ ] Maliyet: ~$0.28 per kullanıcı (700 tweet × $0.40/1K)
- [ ] `source_tweets` tablosuna kaydet (mevcut tablo, yeni alanlar ekle)
- [ ] Yeni alanlar: `tweet_type` (original/reply/quote), `engagement_score`, `algo_score`

**Teknik Detaylar:**
```python
# Apify query'leri (3 ayrı run)
queries = [
    f"from:{handle} -filter:retweets -filter:replies min_faves:10",  # Ana tweet'ler
    f"from:{handle} filter:replies min_faves:5",                      # Reply'lar
    f"from:{handle} filter:quote min_faves:5",                        # Quote tweet'ler
]
```

**DB Migration:**
```sql
-- 007_style_lab_v2.sql
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS tweet_type TEXT DEFAULT 'original';
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS engagement_score FLOAT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS algo_score FLOAT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS word_count INT;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS has_link BOOLEAN DEFAULT FALSE;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS has_media BOOLEAN DEFAULT FALSE;
ALTER TABLE source_tweets ADD COLUMN IF NOT EXISTS language TEXT;

CREATE INDEX IF NOT EXISTS idx_source_tweets_embedding 
  ON source_tweets USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_source_tweets_source_engagement 
  ON source_tweets (source_id, engagement_score DESC);
```

---

### Sprint 1: Algoritma Skoru Hesaplama (0.5 gün)
**Amaç:** Her tweet'e X algoritma uyumluluk skoru vermek

**Görevler:**
- [ ] `services/algo_scorer.py` oluştur
- [ ] Her tweet için algoritma skoru hesapla (0-100 arası):

**Skor Bileşenleri:**
```python
def calculate_algo_score(tweet: dict) -> float:
    score = 50  # Başlangıç
    
    # 1. Reply tetikleme potansiyeli (+0-15)
    # Soru işareti varsa, tartışma açıyorsa, görüş bildiriyorsa
    if has_question(tweet): score += 8
    if has_opinion(tweet): score += 5
    if has_call_to_action(tweet): score += 7
    
    # 2. Dwell time potansiyeli (+0-15)
    # Uzunluk + bilgi yoğunluğu + okunabilirlik
    word_count = len(tweet['content'].split())
    if 20 <= word_count <= 60: score += 10  # Optimal uzunluk
    if has_line_breaks(tweet): score += 5    # Okunabilirlik
    
    # 3. Link cezası (-20)
    if has_external_link(tweet): score -= 20  # %50-90 erişim kaybı
    
    # 4. Dil tutarlılığı (+0-10)
    if is_language_consistent(tweet): score += 10
    # Karışık dil: -5, bilinmeyen dil: -30
    
    # 5. Self-contained (+0-10)
    # Bilgiyi direkt veriyor mu, link'e yönlendirmiyor mu?
    if is_self_contained(tweet): score += 10
    
    # 6. Engagement kanıtı (+0-15)
    # Gerçek engagement verisi varsa (reply/like oranı)
    reply_ratio = tweet.get('replies', 0) / max(tweet.get('likes', 1), 1)
    if reply_ratio > 0.05: score += 10  # Reply oranı yüksek = iyi
    if reply_ratio > 0.15: score += 5   # Çok yüksek reply = harika
    
    # 7. Bookmark potansiyeli (+0-10)
    # Liste, nasıl yapılır, kaynak, bilgi deposu
    if has_save_worthy_content(tweet): score += 10
    
    return min(max(score, 0), 100)
```

- [ ] Tüm `source_tweets`'e algo_score yaz
- [ ] Viral pattern extraction: En yüksek algo_score'lu tweet'lerin ortak özellikleri

**Viral Pattern Extraction:**
```python
def extract_viral_patterns(tweets: List[dict]) -> dict:
    """Top %20 vs bottom %20 karşılaştırma"""
    sorted_tweets = sorted(tweets, key=lambda t: t['engagement_score'], reverse=True)
    top_20 = sorted_tweets[:len(sorted_tweets)//5]
    bottom_20 = sorted_tweets[-len(sorted_tweets)//5:]
    
    patterns = {
        "viral_avg_length": avg_length(top_20),
        "flop_avg_length": avg_length(bottom_20),
        "viral_question_ratio": question_ratio(top_20),
        "flop_question_ratio": question_ratio(bottom_20),
        "viral_emoji_ratio": emoji_ratio(top_20),
        "flop_emoji_ratio": emoji_ratio(bottom_20),
        "viral_line_break_ratio": linebreak_ratio(top_20),
        "flop_line_break_ratio": linebreak_ratio(bottom_20),
        "viral_link_ratio": link_ratio(top_20),
        "flop_link_ratio": link_ratio(bottom_20),
        "viral_opening_patterns": analyze_openings(top_20),  # İlk 5 kelime pattern
        "flop_opening_patterns": analyze_openings(bottom_20),
        "viral_time_distribution": time_distribution(top_20),  # Saat dağılımı
        "optimal_posting_hours": best_hours(top_20),
    }
    return patterns
```

---

### Sprint 2: Mikro-Dilbilim v2 (1 gün)
**Amaç:** Mevcut style_analyzer.py'ı güçlendirmek

**Görevler:**
- [ ] Mevcut 15 analiz fonksiyonunu koru (backward compatible)
- [ ] 8 yeni analiz ekle:

**Yeni Analizler:**
```python
# 1. Açılış Psikolojisi (opening_psychology)
def _opening_psychology(self, contents):
    """İlk cümlenin psikolojik tetikleyicisi"""
    patterns = {
        'question': 0,       # "Hiç düşündünüz mü..."
        'bold_claim': 0,     # "X aslında Y'dir"
        'story': 0,          # "Geçen gün...", "3 yıl önce..."
        'data': 0,           # Rakamla açılış "İnsanların %73'ü..."
        'provocation': 0,    # "Kimse bunu konuşmuyor ama..."
        'direct_address': 0, # "Sana bir şey söyleyeyim"
        'contrast': 0,       # "Herkes X diyor ama..."
        'mystery': 0,        # "Bir sır vereyim..."
    }
    # Her tweet'in ilk cümlesini analiz et, pattern'e göre sınıfla
    return patterns, dominant_pattern, distribution

# 2. Kapanış Stratejisi (closing_strategy)
def _closing_strategy(self, contents):
    """Tweet nasıl bitiyor? CTA, soru, statement, incomplete?"""
    patterns = {
        'question_cta': 0,    # "Sen ne düşünüyorsun?"
        'statement': 0,       # Kesin bir ifade ile bitiş
        'incomplete': 0,      # "..." ile bitiş (merak)
        'emoji_close': 0,     # Emoji ile bitiş
        'no_close': 0,        # Ani bitiş, noktalama yok
        'call_to_action': 0,  # "RT/Like/Kaydet" (algoritma sever)
    }
    return patterns

# 3. Düşünce Yapısı (thought_structure)
def _thought_structure(self, contents):
    """Bilgiyi nasıl organize ediyor?"""
    return {
        'conclusion_first_pct': 0,  # Sonuçtan başlayıp açıklama
        'buildup_pct': 0,           # Yavaş yavaş sonuca varma
        'list_format_pct': 0,       # Madde madde
        'single_thought_pct': 0,    # Tek cümle, tek düşünce
        'multi_thought_pct': 0,     # Birden fazla bağlantılı düşünce
        'contrast_pct': 0,          # X ama Y, X değil Y
    }

# 4. Duygusal Yoğunluk (emotional_intensity)
def _emotional_intensity(self, contents):
    """Yazım ne kadar duygusal vs rasyonel?"""
    return {
        'intensity_score': 0-100,     # 0=soğukkanlı, 100=ateşli
        'dominant_emotion': '',        # 'analytical', 'passionate', 'humorous', 'cynical'
        'exclamation_density': 0,
        'caps_emphasis_density': 0,
        'emoji_emotional_weight': 0,
        'power_words_ratio': 0,        # Güçlü kelimeler oranı
    }

# 5. Okuyucu İlişkisi (reader_relationship)
def _reader_relationship(self, contents):
    """Okuyucuyla nasıl bir ilişki kuruyor?"""
    return {
        'uses_you': 0,          # "Sen", "siz" kullanımı
        'uses_we': 0,           # "Biz" kullanımı
        'uses_i': 0,            # "Ben" kullanımı
        'direct_address_pct': 0, # Doğrudan okuyucuya hitap
        'inclusive_pct': 0,      # Okuyucuyu dahil etme
        'authority_pct': 0,      # Uzman/otorite pozisyonu
        'peer_pct': 0,          # Eşit seviye
    }

# 6. Tekrar Kalıpları (repetition_patterns)
def _repetition_patterns(self, contents):
    """Kişinin tekrar kullandığı yapılar"""
    return {
        'signature_openings': [],   # En sık kullanılan açılış kalıpları
        'signature_closings': [],   # En sık kullanılan kapanış kalıpları
        'filler_words': [],         # Dolgu kelimeleri (yani, işte, aslında)
        'transition_words': [],     # Geçiş kelimeleri (ama, ancak, fakat)
        'catchphrases': [],         # Sık tekrarlanan ifadeler (2+ kez)
    }

# 7. Format Tercihleri (format_preferences)
def _format_preferences(self, contents):
    """Görsel format tercihleri"""
    return {
        'uses_bullet_points': 0,
        'uses_numbered_lists': 0,
        'uses_dashes': 0,
        'uses_arrows': 0,           # → ← ↑ ↓
        'uses_separators': 0,       # --- veya ___
        'uses_parenthetical': 0,    # (parantez içi açıklama)
        'uses_quotes': 0,           # "alıntı" kullanımı
        'thread_style': '',         # Tek tweet mi, thread mı
    }

# 8. Reply/Quote Stili (interaction_style)
def _interaction_style(self, reply_tweets, quote_tweets):
    """Reply ve quote tweet'lerdeki farklı stil"""
    return {
        'reply_avg_length': 0,
        'reply_tone': '',           # Daha samimi mi, formal mi?
        'reply_emoji_change': 0,    # Reply'larda emoji kullanımı farkı
        'quote_adds_opinion': 0,    # Quote'ta fikir mi ekliyor?
        'quote_adds_context': 0,    # Quote'ta bağlam mı ekliyor?
        'quote_adds_humor': 0,      # Quote'ta espri mi yapıyor?
    }
```

- [ ] `generate_style_prompt` v2: Somut kurallar üret
  - "Virgül az kullan" → "Virgül KULLANMA. Kısa cümleler kur. Nokta ile bitir."
  - "Emoji az kullan" → "Sadece şu emojileri kullan: 🔥 💡. Başka emoji YASAK."
- [ ] Yasaklı kalıplar (negative rules): Kişinin ASLA yapmadığı şeyleri tespit et
  - "ASLA hashtag kullanma" (eğer hiç kullanmıyorsa)
  - "ASLA link paylaşma" 
  - "ASLA emoji kullanma"

---

### Sprint 3: Embedding & RAG v2 (1 gün)
**Amaç:** Topic'e en uygun + en viral örnekleri akıllı seçme

**Görevler:**
- [ ] Tüm source_tweets'e embedding oluştur (OpenAI text-embedding-3-small)
- [ ] Supabase pgvector'a kaydet
- [ ] `services/style_rag.py` oluştur

**Akıllı RAG Seçimi:**
```python
async def get_style_examples(
    topic: str, 
    source_id: str, 
    limit: int = 8,
    strategy: str = "hybrid"  # "similarity", "viral", "hybrid"
) -> List[dict]:
    """Topic + engagement + algo_score hibrit seçim"""
    
    # 1. Topic benzerliği ile 20 aday çek (pgvector cosine)
    topic_embedding = await get_embedding(topic)
    candidates = supabase.rpc('match_source_tweets', {
        'query_embedding': topic_embedding,
        'source_id': source_id,
        'match_count': 20,
    }).execute()
    
    # 2. Hibrit skor hesapla
    for tweet in candidates:
        similarity = tweet['similarity']  # 0-1 (cosine)
        engagement = normalize(tweet['engagement_score'])  # 0-1
        algo = tweet['algo_score'] / 100  # 0-1
        
        # Ağırlıklı skor
        tweet['hybrid_score'] = (
            similarity * 0.4 +      # Topic uyumu
            engagement * 0.35 +     # Gerçek viral performans
            algo * 0.25             # Algoritma uyumluluk
        )
    
    # 3. Çeşitlilik filtresi (hep aynı tip tweet seçme)
    selected = diversity_select(candidates, limit=limit)
    # - En az 1 kısa tweet + 1 uzun tweet
    # - En az 1 soru + 1 statement
    # - Farklı açılış pattern'leri
    
    return selected
```

**Supabase RPC Function:**
```sql
CREATE OR REPLACE FUNCTION match_source_tweets(
    query_embedding vector(1536),
    source_id_param UUID,
    match_count INT DEFAULT 20
) RETURNS TABLE (
    id UUID,
    content TEXT,
    likes INT,
    retweets INT,
    engagement_score FLOAT,
    algo_score FLOAT,
    tweet_type TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        st.id, st.content, st.likes, st.retweets,
        st.engagement_score, st.algo_score, st.tweet_type,
        1 - (st.embedding <=> query_embedding) AS similarity
    FROM source_tweets st
    WHERE st.source_id = source_id_param
        AND st.embedding IS NOT NULL
    ORDER BY st.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

---

### Sprint 4: Constraint Engine (0.5 gün)
**Amaç:** Hard limit'ler ile garanti stil uyumu

**Görevler:**
- [ ] `services/style_constraints.py` oluştur

**Constraint Sistemi:**
```python
class StyleConstraints:
    """Stil profilinden çıkarılan hard constraint'ler"""
    
    def __init__(self, fingerprint: dict, viral_patterns: dict):
        self.rules = self._build_rules(fingerprint, viral_patterns)
    
    def _build_rules(self, fp, vp) -> dict:
        rules = {}
        
        # 1. Uzunluk constrainti
        avg_len = fp.get('avg_length', 150)
        rules['min_length'] = int(avg_len * 0.5)
        rules['max_length'] = int(avg_len * 1.5)
        # Viral pattern'den optimal uzunluk
        rules['optimal_length'] = vp.get('viral_avg_length', avg_len)
        
        # 2. Emoji constrainti
        emoji = fp.get('emoji_strategy', {})
        if emoji.get('style') == 'no_emoji':
            rules['emoji_policy'] = 'BANNED'
            rules['emoji_whitelist'] = []
        elif emoji.get('style') == 'light':
            rules['emoji_policy'] = 'WHITELIST'
            rules['emoji_whitelist'] = emoji.get('top_emojis', [])[:5]
        else:
            rules['emoji_policy'] = 'ALLOWED'
            rules['emoji_whitelist'] = emoji.get('top_emojis', [])[:10]
        
        # 3. Hashtag constrainti
        ht = fp.get('hashtag_usage', 0)
        rules['hashtag_policy'] = 'BANNED' if ht < 0.05 else 'ALLOWED'
        
        # 4. Link constrainti (algoritma bilgisi ile)
        link = fp.get('link_usage', 0)
        rules['link_policy'] = 'BANNED'  # Her zaman ban (algoritma cezası)
        rules['link_in_reply'] = True     # Reply'a koy önerisi
        
        # 5. Dil constrainti
        lang = fp.get('language_mix', {})
        rules['language_style'] = lang.get('language_style', 'mixed')
        rules['english_word_pct_target'] = lang.get('english_word_pct', 10)
        
        # 6. Satır yapısı
        line = fp.get('line_structure', {})
        if line.get('multiline_pct', 0) > 50:
            rules['line_break_policy'] = 'REQUIRED'
            rules['target_lines'] = line.get('avg_lines_per_tweet', 3)
        elif line.get('multiline_pct', 0) < 15:
            rules['line_break_policy'] = 'BANNED'
        else:
            rules['line_break_policy'] = 'OPTIONAL'
        
        # 7. Açılış constrainti (viral pattern'den)
        opening = fp.get('opening_psychology', {})
        if opening:
            dominant = opening.get('dominant_pattern', 'direct')
            rules['preferred_opening'] = dominant
            rules['opening_distribution'] = opening.get('distribution', {})
        
        # 8. Kapanış constrainti
        closing = fp.get('closing_strategy', {})
        if closing:
            rules['preferred_closing'] = closing.get('dominant', 'statement')
        
        # 9. Yasaklı kalıplar (kişinin ASLA yapmadığı)
        rules['banned_patterns'] = self._detect_banned(fp)
        
        return rules
    
    def _detect_banned(self, fp) -> List[str]:
        """Kişinin ASLA yapmadığı şeyleri tespit et"""
        banned = []
        if fp.get('hashtag_usage', 0) < 0.02:
            banned.append("ASLA hashtag kullanma (#)")
        if fp.get('emoji_strategy', {}).get('style') == 'no_emoji':
            banned.append("ASLA emoji kullanma")
        if fp.get('link_usage', 0) < 0.05:
            banned.append("ASLA link paylaşma")
        if fp.get('exclamation_ratio', 0) < 0.05:
            banned.append("ASLA ünlem işareti kullanma (!)")
        if fp.get('question_ratio', 0) < 0.03:
            banned.append("Soru sorma, statement yap")
        cap = fp.get('capitalization', {})
        if cap.get('uses_all_caps_emphasis_pct', 0) < 3:
            banned.append("BÜYÜK HARF ile vurgulama yapma")
        return banned
    
    def to_prompt(self) -> str:
        """Constraint'leri prompt formatına çevir"""
        lines = ["## ZORUNLU KURALLAR (İhlal Etme!)"]
        
        lines.append(f"- Karakter limiti: {self.rules['min_length']}-{self.rules['max_length']} karakter")
        
        if self.rules.get('emoji_policy') == 'BANNED':
            lines.append("- ❌ Emoji KULLANMA")
        elif self.rules.get('emoji_policy') == 'WHITELIST':
            emojis = ' '.join(self.rules['emoji_whitelist'])
            lines.append(f"- Sadece bu emojileri kullan: {emojis}")
        
        if self.rules.get('hashtag_policy') == 'BANNED':
            lines.append("- ❌ Hashtag KULLANMA")
        
        lines.append("- ❌ Link KOYMA (algoritma %50-90 ceza veriyor)")
        
        if self.rules.get('line_break_policy') == 'REQUIRED':
            lines.append(f"- Satır kırılması KULLAN (~{self.rules.get('target_lines', 3)} satır)")
        elif self.rules.get('line_break_policy') == 'BANNED':
            lines.append("- Tek blok yaz, satır kırılması YAPMA")
        
        for ban in self.rules.get('banned_patterns', []):
            lines.append(f"- {ban}")
        
        return '\n'.join(lines)
    
    def validate(self, generated_text: str) -> Tuple[bool, List[str]]:
        """Üretilen tweet'in constraint'lere uyumunu kontrol et"""
        violations = []
        
        # Uzunluk kontrolü
        if len(generated_text) < self.rules['min_length']:
            violations.append('too_short')
        if len(generated_text) > self.rules['max_length']:
            violations.append('too_long')
        
        # Emoji kontrolü
        if self.rules.get('emoji_policy') == 'BANNED' and has_emoji(generated_text):
            violations.append('has_emoji')
        
        # Hashtag kontrolü
        if self.rules.get('hashtag_policy') == 'BANNED' and '#' in generated_text:
            violations.append('has_hashtag')
        
        # Link kontrolü
        if 'http' in generated_text.lower():
            violations.append('has_link')
        
        return len(violations) == 0, violations
```

---

### Sprint 5: Multi-Shot Ranking Engine (0.5 gün)
**Amaç:** 5 variant üretip en iyisini seçme

**Görevler:**
- [ ] `services/style_ranker.py` oluştur

**Ranking Sistemi:**
```python
class StyleRanker:
    """Üretilen variant'ları stil + algoritma uyumuna göre sırala"""
    
    def rank(
        self, 
        variants: List[str], 
        style_fingerprint: dict,
        constraints: StyleConstraints,
        reference_tweets: List[dict],
        topic: str
    ) -> List[Tuple[str, float, dict]]:
        """
        Returns: [(text, final_score, score_breakdown), ...]
        """
        scored = []
        
        for variant in variants:
            scores = {}
            
            # 1. Constraint uyumu (pass/fail + violation count)
            passed, violations = constraints.validate(variant)
            scores['constraint'] = 1.0 if passed else max(0, 1.0 - len(violations) * 0.3)
            
            # 2. Uzunluk uyumu (Gaussian, optimal uzunluğa yakınlık)
            optimal = constraints.rules.get('optimal_length', 150)
            length_diff = abs(len(variant) - optimal) / optimal
            scores['length'] = max(0, 1.0 - length_diff)
            
            # 3. Noktalama uyumu (fingerprint ile karşılaştır)
            scores['punctuation'] = self._punctuation_similarity(variant, style_fingerprint)
            
            # 4. Kelime dağılımı benzerliği
            scores['vocabulary'] = self._vocabulary_similarity(variant, reference_tweets)
            
            # 5. Embedding benzerliği (ortalama referans tweet'lere)
            scores['embedding'] = self._embedding_similarity(variant, reference_tweets)
            
            # 6. Algoritma skoru
            scores['algorithm'] = self._algorithm_score(variant)
            
            # 7. Hook kalitesi (açılış gücü)
            scores['hook'] = self._hook_quality(variant)
            
            # 8. Reply tetikleme potansiyeli
            scores['reply_potential'] = self._reply_potential(variant)
            
            # Ağırlıklı final skor
            final = (
                scores['constraint'] * 0.20 +      # Kurallara uyum
                scores['length'] * 0.05 +           # Uzunluk uyumu
                scores['punctuation'] * 0.10 +      # Noktalama uyumu
                scores['vocabulary'] * 0.15 +       # Kelime benzerliği
                scores['embedding'] * 0.15 +        # Semantik benzerlik
                scores['algorithm'] * 0.15 +        # Algoritma uyumu
                scores['hook'] * 0.10 +             # Hook kalitesi
                scores['reply_potential'] * 0.10    # Reply potansiyeli
            )
            
            scored.append((variant, final, scores))
        
        # Sırala ve döndür
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def _algorithm_score(self, text: str) -> float:
        """X algoritma uyumluluk skoru"""
        score = 0.5
        
        # Link yok → iyi
        if 'http' not in text.lower(): score += 0.15
        
        # Soru var → reply tetikler (13.5x ağırlık)
        if '?' in text: score += 0.1
        
        # Dwell time: 20-60 kelime optimal
        words = len(text.split())
        if 20 <= words <= 60: score += 0.1
        
        # Self-contained (link yok, bilgi direkt)
        if 'http' not in text and words > 10: score += 0.05
        
        # Satır kırılması → okunabilirlik → dwell time
        if '\n' in text: score += 0.05
        
        # Report riski düşük (toxic değil)
        score += 0.05  # Default non-toxic varsayım
        
        return min(score, 1.0)
    
    def _hook_quality(self, text: str) -> float:
        """İlk cümlenin dikkat çekiciliği"""
        first_line = text.split('\n')[0].strip()
        score = 0.3  # Baseline
        
        # Kısa ve punch'lı açılış
        if len(first_line.split()) <= 8: score += 0.2
        
        # Rakamla açılış
        if first_line[0].isdigit(): score += 0.15
        
        # Soru ile açılış
        if '?' in first_line: score += 0.15
        
        # Güçlü kelimeler
        power_words = ['asla', 'herkes', 'kimse', 'sır', 'gerçek', 'aslında', 
                       'never', 'everyone', 'nobody', 'secret', 'truth', 'actually']
        if any(w in first_line.lower() for w in power_words): score += 0.15
        
        return min(score, 1.0)
```

---

### Sprint 6: Prompt Builder v2 + Entegrasyon (1 gün)
**Amaç:** Tüm katmanları birleştiren yeni prompt builder

**Görevler:**
- [ ] `prompts/style_prompt_v2.py` oluştur
- [ ] `build_final_prompt` fonksiyonunu güncelle
- [ ] server.py entegrasyonu

**Yeni Prompt Yapısı:**
```python
def build_style_enhanced_prompt(
    topic: str,
    style_fingerprint: dict,
    viral_patterns: dict,
    constraints: StyleConstraints,
    reference_tweets: List[dict],
    algorithm_knowledge: str,
    persona: str,
    tone: str,
    language: str,
) -> str:
    """Tüm katmanları birleştiren mega prompt"""
    
    sections = []
    
    # 1. Temel kimlik
    sections.append(SYSTEM_IDENTITY)  # Mevcut
    
    # 2. X Algoritma bilgisi (compact versiyon)
    sections.append(ALGORITHM_KNOWLEDGE_COMPACT)
    
    # 3. Stil DNA (AI analizi)
    sections.append(f"## STİL DNA\n{style_fingerprint.get('ai_analysis', '')}")
    
    # 4. Mikro kurallar (somut veriler)
    micro = StyleAnalyzer().generate_style_prompt(style_fingerprint)
    sections.append(micro)
    
    # 5. Viral pattern insight
    sections.append(format_viral_patterns(viral_patterns))
    
    # 6. Hard constraint'ler
    sections.append(constraints.to_prompt())
    
    # 7. Referans örnekler (RAG'den gelen 5-8 tweet)
    if reference_tweets:
        examples = "\n\n".join([
            f"Örnek ({t['likes']}❤): {t['content']}" 
            for t in reference_tweets[:8]
        ])
        sections.append(f"## REFERANS ÖRNEKLER\nBu tarzda yaz, kopyalama:\n{examples}")
    
    # 8. Algoritma odaklı CTA stratejisi
    sections.append("""## ALGORİTMA TAKTİĞİ
- Reply tetikle (13.5x boost): Tweet sonunda düşündürücü element bırak
- Dwell time artır (10x boost): Değerli bilgi ver, scroll durdur  
- Link KOYMA (-%50-90 erişim)
- Dil tutarlılığını koru (karışık dil = 0.01x penalty)""")
    
    return '\n\n'.join(sections)
```

**server.py Entegrasyonu:**
```python
@api_router.post("/generate/tweet")
async def generate_tweet(request: TweetGenerateRequest, user=Depends(require_auth)):
    # ... mevcut kod ...
    
    if request.style_profile_id:
        # Style Lab v2 akışı
        profile = get_profile(request.style_profile_id, user.id)
        fingerprint = profile['style_fingerprint']
        viral_patterns = profile.get('viral_patterns', {})
        
        # Constraint engine
        constraints = StyleConstraints(fingerprint, viral_patterns)
        
        # Akıllı RAG
        reference_tweets = await get_style_examples(
            topic=request.topic,
            source_id=profile['source_ids'][0],
            limit=8,
            strategy="hybrid"
        )
        
        # Style-enhanced prompt
        system_prompt = build_style_enhanced_prompt(
            topic=request.topic,
            style_fingerprint=fingerprint,
            viral_patterns=viral_patterns,
            constraints=constraints,
            reference_tweets=reference_tweets,
            algorithm_knowledge=ALGORITHM_KNOWLEDGE_COMPACT,
            persona=request.persona,
            tone=request.tone,
            language=request.language,
        )
        
        # Multi-shot: 5 variant üret
        contents, tokens = await generate_with_model(
            system_prompt, "İçeriği üret.", 
            variants=5,  # Her zaman 5 üret
            user_id=user.id
        )
        
        # Ranking
        ranker = StyleRanker()
        ranked = ranker.rank(contents, fingerprint, constraints, reference_tweets, request.topic)
        
        # Top 3'ü döndür (kullanıcı istediği kadar variant görsün)
        best = ranked[:max(request.variants, 3)]
        
        # Constraint violation olan variant'ları filtrele
        best = [v for v in best if v[2]['constraint'] >= 0.7]
        
        # Posting önerisi ekle
        posting_suggestion = get_posting_suggestion(viral_patterns)
        
        return GenerationResponse(
            variants=[...],
            posting_suggestion=posting_suggestion,  # Yeni alan
            style_scores=[v[2] for v in best],      # Yeni alan
        )
```

---

### Sprint 7: Style Profile v2 Kayıt + UI (0.5 gün)
**Amaç:** Yeni analiz verilerini kaydetme + frontend güncelleme

**Görevler:**
- [ ] `style_profiles` tablosuna yeni alanlar:
```sql
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS viral_patterns JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS constraints JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS algo_insights JSONB DEFAULT '{}';
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS tweet_count INT DEFAULT 0;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS avg_engagement FLOAT;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS profile_version INT DEFAULT 2;
```

- [ ] Frontend: StyleLabPage.jsx güncellemeleri
  - Analiz başlatınca progress bar (tweet çekme → analiz → embedding → skor)
  - Stil kartında yeni bilgiler:
    - "Viral Pattern: Soru ile açılış + kısa cümleler" 
    - "Algoritma Skoru: 78/100"
    - "En güçlü saatler: 09:00, 13:00, 21:00"
    - "Yasaklı: emoji, hashtag, link"
  - Generation sonucunda skor gösterimi:
    - "Stil Uyumu: %87"
    - "Algoritma Skoru: 82/100"
    - "Posting Önerisi: 13:00-14:00 arası paylaş"

---

### Sprint 8: Test & İterasyon (0.5 gün)
**Amaç:** Gerçek kullanıcı verileri ile test

**Görevler:**
- [ ] Semih Kışlar (@semihdev) profili ile v1 vs v2 karşılaştırma
- [ ] 3 farklı hesap ile test:
  - TR teknik hesap (ör: @semihdev)
  - TR mizah hesabı
  - EN tech hesabı
- [ ] Blind test: v1 vs v2 çıktılarını yan yana karşılaştır
- [ ] Skor kalibrasyonu: ranking ağırlıklarını ayarla
- [ ] Edge case'ler: çok az tweet'li hesap, çok niş hesap

---

## Toplam Tahmini Süre: 5-6 gün

| Sprint | Konu | Süre |
|--------|------|------|
| 0 | Veri Toplama (500+ tweet) | 0.5 gün |
| 1 | Algoritma Skoru | 0.5 gün |
| 2 | Mikro-Dilbilim v2 | 1 gün |
| 3 | Embedding & RAG v2 | 1 gün |
| 4 | Constraint Engine | 0.5 gün |
| 5 | Multi-Shot Ranking | 0.5 gün |
| 6 | Prompt Builder v2 + Entegrasyon | 1 gün |
| 7 | DB + UI | 0.5 gün |
| 8 | Test | 0.5 gün |

## Ek Maliyet
- Apify tweet çekme: ~$0.28 / kullanıcı profil
- Embedding: ~$0.01 / 500 tweet (text-embedding-3-small)
- Ekstra variant üretim: 5x yerine 1x → Maverick inference maliyeti ~5x ama çok ucuz ($0.85/1M)
- **Toplam ek maliyet per kullanıcı: ~$0.35**

## Profil Güncelleme Stratejisi
Kullanıcı aylar sonra tekrar analiz istediğinde:
- Eski tweet'ler + yeni tweet'ler **merge** edilir (deduplicate)
- Yeni analiz çalışır, style_fingerprint güncellenir
- Eski embedding'ler kalır, yeni tweet'lere embedding eklenir
- `profile_version` artırılır, `updated_at` güncellenir
- Constraint'ler yeniden hesaplanır (stil değişmiş olabilir)

## Progressive Analiz (UX)
Kullanıcıyı bekletmemek için 2 aşamalı:
1. **Hızlı analiz (15-30sn):** İlk 50 tweet çek → temel mikro-dilbilim + AI DNA → profil v2-lite kaydedilir, hemen kullanılabilir
2. **Derin analiz (arka plan, 2-3dk):** 500+ tweet çek → embedding → algo skoru → viral pattern → profil v2-full'e güncelle
- UI'da "Profilin hazırlanıyor... %40" progress bar
- Derin analiz bitince bildirim: "Stil profilin güçlendirildi!"

## Bağımlılıklar
- [x] Maverick fine-tune tamamlanması (şu an çalışıyor)
- [ ] Supabase pgvector extension (muhtemelen zaten aktif)
- [ ] OpenAI embedding API key (mevcut)
- [ ] Tweet veri kaynağı: Apify vs X API karşılaştırması yapılacak
