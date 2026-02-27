from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any

import httpx

ALGOLIA_BASE_URL = "https://hn.algolia.com/api/v1"
COMMENT_PHRASES = [
    '"wish there was"',
    '"nobody has built"',
    '"I want a tool that"',
]


def _strip_html(text: str) -> str:
    out = []
    in_tag = False
    for ch in text:
        if ch == "<":
            in_tag = True
            continue
        if ch == ">":
            in_tag = False
            continue
        if not in_tag:
            out.append(ch)
    return " ".join(unescape("".join(out)).split())


def _topic_matches(text: str, topic: str | None) -> bool:
    if not topic:
        return True
    topic_tokens = [t for t in topic.lower().split() if t]
    haystack = text.lower()
    return any(token in haystack for token in topic_tokens)


def _normalize_hit(hit: dict[str, Any]) -> dict[str, Any]:
    title = hit.get("title") or hit.get("story_title") or ""
    body = _strip_html(hit.get("comment_text") or hit.get("story_text") or "")
    url = hit.get("url") or hit.get("story_url")
    if not url:
        item_id = hit.get("story_id") or hit.get("objectID")
        url = f"https://news.ycombinator.com/item?id={item_id}"
    created_at = hit.get("created_at") or datetime.now(tz=UTC).isoformat()
    points = int(hit.get("points") or 0)
    num_comments = int(hit.get("num_comments") or 0)
    if hit.get("_tags") and "comment" in hit.get("_tags", []):
        points = int(hit.get("story_points") or points)
    object_id = str(hit.get("objectID"))
    return {
        "source": "hn",
        "id": object_id,
        "title": title.strip() or body[:80] or "HN comment",
        "text": body or title,
        "url": url,
        "author": hit.get("author") or "unknown",
        "created_at": created_at,
        "engagement": {
            "score": points,
            "comments": num_comments,
        },
        "metadata": {
            "hn_tags": hit.get("_tags", []),
            "story_id": hit.get("story_id"),
            "story_title": hit.get("story_title"),
            "search_source": "comment" if "comment" in hit.get("_tags", []) else "ask_hn",
        },
    }


async def _algolia_request(
    client: httpx.AsyncClient,
    endpoint: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    response = await client.get(f"{ALGOLIA_BASE_URL}/{endpoint}", params=params)
    response.raise_for_status()
    return response.json()


async def fetch_hn_signals(
    lookback_days: int,
    max_signals: int,
    topic: str | None = None,
    client: httpx.AsyncClient | None = None,
    request_delay: float = 0.2,
) -> list[dict[str, Any]]:
    cutoff = int((datetime.now(tz=UTC) - timedelta(days=lookback_days)).timestamp())
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "DemandRadar/0.1"})
    assert client is not None

    seen_ids: set[str] = set()
    signals: list[dict[str, Any]] = []

    try:
        ask_params = {
            "tags": "story,ask_hn",
            "hitsPerPage": min(max_signals, 100),
            "numericFilters": f"created_at_i>{cutoff}",
        }
        ask_payload = await _algolia_request(client, "search_by_date", ask_params)
        for hit in ask_payload.get("hits", []):
            normalized = _normalize_hit(hit)
            if normalized["id"] in seen_ids:
                continue
            combined = f"{normalized['title']} {normalized['text']}"
            if _topic_matches(combined, topic):
                seen_ids.add(normalized["id"])
                signals.append(normalized)
            if len(signals) >= max_signals:
                return signals

        for phrase in COMMENT_PHRASES:
            if len(signals) >= max_signals:
                break
            await asyncio.sleep(request_delay)
            query = phrase if not topic else f"{phrase} {topic}"
            comment_params = {
                "tags": "comment",
                "query": query,
                "hitsPerPage": min(max_signals, 100),
                "numericFilters": f"created_at_i>{cutoff}",
            }
            comment_payload = await _algolia_request(client, "search", comment_params)
            for hit in comment_payload.get("hits", []):
                normalized = _normalize_hit(hit)
                if normalized["id"] in seen_ids:
                    continue
                combined = f"{normalized['title']} {normalized['text']}"
                if not _topic_matches(combined, topic):
                    continue
                seen_ids.add(normalized["id"])
                signals.append(normalized)
                if len(signals) >= max_signals:
                    break
        return signals
    finally:
        if own_client:
            await client.aclose()
