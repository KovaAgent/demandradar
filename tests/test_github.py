from __future__ import annotations

import httpx
import pytest

from demandradar.fetchers.github import fetch_github_signals


@pytest.mark.asyncio
async def test_fetch_github_signals_filters_for_popular_repos(
    github_issue_payload: dict,
    github_repo_payload: dict,
    json_response,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search/issues":
            return json_response(github_issue_payload)
        if request.url.path == "/repos/acme/infra":
            return json_response(github_repo_payload)
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        signals = await fetch_github_signals(
            lookback_days=30,
            max_signals=10,
            client=client,
            request_delay=0,
        )

    assert len(signals) == 1
    signal = signals[0]
    assert signal["source"] == "github"
    assert signal["metadata"]["repo_stars"] == 250
    assert "manual checks" in signal["text"]
