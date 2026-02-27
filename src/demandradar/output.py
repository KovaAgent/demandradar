from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


def save_result_json(result: dict[str, Any], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def load_result_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_theme_table(result: dict[str, Any]) -> Table:
    table = Table(title="DemandRadar Results")
    table.add_column("Rank", justify="right")
    table.add_column("Theme")
    table.add_column("Signals", justify="right")
    table.add_column("Avg Frustration", justify="right")
    table.add_column("Top Source")

    for theme in result.get("themes", []):
        table.add_row(
            str(theme.get("rank", "-")),
            str(theme.get("theme", "")),
            str(theme.get("signal_count", 0)),
            f"{float(theme.get('avg_frustration', 0)):.2f}",
            str(theme.get("top_source", "")),
        )
    return table


def print_scan_result(result: dict[str, Any], console: Console | None = None) -> None:
    console = console or Console()
    metadata = result.get("metadata", {})
    console.print(build_theme_table(result))
    console.print(
        f"Scanned sources: {', '.join(metadata.get('sources_scanned', []))} | "
        f"Raw signals: {metadata.get('raw_signal_count', 0)} | "
        f"Processed signals: {metadata.get('processed_signal_count', 0)}"
    )
    for warning in result.get("warnings", []):
        console.print(f"[yellow]Warning:[/yellow] {warning}")


def pretty_print_saved_result(result: dict[str, Any], console: Console | None = None) -> None:
    console = console or Console()
    metadata = result.get("metadata", {})
    console.print(build_theme_table(result))
    console.print(
        f"Generated at: {metadata.get('generated_at', 'unknown')} "
        f"({metadata.get('version', 'v?')})"
    )
    if metadata.get("topic"):
        console.print(f"Topic filter: {metadata['topic']}")
    if result.get("warnings"):
        for warning in result["warnings"]:
            console.print(f"[yellow]Warning:[/yellow] {warning}")
