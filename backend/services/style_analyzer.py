"""Style Analyzer v2 - Mikro-dilbilim + AI DNA sentezi"""
import re
import logging
import unicodedata
from typing import List, Dict, Any, Tuple
from collections import Counter

logger = logging.getLogger(__name__)

# Türkçe stop words (bigram analizinde filtre)
TR_STOP = {'bir', 'de', 've', 'bu', 'da', 'için', 'ile', 'o', 'ne', 'var', 'ben', 'sen', 'biz', 'siz', 'en', 'mi', 'mı', 'mu', 'mü', 'ki', 'ama', 'ya'}

# Emoji regex
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE
)

# İngilizce kelime tespiti (basit heuristic)
EN_COMMON = {'the', 'is', 'are', 'was', 'were', 'have', 'has', 'do', 'does', 'will',
             'can', 'could', 'would', 'should', 'may', 'might', 'shall', 'must',
             'not', 'no', 'yes', 'and', 'or', 'but', 'if', 'then', 'than', 'that',
             'this', 'with', 'from', 'for', 'about', 'into', 'your', 'my', 'our',
             'just', 'like', 'how', 'what', 'when', 'where', 'why', 'who', 'which',
             'new', 'now', 'get', 'got', 'make', 'know', 'think', 'take', 'come',
             'want', 'look', 'use', 'find', 'give', 'more', 'most', 'very', 'also',
             'way', 'out', 'up', 'all', 'been', 'only', 'other', 'some', 'time'}


class StyleAnalyzer:
    """Mikro-dilbilim motoru + AI stil DNA sentezi"""
    
    def analyze(self, tweets: List[Dict]) -> Dict[str, Any]:
        """Kapsamlı mikro-dilbilim analizi"""
        if not tweets:
            return {}
        
        contents = [t.get('content', '') for t in tweets if t.get('content')]
        # Link'leri çıkar (analizi kirletiyor)
        clean_contents = [re.sub(r'https?://\S+', '', c).strip() for c in contents]
        clean_contents = [c for c in clean_contents if len(c) > 10]
        
        if not clean_contents:
            return {"tweet_count": len(tweets)}
        
        fingerprint = {
            "tweet_count": len(tweets),
            "clean_tweet_count": len(clean_contents),
            
            # Temel metrikler
            "avg_length": self._avg_length(clean_contents),
            "length_distribution": self._length_distribution(clean_contents),
            "avg_engagement": self._avg_engagement(tweets),
            
            # Mikro-dilbilim
            "punctuation_dna": self._punctuation_dna(clean_contents),
            "capitalization": self._capitalization_analysis(clean_contents),
            "sentence_architecture": self._sentence_architecture(clean_contents),
            "language_mix": self._language_mix(clean_contents),
            "conjunction_profile": self._conjunction_profile(clean_contents),
            "line_structure": self._line_structure(clean_contents),
            "vocabulary": self._vocabulary_analysis(clean_contents),
            "emoji_strategy": self._emoji_strategy(clean_contents),
            
            # Sprint 2: Mikro-Dilbilim v2
            "opening_psychology": self._opening_psychology(clean_contents),
            "closing_strategy": self._closing_strategy(clean_contents),
            "thought_structure": self._thought_structure(clean_contents),
            "emotional_intensity": self._emotional_intensity(clean_contents),
            "reader_relationship": self._reader_relationship(clean_contents),
            "repetition_patterns": self._repetition_patterns(clean_contents),
            "format_preferences": self._format_preferences(clean_contents),
            "interaction_style": self._interaction_style(
                [t for t in tweets if t.get('is_reply')],
                [t for t in tweets if t.get('is_quote')]
            ),
            
            # Yazım alışkanlıkları (v3 Ghost Writer)
            "typing_habits": self._typing_habits(clean_contents),
            
            # Eski uyumluluk
            "emoji_usage": self._emoji_count_avg(clean_contents),
            "question_ratio": self._ratio_with_char(clean_contents, '?'),
            "exclamation_ratio": self._ratio_with_char(clean_contents, '!'),
            "hashtag_usage": self._hashtag_usage(contents),  # Orijinal (link'li) içerik
            "link_usage": self._link_usage(contents),
            
            # Top tweets (frontend gösterimi için, prompt'a EKLENMİYOR)
            "example_tweets": self._top_tweets(tweets, n=10)
        }
        
        return fingerprint
    
    # ═══════════════════════════════════════════
    # NOKTALAMA DNA'SI
    # ═══════════════════════════════════════════
    def _punctuation_dna(self, contents: List[str]) -> Dict:
        """Noktalama kullanım parmak izi"""
        total_sentences = 0
        comma_count = 0
        ellipsis_count = 0  # ...
        exclamation_count = 0
        question_count = 0
        colon_count = 0
        dash_count = 0  # - veya —
        parenthesis_count = 0
        quote_count = 0
        
        for c in contents:
            sentences = [s.strip() for s in re.split(r'[.!?]+', c) if s.strip()]
            total_sentences += max(len(sentences), 1)
            comma_count += c.count(',')
            ellipsis_count += c.count('...') + c.count('…')
            exclamation_count += c.count('!')
            question_count += c.count('?')
            colon_count += c.count(':')
            dash_count += c.count(' - ') + c.count(' — ') + c.count(' – ')
            parenthesis_count += c.count('(')
            quote_count += c.count('"') + c.count('"') + c.count('"')
        
        n = len(contents)
        return {
            "comma_per_tweet": round(comma_count / n, 2),
            "ellipsis_per_tweet": round(ellipsis_count / n, 2),
            "exclamation_per_tweet": round(exclamation_count / n, 2),
            "question_per_tweet": round(question_count / n, 2),
            "colon_per_tweet": round(colon_count / n, 2),
            "dash_per_tweet": round(dash_count / n, 2),
            "parenthesis_pct": round(parenthesis_count / n * 100, 1),
            "quote_pct": round(quote_count / n * 100, 1),
            "comma_per_sentence": round(comma_count / max(total_sentences, 1), 2),
            "tweets_ending_with_period": round(sum(1 for c in contents if c.rstrip().endswith('.')) / n * 100, 1),
            "tweets_ending_with_exclamation": round(sum(1 for c in contents if c.rstrip().endswith('!')) / n * 100, 1),
            "tweets_ending_no_punct": round(sum(1 for c in contents if c.rstrip()[-1:].isalnum()) / n * 100, 1),
        }
    
    # ═══════════════════════════════════════════
    # BÜYÜK/KÜÇÜK HARF ANALİZİ
    # ═══════════════════════════════════════════
    def _capitalization_analysis(self, contents: List[str]) -> Dict:
        """Büyük/küçük harf tercihleri"""
        starts_upper = 0
        starts_lower = 0
        has_all_caps_word = 0  # BÜYÜK HARF vurgulama
        
        for c in contents:
            first_alpha = ''
            for ch in c:
                if ch.isalpha():
                    first_alpha = ch
                    break
            
            if first_alpha:
                if first_alpha.isupper():
                    starts_upper += 1
                else:
                    starts_lower += 1
            
            # ALL CAPS kelime var mı (3+ harfli)
            words = c.split()
            if any(w.isupper() and len(w) >= 3 and w.isalpha() for w in words):
                has_all_caps_word += 1
        
        n = len(contents)
        return {
            "starts_uppercase_pct": round(starts_upper / n * 100, 1),
            "starts_lowercase_pct": round(starts_lower / n * 100, 1),
            "uses_all_caps_emphasis_pct": round(has_all_caps_word / n * 100, 1),
        }
    
    # ═══════════════════════════════════════════
    # CÜMLE MİMARİSİ
    # ═══════════════════════════════════════════
    def _sentence_architecture(self, contents: List[str]) -> Dict:
        """Cümle yapısı ve uzunluk analizi"""
        all_sentence_lengths = []  # kelime bazlı
        inverted_count = 0  # devrik cümle (fiil sonda değil)
        total_sentences = 0
        short_sentences = 0  # 1-5 kelime
        long_sentences = 0   # 15+ kelime
        
        # Türkçe fiil sonekleri (basit heuristic)
        tr_verb_suffixes = ('yor', 'dı', 'di', 'du', 'dü', 'mış', 'miş', 'muş', 'müş',
                           'cak', 'cek', 'ır', 'ir', 'ur', 'ür', 'ar', 'er',
                           'malı', 'meli', 'lar', 'ler', 'dır', 'dir', 'tır', 'tir')
        
        for c in contents:
            sentences = [s.strip() for s in re.split(r'[.!?\n]+', c) if len(s.strip()) > 3]
            for sent in sentences:
                words = sent.split()
                if not words:
                    continue
                total_sentences += 1
                all_sentence_lengths.append(len(words))
                
                if len(words) <= 5:
                    short_sentences += 1
                elif len(words) >= 15:
                    long_sentences += 1
                
                # Devrik cümle kontrolü: son kelime fiil mi?
                last_word = re.sub(r'[^\wğüşıöçĞÜŞİÖÇ]', '', words[-1].lower())
                is_verb_ending = any(last_word.endswith(s) for s in tr_verb_suffixes)
                if not is_verb_ending and len(words) > 3:
                    inverted_count += 1
        
        if not all_sentence_lengths:
            return {"avg_words_per_sentence": 0}
        
        avg_words = sum(all_sentence_lengths) / len(all_sentence_lengths)
        
        return {
            "avg_words_per_sentence": round(avg_words, 1),
            "short_sentence_pct": round(short_sentences / max(total_sentences, 1) * 100, 1),
            "long_sentence_pct": round(long_sentences / max(total_sentences, 1) * 100, 1),
            "inverted_sentence_pct": round(inverted_count / max(total_sentences, 1) * 100, 1),
            "sentences_per_tweet": round(total_sentences / len(contents), 1),
        }
    
    # ═══════════════════════════════════════════
    # DİL KARIŞIMI
    # ═══════════════════════════════════════════
    def _language_mix(self, contents: List[str]) -> Dict:
        """Türkçe/İngilizce kelime oranı ve kullanım bağlamı"""
        total_words = 0
        en_words = 0
        en_word_examples = Counter()
        
        for c in contents:
            words = re.findall(r'\b[a-zA-ZğüşıöçĞÜŞİÖÇ]+\b', c)
            for w in words:
                if len(w) < 2:
                    continue
                total_words += 1
                w_lower = w.lower()
                # İngilizce kelime mi? (Latin alfabe + İngilizce sözlükte)
                is_ascii = all(ord(ch) < 128 for ch in w_lower)
                if is_ascii and (w_lower in EN_COMMON or (len(w) > 3 and not self._is_turkish_word(w_lower))):
                    en_words += 1
                    en_word_examples[w_lower] += 1
        
        en_pct = round(en_words / max(total_words, 1) * 100, 1)
        
        # En çok kullanılan İngilizce kelimeler (teknik mi günlük mü?)
        top_en = [w for w, _ in en_word_examples.most_common(10)]
        
        return {
            "english_word_pct": en_pct,
            "turkish_word_pct": round(100 - en_pct, 1),
            "top_english_words": top_en[:7],
            "language_style": "pure_turkish" if en_pct < 5 else "mostly_turkish" if en_pct < 15 else "mixed" if en_pct < 40 else "mostly_english"
        }
    
    def _is_turkish_word(self, word: str) -> bool:
        """Basit Türkçe kelime kontrolü (heuristic)"""
        tr_suffixes = ('lar', 'ler', 'lık', 'lik', 'luk', 'lük', 'dan', 'den',
                      'tan', 'ten', 'nın', 'nin', 'nun', 'nün', 'yla', 'yle',
                      'daki', 'deki', 'taki', 'teki')
        return any(word.endswith(s) for s in tr_suffixes)
    
    # ═══════════════════════════════════════════
    # BAĞLAÇ PROFİLİ
    # ═══════════════════════════════════════════
    def _conjunction_profile(self, contents: List[str]) -> Dict:
        """Bağlaç kullanım sıklığı ve tercihleri"""
        conjunctions = {
            'ama': 0, 'ancak': 0, 'fakat': 0, 'lakin': 0,
            'yani': 0, 'çünkü': 0, 'halbuki': 0,
            've': 0, 'veya': 0, 'ya da': 0,
            'hem': 0, 'ne': 0,
            'oysa': 0, 'üstelik': 0, 'ayrıca': 0,
            'but': 0, 'and': 0, 'or': 0, 'because': 0, 'however': 0,
        }
        
        all_text = ' '.join(contents).lower()
        total_words = len(all_text.split())
        
        for conj in conjunctions:
            conjunctions[conj] = len(re.findall(r'\b' + conj + r'\b', all_text))
        
        # En çok kullanılanlar
        top = sorted(conjunctions.items(), key=lambda x: x[1], reverse=True)
        top_used = [(k, v) for k, v in top if v > 0][:5]
        
        total_conj = sum(v for _, v in top_used)
        
        return {
            "conjunction_density": round(total_conj / max(total_words, 1) * 100, 2),
            "top_conjunctions": {k: v for k, v in top_used},
            "prefers_short_sentences": total_conj < len(contents) * 0.5,  # Az bağlaç = kısa cümle tercihi
        }
    
    # ═══════════════════════════════════════════
    # SATIR YAPISI
    # ═══════════════════════════════════════════
    def _line_structure(self, contents: List[str]) -> Dict:
        """Alt satır kullanım paterni"""
        multiline_count = 0
        total_newlines = 0
        avg_lines = []
        uses_bullet = 0
        uses_numbered = 0
        
        for c in contents:
            lines = c.split('\n')
            line_count = len(lines)
            avg_lines.append(line_count)
            
            if line_count > 1:
                multiline_count += 1
                total_newlines += line_count - 1
            
            if re.search(r'^[\-•·▪]', c, re.MULTILINE):
                uses_bullet += 1
            if re.search(r'^\d+[.)\-]', c, re.MULTILINE):
                uses_numbered += 1
        
        n = len(contents)
        return {
            "multiline_pct": round(multiline_count / n * 100, 1),
            "avg_lines_per_tweet": round(sum(avg_lines) / n, 1),
            "newlines_per_tweet": round(total_newlines / n, 1),
            "uses_bullet_pct": round(uses_bullet / n * 100, 1),
            "uses_numbered_pct": round(uses_numbered / n * 100, 1),
            "style": "single_block" if multiline_count / n < 0.2 else "line_breaker" if multiline_count / n < 0.5 else "heavy_formatter"
        }
    
    # ═══════════════════════════════════════════
    # KELİME ZENGİNLİĞİ
    # ═══════════════════════════════════════════
    def _vocabulary_analysis(self, contents: List[str]) -> Dict:
        """Kelime hazinesi zenginliği ve tekrar kalıpları"""
        all_words = []
        for c in contents:
            words = re.findall(r'\b[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}\b', c.lower())
            all_words.extend(words)
        
        if not all_words:
            return {"richness": 0}
        
        unique_words = set(all_words)
        word_freq = Counter(all_words)
        
        # Stop word'leri çıkar
        meaningful_freq = {w: c for w, c in word_freq.items() if w not in TR_STOP and c >= 3}
        top_words = sorted(meaningful_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_words": len(all_words),
            "unique_words": len(unique_words),
            "richness": round(len(unique_words) / len(all_words) * 100, 1),  # type-token ratio
            "signature_words": [w for w, _ in top_words],
            "avg_word_length": round(sum(len(w) for w in all_words) / len(all_words), 1),
        }
    
    # ═══════════════════════════════════════════
    # EMOJİ STRATEJİSİ
    # ═══════════════════════════════════════════
    def _emoji_strategy(self, contents: List[str]) -> Dict:
        """Emoji kullanım paterni ve pozisyonu"""
        total_emoji = 0
        emoji_at_start = 0
        emoji_at_end = 0
        emoji_inline = 0
        tweets_with_emoji = 0
        emoji_counter = Counter()
        
        for c in contents:
            emojis = EMOJI_RE.findall(c)
            if emojis:
                tweets_with_emoji += 1
                total_emoji += len(emojis)
                
                for e in emojis:
                    for char in e:
                        emoji_counter[char] += 1
                
                # Pozisyon
                stripped = c.strip()
                first_emoji_pos = EMOJI_RE.search(stripped)
                if first_emoji_pos:
                    pos_ratio = first_emoji_pos.start() / max(len(stripped), 1)
                    if pos_ratio < 0.1:
                        emoji_at_start += 1
                    elif pos_ratio > 0.8:
                        emoji_at_end += 1
                    else:
                        emoji_inline += 1
        
        n = len(contents)
        top_emojis = [e for e, _ in emoji_counter.most_common(5)]
        
        return {
            "tweets_with_emoji_pct": round(tweets_with_emoji / n * 100, 1),
            "avg_per_tweet": round(total_emoji / n, 2),
            "position": {
                "start_pct": round(emoji_at_start / max(tweets_with_emoji, 1) * 100, 1),
                "end_pct": round(emoji_at_end / max(tweets_with_emoji, 1) * 100, 1),
                "inline_pct": round(emoji_inline / max(tweets_with_emoji, 1) * 100, 1),
            },
            "top_emojis": top_emojis,
            "style": "no_emoji" if tweets_with_emoji / n < 0.1 else "light" if total_emoji / n < 1 else "moderate" if total_emoji / n < 3 else "heavy"
        }
    
    # ═══════════════════════════════════════════
    # AÇILIŞ PSİKOLOJİSİ
    # ═══════════════════════════════════════════
    def _opening_psychology(self, contents: List[str]) -> Dict:
        """İlk cümlenin psikolojik tetikleyicisi"""
        categories = Counter()
        
        for c in contents:
            first_sent = re.split(r'[.!?\n]', c.strip())[0].strip()
            if not first_sent:
                continue
            
            fl = first_sent.lower()
            
            if fl.endswith('?') or any(fl.startswith(q) for q in ('ne ', 'nasıl', 'neden', 'niye', 'kim ', 'hangi', 'what', 'how', 'why', 'who', 'which', 'do you', 'have you', 'is it')):
                categories['question'] += 1
            elif any(w in fl for w in ('bir gün', 'geçen', 'dün', 'bugün', 'hatırlıyorum', 'çocukken', 'yesterday', 'once', 'i remember', 'when i')):
                categories['story'] += 1
            elif re.search(r'\d+[%xX]|\d{2,}', fl):
                categories['data'] += 1
            elif any(w in fl for w in ('sen ', 'siz ', 'sana ', 'size ', 'you ', 'your ')):
                categories['direct_address'] += 1
            elif any(w in fl for w in ('ama ', 'oysa', 'halbuki', 'aksine', 'but ', 'however', 'yet ')):
                categories['contrast'] += 1
            elif any(w in fl for w in ('merak', 'acaba', 'hiç düşündün', 'peki', 'ya ', 'wonder', 'imagine', 'what if')):
                categories['mystery'] += 1
            elif len(first_sent.split()) <= 6 and (first_sent[0].isupper() or first_sent.endswith('.')):
                # Short bold opening
                categories['bold_claim'] += 1
            else:
                categories['provocation'] += 1
        
        n = len(contents)
        distribution = {k: round(v / n * 100, 1) for k, v in categories.items()}
        dominant = categories.most_common(1)[0][0] if categories else 'unknown'
        
        return {
            "distribution": distribution,
            "dominant_opening": dominant,
            "top_3": [k for k, _ in categories.most_common(3)]
        }
    
    # ═══════════════════════════════════════════
    # KAPANIŞ STRATEJİSİ
    # ═══════════════════════════════════════════
    def _closing_strategy(self, contents: List[str]) -> Dict:
        """Tweet nasıl bitiyor"""
        categories = Counter()
        
        for c in contents:
            stripped = c.rstrip()
            if not stripped:
                continue
            
            # Son cümleyi al
            sentences = [s.strip() for s in re.split(r'[\n]', stripped) if s.strip()]
            last_part = sentences[-1] if sentences else stripped
            last_lower = last_part.lower()
            
            if last_part.rstrip().endswith('?'):
                categories['question_cta'] += 1
            elif any(w in last_lower for w in ('...', '…')):
                categories['incomplete'] += 1
            elif EMOJI_RE.search(last_part) and EMOJI_RE.search(last_part).end() >= len(last_part.rstrip()) - 2:
                categories['emoji_close'] += 1
            elif any(w in last_lower for w in ('yap', 'dene', 'bak', 'oku', 'takip', 'follow', 'check', 'try', 'join', 'subscribe', 'link')):
                categories['call_to_action'] += 1
            elif last_part.rstrip()[-1:] in ('.', '!'):
                categories['statement'] += 1
            else:
                categories['no_close'] += 1
        
        n = len(contents)
        distribution = {k: round(v / n * 100, 1) for k, v in categories.items()}
        dominant = categories.most_common(1)[0][0] if categories else 'statement'
        
        return {
            "distribution": distribution,
            "dominant_closing": dominant,
        }
    
    # ═══════════════════════════════════════════
    # DÜŞÜNCE YAPISI
    # ═══════════════════════════════════════════
    def _thought_structure(self, contents: List[str]) -> Dict:
        """Bilgi organizasyonu"""
        categories = Counter()
        
        for c in contents:
            lines = [l.strip() for l in c.split('\n') if l.strip()]
            sentences = [s.strip() for s in re.split(r'[.!?\n]+', c) if len(s.strip()) > 3]
            
            if re.search(r'^[\-•·▪→]|^\d+[.)\-]', c, re.MULTILINE):
                categories['list_format'] += 1
            elif len(sentences) <= 1:
                categories['single_thought'] += 1
            elif any(w in c.lower()[:50] for w in ('ama', 'oysa', 'aksine', 'tam tersi', 'but', 'however', 'on the contrary')):
                categories['contrast'] += 1
            elif len(sentences) >= 3 and len(sentences[-1].split()) > len(sentences[0].split()):
                categories['buildup'] += 1
            elif len(sentences) >= 2 and len(sentences[0].split()) >= len(sentences[-1].split()):
                categories['conclusion_first'] += 1
            else:
                categories['multi_thought'] += 1
        
        n = len(contents)
        distribution = {k: round(v / n * 100, 1) for k, v in categories.items()}
        dominant = categories.most_common(1)[0][0] if categories else 'single_thought'
        
        return {
            "distribution": distribution,
            "dominant_structure": dominant,
        }
    
    # ═══════════════════════════════════════════
    # DUYGUSAL YOĞUNLUK
    # ═══════════════════════════════════════════
    def _emotional_intensity(self, contents: List[str]) -> Dict:
        """Duygusal yoğunluk 0-100 skoru + dominant emotion"""
        emotion_signals = {
            'excitement': re.compile(r'[!]{1,}|🔥|💪|🚀|harika|müthiş|amazing|incredible|awesome|wow', re.I),
            'anger': re.compile(r'saçmalık|rezalet|skandal|absurd|ridiculous|pathetic|utanç|yazık', re.I),
            'curiosity': re.compile(r'\?|merak|acaba|neden|nasıl|why|how|wonder|interesting', re.I),
            'confidence': re.compile(r'kesinlikle|şüphesiz|absolutely|definitely|clearly|obviously|%100|asla', re.I),
            'humor': re.compile(r'😂|🤣|😅|haha|lol|:D|ajsdk|skdj|kdjs', re.I),
            'empathy': re.compile(r'anlıyorum|hissediyorum|understand|feel|❤|🥺|zor|difficult', re.I),
        }
        
        emotion_scores = Counter()
        intensity_scores = []
        
        for c in contents:
            tweet_intensity = 0
            excl = c.count('!')
            caps_words = len(re.findall(r'\b[A-ZĞÜŞİÖÇ]{3,}\b', c))
            emoji_count = len(EMOJI_RE.findall(c))
            
            tweet_intensity += min(excl * 8, 30)
            tweet_intensity += min(caps_words * 10, 25)
            tweet_intensity += min(emoji_count * 5, 20)
            
            for emotion, pattern in emotion_signals.items():
                matches = len(pattern.findall(c))
                if matches:
                    emotion_scores[emotion] += matches
                    tweet_intensity += min(matches * 5, 15)
            
            intensity_scores.append(min(tweet_intensity, 100))
        
        avg_intensity = round(sum(intensity_scores) / len(intensity_scores), 1) if intensity_scores else 0
        dominant = emotion_scores.most_common(1)[0][0] if emotion_scores else 'neutral'
        
        return {
            "score": avg_intensity,
            "dominant_emotion": dominant,
            "emotion_distribution": {k: v for k, v in emotion_scores.most_common(5)},
            "level": "cold" if avg_intensity < 15 else "calm" if avg_intensity < 30 else "warm" if avg_intensity < 50 else "intense" if avg_intensity < 75 else "explosive"
        }
    
    # ═══════════════════════════════════════════
    # OKUYUCU İLİŞKİSİ
    # ═══════════════════════════════════════════
    def _reader_relationship(self, contents: List[str]) -> Dict:
        """Okuyucu ile kurulan ilişki tarzı"""
        you_count = 0  # sen/siz
        we_count = 0   # biz
        i_count = 0    # ben
        authority_signals = 0
        peer_signals = 0
        
        for c in contents:
            cl = c.lower()
            words = cl.split()
            
            you_count += sum(1 for w in words if w in ('sen', 'siz', 'seni', 'sizi', 'sana', 'size', 'senin', 'sizin', 'you', 'your', 'yours'))
            we_count += sum(1 for w in words if w in ('biz', 'bize', 'bizim', 'bizden', 'we', 'our', 'us'))
            i_count += sum(1 for w in words if w in ('ben', 'benim', 'bana', 'beni', 'benden', 'i', 'my', 'me', 'mine'))
            
            # Authority: imperative, teaching, certainty
            if re.search(r'\b(dikkat|unutma|sakın|asla|kesinlikle|şunu|bunu yap|listen|never|always|must|remember)\b', cl):
                authority_signals += 1
            # Peer: hedging, questions, inclusive
            if re.search(r'\b(belki|sanırım|galiba|bence|ne dersin|maybe|perhaps|i think|what do you think|hepimiz)\b', cl):
                peer_signals += 1
        
        n = len(contents)
        total_rel = authority_signals + peer_signals or 1
        
        return {
            "uses_you_per_tweet": round(you_count / n, 2),
            "uses_we_per_tweet": round(we_count / n, 2),
            "uses_i_per_tweet": round(i_count / n, 2),
            "authority_pct": round(authority_signals / total_rel * 100, 1),
            "peer_pct": round(peer_signals / total_rel * 100, 1),
            "dominant_voice": "authority" if authority_signals > peer_signals * 1.5 else "peer" if peer_signals > authority_signals * 1.5 else "balanced",
            "directness": "high" if you_count / n > 0.5 else "medium" if you_count / n > 0.15 else "low"
        }
    
    # ═══════════════════════════════════════════
    # TEKRAR KALIPLARI
    # ═══════════════════════════════════════════
    def _repetition_patterns(self, contents: List[str]) -> Dict:
        """İmza açılışlar, kapanışlar, dolgu kelimeleri, catchphrase'ler"""
        openings = Counter()
        closings = Counter()
        all_bigrams = Counter()
        
        filler_words = {'yani', 'işte', 'aslında', 'hani', 'şey', 'mesela', 'basically', 
                       'literally', 'actually', 'like', 'just', 'really', 'honestly'}
        filler_counts = Counter()
        
        for c in contents:
            words = c.strip().split()
            if not words:
                continue
            
            # First 3 words as opening signature
            opening = ' '.join(words[:min(3, len(words))]).lower()
            opening = re.sub(r'[^\w\s]', '', opening).strip()
            if opening:
                openings[opening] += 1
            
            # Last 3 words as closing
            closing = ' '.join(words[-min(3, len(words)):]).lower()
            closing = re.sub(r'[^\w\s]', '', closing).strip()
            if closing:
                closings[closing] += 1
            
            # Fillers
            for w in words:
                wl = re.sub(r'[^\w]', '', w.lower())
                if wl in filler_words:
                    filler_counts[wl] += 1
            
            # Bigrams for catchphrases
            clean_words = [re.sub(r'[^\w]', '', w.lower()) for w in words if len(w) > 1]
            for i in range(len(clean_words) - 1):
                if clean_words[i] not in TR_STOP or clean_words[i+1] not in TR_STOP:
                    bigram = f"{clean_words[i]} {clean_words[i+1]}"
                    all_bigrams[bigram] += 1
        
        n = len(contents)
        # Signature = appears in >5% of tweets
        threshold = max(3, n * 0.05)
        
        sig_openings = [k for k, v in openings.most_common(10) if v >= threshold]
        sig_closings = [k for k, v in closings.most_common(10) if v >= threshold]
        catchphrases = [k for k, v in all_bigrams.most_common(20) if v >= threshold and k not in TR_STOP]
        
        return {
            "signature_openings": sig_openings[:5],
            "signature_closings": sig_closings[:5],
            "filler_words": {k: v for k, v in filler_counts.most_common(5) if v >= 3},
            "catchphrases": catchphrases[:7],
        }
    
    # ═══════════════════════════════════════════
    # FORMAT TERCİHLERİ
    # ═══════════════════════════════════════════
    def _format_preferences(self, contents: List[str]) -> Dict:
        """Görsel format tercihleri"""
        bullet_count = 0
        numbered_count = 0
        arrow_count = 0
        parenthetical_count = 0
        quote_count = 0
        thread_signal = 0
        
        for c in contents:
            if re.search(r'^[\-•·▪]', c, re.MULTILINE):
                bullet_count += 1
            if re.search(r'^\d+[.)\-]', c, re.MULTILINE):
                numbered_count += 1
            if '→' in c or '->' in c or '⟶' in c or '▸' in c or '►' in c:
                arrow_count += 1
            if '(' in c and ')' in c:
                parenthetical_count += 1
            if '"' in c or '"' in c or '«' in c:
                quote_count += 1
            if re.search(r'🧵|\d+/\d+|thread|konu başlığı', c, re.I):
                thread_signal += 1
        
        n = len(contents)
        return {
            "bullet_points_pct": round(bullet_count / n * 100, 1),
            "numbered_lists_pct": round(numbered_count / n * 100, 1),
            "arrows_pct": round(arrow_count / n * 100, 1),
            "parenthetical_pct": round(parenthetical_count / n * 100, 1),
            "quotes_pct": round(quote_count / n * 100, 1),
            "thread_signals_pct": round(thread_signal / n * 100, 1),
        }
    
    # ═══════════════════════════════════════════
    # ETKİLEŞİM STİLİ
    # ═══════════════════════════════════════════
    def _interaction_style(self, reply_tweets: List[Dict], quote_tweets: List[Dict]) -> Dict:
        """Reply ve quote tweet stilindeki farklar"""
        result = {"has_reply_data": bool(reply_tweets), "has_quote_data": bool(quote_tweets)}
        
        if reply_tweets:
            reply_contents = [t.get('content', '') for t in reply_tweets if t.get('content')]
            if reply_contents:
                reply_lengths = [len(c) for c in reply_contents]
                result["reply_avg_length"] = round(sum(reply_lengths) / len(reply_lengths))
                result["reply_question_pct"] = round(sum(1 for c in reply_contents if '?' in c) / len(reply_contents) * 100, 1)
                result["reply_emoji_pct"] = round(sum(1 for c in reply_contents if EMOJI_RE.search(c)) / len(reply_contents) * 100, 1)
                result["reply_count"] = len(reply_contents)
        
        if quote_tweets:
            quote_contents = [t.get('content', '') for t in quote_tweets if t.get('content')]
            if quote_contents:
                quote_lengths = [len(c) for c in quote_contents]
                result["quote_avg_length"] = round(sum(quote_lengths) / len(quote_lengths))
                result["quote_question_pct"] = round(sum(1 for c in quote_contents if '?' in c) / len(quote_contents) * 100, 1)
                result["quote_count"] = len(quote_contents)
        
        return result
    
    # ═══════════════════════════════════════════
    # YAZIM ALIŞKANLIKLARI (v3 Ghost Writer)
    # ═══════════════════════════════════════════
    def _typing_habits(self, contents: List[str]) -> Dict:
        """Informal yazım alışkanlıkları: lazy typing, küçük harf, noktalama atlama"""
        if not contents:
            return {}
        
        n = len(contents)
        
        # 1. Nokta sonrası küçük harfle devam eden cümle oranı
        total_after_period = 0
        lowercase_after_period = 0
        for c in contents:
            after_period_matches = re.findall(r'\.\s+[a-zA-ZğüşıöçĞÜŞİÖÇ]', c)
            total_after_period += len(after_period_matches)
            lowercase_after_period += len(re.findall(r'\.\s+[a-zğüşıöç]', c))
        
        lowercase_after_period_pct = round(
            lowercase_after_period / max(total_after_period, 1) * 100, 1
        )
        
        # 2. Tamamı küçük harf olan tweet oranı
        all_lowercase_count = 0
        for c in contents:
            # Sadece harf karakterlerine bak
            letters = re.findall(r'[a-zA-ZğüşıöçĞÜŞİÖÇ]', c)
            if letters and all(ch.islower() or ch in 'ğüşıöç' for ch in letters):
                all_lowercase_count += 1
        all_lowercase_pct = round(all_lowercase_count / n * 100, 1)
        
        # 3. Sayı+Türkçe ek pattern oranı (birim kısaltmaları hariç)
        unit_patterns = {'dk', 'sn', 'km', 'cm', 'mm', 'mg', 'kg', 'lt', 'gb', 'mb', 'tb', 'k', 'm', 'b'}
        number_suffix_count = 0
        total_number_patterns = 0
        for c in contents:
            matches = re.findall(r'\d+([a-zğüşıöç]{1,5})', c.lower())
            for suffix in matches:
                total_number_patterns += 1
                if suffix not in unit_patterns:
                    number_suffix_count += 1
        number_suffix_pct = round(number_suffix_count / max(n, 1) * 100, 1)
        
        # 4. Hiç virgül olmayan tweet oranı
        no_comma_count = sum(1 for c in contents if ',' not in c)
        no_comma_tweet_pct = round(no_comma_count / n * 100, 1)
        
        # 5. Noktalama işareti olmadan biten tweet oranı
        no_punct_end_count = sum(1 for c in contents if c.rstrip() and c.rstrip()[-1].isalnum())
        no_punctuation_end_pct = round(no_punct_end_count / n * 100, 1)
        
        # 6. Informal kısaltmalar tespiti
        contraction_patterns = {
            'bi': r'\bbi\b',           # bir yerine
            'bişey': r'\bbişey\b',     # bir şey
            'bişi': r'\bbişi\b',       # bir şey (kısa)
            'deil': r'\bdeil\b',       # değil
            'naber': r'\bnaber\b',     # ne haber
            'nası': r'\bnası\b',       # nasıl
            'nerde': r'\bnerde\b',     # nerede
            'napcaz': r'\bnapcaz\b',   # ne yapacağız
            'napıyon': r'\bnapıyon\b', # ne yapıyorsun
            'bence de': r'\bbence de\b',
        }
        informal_contractions = {}
        all_text_lower = ' '.join(contents).lower()
        for label, pattern in contraction_patterns.items():
            count = len(re.findall(pattern, all_text_lower))
            if count > 0:
                informal_contractions[label] = count
        
        # 7. Kesme işareti eksikliği oranı (basit heuristic)
        # Büyük harfle başlayan kelime + Türkçe ek ama kesme yok
        tr_suffixes_for_apostrophe = (
            'nin', 'nın', 'nun', 'nün', 'in', 'ın', 'un', 'ün',
            'de', 'da', 'te', 'ta', 'den', 'dan', 'ten', 'tan',
            'ye', 'ya', 'e', 'a', 'yi', 'yı', 'yu', 'yü',
            'li', 'lı', 'lu', 'lü', 'le', 'la',
        )
        missing_apostrophe_count = 0
        proper_apostrophe_count = 0
        for c in contents:
            # Kesme işaretli olanları say
            proper_apostrophe_count += len(re.findall(r"[A-ZĞÜŞİÖÇ][a-zğüşıöç]+'[a-zğüşıöç]+", c))
            # Büyük harfle başlayan + ek ama kesme yok
            words = re.findall(r'\b([A-ZĞÜŞİÖÇ][a-zğüşıöç]{2,}(?:' + '|'.join(tr_suffixes_for_apostrophe) + r'))\b', c)
            missing_apostrophe_count += len(words)
        
        total_apostrophe_cases = missing_apostrophe_count + proper_apostrophe_count
        missing_apostrophe_pct = round(
            missing_apostrophe_count / max(total_apostrophe_cases, 1) * 100, 1
        )
        
        # 8. Nokta ayırıcı olarak kullanma (nokta + küçük harf = cümle sonu değil)
        # Bu aslında lowercase_after_period ile aynı metrik
        period_as_separator_pct = lowercase_after_period_pct
        
        # 9. Genel sınıflandırma
        informal_count = sum(informal_contractions.values())
        if all_lowercase_pct > 50 and no_punctuation_end_pct > 50 and informal_count > 5:
            typing_style = "lazy"
        elif all_lowercase_pct < 10 and no_comma_tweet_pct < 50 and no_punctuation_end_pct < 30:
            typing_style = "formal"
        elif all_lowercase_pct >= 10 and all_lowercase_pct <= 50:
            typing_style = "casual"
        else:
            typing_style = "chaotic"
        
        return {
            "lowercase_after_period_pct": lowercase_after_period_pct,
            "all_lowercase_pct": all_lowercase_pct,
            "number_suffix_pct": number_suffix_pct,
            "no_comma_tweet_pct": no_comma_tweet_pct,
            "no_punctuation_end_pct": no_punctuation_end_pct,
            "informal_contractions": informal_contractions,
            "missing_apostrophe_pct": missing_apostrophe_pct,
            "period_as_separator_pct": period_as_separator_pct,
            "typing_style": typing_style,
        }
    
    # ═══════════════════════════════════════════
    # YARDIMCI METOTLAR
    # ═══════════════════════════════════════════
    def _avg_length(self, contents):
        return int(sum(len(c) for c in contents) / len(contents)) if contents else 0
    
    def _length_distribution(self, contents):
        if not contents: return {"short": 0, "medium": 0, "long": 0}
        n = len(contents)
        return {
            "short": round(sum(1 for c in contents if len(c) < 100) / n * 100, 1),
            "medium": round(sum(1 for c in contents if 100 <= len(c) < 200) / n * 100, 1),
            "long": round(sum(1 for c in contents if len(c) >= 200) / n * 100, 1),
        }
    
    def _emoji_count_avg(self, contents):
        if not contents: return 0
        return round(sum(len(EMOJI_RE.findall(c)) for c in contents) / len(contents), 2)
    
    def _ratio_with_char(self, contents, char):
        if not contents: return 0
        return round(sum(1 for c in contents if char in c) / len(contents) * 100, 1)
    
    def _hashtag_usage(self, contents):
        if not contents: return 0
        return round(sum(len(re.findall(r'#\w+', c)) for c in contents) / len(contents), 2)
    
    def _link_usage(self, contents):
        if not contents: return 0
        return round(sum(1 for c in contents if 'http' in c or 't.co' in c) / len(contents) * 100, 1)
    
    def _avg_engagement(self, tweets):
        if not tweets: return {"likes": 0, "retweets": 0, "replies": 0}
        n = len(tweets)
        return {
            "likes": round(sum(t.get('likes', 0) for t in tweets) / n, 1),
            "retweets": round(sum(t.get('retweets', 0) for t in tweets) / n, 1),
            "replies": round(sum(t.get('replies', 0) for t in tweets) / n, 1),
        }
    
    def _top_tweets(self, tweets, n=10):
        sorted_t = sorted(tweets, key=lambda t: t.get('likes', 0) + t.get('retweets', 0) * 2, reverse=True)
        return [{"content": t.get('content', ''), "likes": t.get('likes', 0), "retweets": t.get('retweets', 0)} for t in sorted_t[:n]]
    
    # ═══════════════════════════════════════════
    # STİL PROMPT ÜRETİMİ
    # ═══════════════════════════════════════════
    def generate_style_prompt(self, fingerprint: Dict) -> str:
        """Mikro-dilbilim verileri + AI DNA'sından stil prompt'u üret"""
        if not fingerprint:
            return ""
        
        parts = []
        
        # AI DNA (varsa, ana kaynak)
        ai_analysis = fingerprint.get('ai_analysis', '')
        if ai_analysis:
            parts.append("## STİL DNA (AI Analizi)\n" + ai_analysis)
        
        # Mikro kurallar (somut veriler)
        micro_rules = self._build_micro_rules(fingerprint)
        if micro_rules:
            parts.append("\n## MİKRO KURALLAR (Veri Bazlı)\n" + micro_rules)
        
        return '\n'.join(parts)
    
    def _build_micro_rules(self, fp: Dict) -> str:
        """Fingerprint verilerinden SOMUT ve KESİN mikro kurallar oluştur"""
        rules = []
        banned = []
        
        # ── Noktalama ──
        punct = fp.get('punctuation_dna', {})
        if punct:
            comma = punct.get('comma_per_tweet', 0)
            if comma < 0.5:
                rules.append("- Virgül KULLANMA. Kısa cümleler kur. Nokta ile bitir.")
                banned.append("Virgülle uzayan cümleler")
            elif comma < 1.5:
                rules.append(f"- Virgül nadir kullan (tweet başına max 1)")
            elif comma > 3:
                rules.append(f"- Virgülü bol kullan, uzun akıcı cümleler kur (tweet başına ~{comma:.0f} virgül)")
            
            ellipsis = punct.get('ellipsis_per_tweet', 0)
            if ellipsis > 0.3:
                rules.append(f"- Üç nokta (...) kullan, düşünce askıda bırak")
            elif ellipsis < 0.05:
                banned.append("Üç nokta (...)")
            
            excl = punct.get('exclamation_per_tweet', 0)
            if excl < 0.1:
                rules.append("- Ünlem işareti KULLANMA. Sakin ve düz yaz.")
                banned.append("Ünlem işareti (!)")
            elif excl > 1.5:
                rules.append("- Ünlem kullan! Enerjiyi hissettir!")
            
            no_punct = punct.get('tweets_ending_no_punct', 0)
            if no_punct > 50:
                rules.append(f"- Tweet'i noktalama işareti OLMADAN bitir. Son kelimeden sonra dur.")
            elif no_punct < 10:
                period_end = punct.get('tweets_ending_with_period', 0)
                if period_end > 50:
                    rules.append("- Her tweet'i nokta ile bitir.")
        
        # ── Büyük/küçük harf ──
        cap = fp.get('capitalization', {})
        if cap:
            lower_start = cap.get('starts_lowercase_pct', 0)
            if lower_start > 60:
                rules.append("- Tweet'e küçük harfle başla. Büyük harf KULLANMA başta.")
                banned.append("Cümle başında büyük harf")
            elif lower_start < 15:
                rules.append("- Her cümleye büyük harfle başla.")
            
            caps_emphasis = cap.get('uses_all_caps_emphasis_pct', 0)
            if caps_emphasis > 20:
                rules.append("- Vurgu için BÜYÜK HARF kullan. Önemli kelimeyi CAPS yap.")
            elif caps_emphasis < 3:
                banned.append("BÜYÜK HARF vurgulama")
        
        # ── Cümle yapısı ──
        sent = fp.get('sentence_architecture', {})
        if sent:
            avg_w = sent.get('avg_words_per_sentence', 0)
            short_pct = sent.get('short_sentence_pct', 0)
            if avg_w > 0 and avg_w < 6:
                rules.append(f"- KISA cümleler yaz. Max {int(avg_w)+2} kelime. Fazlasını bölüp iki cümle yap.")
            elif avg_w > 12:
                rules.append(f"- Uzun, akıcı cümleler kur. Cümle başına ~{avg_w:.0f} kelime.")
            
            if short_pct > 50:
                rules.append("- Cümlelerin çoğu 5 kelime veya altında olsun. Telegram tarzı kısa yaz.")
            
            inverted = sent.get('inverted_sentence_pct', 0)
            if inverted > 40:
                rules.append("- Devrik cümle kur. Fiili sona koyma, cümle ortasına al.")
            elif inverted < 10:
                rules.append("- Düz cümle kur. Fiil sonda olsun.")
            
            spt = sent.get('sentences_per_tweet', 0)
            if spt and spt < 2:
                rules.append("- Tweet başına 1-2 cümle yeter. Daha fazla yazma.")
            elif spt and spt > 4:
                rules.append(f"- Tweet başına {spt:.0f} cümle yaz, detaylı anlat.")
        
        # ── Dil karışımı ──
        lang = fp.get('language_mix', {})
        if lang:
            style = lang.get('language_style', 'mixed')
            top_en = lang.get('top_english_words', [])
            if style == 'pure_turkish':
                rules.append("- Saf Türkçe yaz. İngilizce kelime KULLANMA.")
                banned.append("İngilizce kelimeler")
            elif style == 'mostly_turkish':
                if top_en:
                    rules.append(f"- Türkçe yaz. Sadece şu İngilizce kelimeleri kullanabilirsin: {', '.join(top_en[:5])}")
            elif style == 'mixed':
                rules.append(f"- Türkçe-İngilizce karıştır. Sık kullandıkların: {', '.join(top_en[:5])}" if top_en else "- Türkçe-İngilizce karıştır")
            elif style == 'mostly_english':
                rules.append("- Ağırlıklı İngilizce yaz.")
        
        # ── Satır yapısı ──
        line = fp.get('line_structure', {})
        if line:
            multiline = line.get('multiline_pct', 0)
            if multiline > 60:
                avg_nl = line.get('newlines_per_tweet', 0)
                rules.append(f"- Her tweet'te alt satır kullan. Ortalama {avg_nl:.0f} satır kırılması yap.")
            elif multiline < 15:
                rules.append("- Alt satır KULLANMA. Tek paragraf halinde yaz.")
                banned.append("Satır kırılması / alt satır")
        
        # ── Emoji ──
        emoji = fp.get('emoji_strategy', {})
        if emoji:
            style = emoji.get('style', 'no_emoji')
            if style == 'no_emoji':
                rules.append("- Emoji KULLANMA. Asla. Sıfır emoji.")
                banned.append("Her türlü emoji")
            elif style == 'light':
                top = emoji.get('top_emojis', [])
                rules.append(f"- Max 1 emoji kullan, sadece şunlardan: {' '.join(top[:3])}" if top else "- Max 1 emoji, az kullan")
            elif style in ('moderate', 'heavy'):
                top = emoji.get('top_emojis', [])
                pos = emoji.get('position', {})
                if pos.get('end_pct', 0) > 50:
                    rules.append(f"- Emoji tweet SONUNDA kullan: {' '.join(top[:4])}" if top else "- Emoji sonda kullan")
                elif pos.get('start_pct', 0) > 40:
                    rules.append(f"- Emoji tweet BAŞINDA kullan: {' '.join(top[:4])}" if top else "- Emoji başta kullan")
                else:
                    rules.append(f"- Emoji cümle arasında kullan: {' '.join(top[:4])}" if top else "- Emoji arada kullan")
        
        # ── Bağlaç ──
        conj = fp.get('conjunction_profile', {})
        if conj:
            if conj.get('prefers_short_sentences'):
                rules.append("- Bağlaç kullanma. \"ve\", \"ama\" yerine yeni cümle aç.")
                banned.append("\"ve\" ile uzayan cümleler")
            top_conj = conj.get('top_conjunctions', {})
            if top_conj:
                fav = list(top_conj.keys())[:3]
                if fav:
                    rules.append(f"- Bağlaç olarak sadece şunları kullan: {', '.join(fav)}")
        
        # ── Açılış psikolojisi ──
        opening = fp.get('opening_psychology', {})
        if opening:
            dominant = opening.get('dominant_opening', '')
            top3 = opening.get('top_3', [])
            opening_map = {
                'question': 'Soru sorarak başla.',
                'bold_claim': 'Cesur, kısa bir iddia ile başla.',
                'story': 'Kişisel anekdot/hikaye ile başla.',
                'data': 'Veri/sayı ile başla.',
                'provocation': 'Provokatif bir giriş yap.',
                'direct_address': 'Okuyucuya direkt seslen (sen/siz).',
                'contrast': 'Bir karşıtlık ile aç.',
                'mystery': 'Merak uyandırarak başla.',
            }
            if dominant in opening_map:
                rules.append(f"- AÇILIŞ: {opening_map[dominant]}")
        
        # ── Kapanış stratejisi ──
        closing = fp.get('closing_strategy', {})
        if closing:
            dominant = closing.get('dominant_closing', '')
            closing_map = {
                'question_cta': 'Soru sorarak bitir.',
                'statement': 'Kesin bir ifadeyle bitir.',
                'incomplete': 'Düşünceyi yarım bırak (...)',
                'emoji_close': 'Emoji ile bitir.',
                'no_close': 'Doğal bırak, kapatma cümlesi ekleme.',
                'call_to_action': 'Aksiyon çağrısı ile bitir.',
            }
            if dominant in closing_map:
                rules.append(f"- KAPANIŞ: {closing_map[dominant]}")
        
        # ── Duygusal yoğunluk ──
        emotion = fp.get('emotional_intensity', {})
        if emotion:
            level = emotion.get('level', '')
            dom_emotion = emotion.get('dominant_emotion', '')
            if level == 'cold':
                rules.append("- Soğuk ve mesafeli yaz. Duygu katma.")
            elif level == 'calm':
                rules.append("- Sakin ve ölçülü yaz. Abartma.")
            elif level == 'intense':
                rules.append(f"- Yoğun ve tutkulu yaz. Dominant duygu: {dom_emotion}")
            elif level == 'explosive':
                rules.append(f"- PATLAYICI enerji! Coşkulu yaz. Duygu: {dom_emotion}")
        
        # ── Okuyucu ilişkisi ──
        reader = fp.get('reader_relationship', {})
        if reader:
            voice = reader.get('dominant_voice', '')
            if voice == 'authority':
                rules.append("- Otorite tonunda yaz. Öğreten, yönlendiren, kesin konuşan.")
            elif voice == 'peer':
                rules.append("- Eşit tonunda yaz. Düşünen, soran, paylaşan.")
            
            directness = reader.get('directness', '')
            if directness == 'high':
                rules.append("- Okuyucuya direkt seslen: 'sen', 'siz' kullan.")
            elif directness == 'low':
                rules.append("- Okuyucuya direkt seslenme. Genel konuş.")
                banned.append("'Sen' diye direkt hitap")
        
        # ── Tekrar kalıpları ──
        rep = fp.get('repetition_patterns', {})
        if rep:
            sig_openings = rep.get('signature_openings', [])
            if sig_openings:
                rules.append(f"- İmza açılışların: \"{sig_openings[0]}\" tarzı başlangıçlar")
            fillers = rep.get('filler_words', {})
            if fillers:
                filler_list = list(fillers.keys())[:3]
                rules.append(f"- Dolgu kelimeler kullan: {', '.join(filler_list)}")
            catchphrases = rep.get('catchphrases', [])
            if catchphrases:
                rules.append(f"- Catchphrase'ler: {', '.join(catchphrases[:3])}")
        
        # ── Format tercihleri ──
        fmt = fp.get('format_preferences', {})
        if fmt:
            if fmt.get('bullet_points_pct', 0) > 15:
                rules.append("- Madde işareti (•, -) kullan.")
            elif fmt.get('bullet_points_pct', 0) < 2:
                banned.append("Madde işaretli listeler")
            if fmt.get('arrows_pct', 0) > 10:
                rules.append("- Ok işareti (→) kullan geçişlerde.")
            if fmt.get('numbered_lists_pct', 0) > 10:
                rules.append("- Numaralı liste kullan (1. 2. 3.)")
            elif fmt.get('numbered_lists_pct', 0) < 2:
                banned.append("Numaralı listeler")
        
        # ── Düşünce yapısı ──
        thought = fp.get('thought_structure', {})
        if thought:
            dom = thought.get('dominant_structure', '')
            thought_map = {
                'conclusion_first': 'Sonuçla başla, sonra açıkla.',
                'buildup': 'Yavaş kur, sonuca doğru git.',
                'list_format': 'Liste formatında sun.',
                'single_thought': 'Tek bir düşünce, tek bir mesaj.',
                'multi_thought': 'Birden fazla düşünceyi bağla.',
                'contrast': 'Karşıtlık kur, iki tarafı göster.',
            }
            if dom in thought_map:
                rules.append(f"- BİLGİ YAPISI: {thought_map[dom]}")
        
        # Sonuç
        output_parts = []
        if rules:
            output_parts.append('\n'.join(rules))
        
        if banned:
            output_parts.append("\n\n## 🚫 YASAKLI KALIPLAR (ASLA YAPMA)\n" + '\n'.join(f"- ❌ {b}" for b in banned))
        
        return '\n'.join(output_parts) if output_parts else ""
    
    # ═══════════════════════════════════════════
    # AI DERİN ANALİZ
    # ═══════════════════════════════════════════
    def deep_analyze_with_ai(self, tweets: List[Dict], openai_client) -> str:
        """
        GPT-4o ile derinlemesine stil analizi.
        Mikro-dilbilim verilerini de AI'a vererek daha isabetli analiz çıkarır.
        """
        if not tweets or not openai_client:
            return ""
        
        # Önce mikro analizi çalıştır
        micro = self.analyze(tweets)
        
        # Mikro veri özeti
        micro_summary = self._micro_summary_for_ai(micro)
        
        # Top tweet'leri hazırla (engagement bazlı)
        sorted_tweets = sorted(tweets, key=lambda t: t.get('likes', 0) + t.get('retweets', 0) * 2, reverse=True)
        top_tweets = sorted_tweets[:30]
        tweet_texts = []
        for i, t in enumerate(top_tweets, 1):
            content = t.get('content', '')
            likes = t.get('likes', 0)
            tweet_texts.append(f"[{i}] ({likes}❤) {content}")
        tweets_block = '\n\n'.join(tweet_texts)
        
        analysis_prompt = f"""Aşağıdaki tweet'leri ve mikro-dilbilim verilerini analiz et. Bu kişinin yazım tarzının SOYUT DNA'sını çıkar.

⚠️ KRİTİK KURALLAR:
- Asla tweet'lerden alıntı yapma, asla örnek cümle verme
- Amacımız tarzı KOPYALAMAK değil, ÖZÜMSEMEK
- Somut veriler zaten mevcut, sen SOYUT prensipler çıkar

📊 MİKRO-DİLBİLİM VERİLERİ:
{micro_summary}

📝 TWEET'LER:
{tweets_block}

Şu başlıklar altında SOYUT analiz yap:

1. **ZİHİNSEL MODEL**: Bu kişi dünyaya nasıl bakıyor? Bilgiyi nasıl konumlandırıyor? Okuyucuyla ilişkisi ne?

2. **RİTİM ve NEFES**: Cümle ritmi nasıl? Duraklamaları nerede yapıyor? Tempo hızlı mı yavaş mı? Kısa-uzun alternasyonu var mı?

3. **SES ve KİŞİLİK**: Bu yazı bir insanın sesi. O ses nasıl? Güvenli mi tedirgin mi? Sakin mi ateşli mi? Mesafeli mi samimi mi?

4. **BİLGİ MİMARİSİ**: Bilgiyi nasıl paketliyor? Sonuçtan mı başlıyor bağlamdan mı? Keşfettiriyor mu direkt veriyor mu?

5. **AÇILIŞ PSİKOLOJİSİ**: Okuyucuyu hangi psikolojik tetikle yakalıyor? (Şaşırtma, merak, otorite, provokasyon, soru?) Kalıp verme, stratejiyi tanımla.

6. **AYIRT EDİCİ DNA**: Bu kişinin yazımını 1000 kişi arasından ayırt ettirecek 3 soyut özellik.

7. **STİL KODU**: Bu tarzda yazmak için 7 maddelik SOYUT prensip listesi. Her kural bir zihinsel durum ve yaklaşım olsun. Asla "şu kelimeyi kullan" veya "şöyle yaz" deme.

Türkçe yaz. Kısa ve keskin ol, gereksiz açıklama yapma."""
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sen bir dilbilimci ve sosyal medya yazım tarzı analistisin. Somut veriler sana veriliyor, sen soyut prensipler çıkarıyorsun. Kısa ve keskin yaz."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.4,
                max_tokens=2000
            )
            
            analysis = response.choices[0].message.content
            logger.info(f"AI style analysis completed ({len(analysis)} chars)")
            return analysis
            
        except Exception as e:
            logger.error(f"AI style analysis failed: {e}")
            return ""
    
    def _micro_summary_for_ai(self, fp: Dict) -> str:
        """Mikro verileri AI için okunabilir formata çevir"""
        lines = []
        
        punct = fp.get('punctuation_dna', {})
        if punct:
            lines.append(f"Noktalama: virgül/tweet={punct.get('comma_per_tweet',0)}, üç nokta/tweet={punct.get('ellipsis_per_tweet',0)}, soru/tweet={punct.get('question_per_tweet',0)}, ünlem/tweet={punct.get('exclamation_per_tweet',0)}")
            lines.append(f"Bitiş: noktalı=%{punct.get('tweets_ending_with_period',0)}, ünlemli=%{punct.get('tweets_ending_with_exclamation',0)}, işaretsiz=%{punct.get('tweets_ending_no_punct',0)}")
        
        cap = fp.get('capitalization', {})
        if cap:
            lines.append(f"Harf: büyükle başlama=%{cap.get('starts_uppercase_pct',0)}, küçükle=%{cap.get('starts_lowercase_pct',0)}, CAPS vurgu=%{cap.get('uses_all_caps_emphasis_pct',0)}")
        
        sent = fp.get('sentence_architecture', {})
        if sent:
            lines.append(f"Cümle: ort kelime={sent.get('avg_words_per_sentence',0)}, kısa=%{sent.get('short_sentence_pct',0)}, uzun=%{sent.get('long_sentence_pct',0)}, devrik=%{sent.get('inverted_sentence_pct',0)}, cümle/tweet={sent.get('sentences_per_tweet',0)}")
        
        lang = fp.get('language_mix', {})
        if lang:
            lines.append(f"Dil: İngilizce=%{lang.get('english_word_pct',0)}, stil={lang.get('language_style','')}, top EN kelimeler={lang.get('top_english_words',[])}")
        
        line = fp.get('line_structure', {})
        if line:
            lines.append(f"Satır: çoklu satır=%{line.get('multiline_pct',0)}, ort satır/tweet={line.get('avg_lines_per_tweet',0)}, stil={line.get('style','')}")
        
        vocab = fp.get('vocabulary', {})
        if vocab:
            lines.append(f"Kelime: zenginlik=%{vocab.get('richness',0)}, ort uzunluk={vocab.get('avg_word_length',0)}, imza kelimeler={vocab.get('signature_words',[])}")
        
        emoji = fp.get('emoji_strategy', {})
        if emoji:
            lines.append(f"Emoji: stil={emoji.get('style','')}, ort/tweet={emoji.get('avg_per_tweet',0)}, top={emoji.get('top_emojis',[])}")
        
        conj = fp.get('conjunction_profile', {})
        if conj:
            lines.append(f"Bağlaç: yoğunluk=%{conj.get('conjunction_density',0)}, kısa cümle tercihi={conj.get('prefers_short_sentences',False)}, top={list(conj.get('top_conjunctions',{}).keys())}")
        
        opening = fp.get('opening_psychology', {})
        if opening:
            lines.append(f"Açılış: dominant={opening.get('dominant_opening','')}, top3={opening.get('top_3',[])}, dağılım={opening.get('distribution',{})}")
        
        closing = fp.get('closing_strategy', {})
        if closing:
            lines.append(f"Kapanış: dominant={closing.get('dominant_closing','')}, dağılım={closing.get('distribution',{})}")
        
        thought = fp.get('thought_structure', {})
        if thought:
            lines.append(f"Düşünce yapısı: dominant={thought.get('dominant_structure','')}, dağılım={thought.get('distribution',{})}")
        
        emotion = fp.get('emotional_intensity', {})
        if emotion:
            lines.append(f"Duygusal yoğunluk: skor={emotion.get('score',0)}, seviye={emotion.get('level','')}, dominant={emotion.get('dominant_emotion','')}")
        
        reader = fp.get('reader_relationship', {})
        if reader:
            lines.append(f"Okuyucu ilişkisi: ses={reader.get('dominant_voice','')}, direkt hitap={reader.get('directness','')}, sen/tweet={reader.get('uses_you_per_tweet',0)}, ben/tweet={reader.get('uses_i_per_tweet',0)}")
        
        rep = fp.get('repetition_patterns', {})
        if rep:
            lines.append(f"Tekrar: imza açılış={rep.get('signature_openings',[])}, dolgu={list(rep.get('filler_words',{}).keys())}, catchphrase={rep.get('catchphrases',[])}")
        
        fmt = fp.get('format_preferences', {})
        if fmt:
            lines.append(f"Format: bullet=%{fmt.get('bullet_points_pct',0)}, numbered=%{fmt.get('numbered_lists_pct',0)}, ok=%{fmt.get('arrows_pct',0)}, parantez=%{fmt.get('parenthetical_pct',0)}")
        
        return '\n'.join(lines)
    
    def deep_analyze_with_ai(self, tweets: List[Dict], openai_client) -> str:
        """
        GPT-4o ile derinlemesine stil analizi.
        Tweet'leri AI'a gönderip detaylı yazım tarzı raporu çıkarır.
        """
        if not tweets or not openai_client:
            return ""
        
        # En iyi tweet'leri seç (engagement bazlı)
        sorted_tweets = sorted(
            tweets,
            key=lambda t: t.get('likes', 0) + t.get('retweets', 0) * 2,
            reverse=True
        )
        
        # Top 30 tweet'i al (token limiti için)
        top_tweets = sorted_tweets[:30]
        tweet_texts = []
        for i, t in enumerate(top_tweets, 1):
            content = t.get('content', '')
            likes = t.get('likes', 0)
            rts = t.get('retweets', 0)
            tweet_texts.append(f"[{i}] ({likes}❤ {rts}🔁) {content}")
        
        tweets_block = '\n\n'.join(tweet_texts)
        
        analysis_prompt = f"""Aşağıdaki tweet'leri analiz et ve bu kişinin yazım tarzının SOYUT DNA'sını çıkar.

⚠️ KRİTİK KURAL: Asla örnek tweet verme, asla tweet'lerden alıntı yapma, asla spesifik cümle önerme.
Amacımız bu kişinin tarzını KOPYALAMAK değil, ÖZÜMSEMEK. Soyut prensipler ve kurallar çıkar.

TWEET'LER:
{tweets_block}

Şu başlıklar altında SOYUT analiz yap:

1. **ZİHİNSEL MODEL**: Bu kişi dünyaya nasıl bakıyor? Bilgi paylaşırken hangi perspektiften yaklaşıyor? Okuyucuyla ilişkisi nasıl (öğretmen-öğrenci mi, arkadaş mı, mentor mu)?

2. **RİTİM ve TEMPO**: Cümlelerin ritmi nasıl? Kısa-uzun cümle alternasyonu var mı? Nefes noktaları nerede? Alt satır kullanım mantığı ne?

3. **DİL KİMLİĞİ**: Türkçe-İngilizce oranı ne? Teknik terim kullanım biçimi? Konuşma dili mi yazı dili mi? Argo veya jargon seviyesi?

4. **DUYGUSAL İMZA**: Heyecan, güven, merak, otorite gibi duygulardan hangilerini yayıyor? Duygusal yoğunluk seviyesi ne? Abartı mı minimal mi?

5. **AÇILIŞ MATRİSİ**: Tweet'lere giriş mantığı ne? (Kalıp verme, soyut stratejiyi tanımla) Okuyucuyu hangi psikolojik tetikle yakalıyor?

6. **YAPI ARKETİPLERİ**: Hangi yapısal formları tercih ediyor? (tek blok, listeli, parçalı, diyalog tarzı vs.) Paragraf geçiş mantığı ne?

7. **BİLGİ SUNUMU**: Bilgiyi nasıl paketliyor? Direkt mi veriyor, keşfettiriyor mu? Bağlam mı kuruyor yoksa sonuca mı atlıyor?

8. **AYIRT EDİCİ DNA**: Bu kişinin yazımını 1000 kişi arasından ayırt ettirecek 3 soyut özellik ne? (Spesifik kelime veya cümle verme, SOYUT özellik tanımla)

9. **STİL KODU**: Bu tarzda yazmak için uyulması gereken 7 maddelik SOYUT kural listesi. Her kural bir prensip olsun, asla "şu kelimeyi kullan" veya "şöyle başla" deme. "Hangi zihinsel durumda yaz" seviyesinde talimat ver.

SADECE analiz yaz, başka açıklama ekleme. Türkçe yaz. Asla tweet'lerden doğrudan alıntı yapma."""
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sen bir sosyal medya yazım tarzı analistisin. Detaylı ve pratik analizler yaparsın."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            analysis = response.choices[0].message.content
            logger.info(f"AI style analysis completed ({len(analysis)} chars)")
            return analysis
            
        except Exception as e:
            logger.error(f"AI style analysis failed: {e}")
            return ""


# Singleton
analyzer = StyleAnalyzer()
