from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

GITHUB_API_BASE = "https://api.github.com"
SEARCH_PHRASES = [
    '"does this exist"',
    '"is there a tool"',
    '"feature request"',
]
LABELS = ["help wanted", "question"]
MIN_REPO_STARS = 100


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DemandRadar/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _topic_matches(text: str, topic: str | None) -> bool:
    if not topic:
        return True
    tokens = [t for t in topic.lower().split() if t]
    haystack = text.lower()
    return any(token in haystack for token in tokens)


def _repo_web_url(api_url: str) -> str:
    if api_url.startswith(f"{GITHUB_API_BASE}/repos/"):
        return "https://github.com/" + api_url.split("/repos/", 1)[1]
    return api_url


def _normalize_issue(item: dict[str, Any], repo_stars: int) -> dict[str, Any]:
    body = (item.get("body") or "").strip()
    reactions = item.get("reactions") or {}
    return {
        "source": "github",
        "id": str(item.get("id")),
        "title": (item.get("title") or "").strip(),
        "text": body,
        "url": item.get("html_url"),
        "author": (item.get("user") or {}).get("login") or "unknown",
        "created_at": item.get("created_at") or datetime.now(tz=UTC).isoformat(),
        "engagement": {
            "score": int(reactions.get("total_count") or 0),
            "comments": int(item.get("comments") or 0),
        },
        "metadata": {
            "repository": (item.get("repository_url") or "").replace(
                f"{GITHUB_API_BASE}/repos/", ""
            ),
            "repository_url": _repo_web_url(item.get("repository_url") or ""),
            "repo_stars": repo_stars,
            "labels": [
                label.get("name") for label in item.get("labels", []) if isinstance(label, dict)
            ],
            "state": item.get("state"),
        },
    }


async def _search_issues(
    client: httpx.AsyncClient,
    query: str,
    per_page: int = 100,
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{GITHUB_API_BASE}/search/issues",
        params={"q": query, "per_page": per_page, "sort": "updated", "order": "desc"},
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("items", [])


async def _repo_stars(
    client: httpx.AsyncClient,
    cache: dict[str, int],
    repo_api_url: str,
) -> int:
    if repo_api_url in cache:
        return cache[repo_api_url]
    response = await client.get(repo_api_url)
    response.raise_for_status()
    stars = int(response.json().get("stargazers_count") or 0)
    cache[repo_api_url] = stars
    return stars


async def fetch_github_signals(
    lookback_days: int,
    max_signals: int,
    topic: str | None = None,
    github_token: str | None = None,
    client: httpx.AsyncClient | None = None,
    request_delay: float = 0.25,
) -> list[dict[str, Any]]:
    since = (datetime.now(tz=UTC) - timedelta(days=lookback_days)).date().isoformat()
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=20.0, headers=_headers(github_token))
    assert client is not None

    repo_cache: dict[str, int] = {}
    seen_issue_ids: set[str] = set()
    signals: list[dict[str, Any]] = []

    queries: list[str] = []
    for label in LABELS:
        q = f'is:issue is:open label:"{label}" created:>={since}'
        if topic:
            q += f" {topic}"
        queries.append(q)
    for phrase in SEARCH_PHRASES:
        q = f"is:issue is:open {phrase} created:>={since}"
        if topic:
            q += f" {topic}"
        queries.append(q)

    try:
        for query in queries:
            if len(signals) >= max_signals:
                break
            items = await _search_issues(client, query)
            for item in items:
                if item.get("pull_request"):
                    continue
                issue_id = str(item.get("id"))
                if issue_id in seen_issue_ids:
                    continue
                combined = f"{item.get('title', '')} {item.get('body', '')}"
                if not _topic_matches(combined, topic):
                    continue
                repo_api_url = item.get("repository_url") or ""
                if not repo_api_url:
                    continue
                stars = await _repo_stars(client, repo_cache, repo_api_url)
                await asyncio.sleep(request_delay)
                if stars < MIN_REPO_STARS:
                    continue
                signals.append(_normalize_issue(item, repo_stars=stars))
                seen_issue_ids.add(issue_id)
                if len(signals) >= max_signals:
                    break
            await asyncio.sleep(request_delay)
        return signals
    finally:
        if own_client:
            await client.aclose()
