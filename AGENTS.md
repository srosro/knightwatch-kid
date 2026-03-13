# AGENTS.md

Lightweight guidance for AI coding agents working in this repository.

## Mission

keepitdry exists to enforce DRY codebases. Search before building — always.

## Complexity Debt

- Complexity debt is worse than a product that breaks for one user. Do not fix an edge case in a way that adds complexity.
- Heuristic accretion is the canonical failure mode: one keyword exception, then another, then a special case. Avoid it absolutely.
- Complexity debt is doubly harmful: it makes the core solution appear more capable than it is, masking whether the real approach actually works, and it makes the codebase slower and more fragile to change.
- For open-ended interpretation or routing problems, prefer a generalizable semantic/model-based approach over ad hoc heuristic casework.

## Scope

- `src/keepitdry/` is the core library (parser, embeddings, store, indexer, searcher).
- `src/keepitdry/cli.py` is the `kid` CLI — a thin click wrapper over the library.
- `skill/` contains the Claude Code skill for marketplace publishing.
- `tests/` contains all tests.
- `docs/` contains design specs and architecture notes.

## Read First

Before making meaningful changes, read:

1. `docs/superpowers/specs/2026-03-13-keepitdry-design.md` — the design spec

## Core Standard

Write code that is:

- correct
- minimal
- obvious
- consistent with the local codebase
- typed where the shape matters
- easy to delete, extend, or debug

Prefer the simplest implementation that clearly solves the real problem.

## Product Stage

This product is still early. The main goal is to build the right core product, not to preserve every intermediate implementation.

- Prefer clean replacement over migration code.
- Do not add dual-write paths, compatibility layers, fallback implementations, or "old path/new path" systems unless the user explicitly asks for them.
- Do not keep multiple paths that solve the same problem.
- Do not spend time on edge-case hardening or operational complexity that does not help the core use case.
- Design so the core model can extend to adjacent use cases later (e.g., new languages via tree-sitter), but do not prebuild for special cases.

## How To Work

- Act autonomously by default. Read files, inspect state, and run commands without asking for permission.
- Ask questions only when ambiguity materially changes architecture, business logic, or user intent.
- Search before building. Reuse or extend existing code when it is already close to the needed behavior.
- Match the grain of the codebase. Prefer local consistency over introducing a new pattern you happen to like better.
- Touch the smallest surface area that solves the problem.

## Keep It Simple

- Prefer one obvious execution path.
- Do not add speculative abstractions, fallback layers, retries, or knobs unless there is a real requirement.
- Let internal errors surface. Catch only specific errors you can handle meaningfully.
- Avoid single-use helpers unless they materially improve readability.
- Keep imports at the top of the file unless a local import is genuinely needed for an optional dependency or import-cycle reason.
- Remove dead code, commented-out code, stale TODOs, and debug leftovers.

## Types And Data Shape

- Add or preserve type hints for non-trivial code.
- Prefer explicit shaped data over loose dictionaries when practical.
- If a payload shape matters across module boundaries, model it clearly.
- Avoid widening types just to silence checks.

## Tests

Follow red-green TDD. No production code without a failing test first.

1. **RED**: Write a failing test that describes the desired behavior.
2. **GREEN**: Write the minimal code to make it pass.
3. **REFACTOR**: Clean up while keeping tests green.

If you wrote code before the test, delete it and start over.

Test outcomes, not implementation:

- Test behavior and outcomes, not implementation details.
- Avoid brittle assertions tied to incidental formatting, exact internal call structure, or mock choreography.
- Do not write tests for self-evident language or library behavior.

## Definition Of Done

A change is done when:

- a failing test existed before the implementation was written
- it solves the actual problem with minimal code
- the implementation is easy to follow
- the relevant tests pass for the surface you changed
- no unnecessary abstractions or debug artifacts remain

## Communication

- Be concise and concrete.
- State what changed, what you verified, and any real risks or open questions.
- Do not pad responses with process theater.
