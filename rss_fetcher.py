"""RSS Fetcher - GitHub Actions -> Supabase Direct Pipeline.

Fetches RSS feeds from Supabase rss_feeds table, parses them,
and writes normalized signals directly to raw_signals table.
No n8n webhook, no Jina AI - pure RSS ingestion.

Usage:
    python rss_fetcher.py                    # Normal run
    python rss_fetcher.py --cutoff-hours 12  # Custom cutoff
    python rss_fetcher.py --dry-run          # Parse but don't write
"""

import argparse
import logging
import os
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

# ———————————————————————————————————————————————————————————————
# LOGGING
# ———————————————————————————————————————————————————————————————

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rss_fetcher")

# ———————————————————————————————————————————————————————————————
# CONFIG
# ———————————————————————————————————————————————————————————————

MAX_ARTICLES_PER_FEED = 5
REQUEST_TIMEOUT = 30  # seconds
BATCH_INSERT_SIZE = 50  # rows per Supabase POST
RATE_LIMIT_DELAY = 0.5  # seconds between feed fetches
USER_AGENT = "TypeHype-RSS/1.0 (github.com/berkay; bot)"

# Atom namespace
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


# ———————————————————————————————————————————————————————————————
# SUPABASE CLIENT (lightweight, no SDK dependency)
# ———————————————————————————————————————————————————————————————


class SupabaseClient:
    """Minimal Supabase REST client using PostgREST."""

    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not self.url or not self.key:
            log.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
            sys.exit(1)
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def get_active_feeds(self) -> list[dict]:
        """Fetch active RSS feeds from rss_feeds table."""
        resp = requests.get(
            f"{self.url}/rest/v1/rss_feeds?is_active=eq.true&select=id,source,rss_url,niche,language,priority",
            headers=self.headers,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        feeds = resp.json()
        log.info(f"Loaded {len(feeds)} active feeds from Supabase")
        return feeds

    def batch_insert_signals(self, signals: list[dict]) -> int:
        """Insert signals into raw_signals, skip duplicates on url."""
        if not signals:
            return 0

        inserted = 0
        for i in range(0, len(signals), BATCH_INSERT_SIZE):
            batch = signals[i : i + BATCH_INSERT_SIZE]
            resp = requests.post(
                f"{self.url}/rest/v1/raw_signals",
                headers={
                    **self.headers,
                    # On conflict with url: ignore duplicate
                    "Prefer": "return=minimal,resolution=ignore-duplicates",
                },
                json=batch,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code in (200, 201):
                inserted += len(batch)
                log.info(f"Inserted batch {i // BATCH_INSERT_SIZE + 1}: {len(batch)} signals")
            elif resp.status_code == 409:
                # All duplicates, expected
                log.info(f"Batch {i // BATCH_INSERT_SIZE + 1}: all duplicates, skipped")
            else:
                log.error(f"Insert failed ({resp.status_code}): {resp.text[:200]}")

        return inserted

    def update_feed_health(self, feed_id: str, success: bool, error_msg: str | None = None):
        """Update feed health tracking after fetch attempt."""
        now = datetime.now(timezone.utc).isoformat()
        body: dict = {"last_fetched": now}

        if success:
            body["last_status"] = "ok"
            body["error_count"] = 0
        else:
            body["last_status"] = f"error: {error_msg[:100]}" if error_msg else "error"
            # Increment error_count via RPC would be better, but PATCH works for now
            # We'll just set it; the real increment needs a DB function

        resp = requests.patch(
            f"{self.url}/rest/v1/rss_feeds?id=eq.{feed_id}",
            headers=self.headers,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code not in (200, 204):
            log.warning(f"Feed health update failed for {feed_id}: {resp.status_code}")


# ———————————————————————————————————————————————————————————————
# RSS PARSING
# ———————————————————————————————————————————————————————————————


def parse_date(date_str: str) -> datetime | None:
    """Parse various date formats found in RSS/Atom feeds."""
    if not date_str:
        return None

    # RFC 2822 (RSS standard)
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass

    # ISO 8601 (Atom standard)
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def extract_text(element: ET.Element | None) -> str:
    """Extract text from XML element, handling None safely."""
    if element is None:
        return ""
    return (element.text or "").strip()


def parse_rss_xml(xml_content: bytes, max_items: int = MAX_ARTICLES_PER_FEED) -> list[dict]:
    """Parse RSS or Atom XML into normalized items.

    Returns list of dicts with keys: title, url, published_at, description
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValueError(f"XML parse error: {e}") from e

    items = []

    # --- RSS 2.0 format ---
    for item in root.findall(".//item")[:max_items]:
        title = extract_text(item.find("title"))
        link = extract_text(item.find("link"))
        pub_date = extract_text(item.find("pubDate"))
        description = extract_text(item.find("description"))

        # Some feeds use dc:date instead of pubDate
        if not pub_date:
            dc_date = item.find("{http://purl.org/dc/elements/1.1/}date")
            pub_date = extract_text(dc_date)

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "published_at": pub_date,
                "description": description[:2000] if description else "",
            })

    # --- Atom format (if no RSS items found) ---
    if not items:
        for entry in root.findall("atom:entry", ATOM_NS)[:max_items]:
            title = extract_text(entry.find("atom:title", ATOM_NS))

            # Atom links are in <link> elements with href attribute
            link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)
            if link_el is None:
                link_el = entry.find("atom:link", ATOM_NS)
            link = link_el.get("href", "") if link_el is not None else ""

            updated = extract_text(entry.find("atom:updated", ATOM_NS))
            published = extract_text(entry.find("atom:published", ATOM_NS))
            summary = extract_text(entry.find("atom:summary", ATOM_NS))
            content_el = entry.find("atom:content", ATOM_NS)
            content = extract_text(content_el)

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "published_at": published or updated,
                    "description": (summary or content)[:2000],
                })

    return items


def fetch_and_parse_feed(feed: dict, cutoff: datetime) -> tuple[list[dict], str | None]:
    """Fetch a single RSS feed and return normalized signals.

    Args:
        feed: dict with keys from rss_feeds table (id, source, rss_url, niche, ...)
        cutoff: Only include articles published after this datetime

    Returns:
        (signals, error_msg) - signals list and optional error string
    """
    url = feed["rss_url"]
    source_name = feed["source"]
    niche = feed.get("niche", "")

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return [], f"Timeout fetching {url}"
    except requests.exceptions.RequestException as e:
        return [], f"HTTP error: {e}"

    try:
        items = parse_rss_xml(resp.content)
    except ValueError as e:
        return [], str(e)

    if not items:
        return [], None  # No error, just empty feed

    # Filter by cutoff date and normalize to raw_signal schema
    signals = []
    batch_id = str(uuid.uuid4())

    for item in items:
        parsed_date = parse_date(item["published_at"])

        # Skip old articles (if date is parseable)
        if parsed_date and parsed_date < cutoff:
            continue

        # If date unparseable, include it (better to have extra than miss)
        published_iso = parsed_date.isoformat() if parsed_date else None

        signal = {
            "source_type": "rss",
            "source_name": source_name,
            "niche": niche,
            "title": item["title"][:500],
            "url": item["url"][:2000],
            "raw_data": {
                "description": item["description"],
                "published_at": published_iso,
                "feed_url": url,
                "language": feed.get("language", "en"),
            },
            "status": "pending",
            "batch_id": batch_id,
        }
        signals.append(signal)

    return signals, None


# ———————————————————————————————————————————————————————————————
# FALLBACK: HARDCODED FEEDS (if Supabase rss_feeds is empty)
# ———————————————————————————————————————————————————————————————

FALLBACK_FEEDS = [
    {"id": "fallback-1", "source": "OpenAI News", "rss_url": "https://openai.com/news/rss.xml", "niche": "ai", "language": "en", "priority": "High"},
    {"id": "fallback-2", "source": "Google AI Blog", "rss_url": "https://research.google/blog/rss/", "niche": "ai", "language": "en", "priority": "High"},
    {"id": "fallback-3", "source": "Hugging Face Blog", "rss_url": "https://huggingface.co/blog/feed.xml", "niche": "ai", "language": "en", "priority": "High"},
    {"id": "fallback-4", "source": "TechCrunch AI", "rss_url": "https://techcrunch.com/category/artificial-intelligence/feed/", "niche": "ai", "language": "en", "priority": "High"},
    {"id": "fallback-5", "source": "Ars Technica AI", "rss_url": "https://arstechnica.com/ai/feed/", "niche": "ai", "language": "en", "priority": "High"},
    {"id": "fallback-6", "source": "The Verge", "rss_url": "https://www.theverge.com/rss/index.xml", "niche": "ai", "language": "en", "priority": "Medium"},
]


# ———————————————————————————————————————————————————————————————
# MAIN
# ———————————————————————————————————————————————————————————————


def main():
    parser = argparse.ArgumentParser(description="RSS Fetcher for Type Hype Pipeline")
    parser.add_argument("--cutoff-hours", type=int, default=6, help="Only fetch articles from last N hours (default: 6)")
    parser.add_argument("--dry-run", action="store_true", help="Parse feeds but don't write to Supabase")
    parser.add_argument("--max-feeds", type=int, default=0, help="Limit number of feeds to process (0 = all)")
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.cutoff_hours)
    log.info(f"RSS Fetcher started | cutoff={cutoff.isoformat()} | dry_run={args.dry_run}")

    # Init Supabase (always init for reading feeds; dry_run only skips writes)
    db = SupabaseClient()

    # Get feed list
    try:
        feeds = db.get_active_feeds()
    except Exception as e:
        log.warning(f"Could not load feeds from Supabase: {e}")
        feeds = []

    if not feeds:
        log.warning("No feeds from Supabase, using fallback list")
        feeds = FALLBACK_FEEDS

    if args.max_feeds > 0:
        feeds = feeds[: args.max_feeds]
        log.info(f"Limited to {args.max_feeds} feeds")

    # Process feeds
    all_signals = []
    success_count = 0
    error_count = 0
    skip_count = 0

    for i, feed in enumerate(feeds):
        source = feed.get("source", feed.get("rss_url", "?"))
        log.info(f"[{i + 1}/{len(feeds)}] {source}")

        signals, error = fetch_and_parse_feed(feed, cutoff)

        if error:
            log.error(f"  FAIL: {error}")
            error_count += 1
            if db and feed.get("id"):
                db.update_feed_health(feed["id"], success=False, error_msg=error)
        elif not signals:
            log.info(f"  No new articles after cutoff")
            skip_count += 1
            if db and feed.get("id"):
                db.update_feed_health(feed["id"], success=True)
        else:
            log.info(f"  Found {len(signals)} new articles")
            all_signals.extend(signals)
            success_count += 1
            if db and feed.get("id"):
                db.update_feed_health(feed["id"], success=True)

        # Rate limit between feeds
        if i < len(feeds) - 1:
            time.sleep(RATE_LIMIT_DELAY)

    # Insert to Supabase
    inserted = 0
    if all_signals and not args.dry_run:
        log.info(f"Inserting {len(all_signals)} signals to Supabase...")
        inserted = db.batch_insert_signals(all_signals)

    # Trigger FastAPI process-signals if new signals were inserted
    if inserted > 0 and not args.dry_run:
        try:
            api_host = os.environ.get("API_HOST", "https://api.typehype.io")
            cron_secret = os.environ.get("CRON_SECRET", "")
            resp = requests.post(
                f"{api_host}/api/trends/process-signals",
                headers={"X-Cron-Secret": cron_secret},
                timeout=60,
            )
            log.info(f"Triggered process-signals: {resp.status_code}")
        except Exception as e:
            log.warning(f"Could not trigger process-signals: {e}")

    # Summary
    log.info("=" * 50)
    log.info(f"DONE | feeds={len(feeds)} ok={success_count} err={error_count} skip={skip_count}")
    log.info(f"     | signals={len(all_signals)} inserted={inserted}")
    log.info("=" * 50)

    # Exit with error if too many feeds failed (>50%)
    if error_count > len(feeds) * 0.5:
        log.error("More than 50% of feeds failed, exiting with error")
        sys.exit(1)


if __name__ == "__main__":
    main()
