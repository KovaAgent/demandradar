from __future__ import annotations

from demandradar.scorer import rank_themes, score_theme


def test_score_theme_multiplies_signal_count_and_frustration() -> None:
    theme = {"signal_count": 4, "avg_frustration": 3.5}
    assert score_theme(theme) == 14.0


def test_rank_themes_orders_descending_by_score() -> None:
    themes = [
        {"theme": "A", "signal_count": 2, "avg_frustration": 2.0},
        {"theme": "B", "signal_count": 3, "avg_frustration": 3.0},
    ]
    ranked = rank_themes(themes)
    assert [theme["theme"] for theme in ranked] == ["B", "A"]
    assert [theme["rank"] for theme in ranked] == [1, 2]
