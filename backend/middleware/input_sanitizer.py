"""
Input Validation & Prompt Injection Protection.
"""
import re
import html
import logging
import unicodedata
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Max lengths
MAX_TOPIC_LENGTH = 500
MAX_CONTEXT_LENGTH = 1000
MAX_TWEET_CONTENT_LENGTH = 2000

# Prompt injection patterns (case-insensitive)
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"disregard\s+(all\s+)?above",
    r"forget\s+(all\s+)?previous",
    r"forget\s+(all\s+)?instructions",
    r"system\s*:",
    r"you\s+are\s+(now\s+)?(a|an)\s+",
    r"act\s+as\s+(a|an)\s+",
    r"pretend\s+(to\s+be|you\s+are)",
    r"new\s+instructions?\s*:",
    r"override\s+(previous|system)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"\[system\]",
    r"\[instructions?\]",
    r"<\s*system\s*>",
]

_compiled_patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

# HTML/script tag patterns
HTML_TAG_PATTERN = re.compile(r"<[^>]+>", re.IGNORECASE)
SCRIPT_PATTERN = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)

# URL validation
URL_PATTERN = re.compile(
    r"^https?://(twitter\.com|x\.com|mobile\.twitter\.com)/.+/status/\d+",
    re.IGNORECASE
)


def _normalize_unicode(text: str) -> str:
    """Normalize Unicode to prevent lookalike character bypass.

    NFKC normalization converts characters like ⅰ→i, ⅿ→m, ℰ→E etc.
    Also strips zero-width and control characters that could hide
    injection payloads between pattern tokens.
    """
    normalized = unicodedata.normalize("NFKC", text)
    # Strip zero-width and invisible control characters (Cf, Cc categories)
    # except common whitespace (\n, \r, \t)
    return "".join(
        c for c in normalized
        if unicodedata.category(c)[0] != "C" or c in "\n\r\t"
    )


def _check_prompt_injection(text: str) -> bool:
    """Return True if prompt injection detected."""
    # Normalize Unicode before checking — prevents lookalike bypass
    normalized = _normalize_unicode(text)
    for pattern in _compiled_patterns:
        if pattern.search(normalized):
            return True
    return False


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = SCRIPT_PATTERN.sub("", text)
    text = HTML_TAG_PATTERN.sub("", text)
    text = html.unescape(text)
    return text


def sanitize_topic(topic: str) -> str:
    """Validate and sanitize topic field."""
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="Konu boş olamaz")

    topic = _strip_html(topic.strip())

    if len(topic) > MAX_TOPIC_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Konu çok uzun (max {MAX_TOPIC_LENGTH} karakter)"
        )

    if _check_prompt_injection(topic):
        logger.warning(f"Prompt injection detected in topic: {topic[:100]}")
        raise HTTPException(status_code=400, detail="Geçersiz içerik tespit edildi")

    return topic


def sanitize_context(context: str | None) -> str | None:
    """Validate and sanitize additional_context field."""
    if not context:
        return context

    context = _strip_html(context.strip())

    if len(context) > MAX_CONTEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Ek bağlam çok uzun (max {MAX_CONTEXT_LENGTH} karakter)"
        )

    if _check_prompt_injection(context):
        logger.warning(f"Prompt injection detected in context: {context[:100]}")
        raise HTTPException(status_code=400, detail="Geçersiz içerik tespit edildi")

    return context


def sanitize_tweet_url(url: str) -> str:
    """Validate tweet URL format."""
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="Tweet URL gerekli")

    url = url.strip()

    if not URL_PATTERN.match(url):
        # Allow plain tweet IDs too
        if not url.isdigit():
            raise HTTPException(status_code=400, detail="Geçersiz tweet URL formatı")

    return url


def sanitize_tweet_content(content: str | None) -> str | None:
    """Validate and sanitize tweet content."""
    if not content:
        return content

    content = _strip_html(content.strip())

    if len(content) > MAX_TWEET_CONTENT_LENGTH:
        content = content[:MAX_TWEET_CONTENT_LENGTH]

    if _check_prompt_injection(content):
        logger.warning(f"Prompt injection detected in tweet content: {content[:100]}")
        raise HTTPException(status_code=400, detail="Geçersiz içerik tespit edildi")

    return content


def sanitize_generation_request(request) -> None:
    """
    Sanitize a generation request in-place.
    Works with TweetGenerateRequest, QuoteGenerateRequest, ReplyGenerateRequest, ArticleGenerateRequest.
    """
    if hasattr(request, "topic"):
        request.topic = sanitize_topic(request.topic)

    if hasattr(request, "additional_context"):
        request.additional_context = sanitize_context(request.additional_context)

    if hasattr(request, "tweet_url"):
        request.tweet_url = sanitize_tweet_url(request.tweet_url)

    if hasattr(request, "tweet_content"):
        request.tweet_content = sanitize_tweet_content(request.tweet_content)
