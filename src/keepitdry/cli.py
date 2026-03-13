"""kid CLI — semantic code search for DRY codebases."""

from __future__ import annotations

from pathlib import Path

import click

from keepitdry import embeddings as embed_module
from keepitdry.indexer import Indexer
from keepitdry.searcher import Searcher


@click.group()
def main():
    """kid — keep it dry. Semantic code search."""
    pass


@main.command()
@click.argument("project", default=".", type=click.Path(exists=True, path_type=Path))
@click.option("--clear", is_flag=True, help="Clear index before rebuilding.")
def index(project: Path, clear: bool):
    """Index a project directory."""
    project = project.resolve()
    embed_module.check_ollama()

    indexer = Indexer(project)
    stats = indexer.index(clear=clear)

    click.echo(f"Indexed {stats['files_indexed']} files, "
               f"{stats['elements_indexed']} elements. "
               f"Skipped {stats['files_skipped']} unchanged files.")
    if stats["stale_removed"]:
        click.echo(f"Removed {stats['stale_removed']} stale entries.")


@main.command()
@click.argument("query")
@click.option("--project", default=".", type=click.Path(exists=True, path_type=Path),
              help="Project directory to search.")
@click.option("--limit", default=5, help="Max results.")
@click.option("--type", "element_type", default=None, help="Filter by element type.")
@click.option("--file", "file_path", default=None, help="Filter by file path.")
def find(query: str, project: Path, limit: int, element_type: str | None, file_path: str | None):
    """Search for similar code elements."""
    project = Path(project).resolve()
    embed_module.check_ollama()

    searcher = Searcher(project)
    results = searcher.search(
        query=query,
        limit=limit,
        element_type=element_type,
        file_path=file_path,
    )

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        score = r["similarity"]
        click.echo(f"\n{'─' * 60}")
        click.echo(f"  [{i}] {r['element_name']}  ({r['element_type']})  "
                    f"score: {score:.3f}")
        click.echo(f"  {r['file_path']}:{r['line_number']}")
        click.echo(f"  {r['signature']}")
        code_lines = r["code"].split("\n")
        preview = "\n".join(code_lines[:8])
        if len(code_lines) > 8:
            preview += f"\n  ... ({len(code_lines) - 8} more lines)"
        click.echo(f"\n{preview}")


if __name__ == "__main__":
    main()
