# AGENTS.md

## Project Overview

This repository uses a docs-first workflow for AI-assisted development.

### Source of truth order
1. `docs/01-product-scope.md`
2. `docs/02-architecture.md`
3. `docs/03-command-semantics.md`
4. `docs/04-development-guide.md`
5. `README.md`

If these documents conflict, follow the numbered order above.

Supplemental operational guides:
- `docs/05-codex-collaboration-playbook.md`: branch-scoped execution guide for teammates and AI tools.
- `docs/06-testing-playbook.md`: testing and verification guide.
- `docs/07-team-kickoff-script.md`: kickoff script and role assignment guide.

## How AI Should Work In This Repo

Before writing code, the assistant should:
1. Read `docs/01` through `docs/06`.
2. In `docs/05`, locate the section for the assigned branch.
3. In `docs/06`, confirm the required tests for that branch.
4. Confirm the current task fits the MVP or an approved stretch item.
5. Summarize the assigned outcome, fixed contracts, allowed files, and dependent branches.
6. Work in one branch-scoped task only.
7. Keep HTTP behavior intact while adding RESP access only where the assigned branch allows it.
8. Treat `docs/01` through `docs/04` and `docs/07` as shared contract docs after the refresh branch lands.
9. Keep `README.md` short, demo-friendly, and readable by first-time reviewers.

## Development Order

Prefer this order:
1. Shared docs refresh in `docs/parallel-track-refresh`
2. Store core with custom hash table
3. Heap-based expiration sweep
4. RESP protocol entrypoint and wiring
5. Demo, benchmark, CI, and README polish
6. AOF-lite only as a follow-up track after the active parallel work is stable

## Task Sizing Rules

- One branch should focus on one clear outcome.
- Do not ask AI to build the whole project in one prompt.
- Prefer prompts like `implement RESP parser and socket smoke in branch feature/protocol-resp`.
- Avoid using multiple AI agents on the same file at the same time unless explicitly coordinated.

## Collaboration Rules

- Each teammate works on a separate branch.
- Never push directly to `main`.
- Use only `feature/*`, `fix/*`, `docs/*`, `test/*`, or `chore/*` branches.
- Merge to `main` only through pull requests after required checks pass.
- `docs/parallel-track-refresh` is the only branch that should rewrite shared docs `01` through `07` in one pass.
- After that refresh lands, feature branches should implement the documented contracts instead of reopening shared contract docs.
- If a shared contract really must change, do it in a separate `docs/*` branch first, not inside an unrelated feature branch.
- HTTP stays in place; RESP is an additional access path, not a replacement.
- `README.md` is an entry document and presentation summary, not a scratchpad.

## Definition of Done

A task is complete when:
- Code is implemented for the assigned scope.
- Relevant automated checks pass.
- Manual smoke checks for the assigned scope are recorded.
- Related docs are updated when the branch is explicitly responsible for them.
- PR summary explains what changed, why, and any known limitations.

## Good Prompt Examples

- `Read AGENTS.md and docs/01 through docs/06. Implement RESP parsing and TCP handling in branch feature/protocol-resp. Work only in the allowed files and keep HTTP behavior unchanged.`
- `Read docs/02, docs/03, docs/05, and docs/06. Implement the custom hash table contract in branch feature/store-hash-table without changing command semantics.`
- `Using docs/06-testing-playbook.md, add only the branch-scoped tests for heap-based expiration sweep.`
- `Polish README.md, benchmark artifacts, and CI checks for the planned demo based on the currently implemented features only.`

## Things AI Should Avoid

- Inventing requirements not described in the docs
- Removing HTTP while adding RESP
- Editing unrelated files during a branch-scoped task
- Reopening shared contract docs from a feature branch
- Leaving documentation and implementation out of sync
- Turning README into a running dev log
- Expanding scope to replication, cluster, pub/sub, advanced data types, or active AOF work unless explicitly assigned
