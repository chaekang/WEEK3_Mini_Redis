# 06. Testing Playbook

이 문서는 팀원과 AI가 테스트를 **같은 기준**으로 만들고, PR 전에 무엇까지 검증해야 하는지 빠르게 이해하도록 돕는 실행 가이드다.

## 1) 테스트 계층
이 프로젝트는 테스트를 아래 5단계로 나눈다.

1. **정적 검증**
   - `ruff check .`
   - `ruff format --check .`
   - `mypy app`

2. **브랜치 단위 자동 테스트**
   - 해당 브랜치가 책임지는 unit / integration test

3. **브랜치 단위 수동 smoke test**
   - 담당 기능의 핵심 시나리오 짧게 점검

4. **통합 수동 테스트**
   - 데모 전 전체 명령 흐름 점검

5. **benchmark 검증**
   - 발표용 비교 시나리오 확인

주의:
- 현재 활성 병렬 트랙 기준으로 recovery / AOF replay는 필수 테스트가 아니다.
- protocol 또는 store 최적화가 semantics를 바꾸면 안 된다.

## 2) 테스트 도구
- test runner: `pytest`
- coverage: `pytest-cov`
- mocking: `pytest-mock`
- time control: `time-machine`
- HTTP client test: `httpx`

권장 명령:
- `pytest`
- `pytest --cov=app --cov-report=term-missing`

## 3) 브랜치별 테스트 생성 원칙
- 한 브랜치는 자기 책임 범위에 대한 테스트만 추가한다.
- 다른 브랜치의 미완성 기능을 위해 테스트를 억지로 만들지 않는다.
- snapshot보다 입력/출력과 행동 검증을 우선한다.
- 외부 시스템은 mock 하되, branch 핵심 로직은 가능한 실제 로직으로 검증한다.
- 테스트 파일은 기능과 같은 경계에 둔다.
- smoke test는 transport에 맞는 실제 client 형태를 사용한다.
- RESP 추가가 HTTP regression을 깨뜨리지 않는지 반드시 확인한다.

## 4) 브랜치별 테스트 책임

### A. `feature/protocol-resp`
자동 테스트 우선순위:
- RESP parser unit test
- RESP codec unit test
- RESP integration test
- same-dispatcher semantics regression
- HTTP regression test

수동 smoke:
- RESP로 `PING`, `SET`, `GET`, `TTL` 호출
- malformed RESP frame이 simple error로 실패하는지 확인
- 기존 HTTP smoke가 그대로 동작하는지 확인

### B. `feature/store-hash-table`
자동 테스트 우선순위:
- collision handling
- linear probing continuity
- tombstone delete
- resize / rehash
- `GET`, `SET`, `DEL`, `EXPIRE`, `TTL`, `PERSIST` semantics regression
- overwrite 시 TTL 제거 유지

수동 smoke:
- store-level 시나리오에서 기존 명령 의미론이 바뀌지 않았는지 확인

### C. `feature/store-heap-sweep`
자동 테스트 우선순위:
- heap ordering
- stale heap entry cleanup
- TTL / lazy expiration interaction
- periodic sweep cleanup path
- store expiration regression

수동 smoke:
- TTL이 감소하는지
- 만료 후 조회가 miss인지
- lazy expiration과 sweep가 같은 결과를 내는지 확인

### D. `chore/demo-bench-ci-readme`
자동 테스트 우선순위:
- `ruff check .`
- `ruff format --check .`
- `mypy app`
- `pytest`
- benchmark helper correctness
- benchmark repeatability

수동 smoke:
- 발표 순서 기준 demo smoke
- HTTP / RESP 데모 흐름이 README와 일치하는지 확인
- benchmark 시나리오가 짧고 반복 가능한지 확인

## 5) 테스트 작성 순서
1. 현재 브랜치가 책임지는 엔티티 / 명령 / API를 다시 확인한다.
2. 실패했을 때 merge를 막아야 하는 핵심 규칙 3~5개를 먼저 고른다.
3. 그 규칙에 대한 자동 테스트를 먼저 추가한다.
4. 자동화가 어려운 것은 수동 체크리스트로 남긴다.
5. 다른 브랜치 의존 테스트는 `현재 범위 밖`으로 명시한다.

## 6) 권장 테스트 목록

### unit test
- RESP bulk-array parsing
- RESP serializer type mapping
- hash collision resolution
- tombstone reuse
- TTL remove on `SET`
- `PERSIST` success / failure
- expired key access returns miss semantics
- stale heap entry skip logic

### integration test
- client -> protocol layer -> dispatcher -> store 흐름
- malformed command
- malformed RESP request
- expired key access
- multi-command flow
- HTTP regression after RESP wiring

### smoke test
- `GET /v1/ping`
- `PUT /v1/keys/a` with `{ "value": "1" }`
- `GET /v1/keys/a`
- RESP `PING`
- RESP `SET a 1`
- RESP `GET a`
- `POST /v1/keys/a/expire` with `{ "seconds": 1 }`
- 1초 후 HTTP 또는 RESP에서 `GET a` miss

### benchmark test
- demo benchmark helper correctness
- benchmark repeatability over short runs
- 발표용 상대 비교 흐름이 재현되는지 확인

## 7) smoke script 원칙
- smoke는 branch에 맞는 실제 client로 작성한다.
- HTTP smoke는 `httpx`를 사용한다.
- RESP smoke는 raw socket 또는 동등한 client path를 사용한다.
- 스크립트는 데모 순서를 그대로 따라가야 한다.
- 실패 시 어느 단계에서 깨졌는지 바로 알 수 있는 메시지를 출력한다.

## 8) benchmark 원칙
- benchmark는 절대 수치보다 상대 비교를 보여주는 데 목적이 있다.
- 발표용 벤치는 짧고 반복 가능해야 한다.
- core semantics를 바꾸는 최적화는 benchmark 이유로 허용하지 않는다.

## 9) 사람이 해야 하는 것
AI가 기본적으로 도와줄 수 있는 것:
- unit / integration test 초안 생성
- RESP smoke script 초안 생성
- benchmark script 초안 생성
- 수동 smoke checklist 정리

사람이 직접 확인해야 하는 것:
- 실제 데모 체감
- 응답 메시지의 자연스러움
- 전체 흐름 이해 가능성
- 발표 중 설명 가능성

## 10) AI 테스트 프롬프트 예시

### 자동 테스트 생성용
```text
Read AGENTS.md and docs/01 through docs/06. Work only inside branch <branch-name>. Generate only the tests that belong to this branch scope. Follow the documented HTTP contract, RESP request rules, Store API contract, and coarse-lock model. Prefer blocking business rules and command behavior over broad snapshots. At the end, summarize what was tested automatically and what still requires manual verification.
```

### PR 직전 검증용
```text
Read AGENTS.md and docs/01 through docs/06. Review this branch from a testing perspective only. List missing automated tests first, then list manual smoke checks that still need to be run. Do not suggest tests outside this branch scope unless they block merge safety.
```

## 11) 최소 CI 기준
- PR마다 아래 검증을 실행한다.
  - `ruff check .`
  - `ruff format --check .`
  - `mypy app`
  - `pytest`
- 실패 시 merge 금지
- smoke는 수동 체크리스트 또는 smoke script 실행 결과로 PR 본문에 기록
