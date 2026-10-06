# semicon-tracker (임시 이름)

반도체 면접 준비용 개인 사이트입니다. 삼성전자와 SK하이닉스의 공식 뉴스룸 소식을 자동으로 모아 한국어로 요약하고, 기사마다 관련 이론 단원(0~6층, 59개 단원)을 이어 줍니다. 비공개 저장소이며 혼자 씁니다.

지금은 1차 작업 6단계 중 **2단계(기사 수집)**까지 들어 있습니다.

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 표준 태그 사전(55개, 9개 그룹) | 완료(프로젝트 문서) |
| 2 | 저장소, 기사 수집기(RSS 4개, 2026년 1월부터) | **이 커밋** |
| 3 | 요약·번역·태그 분류 | 다음 |
| 4 | 이론 원고 59단원 옮기기 | |
| 5 | 화면: 시장 흐름, 이론 공부, 출처 | |
| 6 | 비공개 배포, 매일 자동 실행 확인 | |

## 구조

```
backend/config.py        수집할 출처 목록(SOURCES), 수집 시작 날짜, 페이지 수 한도
backend/feeds.py         RSS 페이지 읽기, 주소 정리, 기사 id, 카테고리 규칙
backend/collect.py       출처마다 페이지를 넘기며 새 기사를 대기열에 넣기, 출처 점검(selftest)
backend/store.py         상태 파일 읽기·쓰기
backend/state/           seen.json(이미 본 기사), queue.json(요약 대기열), last-run.json(실행 보고서)
tests/                   오프라인 테스트(실제 피드 구조를 본뜬 예제 XML)
docs/DATA_SCHEMA.md      파일 형식 설명
.github/workflows/       매일 수집하는 GitHub Actions 워크플로
```

## 수집 출처

| 출처 | 수집 방법 | 언어 | 수집 대상 |
|---|---|---|---|
| SK하이닉스 뉴스룸 FACT | 영문 RSS `news.skhynix.com/en/category/fact/feed/` | 영어 | 전체 |
| SK하이닉스 뉴스룸 TECH&AI | 영문 RSS `.../category/tech-and-ai/feed/` | 영어 | 전체 |
| SK하이닉스 뉴스룸 PRESS | 영문 RSS `.../category/press/feed/` | 영어 | 전체 |
| 삼성전자 반도체 뉴스룸 | 한국어 RSS `news.samsungsemiconductor.com/kr/feed/` | 한국어 | 보도자료·기술만(문화·ESG 제외) |
| 삼성반도체 뉴스, 테크 블로그 | 수집하지 않음(목록을 자바스크립트로 그려서 단순 수집 불가) | | 화면에 '원문 보기' 링크로만 |

SK하이닉스 한국어 뉴스룸은 자동 요청을 막아서 영문 피드로 수집하고, 3단계에서 제목과 요약을 한국어로 번역합니다.

**저장 원칙:** 기사마다 제목·링크·발행 시각·피드 카테고리만 저장합니다. 피드에 들어 있는 기사 본문은 저장하지 않습니다.

## 수집 방식

```
읽기    출처마다 RSS 1페이지부터 ?paged=2, 3 ... 순서로 읽음(페이지 사이 1초 쉼)
거르기  2026-01-01(한국 시간) 이전 기사, 삼성 뉴스룸의 문화·ESG 기사는 넣지 않음
중복    주소로 같은 기사를 판단. SK하이닉스의 여러 채널에 함께 올라온 기사는 한 번만 넣고 alsoIn에 기록
멈춤    첫 채우기 전: 2026년 1월에 닿을 때까지 / 첫 채우기 뒤: 이미 본 기사가 나온 페이지에서
저장    backend/state/queue.json(요약 대기열), seen.json, last-run.json → 커밋·푸시
```

첫 실행은 2026년 1월까지 거슬러 올라가며 9개월 치를 대기열에 넣습니다. 요약은 3단계에서 실행할 때마다 정해진 건수씩 나눠 합니다(구독 사용량을 릴리스 레이더와 나눠 쓰기 때문).

## 자동 실행

`.github/workflows/collect.yml`

- **매일 한국 시간 07:10:** 수집하고 바뀐 상태 파일을 커밋합니다.
- **수동 실행:** GitHub 저장소 **Actions → 기사 수집 → Run workflow**에서 `collect`(수집+저장), `detect`(결과만 보기), `selftest`(출처 점검)를 고를 수 있습니다.
- **코드를 고쳐 main에 푸시하면:** 오프라인 테스트와 출처 점검만 돌고, 수집은 하지 않습니다.
- **수집 실패:** 출처 하나가 실패해도 나머지는 저장하고, 실행 결과를 실패로 표시합니다. GitHub가 실패 알림 메일을 보냅니다. 실패한 출처는 다음 실행에서 다시 읽습니다.

## 내 컴퓨터에서 실행

```bash
pip install -r backend/requirements.txt pytest
python -m pytest tests -q        # 오프라인 테스트
python -m backend selftest       # 실제 피드 첫 페이지 점검(파일 변경 없음)
python -m backend detect         # 새로 들어갈 기사만 출력(파일 변경 없음)
python -m backend collect        # 수집하고 backend/state 갱신
```

설정은 환경 변수로 바꿀 수 있습니다: `ST_START_DATE`(기본 2026-01-01), `ST_MAX_PAGES`(출처마다 한 번에 읽는 최대 페이지, 기본 25), `ST_PAGE_DELAY`(페이지 사이 쉬는 초, 기본 1).

## 요약용 인증(3단계부터 사용)

릴리스 레이더와 같은 Claude 구독 토큰을 저장소 Secret `CLAUDE_CODE_OAUTH_TOKEN`에 넣어 두었습니다. 2단계 수집기는 이 토큰을 쓰지 않습니다.
