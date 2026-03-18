# 05. Codex Collaboration Playbook

이 문서는 사람 설명서라기보다, 팀원 각자의 AI가 **같은 규칙**으로 움직이도록 만드는 실행 가이드다.

주의:
- 요구사항과 설계 충돌 시 `docs/01` ~ `docs/04`를 우선한다.
- 이 문서는 branch-scoped parallel work를 돕는 보조 문서다.
- HTTP는 유지하고 RESP는 추가한다.

## 1) 시작 순서
각 팀원은 새 작업을 시작할 때 AI에게 아래 순서로 읽게 한다.
1. `AGENTS.md`
2. `docs/01-product-scope.md`
3. `docs/02-architecture.md`
4. `docs/03-command-semantics.md`
5. `docs/04-development-guide.md`
6. `docs/06-testing-playbook.md`
7. 이 문서의 본인 담당 트랙 섹션

## 2) 공통 시작 프롬프트
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside the scope of branch <branch-name>. Before coding, summarize the assigned outcome, allowed files, fixed contracts, out-of-scope items, dependent branches, and required tests. Keep HTTP behavior intact, add RESP only if this branch owns it, and reuse the documented dispatcher semantics instead of redefining command behavior. Then implement only that branch scope, run the relevant checks, and prepare a PR-ready summary.
```

## 3) 공통 작업 원칙
- 한 AI는 한 브랜치의 한 결과만 다룬다.
- 담당 브랜치 범위를 벗어난 파일은 수정하지 않는다.
- shared docs refresh 이후에는 `docs/01` through `docs/04`, `docs/07`을 feature 브랜치에서 다시 열지 않는다.
- shared contract를 바꿔야 하면 기능 브랜치가 아니라 별도 `docs/*` 브랜치로 먼저 정리한다.
- track-local 문서 수정이 꼭 필요하면 `docs/05`, `docs/06`의 자기 섹션 안에서 최소한으로만 한다.
- HTTP와 RESP는 같은 dispatcher semantics를 재사용해야 한다.
- custom hash table, heap sweep, coarse lock은 문서 합의 없이 다시 설계하지 않는다.
- 테스트는 `docs/06` 기준으로 branch scope 안에서만 만든다.

## 4) 4트랙 구조

### A. `feature/protocol-resp`
목표:
- 기존 HTTP를 유지한 채 RESP subset TCP access path를 추가한다.

Allowed files:
- `app/protocol/resp_*`
- `app/main.py`
- `tests/integration/test_protocol_resp.py`
- `tests/smoke/resp_*`

Forbidden files:
- `app/core/*`
- `README.md`
- `.github/workflows/ci.yml`
- `docs/01-product-scope.md`
- `docs/02-architecture.md`
- `docs/03-command-semantics.md`
- `docs/04-development-guide.md`
- `docs/07-team-kickoff-script.md`

Dependent branches:
- `docs/parallel-track-refresh`

Required tests:
- parser / codec unit test
- RESP integration test
- socket smoke
- HTTP regression test

AI prompt template:
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside branch feature/protocol-resp. Keep the existing HTTP contract unchanged, add RESP subset TCP support using the same dispatcher semantics, and stay out of app/core/*. Touch only the allowed files, run the documented RESP and HTTP regression tests, and summarize any remaining protocol limitations.
```

### B. `feature/store-hash-table`
목표:
- public Store API를 유지한 채 custom hash table 기반 저장소를 구현한다.

Allowed files:
- `app/core/hash_table.py`
- `app/core/store.py`
- `tests/unit/test_hash_table.py`
- `tests/unit/test_store_core.py`
- `tests/unit/test_store_expiration.py`

Forbidden files:
- `app/protocol/*`
- `app/main.py`
- `tests/benchmark/*`
- `README.md`
- `.github/workflows/ci.yml`
- `docs/01-product-scope.md`
- `docs/02-architecture.md`
- `docs/03-command-semantics.md`
- `docs/04-development-guide.md`
- `docs/07-team-kickoff-script.md`

Dependent branches:
- `docs/parallel-track-refresh`

Required tests:
- collision
- probing continuity
- tombstone delete
- resize / rehash
- store semantics regression

AI prompt template:
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside branch feature/store-hash-table. Preserve the public Store API and all documented command semantics while replacing the underlying storage with the documented FNV-1a open-addressing hash table. Stay out of protocol, README, benchmark, and CI files. Add only the required hash-table and store regression tests.
```

### C. `feature/store-heap-sweep`
목표:
- lazy expiration은 유지하고, periodic expiration cleanup path를 min-heap 기반으로 최적화한다.

주요 결과물:
- 직접 구현한 hash table 기반 store wrapper
- `GET/SET/DEL`
- `EXPIRE/TTL/PERSIST`
- lazy expiration
- 1초 주기 periodic sweep
- shared `threading.Lock`
Allowed files:
- `app/core/expiration.py`
- `app/core/expiration_heap.py`
- `app/core/store.py`
- `tests/unit/test_expiration_heap.py`
- `tests/unit/test_store_expiration.py`

Forbidden files:
- `app/protocol/*`
- `app/main.py`
- `README.md`
- `.github/workflows/ci.yml`
- `docs/01-product-scope.md`
- `docs/02-architecture.md`
- `docs/03-command-semantics.md`
- `docs/04-development-guide.md`
- `docs/07-team-kickoff-script.md`

Dependent branches:
- `docs/parallel-track-refresh`
- `feature/store-hash-table` merged or used as the parent branch

Required tests:
- heap ordering
- stale heap entry cleanup
- TTL / lazy expiration interaction
- store expiration regression

AI prompt template:
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside branch feature/store-heap-sweep. Start after feature/store-hash-table is merged or branch from it. Keep lazy expiration and the coarse lock model, change only the periodic sweep path to a min-heap design, and do not redefine TTL semantics.
```

### D. `chore/demo-bench-ci-readme`
목표:
- 검증, 데모, benchmark, CI, README 흐름을 발표용으로 정리한다.

Allowed files:
- `tests/benchmark/*`
- `tests/smoke/demo_*`
- `.github/workflows/ci.yml`
- `README.md`

Forbidden files:
- `app/core/*`
- `app/protocol/*`
- `app/main.py`
- `docs/01-product-scope.md`
- `docs/02-architecture.md`
- `docs/03-command-semantics.md`
- `docs/04-development-guide.md`
- `docs/07-team-kickoff-script.md`

Dependent branches:
- `docs/parallel-track-refresh`

Required tests:
- `ruff check .`
- `ruff format --check .`
- `mypy app`
- `pytest`
- benchmark repeatability
- demo smoke

AI prompt template:
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside branch chore/demo-bench-ci-readme. Do not change protocol or store semantics. Improve CI, benchmark repeatability, smoke artifacts, and README demo flow using only the allowed files, then summarize the final verification steps for presenters.
```

## 5) Merge 순서 원칙
- 기준 순서는 `docs/parallel-track-refresh -> feature/store-hash-table -> feature/store-heap-sweep` 이다.
- `feature/protocol-resp`와 `chore/demo-bench-ci-readme`는 refresh 이후 병행 가능하다.
- 병렬 작업 중에도 아래 계약은 문서를 먼저 따른다:
  - command return value
  - RESP request shape
  - TTL semantics
  - error format
  - HTTP endpoint contract
  - Store API contract

## 6) branch-local adapter 원칙
상위 브랜치가 아직 안 합쳐졌다면:
- 최종 contract를 추측하지 않는다.
- branch-local adapter 또는 TODO shim으로 격리한다.
- merge 직전 최신 contract에 맞춘다.
- 특히 `feature/store-heap-sweep`는 hash table 브랜치 결과를 기준으로 움직인다.

## 7) AI에게 맡기기 좋은 단위
- RESP parser 1개
- RESP codec 1개
- hash table 연산 1개
- expiration heap test file 1개
- benchmark helper 1개
- README 섹션 1개

## 8) AI에게 맡기면 안 좋은 단위
- 전체 프로젝트 완성
- protocol + store + benchmark를 한 번에 통합
- 브랜치 범위를 넘는 refactor
- semantics를 다시 설계하게 하기
