---
name: keepitdry
description: Search before writing — enforce DRY by finding similar code semantically
---

# keepitdry

Before writing any new function, class, or significant code block:

1. Run `kid find "<description of what you're about to write>"` in the project directory
2. Review the results:
   - **Similarity > 0.7**: Reuse or extend the existing code
   - **Similarity 0.5–0.7**: Consider whether the existing code can be adapted
   - **No results or < 0.5**: Proceed with writing new code
3. After writing new code, re-index: `kid index .`

## Setup

Requires `kid` CLI installed (`pip install keepitdry`) and Ollama running locally with `mxbai-embed-large`.

## Commands

- `kid index [path]` — Index a project (incremental, fast on re-runs)
- `kid find "query"` — Search for similar code
- `kid find "query" --type function` — Filter by element type
- `kid find "query" --file "api/*.py"` — Filter by file path
- `kid stats` — Show index info
- `kid clean` — Remove index
