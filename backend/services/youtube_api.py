"""
YouTube Data API v3 wrapper service.
Kanal, video, yorum, trending verileri çeker.
API key yoksa mock data döner.
"""
import os
import re
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Mock data for when API key is not available
MOCK_CHANNEL = {
    "id": "UC_mock_channel_id",
    "title": "Demo Channel",
    "description": "Bu bir demo kanaldır. Gerçek YouTube API key ekleyerek gerçek veriler alabilirsiniz.",
    "customUrl": "@demochannel",
    "publishedAt": "2020-01-15T00:00:00Z",
    "thumbnails": {"default": {"url": "https://via.placeholder.com/88"}, "high": {"url": "https://via.placeholder.com/800"}},
    "subscriberCount": 125000,
    "viewCount": 45000000,
    "videoCount": 320,
    "country": "TR",
    "_mock": True
}

MOCK_VIDEOS = [
    {
        "id": f"mock_video_{i}",
        "title": f"Demo Video #{i+1} - YouTube Studio Test",
        "description": f"Bu bir demo video açıklamasıdır #{i+1}.",
        "publishedAt": f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}T12:00:00Z",
        "thumbnails": {"default": {"url": "https://via.placeholder.com/120x90"}, "maxres": {"url": "https://via.placeholder.com/1280x720"}},
        "channelId": "UC_mock_channel_id",
        "channelTitle": "Demo Channel",
        "viewCount": 50000 - i * 1200,
        "likeCount": 2500 - i * 60,
        "commentCount": 350 - i * 10,
        "duration": "PT12M30S",
        "tags": ["demo", "test", "youtube"],
        "categoryId": "22",
        "_mock": True
    }
    for i in range(30)
]

MOCK_COMMENTS = [
    {"id": f"comment_{i}", "authorDisplayName": f"User{i+1}", "textDisplay": text, "likeCount": (30 - i) * 2, "publishedAt": f"2024-01-{(i%28)+1:02d}T10:00:00Z", "_mock": True}
    for i, text in enumerate([
        "Harika video, çok faydalı oldu! 👏", "Bu konuyu daha detaylı anlatır mısın?",
        "Kesinlikle katılıyorum, süper içerik", "Bence bu yanlış, kaynaklarını kontrol et",
        "Tam da aradığım video, teşekkürler!", "Ses kalitesi biraz düşük gibi",
        "Like ve abone oldum 🔥", "Bu konuda bir seri yapabilir misin?",
        "10:25'teki kısım çok iyiydi", "Clickbait başlık, içerik farklı",
        "Muhteşem edit, hangi programı kullanıyorsun?", "Her videonu izliyorum, devam et!",
        "Bu bilgi yanlış, düzeltmenizi öneririm", "Çok uzun olmuş, özetleseydin keşke",
        "İlk defa izliyorum ama bayıldım", "Reklam mı bu?", "Podcast versiyonu olsa süper olur",
        "Diğer kanallardan çok daha kaliteli", "Alt yazı eklesen daha iyi olur",
        "Bu videoyu arkadaşlarıma da gönderdim"
    ])
]

MOCK_TRENDING = [
    {
        "id": f"trending_{i}",
        "title": f"Trending Video #{i+1}",
        "channelTitle": f"Popular Channel {i+1}",
        "viewCount": 1000000 - i * 50000,
        "likeCount": 50000 - i * 2000,
        "commentCount": 5000 - i * 200,
        "publishedAt": "2024-01-15T12:00:00Z",
        "thumbnails": {"default": {"url": "https://via.placeholder.com/120x90"}},
        "_mock": True
    }
    for i in range(20)
]


class YouTubeAPIService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.youtube = None
        self._use_mock = not self.api_key or self.api_key.startswith("placeholder")

        if not self._use_mock:
            try:
                from googleapiclient.discovery import build
                self.youtube = build("youtube", "v3", developerKey=self.api_key)
            except Exception as e:
                logger.warning(f"YouTube API init failed, using mock: {e}")
                self._use_mock = True

        if self._use_mock:
            logger.info("YouTube API: Mock mode active (no valid API key)")

    def extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'(?:youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        # bare ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            return url
        return None

    def extract_channel_id(self, url: str) -> Optional[str]:
        # channel/UCxxxx
        m = re.search(r'youtube\.com/channel/(UC[a-zA-Z0-9_-]+)', url)
        if m:
            return m.group(1)
        # @handle
        m = re.search(r'youtube\.com/@([\w.-]+)', url)
        if m:
            return f"@{m.group(1)}"
        # /c/name or /user/name
        m = re.search(r'youtube\.com/(?:c|user)/([\w.-]+)', url)
        if m:
            return f"@{m.group(1)}"
        return None

    def get_channel(self, url: str) -> dict:
        if self._use_mock:
            return MOCK_CHANNEL

        channel_ref = self.extract_channel_id(url)
        if not channel_ref:
            raise ValueError(f"Geçersiz kanal URL'si: {url}")

        try:
            if channel_ref.startswith("@"):
                # Handle-based lookup
                req = self.youtube.channels().list(
                    part="snippet,statistics,brandingSettings",
                    forHandle=channel_ref[1:]
                )
            elif channel_ref.startswith("UC"):
                req = self.youtube.channels().list(
                    part="snippet,statistics,brandingSettings",
                    id=channel_ref
                )
            else:
                req = self.youtube.channels().list(
                    part="snippet,statistics,brandingSettings",
                    forUsername=channel_ref
                )

            resp = req.execute()
            if not resp.get("items"):
                raise ValueError(f"Kanal bulunamadı: {url}")

            item = resp["items"][0]
            snippet = item["snippet"]
            stats = item["statistics"]

            return {
                "id": item["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "customUrl": snippet.get("customUrl", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "thumbnails": snippet.get("thumbnails", {}),
                "subscriberCount": int(stats.get("subscriberCount", 0)),
                "viewCount": int(stats.get("viewCount", 0)),
                "videoCount": int(stats.get("videoCount", 0)),
                "country": snippet.get("country", ""),
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"YouTube channel fetch error: {e}")
            raise ValueError(f"Kanal bilgileri alınamadı: {str(e)}")

    def get_channel_videos(self, channel_id: str, limit: int = 30) -> list:
        if self._use_mock:
            return MOCK_VIDEOS[:limit]

        try:
            # Get upload playlist
            if channel_id.startswith("@"):
                ch_resp = self.youtube.channels().list(part="contentDetails", forHandle=channel_id[1:]).execute()
            else:
                ch_resp = self.youtube.channels().list(part="contentDetails", id=channel_id).execute()

            if not ch_resp.get("items"):
                return []

            uploads_id = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # Get videos from upload playlist
            videos = []
            next_page = None
            while len(videos) < limit:
                pl_resp = self.youtube.playlistItems().list(
                    part="snippet", playlistId=uploads_id,
                    maxResults=min(50, limit - len(videos)),
                    pageToken=next_page
                ).execute()

                video_ids = [item["snippet"]["resourceId"]["videoId"] for item in pl_resp.get("items", [])]
                if not video_ids:
                    break

                # Get full video details
                vid_resp = self.youtube.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(video_ids)
                ).execute()

                for item in vid_resp.get("items", []):
                    snippet = item["snippet"]
                    stats = item.get("statistics", {})
                    videos.append({
                        "id": item["id"],
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", "")[:500],
                        "publishedAt": snippet.get("publishedAt", ""),
                        "thumbnails": snippet.get("thumbnails", {}),
                        "channelId": snippet.get("channelId", ""),
                        "channelTitle": snippet.get("channelTitle", ""),
                        "viewCount": int(stats.get("viewCount", 0)),
                        "likeCount": int(stats.get("likeCount", 0)),
                        "commentCount": int(stats.get("commentCount", 0)),
                        "duration": item.get("contentDetails", {}).get("duration", ""),
                        "tags": snippet.get("tags", []),
                        "categoryId": snippet.get("categoryId", ""),
                    })

                next_page = pl_resp.get("nextPageToken")
                if not next_page:
                    break

            return videos[:limit]
        except Exception as e:
            logger.error(f"YouTube channel videos error: {e}")
            return []

    def get_video(self, video_id: str) -> dict:
        if self._use_mock:
            return MOCK_VIDEOS[0] | {"id": video_id}

        try:
            resp = self.youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=video_id
            ).execute()

            if not resp.get("items"):
                raise ValueError(f"Video bulunamadı: {video_id}")

            item = resp["items"][0]
            snippet = item["snippet"]
            stats = item.get("statistics", {})

            return {
                "id": item["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "thumbnails": snippet.get("thumbnails", {}),
                "channelId": snippet.get("channelId", ""),
                "channelTitle": snippet.get("channelTitle", ""),
                "viewCount": int(stats.get("viewCount", 0)),
                "likeCount": int(stats.get("likeCount", 0)),
                "commentCount": int(stats.get("commentCount", 0)),
                "duration": item.get("contentDetails", {}).get("duration", ""),
                "tags": snippet.get("tags", []),
                "categoryId": snippet.get("categoryId", ""),
            }
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"YouTube video fetch error: {e}")
            raise ValueError(f"Video bilgileri alınamadı: {str(e)}")

    def get_video_comments(self, video_id: str, limit: int = 100) -> list:
        if self._use_mock:
            return MOCK_COMMENTS[:limit]

        try:
            comments = []
            next_page = None
            while len(comments) < limit:
                resp = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(100, limit - len(comments)),
                    order="relevance",
                    pageToken=next_page
                ).execute()

                for item in resp.get("items", []):
                    top = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append({
                        "id": item["id"],
                        "authorDisplayName": top.get("authorDisplayName", ""),
                        "textDisplay": top.get("textDisplay", ""),
                        "likeCount": top.get("likeCount", 0),
                        "publishedAt": top.get("publishedAt", ""),
                    })

                next_page = resp.get("nextPageToken")
                if not next_page:
                    break

            return comments[:limit]
        except Exception as e:
            logger.error(f"YouTube comments fetch error: {e}")
            return []

    def get_trending(self, region: str = "TR", category: str = None) -> list:
        if self._use_mock:
            return MOCK_TRENDING

        try:
            params = {
                "part": "snippet,statistics",
                "chart": "mostPopular",
                "regionCode": region,
                "maxResults": 50,
            }
            if category:
                params["videoCategoryId"] = category

            resp = self.youtube.videos().list(**params).execute()

            results = []
            for item in resp.get("items", []):
                snippet = item["snippet"]
                stats = item.get("statistics", {})
                results.append({
                    "id": item["id"],
                    "title": snippet.get("title", ""),
                    "channelTitle": snippet.get("channelTitle", ""),
                    "viewCount": int(stats.get("viewCount", 0)),
                    "likeCount": int(stats.get("likeCount", 0)),
                    "commentCount": int(stats.get("commentCount", 0)),
                    "publishedAt": snippet.get("publishedAt", ""),
                    "thumbnails": snippet.get("thumbnails", {}),
                    "categoryId": snippet.get("categoryId", ""),
                })
            return results
        except Exception as e:
            logger.error(f"YouTube trending error: {e}")
            return MOCK_TRENDING


def get_youtube_service() -> YouTubeAPIService:
    return YouTubeAPIService()
