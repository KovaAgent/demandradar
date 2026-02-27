from __future__ import annotations

import httpx
import pytest

from demandradar.fetchers.reddit import fetch_reddit_signals


@pytest.mark.asyncio
async def test_fetch_reddit_signals_parses_posts(
    reddit_search_payload: dict,
    json_response,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search.json"):
            return json_response(reddit_search_payload)
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        signals = await fetch_reddit_signals(
            lookback_days=30,
            max_signals=1,
            client=client,
            request_delay=0,
        )

    assert len(signals) == 1
    assert signals[0]["source"] == "reddit"
    assert signals[0]["metadata"]["subreddit"] in {
        "SideProject",
        "startups",
        "entrepreneur",
        "SaaS",
        "learnprogramming",
    }
