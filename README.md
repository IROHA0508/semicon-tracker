# semicon-tracker (임시 이름)

반도체 면접 준비용 개인 사이트입니다. 삼성전자와 SK하이닉스의 공식 뉴스룸 소식을 자동으로 모아 한국어로 요약하고, 기사마다 관련 이론 단원(0~6층, 59개 단원)을 이어 줍니다. 비공개 저장소이며 혼자 씁니다.

지금은 1차 작업 6단계 중 **3단계(요약·번역·태그 분류)**까지 들어 있습니다.

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 표준 태그 사전(55개, 9개 그룹) | 완료(`data/tags.json`) |
| 2 | 저장소, 기사 수집기(RSS 4개, 2026년 1월부터) | 완료 |
| 3 | 요약·번역·태그 분류, 관련 단원 연결 | **이 커밋** |
| 4 | 이론 원고 59단원 옮기기 | 다음 |
| 5 | 화면: 시장 흐름, 이론 공부, 출처 | |
| 6 | 비공개 배포, 자동 실행 확인 | |

## 구조

```
backend/config.py        출처 목록(SOURCES), 수집 시작 날짜, 요약 모델·건수 한도 등 설정
backend/feeds.py         RSS 페이지 읽기, 주소 정리, 기사 id, 카테고리 규칙, 본문 HTML → 글자
backend/collect.py       출처마다 페이지를 넘기며 새 기사를 대기열에 넣기, 출처 점검(selftest)
backend/bodies.py        요약할 기사의 본문 찾기(피드 → 기사 페이지). 본문은 메모리에서만 씀
backend/summarize.py     Claude 호출(구독 토큰 CLI 또는 API 키), 편집 원칙(RULES), 출력 형식
backend/guard.py         카드의 수치를 원문과 대조(단위 환산 실수 잡기)
backend/tags.py          표준 태그 사전, 동의어 정리, 관련 단원 고르기
backend/digest.py        요약 단계: 대기열 → 카드(data/news/<id>.json)
backend/publish.py       data/manifest.json 만들기, 데이터 점검(validate)
backend/store.py         상태 파일 읽기·쓰기
backend/state/           seen.json(이미 본 기사), queue.json(요약 대기열), last-run.json(실행 보고서)
data/tags.json           표준 태그 55개(9개 그룹)와 동의어·영문 키워드
data/units.json          이론 59단원과 단원별 표준 태그
data/news/               요약 카드(기사 1건 = 파일 1개)
data/manifest.json       사이트가 읽는 카드 목록(관련 단원 포함)
tests/                   오프라인 테스트(실제 피드 구조를 본뜬 예제, 가짜 Claude)
docs/DATA_SCHEMA.md      파일 형식 설명
.github/workflows/       하루 4번 수집·요약하는 GitHub Actions 워크플로
```

## 수집 출처

| 출처 | 수집 방법 | 언어 | 수집 대상 |
|---|---|---|---|
| SK하이닉스 뉴스룸 FACT | 영문 RSS `news.skhynix.com/en/category/fact/feed/` | 영어 | 전체 |
| SK하이닉스 뉴스룸 TECH&AI | 영문 RSS `.../category/tech-and-ai/feed/` | 영어 | 전체 |
| SK하이닉스 뉴스룸 PRESS | 영문 RSS `.../category/press/feed/` | 영어 | 전체 |
| 삼성전자 반도체 뉴스룸 | 한국어 RSS `news.samsungsemiconductor.com/kr/feed/` | 한국어 | 보도자료·기술만(문화·ESG 제외) |
| 삼성반도체 뉴스, 테크 블로그 | 수집하지 않음(목록을 자바스크립트로 그려서 단순 수집 불가) | | 화면에 '원문 보기' 링크로만 |

SK하이닉스 한국어 뉴스룸은 자동 요청을 막아서 영문 피드로 수집하고, 제목과 요약을 한국어로 번역합니다.

**저장 원칙:** 기사마다 제목·링크·발행 시각·피드 카테고리와, 직접 쓴 한국어 요약 카드만 저장합니다. 기사 본문은 요약하는 동안 메모리에서만 읽고 어디에도 저장하지 않습니다. 영문 기사는 번역한 제목과 원제를 함께 보여 주고, 본문 번역은 하지 않습니다.

## 수집 방식

```
읽기    출처마다 RSS 1페이지부터 ?paged=2, 3 ... 순서로 읽음(페이지 사이 1초 쉼)
거르기  2026-01-01(한국 시간) 이전 기사, 삼성 뉴스룸의 문화·ESG 기사는 넣지 않음
중복    주소로 같은 기사를 판단. SK하이닉스의 여러 채널에 함께 올라온 기사는 한 번만 넣고 alsoIn에 기록
멈춤    첫 채우기 전: 2026년 1월에 닿을 때까지 / 첫 채우기 뒤: 이미 본 기사가 나온 페이지에서
저장    backend/state/queue.json(요약 대기열), seen.json, last-run.json
```

## 요약 방식

```
고르기  대기열에서 최신 기사부터 한 번에 10건(ST_SUMMARY_LIMIT)
본문    RSS 피드의 본문(content:encoded)을 메모리로 읽음. 피드에서 빠진 옛 기사는 기사 페이지를 직접 읽음
요약    Claude(구독 토큰)에게 카드 한 장을 받음: 한국어 제목, 요약 2문장(-습니다), 면접 한 줄, 표준 태그 1~4개, 언급 기업
점검    카드의 단위 붙은 수치(150억 달러, 12단, 263% 등)를 원문과 대조
        → 원문에서 못 찾으면 그 목록을 주고 한 번 다시 쓰게 함 → 그래도 안 맞으면 그 문장을 지움
정리    태그는 표준 태그 이름으로 맞춤(동의어·영문 키워드도 인식), 한국어 기사 제목은 원제 그대로
저장    data/news/<id>.json, 대기열에서 빼고 seen.json에 summarized 표시
목록    data/manifest.json을 다시 만들며 카드마다 관련 단원 2개를 붙임
        (태그가 많이 겹치는 단원 → 면접 빈도 별이 많은 단원 → 번호가 큰 단원)
```

- 실패한 기사(본문을 못 찾음, 카드가 형식에 안 맞음 등)는 대기열에 남아 다음 실행에서 다시 하고, 3번 실패하면 대기열에서 빼고 seen.json에 `failed`로 남깁니다.
- 인증 오류나 구독 사용량 한도에 걸리면 그 자리에서 멈추고, 남은 기사는 다음 실행에서 이어 합니다(실패 횟수에 세지 않음).
- 한 번 실행에서 25분(ST_TIME_BUDGET)이 지나면 새 기사를 시작하지 않고 그때까지 한 것을 커밋합니다.
- 대기열이 146건이어서 하루 4번 × 10건이면 4일쯤 걸립니다. 빨리 줄이려면 수동 실행에서 `limit`을 늘리세요.

## 자동 실행

`.github/workflows/collect.yml` (이름: 기사 수집·요약)

- **하루 4번(한국 시간 07:10·13:10·19:10·01:10):** 수집 → 요약 → manifest 갱신 후 바뀐 파일(`data`, `backend/state`)을 커밋합니다. 릴리스 레이더(00·06·12·18시)와 시간을 엇갈렸습니다.
- **수동 실행:** **Actions → 기사 수집·요약 → Run workflow**에서 `update`(수집+요약), `collect`(수집만), `detect`(결과만 보기), `selftest`(출처 점검)를 고르고, `limit`에 이번에 요약할 건수를 넣을 수 있습니다.
- **코드를 고쳐 main에 푸시하면:** 오프라인 테스트, 데이터 점검, 출처 점검만 돌고 수집·요약은 하지 않습니다.
- **실패로 표시되는 경우:** 출처를 못 읽었을 때, Claude 인증이 실패했을 때(토큰을 새로 만들어 Secret을 바꿔야 함). GitHub가 실패 알림 메일을 보냅니다.
- **경고만 남기는 경우:** 기사 요약 실패·포기, 사용량 한도, 토큰이 없어 요약을 건너뜀. 실행 화면의 Annotations에서 볼 수 있습니다.

## 요약용 인증

릴리스 레이더와 같은 Claude 구독 토큰을 저장소 Secret `CLAUDE_CODE_OAUTH_TOKEN`에 넣어 두었습니다. 워크플로가 Claude Code CLI를 설치해 이 토큰으로 요약하므로 API 요금이 들지 않고, 구독 사용량을 씁니다. 토큰이 없고 Secret `ANTHROPIC_API_KEY`가 있으면 API로 요약합니다(요금 발생).

## 내 컴퓨터에서 실행

```bash
pip install -r backend/requirements.txt pytest
python -m pytest tests -q          # 오프라인 테스트
python -m backend selftest         # 실제 피드 첫 페이지 점검(파일 변경 없음)
python -m backend detect           # 새로 들어갈 기사만 출력(파일 변경 없음)
python -m backend collect          # 수집하고 backend/state 갱신
python -m backend summarize --limit 3   # 대기열에서 3건 요약(CLAUDE_CODE_OAUTH_TOKEN 필요)
python -m backend update           # 수집 + 요약 + manifest(워크플로가 하는 일)
python -m backend publish          # data/news로 manifest 다시 만들기
python -m backend requeue --outdated    # 편집 원칙(RULES_VERSION)이 바뀐 뒤 옛 카드를 대기열로 되돌려 다시 요약
python -m backend validate         # 데이터 점검
```

설정은 환경 변수로 바꿀 수 있습니다.

| 변수 | 기본값 | 뜻 |
|---|---|---|
| `ST_START_DATE` | 2026-01-01 | 이 날짜 이후 기사만 수집 |
| `ST_MAX_PAGES` | 25 | 출처마다 한 번에 읽는 최대 피드 페이지 |
| `ST_PAGE_DELAY` | 1 | 피드 페이지 사이 쉬는 초 |
| `ST_MODEL` | claude-sonnet-5-5 | 요약 모델(저장소 Variables에 `ST_MODEL`을 만들면 워크플로에서도 바뀜) |
| `ST_SUMMARY_LIMIT` | 10 | 한 번 실행에서 요약할 최대 기사 수 |
| `ST_TIME_BUDGET` | 1500 | 이 초가 지나면 새 기사 요약을 시작하지 않음 |
