# 03. Command Semantics

이 문서는 **무엇이 정답 동작인지**를 고정하는 문서다.
프로토콜보다 위에 있는 규칙이며, 코드보다 먼저 합의해야 한다.

이 문서는 **명령의 의미(semantic result)** 를 정의한다.
즉, URL 경로나 socket handler보다 먼저 **각 명령이 어떤 결과를 내야 하는지**를 고정한다.

---

## 이번 프로젝트에서 이미 고정한 결정

아래 항목은 **구현 시작 전에 다시 토론하지 않고 그대로 시작**한다.

- 외부 인터페이스는 **HTTP + JSON** 과 **RESP subset TCP** 를 함께 사용한다.
- RESP를 추가해도 기존 HTTP 동작은 유지한다.
- 명령 의미론은 protocol-neutral이며, HTTP와 RESP는 같은 semantic result를 공유한다.
- RESP 요청은 **array of bulk strings only** 로 제한한다.
- missing value는 HTTP에서 **404가 아니라 200 OK** 로 응답한다.
- `GET` miss의 HTTP 응답은 아래 JSON 형태로 고정한다.

```json
{
  "found": false,
  "value": null
}
```

- `GET` miss의 RESP 응답은 **null bulk string** 으로 고정한다.
- `EXPIRE key seconds` 에서 `seconds <= 0` 이면 **즉시 삭제 처리**로 간다.
  - key가 존재했다면 `1`
  - key가 없었다면 `0`
- `DEL`은 **이번 MVP에서 single-key만 지원**한다.
- Stretch 명령(`INCR`, `MGET`, `MSET`)은 문서에 정의하되,
  **필수 기능과 테스트가 끝나기 전까지 구현 범위에 포함하지 않는다.**
- AOF-lite는 이번 활성 병렬 트랙의 범위 밖이다.

---

## 공통 규칙

- key 타입은 string이다.
- value 타입은 string이다.
- key가 expired 상태라면 접근 순간 삭제 후 missing처럼 취급한다.
- write 명령은 성공 시 store에 즉시 반영된다.
- `SET`은 기존 값을 덮어쓴다.
- `SET`이 기존 key를 덮어쓰면, 기존 TTL은 제거된다.
- future stretch 명령 중 `INCR`처럼 **기존 값을 교체하는 게 아니라 갱신하는 명령**은 TTL을 유지한다.
- 이 문서는 명령 의미를 정의하며, 구체적인 HTTP endpoint와 RESP server wiring은 별도 구현 문서 또는 코드에서 정한다.

---

## Protocol-Neutral Principle

- dispatcher는 protocol-neutral semantic result를 만든다.
- HTTP layer와 RESP layer는 그 결과를 각자 직렬화한다.
- command arity, integer parsing, missing key, TTL 계산 규칙은 protocol마다 달라지면 안 된다.
- protocol layer는 transport shape validation을 담당하지만, command semantics 자체를 다시 정의하지 않는다.

---

## HTTP 응답 직렬화 원칙

HTTP 응답 직렬화 규칙은 아래처럼 고정한다.

### 성공 응답

- 문자열 상태 응답:
```json
{ "result": "OK" }
```

또는
```json
{ "result": "PONG" }
```

- 정수 응답:
```json
{ "result": 1 }
```

- 단일 조회 응답:
```json
{ "found": true, "value": "hello" }
```

또는
```json
{ "found": false, "value": null }
```

- 다중 조회 응답(Stretch):
```json
{ "values": ["a", null, "c"] }
```

### 에러 응답

기본 형식:
```json
{ "error": "..." }
```

기본 정책:
- 잘못된 요청 / 잘못된 입력 / 지원하지 않는 명령 -> `400 Bad Request`
- 예상하지 못한 내부 오류 -> `500 Internal Server Error`

---

## RESP 요청 / 응답 직렬화 원칙

### 요청 규칙

- RESP 요청은 `array of bulk strings`만 허용한다.
- 첫 번째 bulk string은 command 이름이다.
- 이후 bulk string들은 command 인자다.
- inline command, nested array, non-bulk element는 protocol error다.

요청 예:
```text
*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n
```

### 응답 규칙

- simple string:
```text
+PONG\r\n
```

또는
```text
+OK\r\n
```

- bulk string:
```text
$5\r\nhello\r\n
```

- null bulk string:
```text
$-1\r\n
```

- integer:
```text
:1\r\n
```

- simple error:
```text
-wrong number of arguments for GET\r\n
```

규칙:
- semantic error 메시지는 HTTP 에러 메시지와 같은 영어 문구를 재사용한다.
- malformed RESP frame도 simple error로 반환한다.
- RESP 추가가 HTTP 직렬화 규칙을 바꾸지는 않는다.

---

## Command Definitions

### 1) PING
의미:
- 서버 생존 확인용 명령

입력:
```text
PING
```

반환:
- `PONG`

HTTP 직렬화 예:
```json
{ "result": "PONG" }
```

RESP 직렬화 예:
```text
+PONG\r\n
```

---

### 2) GET
의미:
- key의 현재 값을 조회한다.

입력:
```text
GET key
```

반환 의미:
- key가 존재하면 value
- key가 없거나 expired면 missing

규칙:
- expired 상태면 조회 전에 삭제한다.
- missing은 에러가 아니다.
- missing은 HTTP에서 `200 OK` 로 응답한다.
- missing은 RESP에서 null bulk string으로 응답한다.

HTTP 직렬화:
- hit
```json
{ "found": true, "value": "hello" }
```

- miss
```json
{ "found": false, "value": null }
```

RESP 직렬화:
- hit
```text
$5\r\nhello\r\n
```

- miss
```text
$-1\r\n
```

---

### 3) SET
의미:
- key에 문자열 value를 저장한다.

입력:
```text
SET key value
```

반환:
- 성공 시 `OK`

규칙:
- 기존 value를 덮어쓴다.
- 기존 TTL이 있더라도 제거한다.
- 성공 시 store에 즉시 반영된다.

HTTP 직렬화 예:
```json
{ "result": "OK" }
```

RESP 직렬화 예:
```text
+OK\r\n
```

---

### 4) DEL
의미:
- key를 삭제한다.

입력:
```text
DEL key
```

반환:
- 실제 삭제된 key 개수

예:
- 존재하는 key 1개 삭제 -> `1`
- 없는 key 삭제 -> `0`

규칙:
- **이번 MVP에서는 단일 key만 지원한다.**
- multi-key DEL은 이번 MVP 범위 밖이다.
- expired 상태의 key는 missing처럼 취급한다.

HTTP 직렬화 예:
```json
{ "result": 1 }
```

RESP 직렬화 예:
```text
:1\r\n
```

---

### 5) EXPIRE
의미:
- key에 expiration time을 설정한다.

입력:
```text
EXPIRE key seconds
```

반환:
- timeout 설정 성공 -> `1`
- key가 없으면 -> `0`

규칙:
- `seconds > 0` 이면 expiration metadata를 해당 값으로 설정한다.
- `seconds <= 0` 이면 **즉시 삭제 처리**한다.
  - key가 존재했다면 `1`
  - key가 없었다면 `0`
- `EXPIRE`는 value를 바꾸지 않고 expiration metadata만 갱신한다.

HTTP 직렬화 예:
```json
{ "result": 1 }
```

RESP 직렬화 예:
```text
:1\r\n
```

---

### 6) TTL
의미:
- key의 남은 만료 시간을 초 단위로 조회한다.

입력:
```text
TTL key
```

반환:
- key가 없으면 `-2`
- key는 있지만 expire가 없으면 `-1`
- expire가 있으면 남은 초(0 이상의 정수)

규칙:
- expired 상태면 삭제 후 `-2`
- TTL은 초 단위 기준으로 정의한다.

HTTP 직렬화 예:
```json
{ "result": -1 }
```

RESP 직렬화 예:
```text
:-1\r\n
```

---

### 7) PERSIST
의미:
- key에 설정된 expiration을 제거한다.

입력:
```text
PERSIST key
```

반환:
- timeout 제거 성공 -> `1`
- key가 없거나 timeout이 없으면 -> `0`

규칙:
- value는 유지하고 expiration metadata만 제거한다.

HTTP 직렬화 예:
```json
{ "result": 1 }
```

RESP 직렬화 예:
```text
:1\r\n
```

---

## Stretch Commands (MVP 범위 밖)

아래 명령은 문서상 의미만 정의한다.
**필수 기능, 필수 테스트, CI가 안정화되기 전에는 구현하지 않는다.**

### 8) INCR (Stretch)
의미:
- key의 정수 문자열 값을 1 증가시킨다.

입력:
```text
INCR key
```

반환:
- 증가 후 값(정수)

규칙:
- key가 없으면 `0`에서 시작해 `1`
- 기존 value가 정수 문자열이 아니면 에러
- 성공 시 결과는 string으로 저장해도 무방
- 기존 TTL은 유지한다

HTTP 직렬화 예:
```json
{ "result": 2 }
```

---

### 9) MGET (Stretch)
의미:
- 여러 key를 한 번에 조회한다.

입력:
```text
MGET key [key ...]
```

반환:
- 각 key에 대한 값 배열
- 없는 key는 `null`
- 순서는 입력 순서를 유지한다

HTTP 직렬화 예:
```json
{ "values": ["a", null, "c"] }
```

---

### 10) MSET (Stretch)
의미:
- 여러 key/value를 한 번에 저장한다.

입력:
```text
MSET key value [key value ...]
```

반환:
- 성공 시 `OK`

규칙:
- 전체를 한 번에 반영한다.
- 중간 일부만 반영된 상태를 외부가 보면 안 된다.
- 기존 TTL은 덮어쓴 key에 대해 제거한다.
- key/value 개수가 맞지 않으면 에러다.

HTTP 직렬화 예:
```json
{ "result": "OK" }
```

---

## Error Mapping

- unknown or unsupported command -> HTTP `400 Bad Request`, RESP simple error
- wrong number of arguments -> HTTP `400 Bad Request`, RESP simple error
- invalid integer -> HTTP `400 Bad Request`, RESP simple error
- wrong type -> HTTP `400 Bad Request`, RESP simple error
- malformed RESP request shape -> RESP simple error
- internal error -> HTTP `500 Internal Server Error`, RESP simple error

HTTP 에러 바디 예:
```json
{ "error": "wrong number of arguments for INCR" }
```

RESP 에러 바디 예:
```text
-wrong number of arguments for INCR\r\n
```

---

## 이번 문서 기준으로 이미 끝난 결정 요약

구현 시작 전에 다시 논의하지 않는다.

- external interface는 **HTTP + RESP**
- HTTP는 유지하고 RESP는 추가한다.
- missing `GET` 응답은 **HTTP에서 `200 OK` + `{ "found": false, "value": null }`**
- missing `GET` 응답은 **RESP에서 null bulk string**
- `EXPIRE <= 0` 은 **즉시 삭제**
- `DEL`은 **MVP에서 single-key only**
- RESP 요청은 **array of bulk strings only**
- Stretch 명령은 **문서화만 하고 기본 구현 범위에서는 제외**
