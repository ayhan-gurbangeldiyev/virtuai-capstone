"""
Style Lab v2 - Sprint 4: Constraint Engine
Hard limit'ler ile garanti stil uyumu.

Stil profilinden çıkarılan kuralları zorlar:
- Uzunluk limitleri
- Emoji whitelist/blacklist
- Hashtag policy
- Link policy (algoritma cezası)
- Dil tutarlılığı
- Satır yapısı
- Yasaklı kalıplar
"""

import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

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


class StyleConstraints:
    """Stil profilinden çıkarılan hard constraint'ler"""
    
    def __init__(self, fingerprint: dict, viral_patterns: dict = None):
        self.fingerprint = fingerprint
        self.viral_patterns = viral_patterns or {}
        self.rules = self._build_rules()
    
    def _build_rules(self) -> dict:
        fp = self.fingerprint
        vp = self.viral_patterns
        rules = {}
        
        # 1. Uzunluk constrainti
        avg_len = fp.get('avg_length', 150)
        viral_len = vp.get('viral_avg_length', avg_len)
        rules['min_length'] = max(int(avg_len * 0.4), 20)
        rules['max_length'] = min(int(avg_len * 1.8), 280)
        rules['optimal_length'] = int(viral_len) if viral_len else int(avg_len)
        
        # 2. Emoji constrainti
        emoji = fp.get('emoji_strategy', {})
        emoji_style = emoji.get('style', 'unknown')
        if emoji_style == 'no_emoji':
            rules['emoji_policy'] = 'BANNED'
            rules['emoji_whitelist'] = []
        elif emoji_style == 'light':
            rules['emoji_policy'] = 'WHITELIST'
            rules['emoji_whitelist'] = emoji.get('top_emojis', [])[:5]
        elif emoji_style in ('moderate', 'heavy'):
            rules['emoji_policy'] = 'ALLOWED'
            rules['emoji_whitelist'] = emoji.get('top_emojis', [])[:10]
        else:
            rules['emoji_policy'] = 'ALLOWED'
            rules['emoji_whitelist'] = []
        
        # 3. Hashtag constrainti
        ht = fp.get('hashtag_usage', 0)
        rules['hashtag_policy'] = 'BANNED' if ht < 0.05 else 'ALLOWED'
        
        # 4. Link constrainti (algoritma bilgisi: %50-90 erişim kaybı)
        rules['link_policy'] = 'BANNED'
        rules['link_in_reply'] = True
        
        # 5. Dil constrainti
        lang = fp.get('language_mix', {})
        rules['language_style'] = lang.get('language_style', 'mixed')
        rules['english_word_pct_target'] = lang.get('english_word_pct', 10)
        
        # 6. Satır yapısı
        line = fp.get('line_structure', {})
        multiline_pct = line.get('multiline_pct', 30)
        if multiline_pct > 50:
            rules['line_break_policy'] = 'REQUIRED'
            rules['target_lines'] = max(2, round(line.get('avg_lines_per_tweet', 3)))
        elif multiline_pct < 15:
            rules['line_break_policy'] = 'BANNED'
        else:
            rules['line_break_policy'] = 'OPTIONAL'
        
        # 7. Açılış constrainti
        opening = fp.get('opening_psychology', {})
        if opening:
            rules['preferred_opening'] = opening.get('dominant_pattern', 'direct')
            rules['opening_distribution'] = opening.get('distribution', {})
        
        # 8. Kapanış constrainti
        closing = fp.get('closing_strategy', {})
        if closing:
            rules['preferred_closing'] = closing.get('dominant', 'statement')
        
        # 9. Büyük/küçük harf
        cap = fp.get('capitalization', {})
        if cap:
            rules['starts_lowercase'] = cap.get('starts_lowercase_pct', 0) > 50
            rules['uses_caps_emphasis'] = cap.get('uses_all_caps_emphasis_pct', 0) > 15
        
        # 10. Yasaklı kalıplar
        rules['banned_patterns'] = self._detect_banned()
        
        return rules
    
    def _detect_banned(self) -> List[str]:
        """Kişinin ASLA yapmadığı şeyleri tespit et"""
        fp = self.fingerprint
        banned = []
        
        if fp.get('hashtag_usage', 0) < 0.02:
            banned.append("ASLA hashtag kullanma (#)")
        
        emoji = fp.get('emoji_strategy', {})
        if emoji.get('style') == 'no_emoji':
            banned.append("ASLA emoji kullanma")
        
        if fp.get('link_usage', 0) < 0.05:
            banned.append("ASLA link paylaşma")
        
        if fp.get('exclamation_ratio', 0) < 0.05:
            banned.append("Ünlem işareti kullanma (!)")
        
        cap = fp.get('capitalization', {})
        if cap.get('uses_all_caps_emphasis_pct', 0) < 3:
            banned.append("BÜYÜK HARF ile vurgulama yapma")
        
        if cap.get('starts_lowercase_pct', 0) > 70:
            banned.append("Her zaman küçük harfle başla")
        
        line = fp.get('line_structure', {})
        if line.get('multiline_pct', 0) < 10:
            banned.append("Satır kırılması yapma, tek blok yaz")
        
        punct = fp.get('punctuation_dna', {})
        if punct:
            if punct.get('ellipsis_per_tweet', 0) < 0.05:
                banned.append("Üç nokta (...) kullanma")
        
        return banned
    
    def to_prompt(self) -> str:
        """Constraint'leri prompt formatına çevir"""
        lines = ["## ZORUNLU KURALLAR (İhlal Etme!)"]
        
        # Uzunluk
        lines.append(f"- Karakter limiti: {self.rules['min_length']}-{self.rules['max_length']} karakter")
        lines.append(f"- Optimal uzunluk: ~{self.rules['optimal_length']} karakter")
        
        # Emoji
        if self.rules.get('emoji_policy') == 'BANNED':
            lines.append("- ❌ Emoji KULLANMA, sıfır emoji")
        elif self.rules.get('emoji_policy') == 'WHITELIST':
            emojis = ' '.join(self.rules['emoji_whitelist'])
            lines.append(f"- Sadece bu emojileri kullan: {emojis}. Başka emoji YASAK.")
        
        # Hashtag
        if self.rules.get('hashtag_policy') == 'BANNED':
            lines.append("- ❌ Hashtag KULLANMA")
        
        # Link (her zaman)
        lines.append("- ❌ Link KOYMA (X algoritması %50-90 erişim cezası veriyor)")
        
        # Satır yapısı
        if self.rules.get('line_break_policy') == 'REQUIRED':
            lines.append(f"- Satır kırılması KULLAN (~{self.rules.get('target_lines', 3)} satır)")
        elif self.rules.get('line_break_policy') == 'BANNED':
            lines.append("- Tek blok yaz, satır kırılması YAPMA")
        
        # Büyük/küçük harf
        if self.rules.get('starts_lowercase'):
            lines.append("- Küçük harfle başla")
        if self.rules.get('uses_caps_emphasis'):
            lines.append("- ÖNEMLİ kelimeleri BÜYÜK HARF ile vurgula")
        
        # Yasaklı kalıplar
        for ban in self.rules.get('banned_patterns', []):
            lines.append(f"- {ban}")
        
        # Algoritma taktikleri
        lines.append("")
        lines.append("## ALGORİTMA TAKTİĞİ")
        lines.append("- Reply tetikle: tweet sonunda düşündürücü element bırak (13.5x boost)")
        lines.append("- Dwell time artır: değerli bilgi ver, scroll durdur (10x boost)")
        lines.append("- Dil tutarlılığını koru (karışık dil = 0.01x penalty)")
        
        return '\n'.join(lines)
    
    def validate(self, text: str) -> Tuple[bool, List[str]]:
        """Üretilen tweet'in constraint'lere uyumunu kontrol et"""
        violations = []
        
        # Uzunluk
        if len(text) < self.rules.get('min_length', 20):
            violations.append('too_short')
        if len(text) > self.rules.get('max_length', 280):
            violations.append('too_long')
        
        # Emoji
        if self.rules.get('emoji_policy') == 'BANNED':
            if EMOJI_RE.search(text):
                violations.append('has_emoji')
        elif self.rules.get('emoji_policy') == 'WHITELIST':
            found_emojis = EMOJI_RE.findall(text)
            whitelist = set(self.rules.get('emoji_whitelist', []))
            for e in found_emojis:
                if e not in whitelist:
                    violations.append('emoji_not_in_whitelist')
                    break
        
        # Hashtag
        if self.rules.get('hashtag_policy') == 'BANNED' and '#' in text:
            violations.append('has_hashtag')
        
        # Link
        if re.search(r'https?://', text):
            violations.append('has_link')
        
        # Satır yapısı
        if self.rules.get('line_break_policy') == 'BANNED' and '\n' in text:
            violations.append('has_linebreak')
        if self.rules.get('line_break_policy') == 'REQUIRED' and '\n' not in text:
            violations.append('missing_linebreak')
        
        return len(violations) == 0, violations
    
    def score(self, text: str) -> float:
        """Constraint uyum skoru (0-1)"""
        passed, violations = self.validate(text)
        if passed:
            return 1.0
        
        # Her violation 0.2 düşürür
        penalty = len(violations) * 0.2
        return max(0.0, 1.0 - penalty)
