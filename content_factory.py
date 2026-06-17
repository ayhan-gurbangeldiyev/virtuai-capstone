# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""Content Factory - AI News to Turkish Content Pipeline.

Fetches AI company news from RSS feeds, extracts content via Jina AI,
and sends to n8n webhook for processing.
"""

import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

# ———————————————————————————————————————————————————————————————
# LOGGING SETUP
# ———————————————————————————————————————————————————————————————

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ———————————————————————————————————————————————————————————————
# CONFIGURATION
# ———————————————————————————————————————————————————————————————

RSS_FEEDS: dict[str, str] = {
    # ===== ŞİRKET BLOGLARI =====
    "Anthropic News": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "Anthropic Engineering": "https://raw.githubusercontent.com/conoro/anthropic-engineering-rss-feed/main/anthropic_engineering_rss.xml",
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Google Research": "https://research.google/blog/rss/",
    "DeepMind": "https://deepmind.google/blog/rss.xml",
    "Meta AI": "https://rsshub.app/meta/ai/blog",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "LangChain": "https://blog.langchain.dev/rss/",
    "NVIDIA AI Blog": "https://developer.nvidia.com/blog/feed/",
    "Microsoft AI Blog": "https://blogs.microsoft.com/ai/feed/",
    "Microsoft Research": "https://www.microsoft.com/en-us/research/feed/",
    "AWS Machine Learning": "https://aws.amazon.com/blogs/machine-learning/feed/",
    "Replicate": "https://replicate.com/blog/rss",
    # ===== HABER KAYNAKLARI =====
    "Techmeme": "https://www.techmeme.com/feed.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat": "https://venturebeat.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Wired": "https://www.wired.com/feed/rss",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
    "SiliconANGLE": "https://siliconangle.com/feed/",
    # ===== DERİNLEMESİNE ANALİZ =====
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Ars Technica AI": "https://arstechnica.com/ai/feed/",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "IEEE Spectrum AI": "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
    # ===== ARAŞTIRMA =====
    "BAIR Blog": "https://bair.berkeley.edu/blog/feed.xml",
    "Distill.pub": "https://distill.pub/rss.xml",
    "ML@CMU": "https://blog.ml.cmu.edu/feed/",
    # ===== NEWSLETTER =====
    "The Rundown AI": "https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml",
    "TheSequence": "https://thesequence.substack.com/feed",
    "Latent Space": "https://www.latent.space/feed",
    "Ahead of AI": "https://magazine.sebastianraschka.com/feed",
    "AI Snake Oil": "https://aisnakeoil.substack.com/feed",
    # ===== COMMUNITY =====
    "Product Hunt AI": "https://www.producthunt.com/feed?category=artificial-intelligence",
    "Reddit r/MachineLearning": "https://www.reddit.com/r/MachineLearning/.rss",
}

MAX_ARTICLES_PER_SOURCE: int = 3
MAX_CONTENT_LENGTH: int = 8000
REQUEST_DELAY: int = 2  # seconds - for rate limiting
CUTOFF_DATE: datetime = datetime(2026, 1, 13, tzinfo=timezone.utc)
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def parse_date(pub_date: str) -> datetime | None:
    """Parse RFC 2822 date string to datetime.

    Args:
        pub_date: Date string in RFC 2822 format.

    Returns:
        Parsed datetime or None if parsing fails.
    """
    try:
        return parsedate_to_datetime(pub_date)
    except (ValueError, TypeError):
        return None


def get_webhook_url() -> str:
    """Get n8n webhook URL from environment variable.

    Returns:
        The webhook URL string.

    Raises:
        SystemExit: If N8N_WEBHOOK_URL is not set.
    """
    url = os.environ.get("N8N_WEBHOOK_URL")
    if not url:
        logger.error("N8N_WEBHOOK_URL environment variable is not set")
        sys.exit(1)
    return url


# ———————————————————————————————————————————————————————————————
# RSS FUNCTIONS
# ———————————————————————————————————————————————————————————————


def fetch_rss(url: str) -> list[dict]:
    """Fetch and parse RSS feed.

    Args:
        url: The RSS feed URL to fetch.

    Returns:
        List of dictionaries containing title, link, and pub_date.
    """
    try:
        logger.info(f"Fetching RSS: {url}")
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        items: list[dict] = []
        for item in root.findall(".//item")[:MAX_ARTICLES_PER_SOURCE]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            link = link_el.text.strip() if link_el is not None and link_el.text else ""
            pub_date = pub_date_el.text.strip() if pub_date_el is not None and pub_date_el.text else ""

            # Clean CDATA
            title = re.sub(r"<!\[CDATA\[|\]\]>", "", title)
            link = re.sub(r"<!\[CDATA\[|\]\]>", "", link)

            if title and link:
                # Check date filter
                parsed_date = parse_date(pub_date)
                if parsed_date is None:
                    logger.warning(f"Could not parse date, processing anyway: {title}")
                    items.append({"title": title, "link": link, "pub_date": pub_date})
                elif parsed_date < CUTOFF_DATE:
                    logger.info(f"Skipping old article: {title} (published {pub_date})")
                    continue
                else:
                    items.append({"title": title, "link": link, "pub_date": pub_date})

        logger.info(f"Found {len(items)} items")
        return items

    except requests.exceptions.Timeout:
        logger.error(f"RSS fetch timeout: {url}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"RSS fetch error: {e}")
        return []
    except ET.ParseError as e:
        logger.error(f"RSS parse error: {e}")
        return []


# ———————————————————————————————————————————————————————————————
# JINA AI FUNCTIONS
# ———————————————————————————————————————————————————————————————


def fetch_article_content(url: str) -> str:
    """Fetch article content via Jina AI Reader.

    Args:
        url: The article URL to fetch content from.

    Returns:
        Parsed markdown content or error message.
    """
    jina_url = f"https://r.jina.ai/{url}"

    try:
        logger.info(f"Fetching content via Jina: {url}")
        response = requests.get(jina_url, headers=REQUEST_HEADERS, timeout=60)
        raw_content = response.text

        # Parse: Get content after "Markdown Content:"
        content = raw_content

        if "Markdown Content:" in raw_content:
            content = raw_content.split("Markdown Content:")[-1].strip()
        else:
            # Alternative: Skip first few lines
            lines = raw_content.split("\n")
            start_idx = 0
            for i, line in enumerate(lines):
                if (
                    not line.startswith("Title:")
                    and not line.startswith("URL Source:")
                    and not line.startswith("Markdown Content:")
                    and len(line.strip()) > 50
                ):
                    start_idx = i
                    break
            content = "\n".join(lines[start_idx:]).strip()

        # Length limit
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."

        logger.info(f"Content fetched: {len(content)} chars")
        return content

    except requests.exceptions.Timeout:
        logger.error(f"Jina timeout for: {url}")
        return "Error fetching article: Timeout"
    except requests.exceptions.RequestException as e:
        logger.error(f"Jina error: {e}")
        return f"Error fetching article: {e}"


# ———————————————————————————————————————————————————————————————
# N8N WEBHOOK
# ———————————————————————————————————————————————————————————————


def send_to_n8n(data: dict, webhook_url: str) -> bool:
    """Send data to n8n webhook.

    Args:
        data: Dictionary containing article data.
        webhook_url: The n8n webhook URL.

    Returns:
        True if successful, False otherwise.
    """
    try:
        logger.info("Sending to n8n webhook...")
        response = requests.post(
            webhook_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        success = response.status_code == 200
        if success:
            logger.info("Successfully sent to n8n")
        else:
            logger.warning(f"n8n returned status: {response.status_code}")
        return success
    except requests.exceptions.Timeout:
        logger.error("n8n webhook timeout")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"n8n error: {e}")
        return False


# ———————————————————————————————————————————————————————————————
# MAIN
# ———————————————————————————————————————————————————————————————


def main() -> None:
    """Main entry point for Content Factory."""
    logger.info("=" * 60)
    logger.info(f"Content Factory - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)

    webhook_url = get_webhook_url()
    logger.info(f"Using webhook URL: {webhook_url}")

    total_sent = 0
    total_failed = 0

    for source_name, rss_url in RSS_FEEDS.items():
        logger.info("-" * 40)
        logger.info(f"Processing source: {source_name}")

        items = fetch_rss(rss_url)

        if not items:
            logger.warning(f"No items found for {source_name}")
            continue

        for item in items:
            logger.info(f"Article: {item['title'][:50]}...")

            # Fetch content
            content = fetch_article_content(item["link"])

            if content.startswith("Error"):
                logger.error(f"Failed to fetch content: {content}")
                total_failed += 1
                continue

            # Send to n8n
            payload = {
                "title": item["title"],
                "link": item["link"],
                "pub_date": item["pub_date"],
                "source": source_name,
                "content": content,
            }

            success = send_to_n8n(payload, webhook_url)

            if success:
                total_sent += 1
            else:
                total_failed += 1

            # Rate limit
            time.sleep(REQUEST_DELAY)

    logger.info("=" * 60)
    logger.info(f"SUMMARY: {total_sent} sent, {total_failed} failed")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
