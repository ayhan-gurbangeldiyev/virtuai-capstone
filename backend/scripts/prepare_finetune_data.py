#!/usr/bin/env python3
# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Type Hype - Fine-tuning Veri Hazırlama Pipeline'ı v3
Supabase'deki viral tweetleri Together AI Llama 4 Maverick 17B-128E fine-tuning formatına çevirir.

Together AI Conversational Format:
  {"messages": [{"role": "system", "content": "..."}, {"role": "user", ...}, {"role": "assistant", ...}]}

Model: meta-llama/Llama-4-Maverick-17B-128E-Instruct
  - LoRA SFT context: 16384 token
  - Min batch size: 16
  - Maliyet: $8/1M token (min $16)
  - Serverless LoRA inference destekli (FP8)

Özellikler:
  - Agresif kalite filtreleme (tek kelimelik, URL-only, mega-hesap noise'u)
  - İki dilli system prompt (TR/EN)
  - Hook tipi otomatik tespiti
  - İçerik yapısı analizi
  - Token limiti (Together AI SFT max: 16384, güvenli: 4096/example)
  - Niche balancing (over/under sampling)
  - Deduplication (similarity_hash + fuzzy)
  - Together AI format doğrulama

Kullanım:
    python prepare_finetune_data.py --dry-run --verbose
    python prepare_finetune_data.py --min-likes 1000 --output-dir backend/data/
    python prepare_finetune_data.py --balance --max-per-niche 200
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("❌ httpx gerekli: pip install httpx")

# tiktoken opsiyonel (token sayımı için)
try:
    import tiktoken
    ENC = tiktoken.get_encoding("cl100k_base")
except ImportError:
    ENC = None
    print("⚠️  tiktoken bulunamadı, token sayımı atlanacak")


# ============================================================
# .env yükleme
# ============================================================
def load_env(path: str = ".env"):
    for candidate in [path, Path(__file__).resolve().parents[1] / ".env", Path.cwd() / ".env"]:
        p = Path(candidate)
        if p.is_file():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                os.environ.setdefault(k.strip(), v)
            return


# ============================================================
# System Prompts (dil bazlı)
# ============================================================
SYSTEM_PROMPT_TR = (
    "Sen X (Twitter) platformunda viral içerik üreten bir uzmansın. "
    "Yüksek etkileşim alan, dikkat çekici ve paylaşılabilir Türkçe tweetler yazıyorsun. "
    "Hook'ların güçlü, dilin doğal ve platforma özgü. "
    "Kısa cümleler, satır araları ve uygun emoji kullanımıyla etki yaratıyorsun. "
    "Verilen konu, niche ve tona uygun özgün içerik üretiyorsun."
)

SYSTEM_PROMPT_EN = (
    "You are an expert at creating viral content on X (Twitter). "
    "You write highly engaging, attention-grabbing, and shareable tweets in English. "
    "Your hooks are strong, your language is natural and platform-native. "
    "You use short sentences, line breaks, and appropriate emojis for impact. "
    "You produce original content matching the given topic, niche, and tone."
)


# ============================================================
# Regex & sabitler
# ============================================================
URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#\w+")
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)

MAX_TOKENS_PER_EXAMPLE = 4096  # Together AI güvenli limit
MIN_CONTENT_LENGTH = 30  # URL/mention temizlendikten sonra
MAX_CONTENT_LENGTH = 1500  # Thread'ler için üst limit

# Mega hesaplar: Engagement follower'dan geliyor, içerik kalitesinden değil
MEGA_ACCOUNTS_SKIP = {
    "elonmusk", "jack", "sundarpichai", "sataborasu",
    # Haber kopyala-yapıştır hesapları (link dump)
}

# Yazar başına max tweet limiti (dataset dengesini korumak için)
# Özel limitler: belirli yazarlar için override
AUTHOR_MAX_TWEETS = 150  # Genel default
AUTHOR_LIMITS_OVERRIDE = {
    "BeatstoBytes": 500,  # Berkay: yarı yarıya indir (1074 → ~500)
}


# ============================================================
# Hook tipi tespiti
# ============================================================
HOOK_PATTERNS = {
    "question": [
        r"^(neden|niye|nasıl|ne zaman|kim|hangi|kaç|what|why|how|when|who|which|did you)\b",
        r"\?$",
        r"^(hiç|ever|have you)\b",
    ],
    "list": [
        r"^\d+[\.\)]\s",
        r"(top \d+|en iyi \d+|\d+ madde|\d+ things|\d+ reasons|\d+ ways)",
        r"(thread|🧵)",
    ],
    "story": [
        r"^(story time|bir gün|one day|dün|yesterday|geçen|last|i remember|hatırlıyorum|anlatayım|let me tell)",
        r"^(bugün|today|this morning|bu sabah)",
    ],
    "bold_claim": [
        r"^(unpopular opinion|hot take|controversial|truth|gerçek|kimse|nobody|most people)",
        r"^(everyone|herkes|çoğu|most)\b",
    ],
    "data": [
        r"(\d+%|\d+x|istatistik|data|study|research|araştırma|according to|survey)",
        r"(experiment|deney|billion|milyon|million|milyar)",
    ],
    "challenge": [
        r"^(eğer|if you|try this|bunu dene|i dare|cesaret)",
        r"(change my mind|değiştir|prove me wrong|ispatla)",
    ],
    "emotional": [
        r"(heartbreaking|yürek|gözyaş|incredible|inanılmaz|beautiful|müthiş|amazing|harika|shocked|şok)",
        r"^(i can't believe|inanamıyorum|just|az önce)",
    ],
    "authority": [
        r"(after \d+ years|\d+ yıl|decade|i've spent|spent \d+|as a|olarak)",
        r"(expert|uzman|ceo|founder|kurucu|professor|dr\.)",
    ],
}


def detect_hook_type(content: str) -> str:
    lower = content.lower().strip()
    scores = defaultdict(int)
    for hook_type, patterns in HOOK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower, re.IGNORECASE | re.MULTILINE):
                scores[hook_type] += 1
    if scores:
        return max(scores, key=scores.get)
    return "direct"


# ============================================================
# Ton tespiti (gelişmiş)
# ============================================================
TONE_SIGNALS = {
    "raw": {
        "keywords": ["amk", "aq", "lan", "ulan", "fuck", "shit", "bruh", "lmao", "💀", "siktir"],
        "weight": 2,
    },
    "motivational": {
        "keywords": ["never give up", "keep going", "başar", "vazgeçme", "güçlü", "hayalini",
                      "inspire", "dream", "you can", "yapabilirsin", "believe", "inan"],
        "weight": 1,
    },
    "informative": {
        "keywords": ["thread", "🧵", "bilgi", "araştırma", "istatistik", "data", "study",
                      "research", "fact", "according", "report", "rapor"],
        "weight": 1,
    },
    "humorous": {
        "keywords": ["😂", "🤣", "lol", "haha", "komik", "djdjd", "sksksk", "💀", "bro", "abi"],
        "weight": 1,
    },
    "controversial": {
        "keywords": ["unpopular opinion", "hot take", "overrated", "nobody talks", "kimse konuşmuyor"],
        "weight": 2,
    },
    "storytelling": {
        "keywords": ["story time", "bir gün", "one day", "i remember", "hatırlıyorum", "anlatayım"],
        "weight": 2,
    },
    "analytical": {
        "keywords": ["because", "çünkü", "reason", "sebep", "analysis", "analiz", "therefore", "dolayısıyla"],
        "weight": 1,
    },
}


def detect_tone(content: str) -> str:
    lower = content.lower()
    scores = {}
    for tone, info in TONE_SIGNALS.items():
        score = sum(info["weight"] for kw in info["keywords"] if kw in lower)
        if score:
            scores[tone] = score
    return max(scores, key=scores.get) if scores else "conversational"


# ============================================================
# İçerik yapısı analizi
# ============================================================
def analyze_structure(content: str) -> str:
    lines = content.strip().split("\n")
    line_count = len([l for l in lines if l.strip()])

    if "🧵" in content or "thread" in content.lower():
        return "thread_starter"
    if line_count >= 5:
        return "multi_line"
    if any(re.match(r"^\d+[\.\)]", l.strip()) for l in lines):
        return "numbered_list"
    if all(l.strip().startswith(("•", "-", "→", "✅", "❌", "▪")) for l in lines if l.strip()):
        return "bullet_list"
    if len(content) < 100:
        return "short_punch"
    return "standard"


# ============================================================
# Konu çıkarma (gelişmiş)
# ============================================================
def extract_topic(content: str, hashtags: list | None) -> str:
    parts = []
    if hashtags and isinstance(hashtags, list):
        tags = [str(t).strip("#") for t in hashtags[:3] if t]
        parts.extend(tags)

    if not parts:
        text = URL_RE.sub("", content).strip()
        text = MENTION_RE.sub("", text).strip()
        text = HASHTAG_RE.sub("", text).strip()
        # İlk satırı konu olarak kullan (genelde hook)
        first_line = text.split("\n")[0].strip()
        topic = first_line[:80].strip()
        if topic:
            parts.append(topic + ("..." if len(first_line) > 80 else ""))

    return ", ".join(parts) if parts else "genel"


# ============================================================
# Kalite filtreleri
# ============================================================
def clean_content(content: str) -> str:
    """URL ve gereksiz boşlukları temizle, içeriği koru."""
    text = URL_RE.sub("", content).strip()
    # Birden fazla boş satırı teke indir
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def passes_quality_filter(tweet: dict, strict: bool = True) -> tuple[bool, str]:
    content = (tweet.get("content") or "").strip()
    handle = (tweet.get("author_handle") or "").lower()

    # 1. Boş / çok kısa
    if not content:
        return False, "empty"
    if len(content) < 10:
        return False, "too_short_raw"

    # 2. RT
    if content.startswith("RT @"):
        return False, "retweet"

    # 3. Mega hesap filtresi
    if handle in MEGA_ACCOUNTS_SKIP:
        return False, f"mega_account_{handle}"

    # 4. URL temizlendikten sonra kalan içerik
    cleaned = clean_content(content)
    if len(cleaned) < MIN_CONTENT_LENGTH:
        return False, "too_short_cleaned"

    if len(cleaned) > MAX_CONTENT_LENGTH:
        return False, "too_long"

    # 5. Çoğunluğu mention olan tweetler
    mentions_count = len(MENTION_RE.findall(content))
    words = content.split()
    if mentions_count > 0 and mentions_count / max(len(words), 1) > 0.5:
        return False, "mostly_mentions"

    # 6. Sadece emoji
    no_emoji = EMOJI_RE.sub("", cleaned).strip()
    if len(no_emoji) < 15:
        return False, "mostly_emoji"

    # 7. Duplicate / spam kalıpları
    if re.match(r"^(giveaway|airdrop|whitelist|rt\s*\+\s*follow|like\s*\+\s*rt)", cleaned.lower()):
        return False, "spam_pattern"

    # 8. Strict: Minimum kelime sayısı
    if strict:
        word_count = len(cleaned.split())
        if word_count < 5:
            return False, "too_few_words"

    # 9. News link dump: Kısa metin + URL = haber paylaşımı, yaratıcı değil
    has_url = bool(URL_RE.search(content))
    if has_url and len(cleaned.split()) < 15:
        return False, "news_link_dump"

    # 10. Media-dependent: Görselde değer var, text boş. Fine-tune için işe yaramaz.
    media = tweet.get("media_type") or "none"
    if media != "none" and len(cleaned.split()) < 15:
        return False, "media_dependent"

    # 11. Reaction tweets: Metin tek başına anlam ifade etmiyor
    REACTION_PATTERNS = [
        r"^(buna bak|şuna bak|yoruma bak|bunu izle|şunu izle|look at this|watch this)",
        r"^(ahahah|hahaha|djdjdj|sksksk|jsjsjsj|kdkdkd|asdfgh|lmao|lol|rofl)",
        r"^(oha|vay|lan|abi|bruh|bro|wow|omg|wtf|aynen|cidden|harbiden)\s*[😂🤣💀😭!]*$",
        r"^(ben|biz|adam|kadın|çocuk|herif)\s+(ya|😂|🤣|💀)",
        r"^(dead|i can.t|crying|screaming|help)\s*[😂🤣💀😭]*$",
    ]
    lower_cleaned = cleaned.lower().strip()
    for pattern in REACTION_PATTERNS:
        if re.match(pattern, lower_cleaned, re.IGNORECASE):
            return False, "reaction_tweet"

    # 12. Laughter-dominant: Metnin %50'den fazlası gülme/emoji
    laugh_chars = sum(1 for c in lower_cleaned if c in "ahjdskwlmf😂🤣💀😭")
    alpha_chars = sum(1 for c in lower_cleaned if c.isalpha())
    if alpha_chars > 0 and laugh_chars / max(alpha_chars, 1) > 0.4 and len(cleaned.split()) < 15:
        return False, "laughter_dominant"

    # 13. Quote/reply bait: Engagement manipulation
    BAIT_PATTERNS = [
        r"(like at|rt at|beğen|retweet yap|takip et|follow).*(takip|follow|like|rt)",
        r"(like if|rt if|retweet if|share if)",
        r"(giveaway|çekiliş|hediye|kazanan|airdrop|whitelist)",
        r"(bu tweeti beğenen|bu tweeti rt)",
    ]
    for pattern in BAIT_PATTERNS:
        if re.search(pattern, lower_cleaned, re.IGNORECASE):
            return False, "engagement_bait"

    return True, ""


# ============================================================
# JSONL mesaj oluşturma
# ============================================================
def build_training_example(tweet: dict) -> dict:
    content = tweet["content"].strip()
    niche = tweet.get("niche") or "genel"
    lang = tweet.get("language") or "tr"
    likes = tweet.get("likes") or 0
    hook_type = detect_hook_type(content)
    tone = detect_tone(content)
    structure = analyze_structure(content)
    topic = extract_topic(content, tweet.get("hashtags"))

    # Dil bazlı system prompt
    system_prompt = SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN

    # User prompt: Model neyi öğrenmesi gerektiğini anlamalı
    if lang == "tr":
        user_content = (
            f"Platform: X (Twitter)\n"
            f"Niche: {niche}\n"
            f"Dil: Türkçe\n"
            f"Ton: {tone}\n"
            f"Hook tipi: {hook_type}\n"
            f"Yapı: {structure}\n"
            f"Konu: {topic}"
        )
    else:
        user_content = (
            f"Platform: X (Twitter)\n"
            f"Niche: {niche}\n"
            f"Language: English\n"
            f"Tone: {tone}\n"
            f"Hook type: {hook_type}\n"
            f"Structure: {structure}\n"
            f"Topic: {topic}"
        )

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": content},
        ],
        "_meta": {
            "author": tweet.get("author_handle"),
            "likes": likes,
            "niche": niche,
            "lang": lang,
            "hook": hook_type,
            "tone": tone,
        },
    }


# ============================================================
# Supabase fetch
# ============================================================
def fetch_tweets(supabase_url: str, supabase_key: str, min_likes: int, verbose: bool) -> list[dict]:
    base = f"https://{supabase_url}" if not supabase_url.startswith("http") else supabase_url
    base = base.rstrip("/")
    url = f"{base}/rest/v1/viral_tweets"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "return=representation",
    }
    params = {
        "select": "content,likes,retweets,replies,quotes,bookmarks,impressions,"
                  "media_type,hashtags,mentions,language,engagement_rate,niche,"
                  "hook_type,author_handle,similarity_hash",
        "likes": f"gte.{min_likes}",
        "order": "likes.desc",
    }

    all_tweets = []
    offset = 0
    page_size = 1000

    with httpx.Client(timeout=30) as client:
        while True:
            params["offset"] = str(offset)
            params["limit"] = str(page_size)
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            all_tweets.extend(batch)
            if verbose:
                print(f"  📦 {len(batch)} tweet çekildi (toplam: {len(all_tweets)})")
            if len(batch) < page_size:
                break
            offset += page_size

    return all_tweets


# ============================================================
# Deduplication
# ============================================================
def deduplicate(tweets: list[dict]) -> list[dict]:
    """similarity_hash + content hash ile dedup."""
    seen_hashes = set()
    seen_content = set()
    unique = []

    for t in tweets:
        # DB'deki similarity_hash
        sim_hash = t.get("similarity_hash")
        if sim_hash and sim_hash in seen_hashes:
            continue

        # Content-based hash (normalize edip)
        content = (t.get("content") or "").strip().lower()
        content_norm = URL_RE.sub("", content).strip()
        content_hash = hashlib.md5(content_norm.encode()).hexdigest()

        if content_hash in seen_content:
            continue

        if sim_hash:
            seen_hashes.add(sim_hash)
        seen_content.add(content_hash)
        unique.append(t)

    return unique


# ============================================================
# Niche balancing
# ============================================================
def balance_niches(examples: list[dict], max_per_niche: int | None = None,
                   min_per_niche: int = 10) -> list[dict]:
    """Niche'leri dengele. Fazla olanları kırp, az olanları olduğu gibi bırak."""
    by_niche = defaultdict(list)
    for ex in examples:
        niche = ex["_meta"]["niche"]
        by_niche[niche].append(ex)

    if max_per_niche is None:
        # Medyan tabanlı: medyan * 2 üst limit
        counts = [len(v) for v in by_niche.values()]
        if counts:
            sorted_counts = sorted(counts)
            median = sorted_counts[len(sorted_counts) // 2]
            max_per_niche = max(median * 2, min_per_niche * 2)
        else:
            return examples

    balanced = []
    for niche, items in by_niche.items():
        if len(items) > max_per_niche:
            # En yüksek like'lıları tut
            items.sort(key=lambda x: x["_meta"]["likes"], reverse=True)
            balanced.extend(items[:max_per_niche])
        else:
            balanced.extend(items)

    return balanced


# ============================================================
# Token sayımı
# ============================================================
def count_tokens(text: str) -> int:
    if ENC:
        return len(ENC.encode(text))
    # Fallback: kelime sayısı * 1.3 (rough estimate)
    return int(len(text.split()) * 1.3)


def example_token_count(example: dict) -> int:
    return sum(count_tokens(m["content"]) for m in example["messages"])


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Type Hype fine-tuning veri hazırlama v2")
    parser.add_argument("--min-likes", type=int, default=1000)
    parser.add_argument("--output-dir", type=str, default="backend/data/")
    parser.add_argument("--split-ratio", type=float, default=0.9)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--balance", action="store_true", help="Niche balancing uygula")
    parser.add_argument("--max-per-niche", type=int, default=None, help="Niche başına max örnek")
    parser.add_argument("--no-meta", action="store_true", help="_meta alanını JSONL'den çıkar")
    args = parser.parse_args()

    load_env()

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        sys.exit("❌ SUPABASE_URL ve SUPABASE_SERVICE_KEY gerekli")

    supabase_url = supabase_url.replace("https://", "").replace("http://", "").rstrip("/")

    print("🚀 Type Hype Fine-tuning Veri Hazırlama v2")
    print(f"   Min likes: {args.min_likes} | Split: {args.split_ratio:.0%}/{1 - args.split_ratio:.0%}")
    if args.balance:
        print(f"   Niche balancing: ON (max: {args.max_per_niche or 'auto'})")
    print()

    # ── 1. Fetch ──
    print("📡 Supabase'den tweetler çekiliyor...")
    raw_tweets = fetch_tweets(supabase_url, supabase_key, args.min_likes, args.verbose)
    print(f"   ✅ {len(raw_tweets)} tweet çekildi")

    # ── 2. Dedup ──
    deduped = deduplicate(raw_tweets)
    dup_count = len(raw_tweets) - len(deduped)
    if dup_count:
        print(f"   🔄 {dup_count} duplicate kaldırıldı → {len(deduped)} unique")

    # ── 3. Quality filter ──
    filtered = []
    reject_reasons = Counter()
    for t in deduped:
        ok, reason = passes_quality_filter(t)
        if ok:
            filtered.append(t)
        else:
            reject_reasons[reason] += 1
            if args.verbose:
                c = (t.get("content") or "")[:60]
                print(f"   ⏭️  [{reason}] @{t.get('author_handle','?')}: {c}")

    print(f"   🔍 Kalite filtresi: {len(filtered)} geçti, {len(deduped) - len(filtered)} elendi")
    if reject_reasons:
        for reason, cnt in reject_reasons.most_common():
            print(f"      {reason}: {cnt}")

    if not filtered:
        sys.exit("❌ Filtre sonrası tweet kalmadı!")

    # ── 4. Build examples ──
    examples = []
    token_counts = []
    skipped_tokens = 0

    for t in filtered:
        ex = build_training_example(t)
        tokens = example_token_count(ex)
        if tokens > MAX_TOKENS_PER_EXAMPLE:
            skipped_tokens += 1
            if args.verbose:
                print(f"   ⏭️  [token_limit] {tokens} tokens: {t.get('content','')[:50]}")
            continue
        examples.append(ex)
        token_counts.append(tokens)

    if skipped_tokens:
        print(f"   ⚠️  {skipped_tokens} örnek token limiti aştı ({MAX_TOKENS_PER_EXAMPLE})")

    # ── 4b. Author capping ──
    from collections import defaultdict as dd
    by_author = dd(list)
    for ex in examples:
        by_author[ex["_meta"]["author"]].append(ex)
    
    capped = []
    capped_count = 0
    for author, items in by_author.items():
        limit = AUTHOR_LIMITS_OVERRIDE.get(author, AUTHOR_MAX_TWEETS)
        if len(items) > limit:
            # En yüksek like'lıları tut
            items.sort(key=lambda x: x["_meta"]["likes"], reverse=True)
            capped.extend(items[:limit])
            capped_count += len(items) - limit
            if args.verbose:
                print(f"   ✂️  @{author}: {len(items)} → {limit} (en iyi like'lılar)")
        else:
            capped.extend(items)
    
    if capped_count:
        print(f"   ✂️  Author capping: {len(examples)} → {len(capped)} ({capped_count} kırpıldı)")
        examples = capped
        token_counts = [example_token_count(ex) for ex in examples]

    # ── 5. Niche balancing ──
    if args.balance:
        before = len(examples)
        examples = balance_niches(examples, args.max_per_niche)
        if len(examples) != before:
            print(f"   ⚖️  Niche balancing: {before} → {len(examples)}")
            # Token counts'ı yeniden hesapla
            token_counts = [example_token_count(ex) for ex in examples]

    # ── 6. Stats ──
    niche_counter = Counter()
    lang_counter = Counter()
    hook_counter = Counter()
    tone_counter = Counter()
    author_counter = Counter()

    for ex in examples:
        m = ex["_meta"]
        niche_counter[m["niche"]] += 1
        lang_counter[m["lang"]] += 1
        hook_counter[m["hook"]] += 1
        tone_counter[m["tone"]] += 1
        author_counter[m["author"]] += 1

    avg_tokens = sum(token_counts) / max(len(token_counts), 1)
    total_tokens = sum(token_counts)

    print()
    print("📊 İstatistikler:")
    print(f"   Toplam örnek: {len(examples)}")
    print(f"   Toplam token: {total_tokens:,}")
    print(f"   Ortalama token: {avg_tokens:.0f} | Min: {min(token_counts)} | Max: {max(token_counts)}")

    # Together AI maliyet tahmini (3 epoch, Llama 4 Maverick: $8.00/1M token, min $16)
    cost_estimate = (total_tokens * 3 * 8.00) / 1_000_000
    cost_actual = max(cost_estimate, 16.00)  # Together AI minimum charge
    print(f"   💰 Tahmini fine-tune maliyeti: ~${cost_actual:.2f} (3 epoch, min $16)")
    print(f"      Model: meta-llama/Llama-4-Maverick-17B-128E-Instruct")

    print()
    print("   📂 Niche dağılımı:")
    for niche, cnt in niche_counter.most_common():
        pct = cnt / len(examples) * 100
        bar = "█" * int(pct / 2)
        print(f"      {niche:20s}: {cnt:4d} ({pct:5.1f}%) {bar}")

    print()
    print("   🌐 Dil dağılımı:")
    for lang, cnt in lang_counter.most_common():
        pct = cnt / len(examples) * 100
        print(f"      {lang}: {cnt} ({pct:.1f}%)")

    print()
    print("   🎣 Hook dağılımı:")
    for hook, cnt in hook_counter.most_common(8):
        pct = cnt / len(examples) * 100
        print(f"      {hook:20s}: {cnt:4d} ({pct:5.1f}%)")

    print()
    print("   🎭 Ton dağılımı:")
    for tone, cnt in tone_counter.most_common(8):
        pct = cnt / len(examples) * 100
        print(f"      {tone:20s}: {cnt:4d} ({pct:5.1f}%)")

    print()
    print("   👤 Top 10 yazar:")
    for author, cnt in author_counter.most_common(10):
        print(f"      @{author}: {cnt}")

    if args.dry_run:
        print("\n🏁 Dry-run tamamlandı. Dosya yazılmadı.")

        # Birkaç örnek göster
        print("\n📝 Örnek JSONL entries:")
        for ex in random.Random(args.seed).sample(examples, min(3, len(examples))):
            print(f"\n  --- @{ex['_meta']['author']} ({ex['_meta']['likes']}❤️, {ex['_meta']['niche']}) ---")
            for msg in ex["messages"]:
                role = msg["role"]
                content = msg["content"][:200]
                print(f"  [{role}]: {content}{'...' if len(msg['content']) > 200 else ''}")
        return

    # ── 7. Train/val split ──
    random.seed(args.seed)
    indices = list(range(len(examples)))
    random.shuffle(indices)
    split_idx = int(len(indices) * args.split_ratio)
    train_indices = indices[:split_idx]
    val_indices = indices[split_idx:]

    # ── 8. Write JSONL ──
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "finetune_train.jsonl"
    val_path = out_dir / "finetune_val.jsonl"
    stats_path = out_dir / "finetune_stats.json"

    def write_jsonl(path: Path, indices_list: list[int]):
        with open(path, "w", encoding="utf-8") as f:
            for i in indices_list:
                ex = examples[i].copy()
                if args.no_meta:
                    ex.pop("_meta", None)
                else:
                    # Together AI formatı: _meta'yı kaldır (sadece messages)
                    ex.pop("_meta", None)
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    write_jsonl(train_path, train_indices)
    write_jsonl(val_path, val_indices)

    # Stats dosyası (analiz için _meta'lı)
    stats = {
        "total_examples": len(examples),
        "train_count": len(train_indices),
        "val_count": len(val_indices),
        "total_tokens": total_tokens,
        "avg_tokens": round(avg_tokens, 1),
        "estimated_cost_3_epoch": round(cost_estimate, 2),
        "niche_distribution": dict(niche_counter.most_common()),
        "language_distribution": dict(lang_counter.most_common()),
        "hook_distribution": dict(hook_counter.most_common()),
        "tone_distribution": dict(tone_counter.most_common()),
        "top_authors": dict(author_counter.most_common(20)),
        "min_likes": args.min_likes,
        "filters_applied": {
            "min_content_length": MIN_CONTENT_LENGTH,
            "max_content_length": MAX_CONTENT_LENGTH,
            "max_tokens": MAX_TOKENS_PER_EXAMPLE,
            "mega_accounts_skipped": list(MEGA_ACCOUNTS_SKIP),
        },
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print()
    print("✅ Dosyalar yazıldı:")
    print(f"   📝 Train: {train_path} ({len(train_indices)} örnek)")
    print(f"   📝 Val:   {val_path} ({len(val_indices)} örnek)")
    print(f"   📊 Stats: {stats_path}")

    # Dosya boyutları
    for p in [train_path, val_path]:
        size_kb = p.stat().st_size / 1024
        print(f"   💾 {p.name}: {size_kb:.1f} KB")

    # ── 9. Format doğrulama ──
    print()
    print("🔍 Together AI format doğrulama:")
    errors = 0
    for path in [train_path, val_path]:
        with open(path) as f:
            for line_no, line in enumerate(f, 1):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    print(f"   ❌ {path.name}:{line_no} JSON parse hatası")
                    errors += 1
                    continue
                if "messages" not in obj:
                    print(f"   ❌ {path.name}:{line_no} 'messages' field eksik")
                    errors += 1
                    continue
                msgs = obj["messages"]
                if not isinstance(msgs, list) or len(msgs) < 2:
                    print(f"   ❌ {path.name}:{line_no} messages min 2 olmalı")
                    errors += 1
                    continue
                # İlk mesaj system veya user olmalı
                if msgs[0]["role"] not in ("system", "user"):
                    print(f"   ❌ {path.name}:{line_no} ilk mesaj system/user olmalı")
                    errors += 1
                # Son mesaj assistant olmalı
                if msgs[-1]["role"] != "assistant":
                    print(f"   ❌ {path.name}:{line_no} son mesaj assistant olmalı")
                    errors += 1
                # _meta olmamalı
                if "_meta" in obj:
                    print(f"   ❌ {path.name}:{line_no} _meta field kaldırılmamış")
                    errors += 1
                # Her mesajda role+content olmalı
                for m in msgs:
                    if "role" not in m or "content" not in m:
                        print(f"   ❌ {path.name}:{line_no} role/content eksik")
                        errors += 1
    if errors == 0:
        print("   ✅ Format doğrulama başarılı! Together AI'a yüklenmeye hazır.")
    else:
        print(f"   ⚠️  {errors} hata bulundu!")

    print(f"\n🏁 Tamamlandı!")
    print(f"   Sonraki adım: together files check {train_path}")
    print(f"   Model: meta-llama/Llama-4-Maverick-17B-128E-Instruct")


if __name__ == "__main__":
    main()
