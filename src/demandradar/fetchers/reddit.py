from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

REDDIT_BASE_URL = "https://old.reddit.com"
SUBREDDITS = ["SideProject", "startups", "entrepreneur", "SaaS", "learnprogramming"]
SEARCH_QUERIES = [
    "wish there was a tool",
    "looking for a tool",
    "tool recommendation",
    "does a tool exist",
]


def _topic_matches(text: str, topic: str | None) -> bool:
    if not topic:
        return True
    tokens = [t for t in topic.lower().split() if t]
    haystack = text.lower()
    return any(token in haystack for token in tokens)


def _normalize_post(post: dict[str, Any], subreddit: str) -> dict[str, Any]:
    data = post.get("data", post)
    created_utc = float(data.get("created_utc") or 0)
    created_at = datetime.fromtimestamp(created_utc, tz=UTC).isoformat() if created_utc else None
    permalink = data.get("permalink") or ""
    url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else data.get("url")
    return {
        "source": "reddit",
        "id": data.get("id") or "",
        "title": (data.get("title") or "").strip(),
        "text": (data.get("selftext") or "").strip(),
        "url": url,
        "author": data.get("author") or "unknown",
        "created_at": created_at or datetime.now(tz=UTC).isoformat(),
        "engagement": {
            "score": int(data.get("ups") or data.get("score") or 0),
            "comments": int(data.get("num_comments") or 0),
        },
        "metadata": {
            "subreddit": subreddit,
            "is_self": bool(data.get("is_self", True)),
        },
    }


async def _search_subreddit(
    client: httpx.AsyncClient,
    subreddit: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{REDDIT_BASE_URL}/r/{subreddit}/search.json",
        params={
            "q": query,
            "restrict_sr": "on",
            "sort": "new",
            "t": "month",
            "limit": limit,
        },
    )
    response.raise_for_status()
    payload = response.json()
    return ((payload.get("data") or {}).get("children") or [])


async def fetch_reddit_signals(
    lookback_days: int,
    max_signals: int,
    topic: str | None = None,
    client: httpx.AsyncClient | None = None,
    request_delay: float = 0.4,
) -> list[dict[str, Any]]:
    del lookback_days  # Reddit search uses t=month for V1.
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "DemandRadar/0.1 (open-source CLI)"},
        )
    assert client is not None

    seen_ids: set[str] = set()
    signals: list[dict[str, Any]] = []

    queries = SEARCH_QUERIES[:]
    if topic:
        queries.insert(0, topic)

    try:
        for subreddit in SUBREDDITS:
            if len(signals) >= max_signals:
                break
            for query in queries:
                if len(signals) >= max_signals:
                    break
                posts = await _search_subreddit(client, subreddit, query, limit=25)
                for post in posts:
                    normalized = _normalize_post(post, subreddit=subreddit)
                    if not normalized["id"] or normalized["id"] in seen_ids:
                        continue
                    combined = f"{normalized['title']} {normalized['text']}"
                    if not _topic_matches(combined, topic):
                        continue
                    seen_ids.add(normalized["id"])
                    signals.append(normalized)
                    if len(signals) >= max_signals:
                        break
                await asyncio.sleep(request_delay)
        return signals
    finally:
        if own_client:
            await client.aclose()
