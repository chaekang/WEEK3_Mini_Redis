# 07. Team Kickoff Script

이 문서는 킥오프에서 10~15분 동안 팀에 그대로 말할 수 있는 진행 스크립트다.

## 0) 시작 멘트

```text
이번 목표는 Redis 전체를 복사하는 게 아니라, Redis-like key-value server의 핵심 경험을 안정적으로 보여주는 거야.
우리는 먼저 공부 모드로 길게 들어가지 않고, command semantics와 역할 분담을 먼저 고정하고 바로 구현 들어갈게.
```

## 1) 범위 고정

```text
우리 필수 범위는 string key/value, PING, GET, SET, DEL, EXPIRE, TTL, PERSIST야.
외부 인터페이스는 HTTP + JSON으로 고정할게.
Stretch는 INCR, MGET/MSET, AOF-lite까지고, list/pubsub/replication은 안 해.
```

체크 질문:
- AOF-lite 넣을지?
- INCR까지 넣을지?

## 2) 핵심 계약 고정

```text
문서 기준으로 GET missing, TTL 반환값, SET이 TTL을 지우는지, DEL 반환값은 여기서 고정하자.
이건 코드보다 문서가 우선이야. 중간에 흔들리면 테스트도 다 흔들린다.
```

고정 항목:
- GET missing 응답
- SET overwrite 시 TTL 제거
- DEL 반환 규칙
- EXPIRE / TTL / PERSIST semantics
- protocol error 형식

## 3) 역할 분담 멘트

```text
A는 contracts/foundation 맡아서 command semantics, registry, core interfaces를 잡아줘.
B는 protocol/network 맡아서 HTTP entrypoint랑 smoke 클라이언트를 잡아줘.
C는 store/expiration 맡아서 hash table, GET/SET/DEL, EXPIRE/TTL/PERSIST를 맡아줘.
D는 persistence/tests/bench/readme 맡아서 AOF-lite, 테스트 하네스, benchmark, README 데모 정리 맡아줘.
```

## 4) 협업 규칙 멘트

```text
각자 자기 브랜치 밖 파일은 건드리지 말고, semantics 바꾸고 싶으면 코드보다 문서를 먼저 수정하자.
텍스트 conflict는 무서워하지 말고, core semantics conflict는 바로 멈추고 같이 맞추자.
머지는 테스트 통과 후에만 한다.
```

## 5) AI 사용 규칙 멘트

```text
AI에는 한 번에 한 결과만 시키자.
항상 allowed files, fixed contracts, out-of-scope를 먼저 요약하게 하고 구현시켜.
AI가 만든 테스트와 코드가 문서 semantics를 어기지 않는지는 사람이 본다.
```

## 6) 초기 구현 체크포인트

```text
초기 구현 단계에서는 skeleton, 필수 command core, protocol entrypoint, 테스트 scaffold까지 나와 있어야 해.
만약 여기서 밀리면 stretch는 바로 포기하고 필수 데모 안정화로 전환하자.
```

## 7) 기능 연결 체크포인트
- 필수 명령 end-to-end 연결 완료
- TTL 데모 완료
- smoke 체크리스트 통과
- README 데모 시나리오 작성

## 8) 데모 직전 체크 멘트

```text
데모 직전에는 새 기능 추가하지 말고, README 순서대로만 데모하자.
명령 의미론, coarse lock 기반 동시성 전략, 만료 처리, 테스트 전략 이 네 개는 누구든 설명 가능하게 맞춰두자.
```

## 9) 상황별 의사결정 규칙

### 시간이 모자랄 때
- HTTP만 유지
- AOF-lite 포기
- INCR / MGET / MSET 포기
- benchmark는 간단한 time measurement만

### 예상보다 잘 될 때
- RESP subset 추가
- INCR 추가
- AOF-lite 추가
- benchmark 결과 표 정리

## 10) 마지막 확인 질문
- 우리가 안 하는 것까지 명확한가?
- 테스트 없는 핵심 로직이 남아 있지 않은가?
- README만 읽어도 데모 흐름이 보이는가?
- 팀원 각자가 자기 브랜치 결과를 30초 설명할 수 있는가?
