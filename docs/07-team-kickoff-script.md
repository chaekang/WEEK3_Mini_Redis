# 07. Team Kickoff Script

이 문서는 킥오프에서 10~15분 동안 팀에 그대로 말할 수 있는 진행 스크립트다.

## 0) 시작 멘트

```text
이번 목표는 Redis 전체를 복사하는 게 아니라, Redis-like key-value server의 핵심 경험을 안정적으로 보여주는 거야.
우리는 먼저 길게 재설계하지 않고, shared docs를 한 번 정리하고 그 계약대로 병렬 구현에 들어갈게.
```

## 1) 범위 고정

```text
우리 필수 범위는 string key/value, PING, GET, SET, DEL, EXPIRE, TTL, PERSIST야.
HTTP + JSON은 그대로 유지하고, RESP subset TCP 접근도 추가할게.
AOF-lite는 이번 활성 트랙에서는 빼고 follow-up으로 남길게.
```

체크 질문:
- HTTP 유지 + RESP 추가 방향이 모두에게 명확한가?
- AOF-lite를 이번 활성 트랙에서 제외하는 데 동의하는가?

## 2) 핵심 계약 고정

```text
문서 기준으로 GET miss, TTL 반환값, SET이 TTL을 지우는지, DEL 반환값, RESP 요청 형식은 여기서 고정하자.
이건 코드보다 문서가 우선이야. 중간에 흔들리면 테스트랑 병렬 작업이 다 흔들린다.
```

고정 항목:
- GET miss 응답
- SET overwrite 시 TTL 제거
- DEL 반환 규칙
- EXPIRE / TTL / PERSIST semantics
- RESP request는 bulk-array-only
- protocol error / command error 직렬화 원칙
- hash table 전략
- heap sweep 전략

## 3) shared docs 운영 규칙

```text
먼저 docs/parallel-track-refresh 브랜치에서 AGENTS랑 docs/01~07을 한 번에 정리할게.
그 브랜치가 머지된 뒤에는 기능 브랜치가 shared contract docs를 다시 흔들지 말고, 자기 코드와 자기 테스트에 집중하자.
공용 계약이 정말 바뀌면 기능 브랜치에서 우회하지 말고 docs 브랜치를 따로 열자.
```

## 4) 역할 분담 멘트

```text
한 트랙은 protocol-resp 맡아서 HTTP는 유지하고 RESP entrypoint랑 main wiring을 잡아줘.
한 트랙은 store-hash-table 맡아서 custom hash table이랑 store 연결을 잡아줘.
한 트랙은 store-heap-sweep 맡아서 lazy expiration은 유지하고 min-heap 기반 sweep 최적화를 맡아줘.
한 트랙은 demo-bench-ci-readme 맡아서 CI, benchmark, smoke, README 발표 흐름을 정리해줘.
```

## 5) 협업 규칙 멘트

```text
각자 자기 브랜치 밖 hotspot 파일은 건드리지 말고, semantics 바꾸고 싶으면 코드보다 문서를 먼저 보자.
HTTP는 유지하고 RESP는 추가하는 거지, 기존 HTTP를 깨는 작업이 아니야.
머지는 테스트 통과 후에만 하고, heap sweep 브랜치는 hash table 브랜치 위에서 움직이자.
```

## 6) AI 사용 규칙 멘트

```text
AI에는 한 번에 한 결과만 시키자.
항상 allowed files, fixed contracts, dependent branches, required tests를 먼저 요약하게 하고 구현시켜.
AI가 만든 테스트와 코드가 문서 semantics를 어기지 않는지는 사람이 본다.
```

## 7) 초기 구현 체크포인트

```text
초기 단계에서는 shared docs refresh, custom hash table skeleton, TTL 의미론 유지, RESP parser/codec 범위가 먼저 정리돼 있어야 해.
여기서 밀리면 AOF나 추가 stretch는 바로 뒤로 미루고 필수 동작 안정화로 전환하자.
```

## 8) 기능 연결 체크포인트
- 필수 명령 end-to-end 연결 완료
- HTTP regression 유지
- RESP 기본 흐름 확인
- TTL 데모 완료
- benchmark / smoke 체크리스트 초안 완료
- README 데모 시나리오 작성

## 9) 데모 직전 체크 멘트

```text
데모 직전에는 새 기능 추가하지 말고, README 순서대로만 데모하자.
명령 의미론, hash table 전략, coarse lock 기반 동시성, expiration 처리, HTTP와 RESP의 관계 이 다섯 개는 누구든 설명 가능하게 맞춰두자.
```

## 10) 상황별 의사결정 규칙

### 시간이 모자랄 때
- HTTP는 반드시 유지
- RESP는 문서화한 subset과 필수 명령 위주로 마감
- AOF-lite는 포기
- stretch 명령은 포기
- benchmark는 짧고 반복 가능한 형태만 유지

### 예상보다 잘 될 때
- RESP smoke 고도화
- INCR 추가
- MGET / MSET 추가
- benchmark 결과 표 정리
- AOF-lite follow-up 브랜치 계획 수립

## 11) 마지막 확인 질문
- 우리가 안 하는 것까지 명확한가?
- 테스트 없는 핵심 로직이 남아 있지 않은가?
- README만 읽어도 데모 흐름이 보이는가?
- 팀원 각자가 자기 브랜치 결과를 30초 설명할 수 있는가?
