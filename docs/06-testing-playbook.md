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
   - 성능 비교 시나리오 확인

주의:
- AOF recovery / replay는 persistence 범위에서 필수 검증 항목이다.
- TTL 관련 recovery 검증은 상대 `seconds`가 아니라 절대 만료 시각 `expires_at` 기준으로 확인한다.

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
- smoke test는 Python 스크립트로 작성한다.

## 4) 브랜치별 테스트 책임

### A. `feature/contracts-foundation`
자동 테스트 우선순위:
- command arity validation
- error mapping unit test
- registry dispatch test

수동 smoke:
- 잘못된 명령이 에러로 응답되는지 확인
- command 이름과 문서가 일치하는지 확인

### B. `feature/protocol-network`
자동 테스트 우선순위:
- FastAPI route input/output test
- serializer response test
- `httpx` 기반 request/response integration test

수동 smoke:
- Python smoke script로 `PING`, `SET`, `GET` 호출
- malformed request가 안전하게 실패하는지 확인

### C. `feature/store-expiration`
자동 테스트 우선순위:
- hash table 기반 store put/get/delete
- overwrite behavior
- `SET`이 TTL 제거하는지
- `EXPIRE`, `TTL`, `PERSIST`
- 절대 만료 시각 저장/계산
- lazy expiration
- 1초 주기 periodic sweep
- coarse lock 하에서 상태 일관성이 유지되는지

수동 smoke:
- TTL이 감소하는지
- 만료 후 조회가 miss인지

### D. `feature/persistence-tests-bench`
자동 테스트 우선순위:
- startup replay recovery
- malformed AOF startup failure
- replay 중 file growth 없음
- expired-at-replay key가 다시 살아나지 않음
- benchmark helper correctness test
- 미니 Redis 미사용 시나리오와 사용 시나리오 비교 검증

수동 smoke:
- 캐시 미사용 경로가 동작하는지 확인
- 미니 Redis 캐시 사용 경로가 더 빠르게 응답하는지 확인

주의:
- recovery 테스트는 AOF always-on 가정을 따른다.
- TTL recovery는 `EXPIRE key seconds` 재실행이 아니라 AOF의 절대 만료 시각 `expires_at` 복원 규칙을 검증해야 한다.

## 5) 테스트 작성 순서
1. 현재 브랜치가 책임지는 엔티티/명령/API를 다시 확인한다.
2. 실패했을 때 merge를 막아야 하는 핵심 규칙 3~5개를 먼저 고른다.
3. 그 규칙에 대한 자동 테스트를 먼저 추가한다.
4. 자동화가 어려운 것은 수동 체크리스트로 남긴다.
5. 다른 브랜치 의존 테스트는 `현재 범위 밖`으로 명시한다.

## 6) 권장 테스트 목록

### unit test
- missing key read
- overwrite
- TTL remove on SET
- PERSIST success / failure
- expired key access returns miss semantics
- concurrent `GET` / `SET` / `EXPIRE` access safety under coarse lock

### integration test
- client -> FastAPI route -> dispatcher -> store 흐름
- malformed command
- expired key access
- multi-command flow

### smoke test
- `GET /v1/ping`
- `PUT /v1/keys/a` with `{ "value": "1" }`
- `GET /v1/keys/a`
- `POST /v1/keys/a/expire` with `{ "seconds": 1 }`
- 1초 후 `GET /v1/keys/a` miss
- `DELETE /v1/keys/a/expiration`

### benchmark test
- 미니 Redis 서버 없는 경우의 응답 시간
- 미니 Redis 서버를 써서 캐싱한 경우의 응답 시간

## 7) smoke script 원칙
- smoke는 Python 스크립트로 작성한다.
- `httpx`를 사용해 실제 HTTP endpoint를 호출한다.
- 스크립트는 데모 순서를 그대로 따라가야 한다.
- 실패 시 어느 단계에서 깨졌는지 바로 알 수 있는 메시지를 출력한다.

## 8) benchmark 원칙
- 비교 대상은 아래 2개로 고정한다.
  - 미니 Redis 서버 없이 처리하는 경우
  - 미니 Redis 서버를 캐시로 사용해 더 빠르게 처리하는 경우
- benchmark는 절대 수치보다 상대 비교를 보여주는 데 목적이 있다.
- 발표용 벤치는 짧고 반복 가능해야 한다.

## 9) 사람이 해야 하는 것
AI가 기본적으로 도와줄 수 있는 것:
- unit / integration test 초안 생성
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
Read AGENTS.md and docs/01 through docs/06. Work only inside branch <branch-name>. Generate only the tests that belong to this branch scope. Follow the documented FastAPI endpoint contract, store API contract, and coarse-lock model. Prefer blocking business rules and command behavior over broad snapshots. At the end, summarize what was tested automatically and what still requires manual verification.
```

### PR 직전 검증용
```text
Read AGENTS.md and docs/01 through docs/06. Review this branch from a testing perspective only. List missing automated tests first, then list manual smoke checks that still need to be run. Do not suggest tests outside this branch scope unless they block merge safety.
```

## 11) 최소 CI 기준
- PR마다 자동 테스트 실행
- 실패 시 merge 금지
- smoke는 수동 체크리스트 또는 Python smoke script 실행 결과로 PR 본문에 기록
