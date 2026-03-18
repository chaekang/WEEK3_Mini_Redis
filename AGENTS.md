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
2. Confirm the current task fits the MVP or stretch scope.
3. Summarize the assigned outcome, fixed contracts, allowed files, and dependent branches.
4. Work in one branch-scoped task only.
5. Update related docs when behavior, contracts, or conventions change.
6. Keep `README.md` short, demo-friendly, and readable by first-time reviewers.

## Development Order

Prefer this order:
1. Contracts and folder skeleton
2. Store core and expiration metadata
3. Protocol or API entrypoint
4. Tests for mandatory commands
5. Persistence-lite and benchmark
6. README polish for demo

## Task Sizing Rules

- One branch should focus on one clear outcome.
- Do not ask AI to build the whole project in one prompt.
- Prefer prompts like `implement TTL semantics and tests in branch feature/store-expiration`.
- Avoid using multiple AI agents on the same file at the same time unless explicitly coordinated.

## Collaboration Rules

- Each teammate works on a separate branch.
- Never push directly to `main`.
- Use only `feature/*`, `fix/*`, `docs/*`, `test/*`, or `chore/*` branches.
- Merge to `main` only through pull requests after required checks pass.
- Command behavior changes must update `docs/03-command-semantics.md` in the same PR.
- Architecture changes must update `docs/02-architecture.md` in the same PR.
- Process or branching changes must update `docs/04-development-guide.md` or `docs/05-codex-collaboration-playbook.md` in the same PR.
- `README.md` is an entry document and presentation summary, not a scratchpad.

## Definition of Done

A task is complete when:
- Code is implemented for the assigned scope.
- Relevant automated checks pass.
- Manual smoke checks for the assigned scope are recorded.
- Related docs are updated.
- PR summary explains what changed, why, and any known limitations.

## Good Prompt Examples

- `Read AGENTS.md and docs/01 through docs/06. Implement GET/SET/DEL semantics in branch feature/store-expiration. Work only in the allowed files.`
- `Read docs/03-command-semantics.md and add HTTP handler support for PING, GET, SET, DEL in branch feature/protocol-network.`
- `Using docs/06-testing-playbook.md, add only the branch-scoped tests for AOF replay.`
- `Polish README.md for the planned demo based on the currently implemented features only.`

## Things AI Should Avoid

- Inventing requirements not described in the docs
- Editing unrelated files during a branch-scoped task
- Leaving documentation and implementation out of sync
- Turning README into a running dev log
- Expanding scope to replication, cluster, pub/sub, or advanced data types unless explicitly assigned
