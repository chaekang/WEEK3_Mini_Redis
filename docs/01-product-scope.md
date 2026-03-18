# 01. Product Scope

## 목표
짧은 구현 기간 안에 **Redis의 모든 기능**이 아니라, **Redis-like key-value server의 핵심 경험**을 재현한다.

## 문제 정의
이번 프로젝트의 본질은 다음을 직접 구현하고 설명하는 것이다.
- 해시 테이블 기반 저장 구조
- 외부에서 접근 가능한 인터페이스
- 만료된 값 처리 방식
- 동시성 충돌을 줄이는 구조
- 테스트 가능한 품질 기준

## 핵심 사용자 / 평가자 관점
- 팀 내부 개발자: 구조와 의미론이 명확해야 한다.
- 발표 청중: 데모가 안정적으로 돌아가야 한다.
- 코치 / 리뷰어: 해시 테이블 설계 원리와 테스트 전략을 설명할 수 있어야 한다.

## 필수 범위 (MVP)
1. **데이터 범위**
   - key: string
   - value: string

2. **필수 명령**
   - `PING`
   - `GET`
   - `SET`
   - `DEL`
   - `EXPIRE`
   - `TTL`
   - `PERSIST`

3. **필수 구조**
   - hash table 기반 저장소
   - expiration metadata 관리
   - HTTP + JSON external interface 1종
   - unit / integration / smoke test

4. **필수 데모**
   - 저장 / 조회 / 삭제
   - TTL 감소 및 만료
   - 외부 클라이언트에서 명령 호출
   - 캐시 도입 전후 간단 비교

## Stretch 범위
- `INCR`
- `MGET`, `MSET`
- RESP subset TCP server
- AOF-lite
- benchmark script 자동화

## 이번에 하지 않는 것
- list / set / zset / stream
- `MULTI/EXEC`
- pub/sub
- replication / cluster
- eviction policy
- production-grade durability

## 성공 기준
- 명령 의미론이 문서와 코드에서 일치한다.
- 핵심 테스트가 자동화되어 있다.
- README만 읽어도 데모 흐름을 이해할 수 있다.
- 팀원 누구든 최소 핵심 명령 3개 이상은 직접 설명할 수 있다.

## 실패 기준
- 기능은 있어 보이지만 semantics가 문서와 다르다.
- 테스트 없이 수동 확인만으로 통과하려 한다.
- 프로토콜, store, TTL 계약이 중간에 계속 흔들린다.
- stretch 기능 때문에 필수 동작이 불안정해진다.

## 구현 전 확정 항목
- MVP 범위
- command semantics
- branch / role 분리 기준
- 테스트 계층
- kickoff 순서
