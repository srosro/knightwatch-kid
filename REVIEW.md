# Review instructions — knightwatch-kid

## Cause-first bug fixes

Fix at the cause; never with a workaround that leaves the cause in place. A guard or check at the boundary where the cause lives is a cause-level fix. If a fix adds a maintained path or net complexity, explain why removing the cause directly is insufficient. No stopgaps: they promote brittle, confusing, unreliable code. Ship the fix at the cause. Required rollout sequencing (staged removals, compatibility windows) and authorized incident containment, labeled with when it's removed, are not stopgaps. When the bug comes from a duplicated source or identity, remove the duplicate rather than bridging the two. Limits a REVIEW.md already records as accepted stay out of review unless the diff widens them.

Repo-specific reviewer policy. The universal review policy is prepended by the reviewer and is not restated here.

## What this repo is

`kid` (keepitdry): local semantic code search. It indexes a project with tree-sitter and local Ollama embeddings into a chromadb store, then answers queries by meaning. knightwatch-reviewer runs it as its prior-art (DRY) pre-pass, and an hourly host timer builds the indexes for every tracked repo.

**Stage:** single operator; the main consumer is the reviewer fleet. `AGENTS.md` carries the same stance on complexity debt.

## Review priority

**#1: low complexity.** Pre-PMF, simple code that meets the need beats complete code. Weigh every finding against this first.

- **Cut scope creep.** Flag a change that grows past its stated ask. The remedy is a smaller change, not more code.
- **DRY.** Flag a second copy of logic or facts that already have an owner. The remedy is to reuse that owner or delete the copy.
- **Few conditionals.** Each new branch, guard, fallback or special case is a finding unless it handles a failure that actually happens. Security and access checks are not special cases.
- **Model decision over regex.** Judging the meaning of natural language belongs to an LLM call, never a regex or keyword list. Deterministic checks on structured or model output (a required tag, a value from a fixed set, a sum) stay code and are not findings.

Prefer subtractive remedies (delete, collapse, reuse) over additive ones at any severity.

## Where the real risks are

- **Index that never finishes or silently goes stale.** Large repos take hours to index; flag a change that loses progress on a timeout or crash, or reports success on a partial index.
- **Query contract.** The reviewer parses `kid` output; flag a change to output shape or ids that breaks existing indexes or the reviewer's reader.
