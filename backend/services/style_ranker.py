"""
Style Lab v2 - Sprint 5: Multi-Shot Ranking Engine
5 variant üretip en iyisini seçer.

Ranking kriterleri:
1. Constraint uyumu (hard rules)
2. Uzunluk uyumu (Gaussian, optimal'e yakınlık)
3. Noktalama benzerliği
4. Kelime dağılımı benzerliği
5. Algoritma skoru
6. Hook kalitesi
7. Reply tetikleme potansiyeli
"""

import re
import math
import logging
from typing import List, Dict, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class StyleRanker:
    """Üretilen variant'ları stil + algoritma uyumuna göre sıralar"""
    
    def rank(
        self,
        variants: List[str],
        style_fingerprint: dict,
        constraints,  # StyleConstraints instance
        reference_tweets: List[dict] = None,
    ) -> List[Tuple[str, float, dict]]:
        """
        Variant'ları sıralar.
        
        Returns: [(text, final_score, score_breakdown), ...] sorted by score DESC
        """
        if not variants:
            return []
        
        reference_tweets = reference_tweets or []
        scored = []
        
        for variant in variants:
            scores = self._score_variant(
                variant, style_fingerprint, constraints, reference_tweets
            )
            
            # Ağırlıklı final skor
            final = (
                scores['constraint'] * 0.25 +
                scores['length'] * 0.10 +
                scores['punctuation'] * 0.10 +
                scores['vocabulary'] * 0.10 +
                scores['algorithm'] * 0.20 +
                scores['hook'] * 0.15 +
                scores['reply_potential'] * 0.10
            )
            
            scored.append((variant, round(final, 3), scores))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
    
    def _score_variant(
        self,
        text: str,
        fp: dict,
        constraints,
        reference_tweets: List[dict],
    ) -> dict:
        """Tek bir variant'ın tüm skorlarını hesapla"""
        scores = {}
        
        # 1. Constraint uyumu
        scores['constraint'] = constraints.score(text)
        
        # 2. Uzunluk uyumu
        scores['length'] = self._length_score(text, fp, constraints)
        
        # 3. Noktalama benzerliği
        scores['punctuation'] = self._punctuation_score(text, fp)
        
        # 4. Kelime dağılımı benzerliği
        scores['vocabulary'] = self._vocabulary_score(text, reference_tweets)
        
        # 5. Algoritma skoru
        scores['algorithm'] = self._algorithm_score(text)
        
        # 6. Hook kalitesi
        scores['hook'] = self._hook_score(text)
        
        # 7. Reply tetikleme potansiyeli
        scores['reply_potential'] = self._reply_potential_score(text)
        
        return scores
    
    def _length_score(self, text: str, fp: dict, constraints) -> float:
        """Optimal uzunluğa yakınlık (Gaussian)"""
        optimal = constraints.rules.get('optimal_length', 150)
        actual = len(text)
        
        # Gaussian scoring: e^(-(diff/sigma)^2)
        sigma = optimal * 0.4  # %40 tolerans
        diff = abs(actual - optimal)
        return math.exp(-(diff / max(sigma, 1)) ** 2)
    
    def _punctuation_score(self, text: str, fp: dict) -> float:
        """Noktalama kullanım benzerliği"""
        punct = fp.get('punctuation_dna', {})
        if not punct:
            return 0.5
        
        score = 0.5
        
        # Virgül yoğunluğu
        target_comma = punct.get('comma_per_tweet', 1)
        actual_comma = text.count(',')
        comma_diff = abs(actual_comma - target_comma) / max(target_comma, 1)
        score += max(0, 0.15 - comma_diff * 0.05)
        
        # Üç nokta kullanımı
        target_ellipsis = punct.get('ellipsis_per_tweet', 0)
        actual_ellipsis = text.count('...')
        if target_ellipsis < 0.1 and actual_ellipsis > 0:
            score -= 0.1  # Kullanmaması gerekirken kullanmış
        elif target_ellipsis > 0.3 and actual_ellipsis > 0:
            score += 0.1  # Doğru kullanım
        
        # Bitiş stili
        no_punct_pct = punct.get('tweets_ending_no_punct', 0)
        last_char = text.strip()[-1] if text.strip() else ''
        if no_punct_pct > 50 and last_char.isalpha():
            score += 0.1  # Noktalama olmadan bitiyor, doğru
        elif no_punct_pct < 20 and last_char in '.!?':
            score += 0.1  # Noktalama ile bitiyor, doğru
        
        # Ünlem/soru oranı
        excl_target = punct.get('exclamation_per_tweet', 0)
        if excl_target < 0.1 and '!' in text:
            score -= 0.1
        
        return max(0, min(1, score))
    
    def _vocabulary_score(self, text: str, reference_tweets: List[dict]) -> float:
        """Kelime dağılımı benzerliği (referans tweet'lerle)"""
        if not reference_tweets:
            return 0.5
        
        # Referans kelime frekansları
        ref_words = Counter()
        for t in reference_tweets:
            content = t.get('content', '')
            words = re.findall(r'\b\w+\b', content.lower())
            ref_words.update(words)
        
        if not ref_words:
            return 0.5
        
        # Variant kelime frekansları
        var_words = Counter(re.findall(r'\b\w+\b', text.lower()))
        
        # Jaccard similarity
        common = set(var_words.keys()) & set(ref_words.keys())
        union = set(var_words.keys()) | set(ref_words.keys())
        
        if not union:
            return 0.5
        
        jaccard = len(common) / len(union)
        
        # Normalize (Jaccard genelde düşük olur tweet'lerde)
        return min(1.0, jaccard * 3)
    
    def _algorithm_score(self, text: str) -> float:
        """X algoritma uyumluluk skoru"""
        score = 0.4
        text_lower = text.lower()
        words = text.split()
        word_count = len(words)
        
        # Link yok
        if 'http' not in text_lower:
            score += 0.15
        else:
            score -= 0.2
        
        # Soru var (reply tetikler, 13.5x)
        if '?' in text:
            score += 0.1
        
        # Optimal uzunluk (dwell time)
        if 20 <= word_count <= 60:
            score += 0.1
        elif 10 <= word_count < 20:
            score += 0.05
        
        # Satır kırılması (okunabilirlik)
        if '\n' in text:
            score += 0.05
        
        # Self-contained
        if 'http' not in text_lower and word_count >= 10:
            score += 0.05
        
        # Dil tutarlılığı (basit check)
        score += 0.05
        
        return min(1.0, max(0.0, score))
    
    def _hook_score(self, text: str) -> float:
        """İlk cümlenin dikkat çekiciliği"""
        first_line = text.split('\n')[0].strip()
        first_words = first_line.split()
        score = 0.3
        
        # Kısa açılış (6 kelime altı)
        if len(first_words) <= 6:
            score += 0.15
        
        # Rakamla açılış
        if first_line and first_line[0].isdigit():
            score += 0.15
        
        # Soru ile açılış
        if '?' in first_line and len(first_line) < 80:
            score += 0.1
        
        # Güçlü kelimeler
        power_words = {
            'asla', 'herkes', 'kimse', 'sır', 'gerçek', 'aslında',
            'never', 'everyone', 'nobody', 'secret', 'truth', 'actually',
            'dikkat', 'kritik', 'breaking', 'shocking',
        }
        first_lower = ' '.join(first_words[:5]).lower()
        if any(w in first_lower for w in power_words):
            score += 0.15
        
        # Contrast/bold claim
        contrast = ['ama', 'ancak', 'fakat', 'but', 'however', 'değil']
        if any(w in first_lower for w in contrast):
            score += 0.1
        
        return min(1.0, score)
    
    def _reply_potential_score(self, text: str) -> float:
        """Reply tetikleme potansiyeli"""
        text_lower = text.lower()
        score = 0.2
        
        # Soru işareti
        if '?' in text:
            score += 0.2
        
        # Doğrudan soru
        reply_triggers = [
            'ne düşünüyorsun', 'siz ne dersiniz', 'katılıyor musun',
            'what do you think', 'do you agree', 'thoughts',
            'hangisi', 'your take', 'senin fikrin',
        ]
        for trigger in reply_triggers:
            if trigger in text_lower:
                score += 0.2
                break
        
        # Tartışmalı ifade
        opinion_markers = [
            'bence', 'unpopular opinion', 'hot take', 'tartışılır',
            'katılmıyorum', 'controversial', 'aslında herkes yanlış',
        ]
        for marker in opinion_markers:
            if marker in text_lower:
                score += 0.15
                break
        
        # CTA
        cta_patterns = ['yorumlara yaz', 'comment', 'rt if', 'like if', 'paylaş']
        for cta in cta_patterns:
            if cta in text_lower:
                score += 0.1
                break
        
        # Açık uçlu bitiş (incomplete)
        if text.strip().endswith('...') or text.strip().endswith('…'):
            score += 0.1
        
        return min(1.0, score)
    
    def get_top_variants(
        self,
        ranked: List[Tuple[str, float, dict]],
        count: int = 3,
        min_constraint_score: float = 0.6,
    ) -> List[Tuple[str, float, dict]]:
        """Constraint'e uyan en iyi variant'ları döndür"""
        filtered = [
            r for r in ranked 
            if r[2].get('constraint', 0) >= min_constraint_score
        ]
        
        if not filtered:
            # Hiçbiri constraint'e uymuyorsa en iyi 3'ü döndür
            logger.warning("No variants passed constraint filter, returning best available")
            return ranked[:count]
        
        return filtered[:count]


def get_posting_suggestion(viral_patterns: dict) -> Optional[dict]:
    """Viral pattern'lerden posting önerisi çıkar"""
    if not viral_patterns:
        return None
    
    suggestion = {}
    
    # Optimal uzunluk
    viral_len = viral_patterns.get('viral_avg_length', 0)
    if viral_len:
        suggestion['optimal_length'] = int(viral_len)
    
    # Viral özellikler
    insights = viral_patterns.get('insights', [])
    if insights:
        suggestion['tips'] = insights[:3]
    
    # Soru kullanımı
    viral_q = viral_patterns.get('viral_question_ratio', 0)
    if viral_q > 0.3:
        suggestion['use_question'] = True
    
    # Link uyarısı
    flop_link = viral_patterns.get('flop_link_ratio', 0)
    if flop_link > 0.2:
        suggestion['avoid_links'] = True
    
    return suggestion if suggestion else None
