from __future__ import annotations

from demandradar.processor import cluster_signals, process_raw_signals


def test_process_raw_signals_heuristic_extracts_required_fields() -> None:
    raw = [
        {
            "source": "hn",
            "id": "1",
            "title": "Ask HN: Need a tool for deployment diffs",
            "text": (
                "Manual deploy validation is frustrating and slow. "
                "We currently use spreadsheets."
            ),
            "url": "https://example.com/1",
            "author": "alice",
            "created_at": "2026-02-01T00:00:00Z",
            "engagement": {"score": 22, "comments": 18},
            "metadata": {},
        }
    ]
    processed, meta = process_raw_signals(raw)
    assert meta["extraction_method"] == "heuristic"
    assert len(processed) == 1
    signal = processed[0]
    assert signal["problem_statement"]
    assert signal["target_audience"]
    assert isinstance(signal["existing_solutions"], list)
    assert 1 <= signal["frustration_level"] <= 5
    assert signal["frequency_indicator"]


def test_cluster_signals_groups_similar_signals() -> None:
    raw = [
        {
            "source": "hn",
            "id": "1",
            "title": "Need deployment diff tool",
            "text": "Manual deployment diff checks are slow and painful",
            "url": "https://example.com/1",
            "author": "a",
            "created_at": "2026-02-01T00:00:00Z",
            "engagement": {"score": 8, "comments": 4},
            "metadata": {},
        },
        {
            "source": "reddit",
            "id": "2",
            "title": "Looking for deploy diff automation",
            "text": "Deployment diff review is still manual for our team",
            "url": "https://example.com/2",
            "author": "b",
            "created_at": "2026-02-02T00:00:00Z",
            "engagement": {"score": 5, "comments": 2},
            "metadata": {},
        },
    ]
    processed, _ = process_raw_signals(raw)
    themes, meta = cluster_signals(processed)
    assert meta["clustering_method"] == "keyword_similarity"
    assert len(themes) == 1
    assert themes[0]["signal_count"] == 2
