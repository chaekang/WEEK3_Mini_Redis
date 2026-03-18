# Mini Redis

`Mini Redis`는 해시 테이블 기반의 경량 in-memory key-value 저장소를 직접 구현해, Redis의 핵심 개념인 **빠른 조회**, **TTL 만료**, **외부 접근 가능한 인터페이스**, **기초적인 안정성 검증**을 보여주는 발표용 프로젝트입니다.

## 프로젝트 한 줄 소개
- 문자열 key / value 저장소를 해시 테이블로 직접 구현하고, TTL과 간단한 persistence를 얹은 Redis-like 서버

## 이번 프로젝트에서 복사하려는 Redis 핵심
- `GET`, `SET`, `DEL` 같은 문자열 기반 key-value 조작
- `EXPIRE`, `TTL`, `PERSIST`를 통한 만료 관리
- 외부 클라이언트가 접근 가능한 서버 인터페이스
- 테스트 가능한 명령 의미론과 간단한 recovery 흐름

## MVP 범위
- string key / string value
- `PING`, `GET`, `SET`, `DEL`
- `EXPIRE`, `TTL`, `PERSIST`
- HTTP + JSON external interface
- lazy expiration + periodic expiration sweep
- store-level coarse lock 기반 안전한 요청 처리
- 단위 테스트, 통합 테스트, 수동 smoke test

## Stretch 범위
- `INCR`
- `MGET`, `MSET`
- AOF-lite
- RESP subset TCP 서버
- 간단한 benchmark

## 하지 않는 것
- Redis 전체 호환
- list / set / hash / zset
- pub/sub
- replication / cluster
- eviction policy
- production-grade persistence

## 데모 시나리오
1. 서버를 실행한다.
2. `PING` 요청으로 서버 생존을 확인한다.
3. `SET user:1 hello` 후 `GET user:1`로 저장/조회 동작을 확인한다.
4. `EXPIRE user:1 2` 후 `TTL user:1`의 감소를 확인한다.
5. 2초 뒤 `GET user:1`이 miss를 반환하는지 확인한다.
6. `PERSIST` 또는 AOF-lite가 구현되었다면 재시작 후 복구 여부를 확인한다.
7. 느린 API 호출에 캐시를 붙인 전후 시간을 비교한다.

## 아키텍처 요약
- **Protocol Layer**: HTTP request parsing + JSON serialization
- **Command Layer**: 명령 검증, dispatch, 공통 에러 응답
- **Store Layer**: hash table, TTL metadata, 삭제/조회/갱신 로직
- **Persistence Layer**: append-only log replay (선택)
- **Test Layer**: unit / integration / smoke / recovery / benchmark

## 추천 디렉토리 구조
```text
.
├── AGENTS.md
├── README.md
├── docs/
│   ├── 01-product-scope.md
│   ├── 02-architecture.md
│   ├── 03-command-semantics.md
│   ├── 04-development-guide.md
│   ├── 05-codex-collaboration-playbook.md
│   ├── 06-testing-playbook.md
│   └── 07-team-kickoff-script.md
├── app/
│   ├── protocol/
│   ├── commands/
│   ├── core/
│   └── persistence/
└── tests/
    ├── unit/
    ├── integration/
    ├── smoke/
    └── benchmark/
```

## 실행 예시
프로젝트 언어와 프레임워크가 정해지면 여기 명령을 확정한다.

예시(Python 기준):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
python -m app.main
```

## 검증
- 자동 검증: unit / integration / recovery test
- 수동 검증: smoke demo, benchmark demo
- PR merge 조건: required checks 통과 + 담당 범위 smoke 확인

## Known Limitations
- Redis 전체 프로토콜 및 명령을 지원하지 않는다.
- 고성능 최적화보다는 명령 의미론의 명확성과 데모 안정성에 집중한다.
- persistence는 선택 기능이며 구현 수준에 따라 durability가 제한적일 수 있다.

## 문서 목록
- [작업 규칙](AGENTS.md)
- [제품 범위](./docs/01-product-scope.md)
- [아키텍처](./docs/02-architecture.md)
- [명령 의미론](./docs/03-command-semantics.md)
- [개발 가이드](./docs/04-development-guide.md)
- [협업 플레이북](./docs/05-codex-collaboration-playbook.md)
- [테스트 플레이북](./docs/06-testing-playbook.md)
- [팀 킥오프 스크립트](./docs/07-team-kickoff-script.md)
