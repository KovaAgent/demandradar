from __future__ import annotations

import httpx
import pytest

from demandradar.fetchers.hn import fetch_hn_signals


@pytest.mark.asyncio
async def test_fetch_hn_signals_parses_ask_and_comment_hits(
    hn_ask_payload: dict,
    hn_comment_payload: dict,
    json_response,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search_by_date"):
            return json_response(hn_ask_payload)
        if request.url.path.endswith("/search"):
            return json_response(hn_comment_payload)
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        signals = await fetch_hn_signals(
            lookback_days=30,
            max_signals=5,
            client=client,
            request_delay=0,
        )

    assert len(signals) >= 2
    assert {signal["source"] for signal in signals} == {"hn"}
    assert signals[0]["title"].startswith("Ask HN")
    assert any("auto-documents" in signal["text"] for signal in signals)
