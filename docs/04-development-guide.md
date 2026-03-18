# 04. Development Guide

## 구현 시작 전 확정 항목
1. 문서 refresh 초안 확정
2. MVP / Stretch 범위 확정
3. 동시성 모델 확정 (`store-level coarse lock`)
4. 역할 분담 초안 확정
5. 브랜치 전략 확정
6. 테스트 계층 확정
7. 기술 스택 확정

## 구현 원칙
- 먼저 문서, 다음 코드
- 먼저 semantics, 다음 implementation
- 먼저 branch scope, 다음 AI prompt
- HTTP는 유지하고 RESP는 추가한다.
- 먼저 자동 테스트, 다음 데모 polish

## 현재 확정 기술 스택

### 런타임 / 서버
- Python
- FastAPI for HTTP
- RESP subset TCP server

### 테스트
- `pytest`
- `pytest-cov`
- `pytest-mock`
- `time-machine`
- `httpx`

### 정적 검증
- `ruff` for lint + format
- `mypy` for type check

### 권장 실행 명령
- lint: `ruff check .`
- format check: `ruff format --check .`
- type check: `mypy app`
- test: `pytest`
- coverage: `pytest --cov=app --cov-report=term-missing`

## 브랜치 전략

### 공용 문서 refresh 브랜치
- `docs/parallel-track-refresh`

### 활성 기능 브랜치
- `feature/store-hash-table`
- `feature/store-heap-sweep`
- `feature/protocol-resp`
- `chore/demo-bench-ci-readme`

### 기타 유지 브랜치
- `docs/*`
- `fix/*`
- `test/*`

## 기본 작업 순서
1. `main`에서 최신 pull
2. 자기 브랜치 생성
3. `AGENTS.md`, `docs/01` through `docs/06`, 그리고 자기 브랜치 섹션 재확인
4. branch scope 밖 파일 수정 금지
5. 관련 테스트 추가 또는 갱신
6. 로컬 체크
7. PR 생성
8. 리뷰 후 merge

## Merge 순서
1. `docs/parallel-track-refresh`
2. `feature/store-hash-table`
3. `feature/store-heap-sweep`
4. `feature/protocol-resp`와 `chore/demo-bench-ci-readme`는 refresh 이후 병행 가능

주의:
- `feature/store-heap-sweep`는 `feature/store-hash-table` merge 이후에 시작하거나, 그 브랜치 위에서 파생한다.
- `feature/protocol-resp`는 store internals를 재설계하지 않는다.
- `chore/demo-bench-ci-readme`는 core semantics를 바꾸지 않는다.

## Shared Hotspot Ownership
- `app/main.py`: `feature/protocol-resp` 전담
- `app/core/store.py`: `feature/store-hash-table` 선행 소유, `feature/store-heap-sweep`는 hash merge 이후에만 수정
- `README.md`, `.github/workflows/ci.yml`, `tests/benchmark/*`: `chore/demo-bench-ci-readme` 전담

## 문서 수정 규칙
- `docs/parallel-track-refresh` 브랜치에서 `AGENTS.md`와 `docs/01` through `docs/07`을 한 번에 정리한다.
- 이후 기능 브랜치는 그 문서를 구현 대상으로 삼는다.
- 기능 브랜치는 원칙적으로 shared contract docs `docs/01` through `docs/04`, `docs/07`을 다시 수정하지 않는다.
- shared contract가 정말 바뀌어야 하면 별도 `docs/*` 브랜치로 먼저 합의한다.
- branch-local 노트가 꼭 필요할 때만 `docs/05`, `docs/06`의 자기 섹션 안에서 최소 수정한다.

## 문서 업데이트 매핑
- 명령 의미 자체 변경 -> 별도 `docs/*` 브랜치에서 `docs/03-command-semantics.md`
- 구조 변경 -> 별도 `docs/*` 브랜치에서 `docs/02-architecture.md`
- 프로세스 / merge rule 변경 -> 별도 `docs/*` 브랜치에서 `docs/04` 또는 `docs/05`
- 검증 방식 변경 -> `docs/06-testing-playbook.md`
- 발표 흐름 변경 -> `README.md` 또는 `docs/07-team-kickoff-script.md`

## 구현 우선순위

### P0 - 구현 전에 무조건 결정
- dual external interface: HTTP + RESP
- FastAPI 유지
- RESP 요청 범위: bulk array only
- 필수 명령 목록
- custom hash table 전략
- min-heap sweep 전략
- expiration rules
- 동시성 모델: store-level coarse lock
- branch ownership
- 테스트 최소선
- 정적 검증 및 테스트 도구

### P1 - 초기 구현 단계
- shared docs refresh
- custom hash table skeleton
- store semantics regression 보존
- 필수 test scaffold

### P2 - 기능 연결 단계
- heap-based expiration sweep 연결
- RESP parser / codec / server 연결
- HTTP regression 확인

### P3 - 데모 마감 단계
- benchmark / smoke / CI 정리
- README 데모 정리

### P4 - 추후 확장
- AOF-lite
- stretch 명령

## AOF-lite에 대한 현재 결정
- `app/persistence/` 구조는 유지한다.
- 그러나 현재 활성 병렬 트랙에서는 AOF-lite를 구현하지 않는다.
- replay, recovery test, append format은 후속 범위가 열릴 때 별도 브랜치에서 다룬다.

## 충돌 처리 규칙
- 텍스트 conflict 자체는 두려워하지 않는다.
- 대신 **core semantics conflict**는 즉시 멈추고 문서부터 다시 확인한다.
- 다음 항목은 구현 브랜치보다 문서가 우선한다:
  - command semantics
  - RESP request shape
  - HTTP error format
  - TTL rules
  - concurrency model
  - HTTP endpoint contract
  - Store API contract

## AI 사용 원칙
- 한 AI 프롬프트는 한 결과만 요청한다.
- 구현 전 반드시 “allowed files / fixed contracts / out-of-scope / required tests”를 요약하게 한다.
- AI가 만든 테스트는 사람이 시나리오 관점에서 검토한다.
- AI가 command semantics를 임의로 바꾸지 못하게 한다.
- HTTP contract, RESP request shape, store API, lock 정책은 문서 합의 없이 바꾸지 않는다.

## 권장 브랜치별 초점

### `feature/store-hash-table`
- custom hash table 구현
- store wrapper 연결
- 기존 command semantics 보존

### `feature/store-heap-sweep`
- expiration heap
- lazy expiration + periodic sweep 상호작용
- coarse lock 유지

### `feature/protocol-resp`
- RESP parser / codec / server
- `app/main.py` wiring
- HTTP regression 유지

### `chore/demo-bench-ci-readme`
- benchmark script
- smoke demo artifacts
- README / CI polish

## Merge 기준
- 자동 테스트 통과
- branch scope smoke 완료
- 관련 docs 업데이트 여부 확인
- PR 본문에 `변경점 / 테스트 / 수동 확인 / known limitation` 기재

## PR 템플릿 예시
```text
## What changed
- 

## Why
- 

## Tests
- automated:
- manual smoke:

## Docs updated
- 

## Known limitations
- 
```
