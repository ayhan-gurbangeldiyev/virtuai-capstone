"""Postiz REST client + CrewAI tool wrapper.

Docs: https://docs.postiz.com/public-api
Rate limit: 30 requests/hour per API key (tüm endpoint'ler birlikte).

Phase 20: multi-platform support — single POST /posts call carrying multiple
`posts: [...]` entries (one per platform), all scheduled to the same `date`.
"""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
try:
    from crewai.tools import tool
except ImportError:
    # Backend (contentfactory venv) reuses PostizClient without crewai.
    # The @tool decoration below is only used by Hype Crew Flow agents;
    # falling back to a no-op decorator keeps the file importable.
    def tool(*args, **kwargs):  # type: ignore[no-redef]
        def _decorate(fn):
            return fn
        # Support both @tool and @tool("name") usages.
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate
from loguru import logger

from config import settings


def _log_http_error(label: str, response: httpx.Response, request_body: Optional[Any] = None) -> None:
    """Dump response body + request body before raise_for_status. Postiz returns
    structured JSON error messages on 4xx that are critical for diagnosis."""
    try:
        body_text = response.text
    except Exception:
        body_text = "<unreadable>"
    logger.error(
        f"[postiz.{label}] HTTP {response.status_code} {response.reason_phrase} — body: {body_text[:1800]}"
    )
    if request_body is not None:
        try:
            req_str = json.dumps(request_body, default=str)
        except Exception:
            req_str = str(request_body)
        logger.error(f"[postiz.{label}] request payload: {req_str[:2200]}")


# Postiz `__type` mapping (verified from Postiz public docs 2026-05-16):
# - twitter → "x"  (rebrand; Postiz still accepts "twitter" for backcompat but prefers "x")
# - linkedin → "linkedin"
# - devto → "devto"
# - instagram → "instagram" (Postiz lists identifier 'instagram-standalone' for
#                           Facebook-unlinked accounts but post __type is still
#                           'instagram')
# - youtube → "youtube"
# - medium → "medium"
POSTIZ_TYPE_BY_PROVIDER = {
    "twitter": "x",
    "x": "x",
    "linkedin": "linkedin",
    "devto": "devto",
    "instagram": "instagram",
    "instagram-standalone": "instagram",
    "youtube": "youtube",
    "medium": "medium",
}


@dataclass(frozen=True)
class PlatformPost:
    """One platform's slice of a multi-platform schedule call."""

    integration_id: str
    provider: str                       # 'twitter' | 'linkedin' | 'devto' | ...
    content: str
    title: Optional[str] = None         # required for devto/medium articles
    tags: Optional[list[str]] = None    # devto/medium tags
    # Postiz returns {id, path} from /upload; pass both so Postiz can use the
    # CDN-hosted image without re-fetching.
    media: Optional[list[dict[str, str]]] = None
    # Phase 40 — when True, `media` contains an MP4/video reference (not image).
    # Drives Postiz settings (YT requires title+type, IG switches to Reels).
    is_video: bool = False


def _settings_for_platform(post: PlatformPost) -> dict[str, Any]:
    """Build the platform-specific `settings` block Postiz expects.

    Each provider has slightly different fields (devto needs title+tags, linkedin
    has post_as_images_carousel toggle, x is bare). Keep all in one place.
    """
    type_value = POSTIZ_TYPE_BY_PROVIDER.get(post.provider.lower())
    if not type_value:
        raise ValueError(f"unknown Postiz provider: {post.provider!r}")

    base: dict[str, Any] = {"__type": type_value}

    if type_value == "x":
        # Twitter/X — bare settings, optional `who_can_reply_post`
        base["who_can_reply_post"] = "everyone"
    elif type_value == "linkedin":
        # LinkedIn — text, image, native video, or multi-image carousel.
        # Postiz LinkedIn settings: post_as_images_carousel (bool).
        #   - text only (no media):           carousel=False
        #   - single image OR native video:   carousel=False
        #   - 2+ images:                      carousel=True (PDF-style carousel)
        # LinkedIn auto-detects the media type from the upload's MIME, so
        # we don't need a separate `is_video` flag in settings; we just
        # pass media[] through and toggle carousel only when 2+ images.
        is_carousel = (
            bool(post.media)
            and not post.is_video
            and len(post.media) >= 2
        )
        base["post_as_images_carousel"] = is_carousel
    elif type_value == "devto":
        # Dev.to — Postiz docs: https://docs.postiz.com/public-api/providers/devto
        #   { __type: "devto", title (required, ≥2 chars),
        #     main_image: {id, path}     ← cover image, same shape as upload
        #     tags: [{value, label}]     ← max 4, string values (lowercased)
        #     canonical: string (opt),    organization: string (opt) }
        #
        # The earlier "tags must be numeric ID" assumption was wrong — Postiz
        # accepts {value,label} string pairs the same way YouTube does. We
        # cap tags at 4 (Dev.to article limit) and pass the same upload
        # payload as `main_image` when the caller uploaded an image.
        if not post.title:
            raise ValueError("devto post requires `title`")
        base["title"] = post.title

        # main_image: only attach when caller uploaded an IMAGE (not a video)
        # Postiz devto API does not document a video cover, and using a video
        # media reference here would 400.
        if post.media and not post.is_video:
            first = post.media[0]
            if isinstance(first, dict) and first.get("id"):
                base["main_image"] = {
                    "id": str(first.get("id") or ""),
                    "path": str(first.get("path") or ""),
                }

        # tags intentionally omitted (2026-06-04 incident): Postiz's devto
        # endpoint now validates `tags.value` as a numeric tag ID, returning
        # 400 "posts.N.settings.tags.0.value must be a number" for string
        # values. We don't have a tag-ID lookup table, so the safe action is
        # to publish without tags — devto auto-tags from content content
        # otherwise. Re-enable when Postiz publishes a stable schema. The
        # raw `post.tags` value is preserved on the PlatformPost dataclass
        # so future code can re-attach if/when supported.
        _ = post.tags  # acknowledged, intentionally unused
    elif type_value == "medium":
        if not post.title:
            raise ValueError("medium post requires `title`")
        base["title"] = post.title
        if post.tags:
            base["tags"] = post.tags[:5]
    elif type_value == "instagram":
        # Instagram — needs media (image OR video) AND `post_type`.
        # Postiz' validator (2026-06-06) only accepts {"post", "story"}.
        # Sending "reel" → HTTP 400:
        #   'posts.0.settings.post_type must be one of "post" or "story"'
        # which was the 6 Haz 2026 IG-stuck-pending_review bug. Video on
        # Instagram is still a Reel at the platform level — Postiz' API
        # just uses post_type="post" + a video media id to drive it.
        if not post.media:
            raise ValueError("instagram post requires `media` (use PostizClient.upload_image_url first)")
        base["post_type"] = "post"
    elif type_value == "youtube":
        # Phase 40 — YouTube settings per Postiz docs: title (2-100 chars),
        # type (visibility), selfDeclaredMadeForKids, tags.
        # https://docs.postiz.com/public-api/providers/youtube.md
        if not post.media:
            raise ValueError("youtube post requires `media` (video MP4)")
        if not post.is_video:
            raise ValueError("youtube post requires a video media reference (is_video=True)")
        # Title falls back to first 95 chars of content if not explicitly set.
        title = post.title or (post.content or "").strip().split("\n")[0][:95] or "Cansu Dut"
        # Postiz enforces 2-100 char title length.
        title = title[:100]
        if len(title) < 2:
            title = "Cansu Dut"
        base["title"] = title
        base["type"] = "public"  # public | unlisted | private
        base["selfDeclaredMadeForKids"] = "no"
        if post.tags:
            base["tags"] = [{"value": t, "label": t} for t in post.tags[:10]]
        else:
            base["tags"] = []
    return base


def _value_for_post(post: PlatformPost) -> list[dict[str, Any]]:
    """Build the `value` list (each item = one piece of content in the post).

    Postiz now ALWAYS requires an `image` array on every value entry — even
    text-only posts must include an empty `image: []`. Sending no key returns
    400 `posts.N.value.0.image must be an array`.
    """
    entry: dict[str, Any] = {
        "content": post.content,
        "image": list(post.media) if post.media else [],
    }
    return [entry]


class PostizClient:
    """Thin wrapper around Postiz Public API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.postiz_api_key
        self.base_url = (base_url or settings.postiz_base_url).rstrip("/")
        # `Authorization: <key>` (Postiz uses raw key, not "Bearer <key>")
        self._headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

    def upload_image_url(self, image_url: str, timeout: float = 60.0) -> dict[str, str]:
        """Download an image from a public URL and POST it to Postiz /upload.

        Postiz returns ``{id, path}`` — pass that dict (or list of dicts) back as
        ``PlatformPost.media`` so the platform's Postiz post call references it
        by id. Instagram in particular rejects URL-only media.
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set; cannot upload image.")
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(image_url)
            r.raise_for_status()
            data = r.content
            content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            filename = image_url.rsplit("/", 1)[-1].split("?")[0] or "image.jpg"
            logger.info(
                f"postiz.upload size={len(data)} bytes type={content_type} name={filename}"
            )
            upload = client.post(
                f"{self.base_url}/upload",
                # No JSON Content-Type — httpx sets multipart boundary itself.
                headers={"Authorization": self.api_key},
                files={"file": (filename, data, content_type)},
            )
            if not upload.is_success:
                _log_http_error("upload_image", upload, request_body={"filename": filename, "size": len(data), "content_type": content_type})
            upload.raise_for_status()
            payload = upload.json()
        # Normalise — older Postiz versions may return {id} only, newer return {id, path}.
        if isinstance(payload, dict):
            return {
                "id": str(payload.get("id") or ""),
                "path": str(payload.get("path") or payload.get("url") or ""),
            }
        raise RuntimeError(f"unexpected Postiz upload response: {payload!r}")

    def schedule_posts(
        self,
        posts: list[PlatformPost],
        scheduled_at: datetime,
    ) -> dict[str, Any]:
        """Schedule multi-platform posts in a single API call.

        Returns Postiz response dict. Each platform shows up as a separate item
        in the `posts` field of the response (some Postiz versions return a list).
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set; cannot publish.")
        if not posts:
            raise ValueError("schedule_posts requires at least one PlatformPost")

        # Postiz now requires top-level `shortLink` (bool) and `tags` (array)
        # even when neither is meaningful for our pipeline. Without them we get
        # 400 `shortLink should not be null or undefined` + `tags must be an array`.
        body = {
            "type": "schedule",
            "date": scheduled_at.astimezone(timezone.utc).isoformat(),
            "shortLink": False,
            "tags": [],
            "posts": [
                {
                    "integration": {"id": p.integration_id},
                    "value": _value_for_post(p),
                    "settings": _settings_for_platform(p),
                }
                for p in posts
            ],
        }
        logger.info(
            f"postiz.schedule_posts platforms={[p.provider for p in posts]} "
            f"date={scheduled_at.astimezone(timezone.utc).isoformat()}"
        )
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{self.base_url}/posts", headers=self._headers, json=body)
            if not r.is_success:
                _log_http_error("schedule_posts", r, request_body=body)
            r.raise_for_status()
            return r.json()

    # Backwards-compatible single-platform shim (existing callers still work).
    def schedule_post(
        self,
        integration_id: str,
        content: str,
        scheduled_at: datetime,
        provider: str = "twitter",
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        return self.schedule_posts(
            [PlatformPost(
                integration_id=integration_id,
                provider=provider,
                content=content,
                title=title,
                tags=tags,
            )],
            scheduled_at,
        )

    def cancel_post(self, post_id: str) -> bool:
        """Cancel a scheduled post (not yet published)."""
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.delete(f"{self.base_url}/posts/{post_id}", headers=self._headers)
            return r.status_code in (200, 204)

    def get_post_status(self, post_id: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/posts/{post_id}", headers=self._headers)
            r.raise_for_status()
            return r.json()

    def get_post_analytics(self, post_id: str, days: int = 7) -> list[dict[str, Any]]:
        """Fetch engagement analytics for a published post.

        Endpoint: GET /analytics/post/{postId}?date={days}

        Returns an array of metric label objects, e.g.:
            [
              {"label": "Likes", "data": [{"total": "150", "date": "..."}], "percentageChange": 16.7},
              {"label": "Impressions", "data": [...], "percentageChange": ...},
              ...
            ]

        Note: only works for posts with state=PUBLISHED + a valid releaseId.
        Posts whose releaseId is 'missing' need POST /posts/{id}/release-id
        (Postiz Update Release ID endpoint) before analytics tracking starts.

        Raises httpx.HTTPStatusError on 4xx/5xx — caller should handle gracefully
        (e.g. unpublished posts return 404 or empty array).
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{self.base_url}/analytics/post/{post_id}",
                headers=self._headers,
                params={"date": str(days)},
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []

    def list_posts(
        self, *, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Fetch posts within a date range. Returns list of post objects with
        fields: id, content, publishDate, releaseURL, state (QUEUE|PUBLISHED|
        ERROR|DRAFT), integration.{id, providerIdentifier, name, picture}.

        Used by the engagement poller to filter PUBLISHED-state posts before
        spending an analytics API call.
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.get(
                f"{self.base_url}/posts",
                headers=self._headers,
                params={"startDate": start_date, "endDate": end_date},
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("posts", [])

    # ─── Phase 36 — Social Media Manager UI (Berkay 30 May 2026) ─────────

    def list_integrations(self) -> list[dict[str, Any]]:
        """GET /integrations → connected channels list.

        Each entry: {id, name, identifier, picture, disabled, profile, customer}.
        `identifier` is the canonical platform key (x, linkedin, linkedin-page,
        youtube, instagram, devto, tiktok, facebook, threads, ...).
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/integrations", headers=self._headers)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else data.get("integrations", [])

    def upload_from_url(self, public_url: str) -> dict[str, str]:
        """POST /upload-from-url — Postiz fetches the URL server-side and
        stores the asset. Skips the download-then-multipart roundtrip.

        Returns ``{id, path}``. Use for HeyGen/Supabase media that's already
        on a public HTTPS URL.
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{self.base_url}/upload-from-url",
                headers=self._headers,
                json={"url": public_url},
            )
            if not r.is_success:
                _log_http_error("upload_from_url", r, request_body={"url": public_url})
            r.raise_for_status()
            payload = r.json()
        if isinstance(payload, dict):
            return {
                "id": str(payload.get("id") or ""),
                "path": str(payload.get("path") or payload.get("url") or ""),
            }
        raise RuntimeError(f"unexpected Postiz upload-from-url response: {payload!r}")

    def update_post(
        self,
        group_id: str,
        posts: list[PlatformPost],
        scheduled_at: datetime,
    ) -> dict[str, Any]:
        """Edit a scheduled (QUEUE state) post group.

        Uses POST /posts with type='update'. The `group_id` must reference an
        existing group (one Postiz "post" can span multiple platforms — they
        all share a group id). `value[]` and `settings` are replaced; `date`
        effectively reschedules the post.

        Returns Postiz response dict.
        """
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        if not group_id:
            raise ValueError("update_post requires group_id")
        if not posts:
            raise ValueError("update_post requires at least one PlatformPost")

        # Postiz public docs only define type ∈ {now, schedule, draft} —
        # `type:"update"` is undocumented and was silently ignoring the new
        # `date`, leaving the post on its original schedule. `type:"schedule"`
        # is the documented way to (re)start the publishing workflow at the
        # stored date — combined with the same `group`, Postiz treats this
        # as an in-place rewrite of all posts in the group with the new date.
        body = {
            "type": "schedule",
            "date": scheduled_at.astimezone(timezone.utc).isoformat(),
            "shortLink": False,
            "tags": [],
            "creationMethod": "API",
            "posts": [
                {
                    "integration": {"id": p.integration_id},
                    "group": group_id,
                    "value": _value_for_post(p),
                    "settings": _settings_for_platform(p),
                }
                for p in posts
            ],
        }
        logger.info(
            f"postiz.update_post group={group_id[:8]} platforms={[p.provider for p in posts]} "
            f"date={scheduled_at.astimezone(timezone.utc).isoformat()} (type=schedule)"
        )
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{self.base_url}/posts", headers=self._headers, json=body)
            if not r.is_success:
                _log_http_error("update_post", r, request_body=body)
            r.raise_for_status()
            return r.json()

    def change_post_status(self, post_id: str, status: str) -> bool:
        """PUT /posts/{id}/status — toggle between 'draft' and 'schedule'."""
        if status not in ("draft", "schedule"):
            raise ValueError(f"invalid status '{status}' — must be 'draft' or 'schedule'")
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.put(
                f"{self.base_url}/posts/{post_id}/status",
                headers=self._headers,
                json={"status": status},
            )
            if not r.is_success:
                _log_http_error("change_post_status", r, request_body={"status": status})
            return r.is_success

    def delete_post_group(self, group_id: str) -> bool:
        """DELETE /posts/group/{group} — delete entire multi-platform group."""
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        with httpx.Client(timeout=30.0) as client:
            r = client.delete(
                f"{self.base_url}/posts/group/{group_id}",
                headers=self._headers,
            )
            return r.status_code in (200, 204, 404)  # 404 = already deleted

    def find_slot(self, integration_id: Optional[str] = None) -> dict[str, Any]:
        """GET /find-slot/:id? — Postiz returns the next free scheduling slot
        based on the org's posting schedule. Useful for "auto-schedule next
        available time" UI affordance."""
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        path = f"{self.base_url}/find-slot"
        if integration_id:
            path = f"{path}/{integration_id}"
        with httpx.Client(timeout=30.0) as client:
            r = client.get(path, headers=self._headers)
            r.raise_for_status()
            return r.json()

    def schedule_now(self, posts: list[PlatformPost]) -> dict[str, Any]:
        """Publish immediately — bypasses scheduling, releases at current minute.
        Uses POST /posts with type='now'."""
        if not self.api_key:
            raise RuntimeError("POSTIZ_API_KEY not set.")
        body = {
            "type": "now",
            "date": datetime.now(timezone.utc).isoformat(),
            "shortLink": False,
            "tags": [],
            "creationMethod": "API",
            "posts": [
                {
                    "integration": {"id": p.integration_id},
                    "value": _value_for_post(p),
                    "settings": _settings_for_platform(p),
                }
                for p in posts
            ],
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{self.base_url}/posts", headers=self._headers, json=body)
            if not r.is_success:
                _log_http_error("schedule_now", r, request_body=body)
            r.raise_for_status()
            return r.json()


@tool("postiz_schedule_post")
def postiz_schedule_post(
    integration_id: str,
    content: str,
    schedule_delay_hours: int = 2,
) -> dict:
    """Schedule a single tweet via Postiz (backwards-compatible CrewAI tool).

    For multi-platform scheduling, call PostizClient.schedule_posts() directly
    from Flow.publish_to_drafts.

    If HYPE_DRY_RUN=true (settings.dry_run), no API call — returns synthetic dry-run id.
    """
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=schedule_delay_hours)

    if settings.dry_run:
        return {
            "postiz_post_id": f"DRY_RUN_{uuid.uuid4().hex[:12]}",
            "integration_id": integration_id,
            "scheduled_at": scheduled_at.isoformat(),
            "dry_run": True,
            "preview_content": content[:80] + ("..." if len(content) > 80 else ""),
        }

    if not settings.postiz_api_key:
        return {
            "postiz_post_id": "ERROR_no_api_key",
            "integration_id": integration_id,
            "scheduled_at": scheduled_at.isoformat(),
            "dry_run": False,
            "error": "POSTIZ_API_KEY not configured",
        }

    client = PostizClient()
    try:
        resp = client.schedule_post(integration_id, content, scheduled_at, provider="twitter")
        post_id = (
            resp.get("id")
            or resp.get("post_id")
            or (resp.get("posts", [{}])[0].get("id") if resp.get("posts") else None)
            or ""
        )
        return {
            "postiz_post_id": str(post_id),
            "integration_id": integration_id,
            "scheduled_at": scheduled_at.isoformat(),
            "dry_run": False,
            "raw_response": resp,
        }
    except httpx.HTTPStatusError as e:
        return {
            "postiz_post_id": f"ERROR_http_{e.response.status_code}",
            "integration_id": integration_id,
            "scheduled_at": scheduled_at.isoformat(),
            "dry_run": False,
            "error": str(e)[:200],
        }
    except Exception as e:
        return {
            "postiz_post_id": "ERROR_exception",
            "integration_id": integration_id,
            "scheduled_at": scheduled_at.isoformat(),
            "dry_run": False,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
        }
