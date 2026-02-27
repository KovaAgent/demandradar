from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console

from . import __version__
from .config import load_config, resolve_sources
from .fetchers import fetch_github_signals, fetch_hn_signals, fetch_reddit_signals
from .output import load_result_json, pretty_print_saved_result, print_scan_result, save_result_json
from .processor import cluster_signals, process_raw_signals
from .scorer import rank_themes

console = Console()
VALID_SOURCES = {"hn", "github", "reddit"}

Fetcher = Callable[..., Awaitable[list[dict[str, Any]]]]


async def _run_fetcher(
    name: str,
    fetcher: Fetcher,
    *,
    lookback_days: int,
    max_signals: int,
    topic: str | None,
    github_token: str | None,
) -> tuple[str, list[dict[str, Any]], str | None]:
    try:
        kwargs: dict[str, Any] = {
            "lookback_days": lookback_days,
            "max_signals": max_signals,
            "topic": topic,
        }
        if name == "github":
            kwargs["github_token"] = github_token
        signals = await fetcher(**kwargs)
        return name, signals, None
    except Exception as exc:  # pragma: no cover - exercised via CLI behavior integration path.
        return name, [], f"{name} fetch failed: {exc}"


async def run_scan_pipeline(
    sources: list[str],
    topic: str | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    source_map: dict[str, Fetcher] = {
        "hn": fetch_hn_signals,
        "github": fetch_github_signals,
        "reddit": fetch_reddit_signals,
    }
    tasks = [
        _run_fetcher(
            source,
            source_map[source],
            lookback_days=int(config["lookback_days"]),
            max_signals=int(config["max_signals_per_source"]),
            topic=topic,
            github_token=config.get("github_token") or None,
        )
        for source in sources
    ]
    results = await asyncio.gather(*tasks)

    warnings: list[str] = []
    raw_signals: list[dict[str, Any]] = []
    raw_counts: dict[str, int] = {}
    for source_name, signals, warning in results:
        raw_counts[source_name] = len(signals)
        raw_signals.extend(signals)
        if warning:
            warnings.append(warning)

    processed_signals, processing_meta = process_raw_signals(
        raw_signals,
        openai_api_key=(config.get("openai_api_key") or None),
        topic=topic,
    )
    themes, clustering_meta = cluster_signals(processed_signals)
    ranked_themes = rank_themes(themes)

    warnings.extend(processing_meta.get("processor_warnings", []))
    metadata = {
        "version": __version__,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "sources_scanned": sources,
        "source_counts": raw_counts,
        "raw_signal_count": len(raw_signals),
        "processed_signal_count": len(processed_signals),
        "topic": topic,
        "lookback_days": int(config["lookback_days"]),
        "max_signals_per_source": int(config["max_signals_per_source"]),
        "extraction_method": processing_meta.get("extraction_method"),
        "clustering_method": clustering_meta.get("clustering_method"),
    }

    return {
        "metadata": metadata,
        "themes": ranked_themes,
        "warnings": warnings,
    }


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__)
def cli() -> None:
    """DemandRadar: scan developer communities for unmet demand signals."""


@cli.command()
@click.option(
    "--sources",
    help="Comma-separated sources to scan (hn,github,reddit). Defaults to config sources.",
)
@click.option("--topic", help="Optional topic/keyword filter, e.g. 'developer tools'.")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write full JSON results to a file.",
)
def scan(sources: str | None, topic: str | None, output: Path | None) -> None:
    """Scan data sources and output a ranked list of product ideas."""
    config = load_config()
    selected_sources = resolve_sources(sources, config_sources=config["sources"])
    invalid = [source for source in selected_sources if source not in VALID_SOURCES]
    if invalid:
        raise click.ClickException(
            "Invalid sources: "
            f"{', '.join(invalid)}. Valid values: {', '.join(sorted(VALID_SOURCES))}"
        )
    if not selected_sources:
        raise click.ClickException("No sources selected.")

    result = asyncio.run(run_scan_pipeline(selected_sources, topic=topic, config=config))
    print_scan_result(result, console=console)
    if output:
        path = save_result_json(result, output)
        console.print(f"Saved results to [green]{path}[/green]")


@cli.command()
@click.argument("result_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def show(result_file: Path) -> None:
    """Pretty-print a previously saved scan JSON file."""
    result = load_result_json(result_file)
    pretty_print_saved_result(result, console=console)


if __name__ == "__main__":
    cli()
