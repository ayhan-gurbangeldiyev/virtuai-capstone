"""
Style Lab v2 - Algoritma Skoru Hesaplama
Her tweet'e X algoritma uyumluluk skoru verir (0-100).

X Algoritma kaynak kodu referansları:
- reply_engaged_by_author: 75.0x
- Reply: 13.5x
- Profile click: ~12.0x
- Bookmark: ~10.0x
- Good click v2 (dwell 2+ min): 10.0x
- Repost: 1.0x
- Like: 0.5x
- Report: -369.0
- Negative feedback: -74.0
- Unknown language: 0.01x
- External link penalty: %50-90 reach loss
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# Güçlü hook kelimeleri (TR + EN)
POWER_WORDS_TR = {
    'asla', 'herkes', 'kimse', 'sır', 'gerçek', 'aslında', 'inanılmaz',
    'dikkat', 'tehlike', 'acil', 'önemli', 'kritik', 'son dakika',
    'şok', 'bomba', 'olay', 'skandal', 'mucize', 'efsane', 'unutma',
    'sakın', 'kesinlikle', 'mutlaka', 'ilk kez', 'hiç kimse', 'sadece',
}

POWER_WORDS_EN = {
    'never', 'everyone', 'nobody', 'secret', 'truth', 'actually',
    'breaking', 'urgent', 'shocking', 'incredible', 'critical',
    'warning', 'exclusive', 'finally', 'remember', 'stop', 'must',
    'always', 'only', 'just discovered', 'no one', 'first time',
}

# Reply tetikleyen pattern'ler
REPLY_TRIGGERS_TR = [
    r'ne düşünüyorsun', r'siz ne dersini', r'katılıyor musun',
    r'hangisi', r'senin fikrin', r'yorumlara yaz', r'sen de',
    r'hanginiz', r'var mı', r'bilen var mı', r'nasıl',
]

REPLY_TRIGGERS_EN = [
    r'what do you think', r'do you agree', r'thoughts\?',
    r'which one', r'your take', r'let me know', r'comment below',
    r'who else', r'anyone', r'how do you', r'what\'s your',
]

# Bookmark-worthy content signals
SAVE_WORTHY_PATTERNS = [
    r'\d+\s*(adım|step|tip|rule|lesson|hack|way|thing)',
    r'nasıl\s+\w+', r'how to\s+\w+',
    r'rehber|guide|checklist|cheat sheet|template',
    r'kaydet|bookmark|save this',
    r'thread|🧵',
    r'\d+[.)\-]\s',  # numbered list
]

# Link detection (excluding t.co)
EXTERNAL_LINK_RE = re.compile(r'https?://(?!t\.co/)\S+')
TCO_LINK_RE = re.compile(r'https?://t\.co/\w+')


def calculate_algo_score(tweet: dict) -> float:
    """
    X algoritma uyumluluk skoru hesapla (0-100).
    
    Bileşenler:
    1. Reply tetikleme potansiyeli (+0-15)
    2. Dwell time potansiyeli (+0-15)
    3. Link cezası (-20)
    4. Dil tutarlılığı (+0-10)
    5. Self-contained bonus (+0-10)
    6. Engagement kanıtı (+0-15)
    7. Bookmark potansiyeli (+0-10)
    8. Hook kalitesi (+0-10)
    9. Report riski (-0-15)
    """
    content = tweet.get("content", "")
    if not content:
        return 0
    
    score = 40  # Başlangıç (nötr)
    content_lower = content.lower()
    words = content.split()
    word_count = len(words)
    
    # 1. Reply tetikleme potansiyeli (+0-15)
    reply_score = 0
    if '?' in content:
        reply_score += 6
    
    # Doğrudan reply trigger pattern'leri
    all_triggers = REPLY_TRIGGERS_TR + REPLY_TRIGGERS_EN
    for pattern in all_triggers:
        if re.search(pattern, content_lower):
            reply_score += 4
            break
    
    # Tartışmalı/fikir belirten ifade
    opinion_markers = ['bence', 'aslında', 'katılmıyorum', 'unpopular opinion', 
                       'hot take', 'controversial', 'tartışılır']
    if any(m in content_lower for m in opinion_markers):
        reply_score += 5
    
    score += min(reply_score, 15)
    
    # 2. Dwell time potansiyeli (+0-15)
    dwell_score = 0
    
    # Optimal uzunluk (20-60 kelime = 3-15 sn okuma)
    if 20 <= word_count <= 60:
        dwell_score += 8
    elif 10 <= word_count < 20:
        dwell_score += 4
    elif word_count > 60:
        dwell_score += 6  # Uzun ama okunabilir
    
    # Satır kırılması → okunabilirlik → dwell time
    newline_count = content.count('\n')
    if newline_count >= 2:
        dwell_score += 4
    elif newline_count == 1:
        dwell_score += 2
    
    # Bilgi yoğunluğu (rakam, liste)
    if re.search(r'\d', content):
        dwell_score += 3
    
    score += min(dwell_score, 15)
    
    # 3. Link cezası (-20)
    if EXTERNAL_LINK_RE.search(content):
        score -= 20  # %50-90 erişim kaybı
    elif TCO_LINK_RE.search(content):
        score -= 10  # t.co link (biraz daha az ceza)
    
    # 4. Dil tutarlılığı (+0-10)
    lang = tweet.get("language", "und")
    if lang in ("tr", "en"):
        score += 8  # Bilinen dil
    elif lang == "und":
        score -= 5  # Bilinmeyen dil riski
    else:
        score += 4  # Diğer bilinen diller
    
    # Karışık dil detection (TR kelimeler + EN kelimeler fazla karışıksa)
    # Basit heuristic: her iki dilden de 3+ kelime varsa karışık
    
    # 5. Self-contained bonus (+0-10)
    if not EXTERNAL_LINK_RE.search(content) and not TCO_LINK_RE.search(content):
        if word_count >= 10:
            score += 8  # Link yok, yeterli içerik var
        else:
            score += 4
    
    # 6. Engagement kanıtı (+0-15)
    likes = tweet.get("likes", 0)
    replies_count = tweet.get("replies", 0)
    retweets = tweet.get("retweets", 0)
    
    if likes > 0:
        reply_ratio = replies_count / max(likes, 1)
        if reply_ratio > 0.15:
            score += 12  # Çok yüksek reply oranı
        elif reply_ratio > 0.05:
            score += 8   # İyi reply oranı
        elif reply_ratio > 0.02:
            score += 4
    
    # Bookmark verisi varsa
    bookmarks = tweet.get("bookmarks", 0)
    if bookmarks > 0:
        bookmark_ratio = bookmarks / max(likes, 1)
        if bookmark_ratio > 0.05:
            score += 3  # Yüksek bookmark oranı
    
    # 7. Bookmark potansiyeli (+0-10)
    save_score = 0
    for pattern in SAVE_WORTHY_PATTERNS:
        if re.search(pattern, content_lower):
            save_score += 5
            break
    
    # Bilgi deposu sinyalleri
    if re.search(r'[1-9][0-9]?\s*[.)\-:]\s', content):
        save_score += 3  # Numbered list
    if '🧵' in content or 'thread' in content_lower:
        save_score += 3
    
    score += min(save_score, 10)
    
    # 8. Hook kalitesi (+0-10)
    hook_score = _evaluate_hook(content)
    score += min(hook_score, 10)
    
    # 9. Report riski (-0-15)
    # Toxic / spam sinyalleri
    caps_ratio = sum(1 for c in content if c.isupper()) / max(len(content), 1)
    if caps_ratio > 0.5 and word_count > 5:
        score -= 5  # Çok fazla CAPS LOCK
    
    # Spam pattern
    if content.count('!') > 5:
        score -= 5
    
    return max(0, min(100, round(score, 1)))


def _evaluate_hook(content: str) -> float:
    """İlk cümlenin dikkat çekiciliğini değerlendir"""
    first_line = content.split('\n')[0].strip()
    first_words = first_line.split()[:8]
    first_text = ' '.join(first_words).lower()
    
    score = 0
    
    # Kısa ve punch'lı açılış
    if len(first_words) <= 6:
        score += 3
    
    # Rakamla açılış
    if first_line and first_line[0].isdigit():
        score += 3
    
    # Soru ile açılış
    if '?' in first_line and len(first_line) < 100:
        score += 3
    
    # Güçlü kelimeler
    all_power = POWER_WORDS_TR | POWER_WORDS_EN
    if any(w in first_text for w in all_power):
        score += 3
    
    # Emoji hook (dikkat çekici)
    if first_line and ord(first_line[0]) > 127:
        score += 1  # Emoji ile açılış
    
    # Bold claim / contrast
    contrast_markers = ['ama', 'ancak', 'fakat', 'but', 'however', 'yet', 'değil']
    if any(m in first_text for m in contrast_markers):
        score += 2
    
    return score


def score_all_tweets(tweets: List[Dict]) -> List[Dict]:
    """Tüm tweet'lere algo_score ekle"""
    for tweet in tweets:
        tweet["algo_score"] = calculate_algo_score(tweet)
    return tweets


def extract_viral_patterns(tweets: List[Dict]) -> Dict:
    """
    Top %20 vs bottom %20 karşılaştırma.
    Hangi özellikler viral performansı etkiliyor?
    """
    if len(tweets) < 10:
        return {}
    
    # Engagement score'a göre sırala
    sorted_tweets = sorted(
        tweets, 
        key=lambda t: t.get("engagement_score", 0), 
        reverse=True
    )
    
    cutoff = max(len(sorted_tweets) // 5, 3)
    top = sorted_tweets[:cutoff]
    bottom = sorted_tweets[-cutoff:]
    
    def avg_len(ts):
        return sum(len(t.get("content", "")) for t in ts) / max(len(ts), 1)
    
    def avg_words(ts):
        return sum(t.get("word_count", 0) for t in ts) / max(len(ts), 1)
    
    def question_ratio(ts):
        return sum(1 for t in ts if '?' in t.get("content", "")) / max(len(ts), 1)
    
    def emoji_ratio(ts):
        import emoji
        count = 0
        for t in ts:
            try:
                count += 1 if any(c in t.get("content", "") for c in '🔥💡🚀❤️😂🤔👀💀🎯✅❌⚡️🧵') else 0
            except:
                pass
        return count / max(len(ts), 1)
    
    def linebreak_ratio(ts):
        return sum(1 for t in ts if '\n' in t.get("content", "")) / max(len(ts), 1)
    
    def link_ratio(ts):
        return sum(1 for t in ts if t.get("has_link")) / max(len(ts), 1)
    
    def avg_algo(ts):
        return sum(t.get("algo_score", 0) for t in ts) / max(len(ts), 1)
    
    def analyze_openings(ts):
        """İlk kelime pattern'leri"""
        first_words = []
        for t in ts:
            words = t.get("content", "").split()
            if words:
                first_words.append(words[0].lower().rstrip('.,!?:'))
        return dict(Counter(first_words).most_common(10))
    
    def analyze_closings(ts):
        """Son karakter pattern'leri"""
        endings = []
        for t in ts:
            content = t.get("content", "").strip()
            if content:
                last_char = content[-1]
                if last_char in '.!?…':
                    endings.append(last_char)
                elif last_char.isalpha() or last_char.isdigit():
                    endings.append('no_punct')
                else:
                    endings.append('emoji_or_other')
        return dict(Counter(endings).most_common(5))
    
    def type_distribution(ts):
        """Tweet type dağılımı"""
        types = [t.get("tweet_type", "original") for t in ts]
        return dict(Counter(types))
    
    patterns = {
        # Viral vs flop karşılaştırma
        "viral_avg_length": round(avg_len(top), 1),
        "flop_avg_length": round(avg_len(bottom), 1),
        "viral_avg_words": round(avg_words(top), 1),
        "flop_avg_words": round(avg_words(bottom), 1),
        "viral_question_ratio": round(question_ratio(top), 2),
        "flop_question_ratio": round(question_ratio(bottom), 2),
        "viral_emoji_ratio": round(emoji_ratio(top), 2),
        "flop_emoji_ratio": round(emoji_ratio(bottom), 2),
        "viral_linebreak_ratio": round(linebreak_ratio(top), 2),
        "flop_linebreak_ratio": round(linebreak_ratio(bottom), 2),
        "viral_link_ratio": round(link_ratio(top), 2),
        "flop_link_ratio": round(link_ratio(bottom), 2),
        "viral_avg_algo_score": round(avg_algo(top), 1),
        "flop_avg_algo_score": round(avg_algo(bottom), 1),
        
        # Opening/closing patterns
        "viral_openings": analyze_openings(top),
        "flop_openings": analyze_openings(bottom),
        "viral_closings": analyze_closings(top),
        "flop_closings": analyze_closings(bottom),
        
        # Type distribution
        "viral_types": type_distribution(top),
        "flop_types": type_distribution(bottom),
        
        # Insights (human-readable)
        "insights": _generate_insights(top, bottom),
    }
    
    return patterns


def _generate_insights(top: List[Dict], bottom: List[Dict]) -> List[str]:
    """Viral pattern'lerden okunabilir insight'lar çıkar"""
    insights = []
    
    # Uzunluk farkı
    top_avg = sum(t.get("word_count", 0) for t in top) / max(len(top), 1)
    bot_avg = sum(t.get("word_count", 0) for t in bottom) / max(len(bottom), 1)
    if top_avg > bot_avg * 1.3:
        insights.append(f"Viral tweet'ler daha uzun (ort. {top_avg:.0f} vs {bot_avg:.0f} kelime)")
    elif bot_avg > top_avg * 1.3:
        insights.append(f"Kısa tweet'ler daha viral (ort. {top_avg:.0f} vs {bot_avg:.0f} kelime)")
    
    # Soru farkı
    top_q = sum(1 for t in top if '?' in t.get("content", "")) / max(len(top), 1)
    bot_q = sum(1 for t in bottom if '?' in t.get("content", "")) / max(len(bottom), 1)
    if top_q > bot_q + 0.15:
        insights.append(f"Soru sormak viral etkiyi artırıyor (%{top_q*100:.0f} vs %{bot_q*100:.0f})")
    
    # Link farkı
    top_link = sum(1 for t in top if t.get("has_link")) / max(len(top), 1)
    bot_link = sum(1 for t in bottom if t.get("has_link")) / max(len(bottom), 1)
    if bot_link > top_link + 0.1:
        insights.append("Link paylaşan tweet'ler daha az viral (algoritma cezası)")
    
    # Linebreak farkı
    top_lb = sum(1 for t in top if '\n' in t.get("content", "")) / max(len(top), 1)
    bot_lb = sum(1 for t in bottom if '\n' in t.get("content", "")) / max(len(bottom), 1)
    if top_lb > bot_lb + 0.15:
        insights.append("Çok satırlı format viral etkiyi artırıyor (dwell time)")
    
    return insights
