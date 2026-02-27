from __future__ import annotations

from typing import Any


def score_theme(theme: dict[str, Any]) -> float:
    signal_count = int(theme.get("signal_count") or 0)
    avg_frustration = float(theme.get("avg_frustration") or 0)
    return round(signal_count * avg_frustration, 2)


def rank_themes(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for theme in themes:
        theme_copy = dict(theme)
        theme_copy["score"] = score_theme(theme_copy)
        ranked.append(theme_copy)
    ranked.sort(key=lambda t: (t["score"], t.get("signal_count", 0)), reverse=True)
    for idx, theme in enumerate(ranked, start=1):
        theme["rank"] = idx
    return ranked
