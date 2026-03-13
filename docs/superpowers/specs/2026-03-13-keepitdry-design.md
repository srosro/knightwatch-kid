# keepitdry (kid) — Semantic Code Search for DRY Codebases

## High-Level Goal

**Prevent spaghetti code and duplicative functions/classes/variables.**

`keepitdry` is a semantic code search tool that lets developers (and Claude Code agents) search a codebase by *meaning* before writing new code. The core workflow:

1. Developer is about to write a new function/class
2. They search semantically: `kid find "parse config from yaml file"`
3. If something similar already exists, they reuse/extend it instead of duplicating
4. Result: DRY code, fewer duplicates, less spaghetti

This is especially powerful as a Claude Code skill — agents can be instructed to **always search before writing**, enforcing DRY as a first-class development practice.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Library + CLI + Skill (layered) | Clean separation; library is reusable, CLI and skill evolve independently, testable |
| Embedding model | `mxbai-embed-large` via Ollama | Best quality that fits 3090 (24GB), 1024 dims, ~1GB VRAM, free/offline |
| Vector storage | ChromaDB | Zero-config, embedded, good API, per-project storage |
| Code parsing | tree-sitter | Universal parser (40+ languages), structured extraction, Python-only for v1 |
| Index location | `.keepitdry/` inside each project | Avoids leaking sensitive code to centralized location, easy to .gitignore |
| CLI name | `kid` | Short for "keep it dry" |
| Languages (v1) | Python only | Functions, classes, variables. Tree-sitter makes adding languages easy later |

## Architecture

### Layered Design

```
┌─────────────────────────────────────┐
│  Claude Code Skill (skill/)         │  ← Publishable marketplace skill
│  Invokes library or CLI             │
├─────────────────────────────────────┤
│  CLI: `kid` (cli/)                  │  ← User-facing terminal interface
│  Thin click wrapper                 │
├─────────────────────────────────────┤
│  Core Library: keepitdry (src/)     │  ← Shared engine
│  parser → embeddings → store        │
│  indexer (orchestrator)             │
│  searcher (query + rank)            │
└─────────────────────────────────────┘
│  ChromaDB        │  Ollama          │  ← External dependencies
│  (per-project)   │  (local server)  │
└──────────────────┴──────────────────┘
```

### Project Structure

```
knightwatch-kid/
├── src/
│   └── keepitdry/
│       ├── __init__.py
│       ├── parser.py          # tree-sitter Python extraction
│       ├── embeddings.py      # Ollama mxbai-embed-large client
│       ├── store.py           # ChromaDB operations
│       ├── indexer.py         # orchestrates parse → embed → store
│       └── searcher.py        # query embedding + search + ranking
├── cli/
│   └── kid.py                 # click-based CLI entry point
├── skill/
│   ├── SKILL.md               # Claude Code skill definition
│   └── skill.py               # skill handler (calls library)
├── tests/
│   ├── test_parser.py
│   ├── test_embeddings.py
│   ├── test_store.py
│   ├── test_indexer.py
│   └── test_searcher.py
├── pyproject.toml             # package config, `kid` CLI entry point
└── .gitignore
```

## Core Library Modules

### parser.py — Tree-sitter Code Extraction

Extracts code elements from Python files using tree-sitter:

- **Functions** (top-level and nested)
- **Classes** (with methods as separate elements)
- **Module-level variables** (assignments)

Each extracted element produces a `CodeElement`:

```python
@dataclass
class CodeElement:
    file_path: str          # relative to project root
    element_name: str       # e.g., "MyClass.process_data"
    element_type: str       # "function" | "class" | "method" | "variable"
    signature: str          # e.g., "def process_data(self, input: str) -> dict"
    docstring: str | None
    code_body: str          # actual source code of the element
    line_number: int
    parent_chain: str       # e.g., "mymodule.py > MyClass"
```

Key design choices:
- **Embed the actual code body**, not just metadata — most code has no docstrings
- **Hierarchical context via `parent_chain`** — prepend module path and parent class so "database connection" ranks `db/connection.py::ConnectionPool.connect()` higher
- **Smart chunking for large elements** — if a function/class exceeds a token threshold, split at tree-sitter child node boundaries (methods, if/for/with blocks), not arbitrary line counts. Each chunk inherits its parent context as a prefix.

### embeddings.py — Ollama Client

Generates embeddings via local Ollama server:

- Model: `mxbai-embed-large` (1024 dimensions)
- Constructs searchable text: `parent_chain + element_name + signature + docstring + code_body`
- Batch embedding support for indexing speed
- Ollama health check / helpful error if Ollama isn't running

### store.py — ChromaDB Operations

Manages per-project ChromaDB collections:

- DB location: `<project_root>/.keepitdry/`
- Collection per project (single collection for all elements)
- Stores embeddings + metadata (file_path, element_type, line_number, etc.)
- Supports metadata filtering (by type, file path glob)
- Handles upsert for incremental indexing

### indexer.py — Orchestrator

Coordinates the index pipeline:

1. Walk project directory, discover Python files
2. Respect `.gitignore` patterns, skip `.keepitdry/`, `__pycache__`, `node_modules`, `.venv`
3. Compute file hashes → skip unchanged files (incremental indexing)
4. Parse each changed file via `parser.py`
5. Chunk large elements
6. Batch embed via `embeddings.py`
7. Upsert into ChromaDB via `store.py`
8. Remove stale entries for deleted/renamed files

File hash cache stored in `.keepitdry/file_hashes.json`.

### searcher.py — Query + Rank

Handles search queries:

1. Embed query text via `embeddings.py`
2. Query ChromaDB for top-K similar vectors
3. Support metadata filters: `--type function`, `--file "models/*.py"`
4. Return results with similarity scores, file paths, line numbers, code previews

## CLI Interface

```bash
# Index current directory
kid index [--clear] [--verbose]

# Index specific directory
kid index /path/to/project

# Search
kid find "parse configuration from yaml"
kid find "database connection pooling" --limit 10
kid find "auth" --type function --file "api/*.py"

# Show index stats
kid stats

# Remove index
kid clean
```

## Claude Code Skill

The skill instructs Claude Code to search before writing:

```markdown
# SKILL.md
Before writing any new function, class, or significant code block:
1. Run `kid find "<description of what you're about to write>"`
2. If similar code exists (similarity > 0.7), reuse or extend it
3. Only write new code if nothing similar exists
4. After writing, re-index: `kid index .`
```

The skill will be publishable on the Claude Code marketplace.

## Search Quality Improvements

Beyond basic vector similarity:

1. **Code body in embeddings** — embed actual source, not just names/docstrings
2. **Hierarchical context prefix** — module path + parent class prepended to improve ranking
3. **Smart chunking** — large elements split at tree-sitter node boundaries, each chunk inherits parent context
4. **Incremental indexing** — file hash-based, fast enough to run frequently
5. **Metadata filtering** — combine vector search with type/path filters via ChromaDB

## Dependencies

```
# Core
tree-sitter >= 0.21
tree-sitter-python >= 0.21
chromadb >= 0.4
requests >= 2.31        # for Ollama HTTP API

# CLI
click >= 8.0

# Dev
pytest >= 7.0
```

## External Requirements

- **Ollama** running locally with `mxbai-embed-large` pulled:
  ```bash
  ollama pull mxbai-embed-large
  ```

## Future Extensions (Not v1)

- Additional languages via tree-sitter grammars (JS/TS, Go, Rust, etc.)
- Hybrid search: combine vector similarity with BM25 keyword matching
- MCP server wrapper for native Claude Code tool integration
- Pre-commit hook: auto-index on commit
- Watch mode: re-index on file changes
- Cross-project search: find similar code across multiple repos

## Prior Art

This design is informed by the semantic search implementation in `~/Hacking/codel/ct1/arsenal/dot-claude/skills/semantic-search/`. Key differences from arsenal:

| Arsenal | keepitdry |
|---------|-----------|
| OpenAI embeddings (paid, network) | Ollama local embeddings (free, offline) |
| PostgreSQL + pgvector (Docker) | ChromaDB (embedded, no infra) |
| Python AST only | tree-sitter (extensible to any language) |
| Name + signature + docstring only | Full code body + hierarchical context |
| No incremental indexing | File hash-based incremental |
| Docker-coupled | Standalone pip-installable CLI |
