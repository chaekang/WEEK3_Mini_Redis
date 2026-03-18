# Mini Redis

`Mini Redis`는 문서로 고정한 command semantics를 기준으로, Redis-like key-value 서버의 핵심 경험을 짧고 안정적으로 보여주기 위한 프로젝트입니다.

## MVP
- string key / string value
- `PING`, `GET`, `SET`, `DEL`, `EXPIRE`, `TTL`, `PERSIST`
- HTTP + JSON external interface
- lazy expiration + periodic sweep
- branch-scoped automated tests + manual smoke

## This Branch Adds
- `app/persistence/*`의 isolated AOF-lite writer / replay helper
- `tests/unit/test_persistence_aof.py`의 persistence 자동 테스트
- `tests/benchmark/*`의 benchmark helper, benchmark test, demo script
- `tests/smoke/http_demo.py`의 client-only HTTP smoke artifact

## Persistence Status
- 구현됨: JSON Lines 기반 `SET`, `DEL`, `EXPIRE`, `PERSIST` append / replay helper
- 아직 미연결: `app/main.py` startup replay, dispatcher/store wiring
- 현재 브랜치에서는 recovery를 isolated callback replay 수준까지만 검증한다.

## Demo Flow
1. protocol/store 브랜치가 병합된 서버를 실행한다.
2. HTTP smoke를 실행한다.
   `python tests/smoke/http_demo.py --base-url http://127.0.0.1:8000`
3. benchmark harness를 실행한다.
   `python tests/benchmark/run_benchmark_demo.py`
4. persistence wiring이 병합된 뒤에는 startup replay recovery smoke를 추가로 확인한다.

## Validation
- Automated:
  `pytest tests/unit/test_persistence_aof.py tests/benchmark/test_benchmark_helper.py`
- Static:
  `ruff check .`
  `mypy app`
- Manual smoke:
  `python tests/smoke/http_demo.py --base-url http://127.0.0.1:8000`
  `python tests/benchmark/run_benchmark_demo.py`

## Known Limitations
- core semantics와 HTTP contract는 이 브랜치에서 재정의하지 않는다.
- end-to-end AOF recovery wiring은 아직 없다.
- benchmark demo는 upstream integration 전까지 simulated cache path를 사용한다.

## Docs
- [작업 규칙](AGENTS.md)
- [제품 범위](docs/01-product-scope.md)
- [아키텍처](docs/02-architecture.md)
- [명령 의미론](docs/03-command-semantics.md)
- [개발 가이드](docs/04-development-guide.md)
- [협업 플레이북](docs/05-codex-collaboration-playbook.md)
- [테스트 플레이북](docs/06-testing-playbook.md)
- [팀 킥오프 스크립트](docs/07-team-kickoff-script.md)
