from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def hn_ask_payload() -> dict[str, Any]:
    return {
        "hits": [
            {
                "objectID": "1001",
                "title": "Ask HN: I wish there was a better deploy diff tool",
                "story_text": "Manual deploy reviews are painful for small teams.",
                "author": "alice",
                "created_at": "2026-02-10T12:00:00Z",
                "points": 25,
                "num_comments": 12,
                "_tags": ["story", "ask_hn"],
                "url": "https://news.ycombinator.com/item?id=1001",
            }
        ]
    }


@pytest.fixture
def hn_comment_payload() -> dict[str, Any]:
    return {
        "hits": [
            {
                "objectID": "2001",
                "comment_text": "I want a tool that auto-documents internal APIs.",
                "story_title": "Show HN: API docs generator",
                "story_id": 2222,
                "author": "bob",
                "created_at": "2026-02-11T12:00:00Z",
                "story_points": 18,
                "_tags": ["comment", "author_bob", "story_2222"],
            }
        ]
    }


@pytest.fixture
def github_issue_payload() -> dict[str, Any]:
    issue = {
        "id": 333,
        "title": "Is there a tool to preview migration impact?",
        "body": "We currently use spreadsheets and manual checks. Does this exist?",
        "html_url": "https://github.com/acme/infra/issues/333",
        "repository_url": "https://api.github.com/repos/acme/infra",
        "user": {"login": "carol"},
        "created_at": "2026-02-14T10:00:00Z",
        "comments": 7,
        "labels": [{"name": "question"}],
        "state": "open",
        "reactions": {"total_count": 4},
    }
    return {"items": [issue]}


@pytest.fixture
def github_repo_payload() -> dict[str, Any]:
    return {"full_name": "acme/infra", "stargazers_count": 250}


@pytest.fixture
def reddit_search_payload() -> dict[str, Any]:
    return {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "r1",
                        "title": "Looking for a tool recommendation for API changelog diffs",
                        "selftext": "Current process is manual and slow for our team.",
                        "author": "dave",
                        "ups": 14,
                        "num_comments": 5,
                        "created_utc": 1760054400,
                        "permalink": "/r/SaaS/comments/r1/example/",
                        "is_self": True,
                    }
                }
            ]
        }
    }


@pytest.fixture
def json_response() -> Any:
    def _factory(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
        return httpx.Response(status_code=status_code, json=payload)

    return _factory
