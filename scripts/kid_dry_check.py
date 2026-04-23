#!/usr/bin/env python3
"""Inject DRY prior-art matches into automated code reviews.

Reads a unified diff on stdin. For each contiguous run of added lines of
length >= MIN_BLOCK_LINES in a supported source file, runs `kid find` against
the indexed project and collects the top matches above SCORE_FLOOR.

Emits a markdown block suitable for appending to the reviewer prompt on
stdout. Exits non-zero with a traceback on any failure (missing kid binary,
kid error, Ollama unreachable, bad JSON, timeout) — the reviewer should abort
loudly rather than silently proceed without prior-art context.

Env vars:
  KID_BIN       — path to `kid` executable (default: kid on PATH)
  KID_PROJECT   — project directory indexed by kid (required)

Invocation: `kid_dry_check.py < pr.diff`
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

KID_BIN = os.environ.get("KID_BIN", "kid")
KID_PROJECT = os.environ["KID_PROJECT"]

MIN_BLOCK_LINES = 3
MAX_BLOCKS = 20
MAX_MATCHES_PER_BLOCK = 5
SCORE_FLOOR = 0.70
KID_TIMEOUT_SECS = 15

SUPPORTED_EXTS = (".py", ".swift")

_TEST_PATTERNS = [
    re.compile(r"(^|/)tests?/"),
    re.compile(r"(^|/)test_[^/]+\.py$"),
    re.compile(r"(^|/)[^/]+_test\.py$"),
    re.compile(r"(^|/)[^/]+Tests\.swift$"),
]


def _is_test_file(path: str) -> bool:
    return any(p.search(path) for p in _TEST_PATTERNS)


@dataclass
class Block:
    file_path: str
    start_line: int
    lines: list[str] = field(default_factory=list)

    @property
    def significant_loc(self) -> int:
        return sum(
            1 for line in self.lines
            if line.strip() and not line.lstrip().startswith(("#", "//", "/*", "*"))
        )

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_diff(diff: str) -> list[Block]:
    """Extract contiguous runs of added lines from a unified diff."""
    blocks: list[Block] = []
    current_file: str | None = None
    line_in_new: int = 0
    open_block: Block | None = None

    def flush() -> None:
        nonlocal open_block
        if open_block and open_block.significant_loc >= MIN_BLOCK_LINES:
            blocks.append(open_block)
        open_block = None

    for line in diff.splitlines():
        if line.startswith("+++ "):
            flush()
            p = line[4:].strip()
            if p.startswith("b/"):
                p = p[2:]
            current_file = p if p != "/dev/null" else None
            continue
        if line.startswith("--- "):
            flush()
            continue
        if line.startswith("@@"):
            flush()
            m = _HUNK_RE.match(line)
            line_in_new = int(m.group(1)) if m else 0
            continue
        if current_file is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            if open_block is None:
                open_block = Block(current_file, line_in_new)
            open_block.lines.append(content)
            line_in_new += 1
        elif line.startswith("-"):
            flush()
        else:
            flush()
            if line and line.startswith(" "):
                line_in_new += 1

    flush()
    return blocks


def _filter_blocks(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        if not b.file_path.endswith(SUPPORTED_EXTS):
            continue
        if _is_test_file(b.file_path):
            continue
        out.append(b)
    return out[:MAX_BLOCKS]


def _query_kid(text: str) -> list[dict]:
    """Run `kid find --json` and return hits. Raises on any failure."""
    proc = subprocess.run(
        [KID_BIN, "find", "--project", KID_PROJECT, "--json",
         "--limit", str(MAX_MATCHES_PER_BLOCK), text],
        capture_output=True,
        text=True,
        timeout=KID_TIMEOUT_SECS,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kid find exited {proc.returncode}: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return json.loads(proc.stdout or "[]")


def _format_match(m: dict, *, same_file: bool) -> str:
    tag = " _(same file)_" if same_file else ""
    return (
        f"- `{m['element_name']}` ({m['element_type']}) — "
        f"`{m['file_path']}:{m['line_number']}` · "
        f"score {m['similarity']:.2f}{tag}"
    )


def _format_block(block: Block, matches: list[dict]) -> str:
    preview_lines = block.lines[:3]
    preview = "\n".join(f"  {ln}" for ln in preview_lines)
    if len(block.lines) > 3:
        preview += f"\n  … (+{len(block.lines) - 3} more)"

    lines = [
        f"### New block in `{block.file_path}:{block.start_line}` ({block.significant_loc} LOC)",
        "```",
        preview,
        "```",
        "Nearest prior art in the repo:",
    ]
    for m in matches:
        lines.append(_format_match(m, same_file=m["file_path"] == block.file_path))
    return "\n".join(lines)


def main() -> int:
    diff = sys.stdin.read()
    if not diff.strip():
        return 0

    blocks = _filter_blocks(parse_diff(diff))
    if not blocks:
        return 0

    sections: list[str] = []
    for block in blocks:
        hits = _query_kid(block.text)
        hits = [h for h in hits if h.get("similarity", 0) >= SCORE_FLOOR]
        if not hits:
            continue
        sections.append(_format_block(block, hits))

    if not sections:
        return 0

    print("## PRIOR ART (DRY CHECK)")
    print()
    print(
        "For each block below, either dismiss the match with a reason "
        "(different contract, unavoidable duplication, etc.) or raise it as a "
        "`blocking: dry` finding."
    )
    print()
    for s in sections:
        print(s)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
