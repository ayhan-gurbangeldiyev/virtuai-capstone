# Feed UI API Specification — Lovable İçin

## Overview

TypeHype, toplanan tweet sinyallerini `tweet_feed` tablosunda tutuyor. Feed UI'ı bu endpoint üzerinden veri çeker.

---

## Endpoint

```
GET https://api.typehype.io/api/feed
```

---

## Query Parameters

| Param | Type | Default | Description |
|---|---|---|---|
| `batch_type` | string | `"all"` | Filter by category. Options: `ai_tech`, `tr_haber`, `spor`, `monitor`, `radar`, `all` |
| `limit` | integer | `50` | Max results per page. Max: `200` |
| `offset` | integer | `0` | Pagination offset |
| `sort` | string | `"recent"` | Sort order: `recent` (default, by time) or `popular` (by engagement) |

---

## Response

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "tweet_id": "1234567890123456789",
      "username": "OpenAI",
      "display_name": "OpenAI",
      "avatar_url": "https://pbs.twimg.com/profile_images/xxxxx/xxxxx_400x400.jpg",
      "content": "We are excited to announce our latest model...",
      "likes": 1234,
      "retweets": 456,
      "replies": 89,
      "views": 45678,
      "tweet_url": "https://x.com/OpenAI/status/1234567890123456789",
      "batch_type": "ai_tech",
      "source_detail": "OpenAI",
      "tweet_created_at": "2026-01-15T10:30:00Z",
      "collected_at": "2026-01-15T10:35:00Z"
    }
  ],
  "total": 342,
  "limit": 50,
  "offset": 0,
  "batch_type": "all"
}
```

---

## Data Model

### FeedItem Fields

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `tweet_id` | string | Tweet ID from X (unique) |
| `username` | string | X username (e.g. `OpenAI`) |
| `display_name` | string | Display name (e.g. `OpenAI`) |
| `avatar_url` | string | Profile image URL (400x400) |
| `content` | string | Tweet text |
| `likes` | integer | Like count |
| `retweets` | integer | Retweet count |
| `replies` | integer | Reply count |
| `views` | integer | View count |
| `tweet_url` | string | Direct link to tweet |
| `batch_type` | string | Category: `ai_tech`, `tr_haber`, `spor`, `monitor`, `radar` |
| `source_detail` | string | Detail: for batches = username, for radar = source name |
| `tweet_created_at` | ISO8601 | When the tweet was posted |
| `collected_at` | ISO8601 | When we collected this tweet |

### batch_type Values

| Value | Source | Description |
|---|---|---|
| `ai_tech` | Batch | AI, tech, coding accounts |
| `tr_haber` | Batch | Turkish news & media accounts |
| `spor` | Batch | Sports accounts |
| `monitor` | Batch | Monitored accounts (realtime events) |
| `radar` | Batch | Trending from Google Trends, HN, Reddit, GitHub, etc. |

---

## Authentication

No authentication required for feed reads (public data).

---

## Rate Limit

Standard rate limiting applies (100 req/min).

---

## UI Design Notes

- **Avatar**: 400x400px, circular
- **Engagement badges**: likes, retweets, replies, views — icon + number format
- **Tweet link**: Opens `tweet_url` in new tab
- **Category tabs**: `all | ai_tech | tr_haber | spor | radar`
- **Sort toggle**: Recent / Popular (icon toggle)
- **Infinite scroll or pagination**: Use `offset` + `limit` for pagination
- **Empty state**: "Bu kategoride henüz tweet yok"
- **Loading state**: Skeleton cards

---

## Example Usage

```javascript
// Fetch AI Tech tweets, most popular first
const res = await fetch('https://api.typehype.io/api/feed?batch_type=ai_tech&sort=popular&limit=20');
const data = await res.json();
```

```javascript
// Paginate through all feed
const page1 = await fetch('https://api.typehype.io/api/feed?limit=50&offset=0');
const page2 = await fetch('https://api.typehype.io/api/feed?limit=50&offset=50');
```
