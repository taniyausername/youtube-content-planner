"""Bounded collection of public metadata; no scraping or private analytics."""
import asyncio
from datetime import datetime, timedelta, timezone
import re
import httpx
from .models import ResearchRequest, Video


class CollectionError(Exception):
    pass


def clean(items: list[Video], now: datetime) -> list[Video]:
    unique = {}
    for v in items:
        if v.published_at > now or not v.title.strip() or not v.channel_id:
            continue
        if not v.synthetic and not re.fullmatch(r'[A-Za-z0-9_-]{11}', v.id):
            continue
        unique[v.id] = v.model_copy(update={
            'title': ' '.join(v.title.split()),
            'description': ' '.join(v.description.split())[:1500],
        })
    return list(unique.values())


async def collect_youtube(request: ResearchRequest, key: str,
                          client: httpx.AsyncClient | None = None) -> list[Video]:
    if not key:
        raise CollectionError('Live mode needs YOUTUBE_API_KEY on the server. Demo mode works without a key.')
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20)
    now = datetime.now(timezone.utc)

    async def get(resource: str, params: dict) -> dict:
        for attempt in range(3):
            try:
                response = await client.get('https://www.googleapis.com/youtube/v3/' + resource,
                                            params={**params, 'key': key})
            except httpx.RequestError:
                if attempt == 2:
                    raise CollectionError('YouTube could not be reached. Check the connection and retry.') from None
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise CollectionError('YouTube is busy or rate limiting requests. Try again later.')
            if response.status_code != 200:
                # Never expose provider response bodies or a URL containing an API key.
                raise CollectionError('YouTube rejected the request. Check API enablement, key restrictions and quota.')
            try:
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError()
                return data
            except ValueError:
                raise CollectionError('YouTube returned an unreadable response.') from None
        raise CollectionError('YouTube request failed.')

    try:
        ids, token = [], None
        for _ in range(2):
            params = {'part': 'snippet', 'type': 'video', 'q': request.niche,
                      'order': 'relevance', 'maxResults': min(50, request.max_videos - len(ids)),
                      'publishedAfter': (now - timedelta(days=request.days)).isoformat().replace('+00:00', 'Z')}
            if token:
                params['pageToken'] = token
            data = await get('search', params)
            for item in data.get('items', []):
                vid = item.get('id', {}).get('videoId')
                if vid and vid not in ids:
                    ids.append(vid)
            token = data.get('nextPageToken')
            if not token or len(ids) >= request.max_videos:
                break
        videos = []
        for offset in range(0, len(ids), 50):
            data = await get('videos', {'part': 'snippet,statistics', 'id': ','.join(ids[offset:offset + 50])})
            for item in data.get('items', []):
                try:
                    snippet, stats = item['snippet'], item.get('statistics', {})
                    videos.append(Video(
                        id=item['id'], title=snippet['title'], description=snippet.get('description', ''),
                        channel_id=snippet['channelId'], channel_title=snippet.get('channelTitle', ''),
                        published_at=snippet['publishedAt'], observed_at=now,
                        views=stats.get('viewCount'), likes=stats.get('likeCount'),
                        comments=stats.get('commentCount'), category_id=snippet.get('categoryId', '')))
                except (KeyError, ValueError, TypeError):
                    continue
        return clean(videos, now)
    finally:
        if own_client:
            await client.aclose()


def demo_videos(request: ResearchRequest) -> list[Video]:
    """Synthetic, repeatable scenarios; never presented as actual YouTube evidence."""
    now = datetime.now(timezone.utc)
    themes = [
        ('beginner setup', 'setup installation first steps beginner guide'),
        ('workflow automation', 'automation workflow integration tasks productivity'),
        ('cost comparison', 'cost pricing comparison budget alternatives'),
        ('common mistakes', 'mistakes troubleshooting errors debugging fixes'),
    ]
    result = []
    for i in range(request.max_videos):
        topic, description = themes[i % 4]
        age = 1 + (i * 7 % request.days)
        views = (1200 + (i * 479 % 6500)) * (1 + i % 4)
        if i == 7:
            views = 180000  # Deliberate outlier for the critic to identify.
        result.append(Video(
            id=f'demo-{i:03d}', title=f'{request.niche}: {topic} — example {i + 1}',
            description=description, channel_id=f'demo-channel-{i % 7}',
            channel_title=f'Sample creator {i % 7 + 1}',
            published_at=now - timedelta(days=age), observed_at=now,
            views=views, likes=None if i % 9 == 0 else views // (25 + i % 12),
            comments=None if i % 11 == 0 else views // (160 + i % 50), synthetic=True))
    return result
