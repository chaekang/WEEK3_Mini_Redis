# 05. Codex Collaboration Playbook

이 문서는 사람 설명서라기보다, 팀원 각자의 AI가 **같은 규칙**으로 움직이도록 만드는 실행 가이드다.

주의:
- 요구사항과 설계 충돌 시 `docs/01` ~ `docs/04`를 우선한다.
- 이 문서는 branch-scoped parallel work를 돕는 보조 문서다.

## 1) 시작 순서
각 팀원은 새 작업을 시작할 때 AI에게 아래 순서로 읽게 한다.
1. `AGENTS.md`
2. `docs/01-product-scope.md`
3. `docs/02-architecture.md`
4. `docs/03-command-semantics.md`
5. `docs/04-development-guide.md`
6. `docs/06-testing-playbook.md`
7. 본인 담당 트랙 섹션

## 2) 공통 시작 프롬프트
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside the scope of branch <branch-name>. Before coding, summarize the assigned outcome, allowed files, fixed contracts, out-of-scope items, and required tests. Use the documented FastAPI HTTP contract, store API contract, and coarse-lock concurrency model without redefining them. Then implement only that branch scope, run the relevant checks, and prepare a PR-ready summary.
```

## 3) 공통 작업 원칙
- 한 AI는 한 브랜치의 한 결과만 다룬다.
- 담당 브랜치 범위를 벗어난 파일은 수정하지 않는다.
- 스키마/semantics/process가 바뀌면 관련 docs를 같은 브랜치에서 업데이트한다.
- PR 전에는 `main` 최신 내용이 반영됐는지 확인한다.
- 충돌이 나면 기능을 밀어붙이지 말고 먼저 rebase / merge 후 다시 확인한다.
- 테스트는 `docs/06` 기준으로 branch scope 안에서만 만든다.
- FastAPI, REST-like endpoint, store API, `threading.Lock` 기반 coarse lock은 재설계하지 않는다.

## 4) 4인 트랙 구조

### A. `feature/contracts-foundation`
목표:
- core contract 고정

주요 결과물:
- `docs/03-command-semantics.md` 유지/보완
- command registry shape
- shared error definitions
- core interfaces
- folder skeleton

허용 파일 예시:
- `docs/03-command-semantics.md`
- `app/commands/registry.*`
- `app/commands/errors.*`
- `app/commands/dispatcher.*`
- `app/core/interfaces.*`

금지:
- protocol 구현 전체 떠안기
- store 로직까지 과도하게 확장

### B. `feature/protocol-network`
목표:
- 외부 진입점 구현

주요 결과물:
- FastAPI route
- request parser / serializer
- route schema
- Python smoke script

허용 파일 예시:
- `app/protocol/*`
- `app/main.*`
- `tests/integration/test_protocol_*`
- `tests/smoke/*.py`

금지:
- store semantics 임의 변경
- endpoint contract 임의 재정의

### C. `feature/store-expiration`
목표:
- 핵심 저장소와 TTL 로직 구현

주요 결과물:
- `dict` 기반 store wrapper
- `GET/SET/DEL`
- `EXPIRE/TTL/PERSIST`
- lazy expiration
- 1초 주기 periodic sweep
- shared `threading.Lock`

허용 파일 예시:
- `app/core/*`
- `tests/unit/test_store_*`
- `tests/unit/test_expiration_*`

금지:
- protocol 응답 형식 임의 변경
- FastAPI route 설계 임의 변경

### D. `feature/persistence-tests-bench`
목표:
- 회복력 대비 구조 준비, 검증, 데모 포장

주요 결과물:
- `app/persistence/` 구조 유지
- benchmark script
- README 데모 시나리오
- smoke / benchmark test 정리

허용 파일 예시:
- `app/persistence/*`
- `tests/smoke/*`
- `tests/benchmark/*`
- `README.md`

금지:
- 핵심 semantics 재정의
- AOF-lite를 현재 MVP 필수 기능처럼 가정하기

## 5) merge 순서 원칙
- 가장 이상적인 순서는 A -> C -> B -> D
- 하지만 완전한 직렬 순서를 강요하지는 않는다.
- 다만 아래 계약은 문서를 먼저 따른다:
  - command return value
  - TTL semantics
  - error format
  - replay semantics
  - HTTP endpoint contract
  - Store API contract

## 6) branch-local adapter 원칙
상위 브랜치가 아직 안 합쳐졌다면:
- 최종 계약을 추측하지 않는다.
- branch-local adapter 또는 TODO shim으로 격리한다.
- 머지 직전 최신 contract에 맞춘다.

## 7) AI에게 맡기기 좋은 단위
- FastAPI route 1종
- command handler 1~2개
- test file 1개
- README 섹션 1개
- benchmark script 1개

## 8) AI에게 맡기면 안 좋은 단위
- 전체 프로젝트 완성
- protocol + store + persistence를 한 번에 통합
- 브랜치 범위를 넘는 refactor
- semantics를 다시 설계하게 하기
