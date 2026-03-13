"""Skill handler for Claude Code integration."""

from __future__ import annotations

import subprocess
import sys


def run_kid(args: list[str]) -> str:
    """Run a kid CLI command and return output."""
    result = subprocess.run(
        ["kid", *args],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr


def search_before_writing(description: str, project: str = ".") -> str:
    """Search for existing code before writing new code."""
    return run_kid(["find", description, "--project", project])


def reindex(project: str = ".") -> str:
    """Re-index after writing new code."""
    return run_kid(["index", project])
