# kid — keep it dry

Semantic code search. Index a project once, then query it by meaning rather than by literal string. Backed by local embeddings via Ollama, so nothing leaves your machine.

Currently indexes Python (via tree-sitter).

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) for installing the CLI
- [Ollama](https://ollama.ai/) running (locally on `http://localhost:11434` by default — see [Configuration](#configuration))
- An embedding model pulled into Ollama (`mxbai-embed-large` by default)

## Install

```bash
git clone https://github.com/srosro/knightwatch-kid.git
cd knightwatch-kid
uv tool install .
```

This installs a `kid` executable (usually at `~/.local/bin/kid` — make sure it's on your `PATH`).

To upgrade later, pull and reinstall:

```bash
git pull
uv tool install . --reinstall
```

## Ollama setup

Install Ollama (see https://ollama.ai) and pull the embedding model:

```bash
ollama pull mxbai-embed-large
```

Make sure the server is running. With systemd it's usually automatic; without it:

```bash
nohup ollama serve > /tmp/ollama.log 2>&1 &
```

Verify:

```bash
curl -s http://localhost:11434/api/tags
```

## Configuration

The model and endpoint are read from the environment, with defaults that work for a local CPU-friendly setup. Override them per host — e.g. point at a remote Ollama, or use a larger model on a GPU box:

| Variable | Default | Purpose |
| --- | --- | --- |
| `KID_EMBED_MODEL` | `mxbai-embed-large` | Embedding model to use. |
| `KID_OLLAMA_URL` | `http://localhost:11434` | Ollama base URL. |
| `KID_MAX_EMBED_CHARS` | `900` | Per-element input truncation (raise it for longer-context models). |

```bash
# example: a bigger model on a GPU host
export KID_EMBED_MODEL=qwen3-embedding:8b
export KID_MAX_EMBED_CHARS=4000
ollama pull qwen3-embedding:8b
```

> **Changing the model means re-indexing.** The vector dimension is fixed by the model (e.g. `mxbai-embed-large` is 1024-dim, `qwen3-embedding:8b` is 4096-dim), and an existing `.keepitdry` index is tied to the dimension it was built with. After switching `KID_EMBED_MODEL`, rebuild with `kid index --clear <project>` (or `kid clean` then `kid index`).

## Usage

### Index a project

```bash
kid index /path/to/project
```

The index lives in `<project>/.keepitdry/`. Re-running `kid index` is incremental — unchanged files are skipped and stale entries are pruned. Use `--clear` to force a full rebuild.

### Search

```bash
kid find "oauth token exchange" --project /path/to/project
```

Options:

- `--limit N` — number of results (default 5)
- `--type <kind>` — filter by element type (e.g. `function`, `method`, `class`, `variable`)
- `--file <path>` — restrict to a single file

Each hit shows the element name, type, similarity score, file:line, signature, and a code preview.

### Stats

```bash
kid stats --project /path/to/project
```

### Clean

```bash
kid clean /path/to/project
```

Removes the `.keepitdry` index for that project.

## Typical workflow

Keep a read-only checkout of the main branch as a "canonical" reference, index it, and search it when reviewing new work:

```bash
# one-time
git clone <repo-url> ~/code/myproj-main
kid index ~/code/myproj-main

# periodically
cd ~/code/myproj-main && git pull --ff-only && kid index .

# while reviewing new code elsewhere
kid find "rate limit bucket" --project ~/code/myproj-main
```

## Notes and limitations

- Only Python is parsed today. Other languages are ignored.
- Long functions or classes are truncated to `KID_MAX_EMBED_CHARS` before embedding to fit the model's context window (`mxbai-embed-large` is 512 tokens). If you see `400 Client Error` from `/api/embed` with `input length exceeds the context length` in Ollama's log, lower `KID_MAX_EMBED_CHARS`.
- Similarity scores are cosine-based; numbers are only meaningful relative to each other within the same query.
