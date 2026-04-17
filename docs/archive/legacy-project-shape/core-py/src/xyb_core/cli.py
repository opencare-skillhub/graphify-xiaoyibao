from __future__ import annotations

import typer

app = typer.Typer(help="xiaoyibao patient knowledge graph CLI")


@app.command()
def scan(path: str) -> None:
    """Scan a patient record directory."""
    typer.echo(f"scan {path}")


@app.command()
def report() -> None:
    """Render a patient summary report."""
    typer.echo("report")


@app.command()
def serve() -> None:
    """Serve the local MCP/HTTP bridge."""
    typer.echo("serve")
