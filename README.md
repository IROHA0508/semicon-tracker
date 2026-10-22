# semicon-tracker (임시 이름)

반도체 면접 준비용 개인 사이트입니다. 삼성전자와 SK하이닉스의 공식 뉴스룸 소식을 자동으로 모아 한국어로 요약하고, 기사마다 관련 이론 단원(0~6층, 59개 단원)을 이어 줍니다. 저장소와 사이트는 공개이고(2026-10-13 결정), 검색 엔진 색인만 막아 둡니다.

1차 작업 6단계를 모두 마쳤습니다(2026-10-13). 사이트: https://semicon-tracker.vercel.app/ 화면(`index.html`)은 시장 흐름, 이론 공부(층 지도·단원 페이지), 출처의 세 탭이고, 이론 원고 59단원(`theory/`)과 도식 80개, 단원별 영상 링크, 단계별 애니메이션 49개(`animations/`)를 단원 페이지에서 함께 봅니다.

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 표준 태그 사전(55개, 9개 그룹) | 완료(`data/tags.json`) |
| 2 | 저장소, 기사 수집기(RSS 4개, 2026년 1월부터) | 완료 |
| 3 | 요약·번역·태그 분류, 관련 단원 연결 | 완료 |
| 4 | 이론 원고 59단원 옮기기(도식·영상·애니메이션 연결 포함) | 완료(`theory/`, `data/theory.json`) |
| 5 | 화면: 시장 흐름, 이론 공부, 출처 | 완료(`index.html`) |
| 6 | 배포(Vercel), 자동 실행 확인 | 완료(https://semicon-tracker.vercel.app/) |

## 화면

`index.html` 한 파일이 데이터 파일을 읽어 그립니다(빌드 없음). 주소의 `#` 뒤로 화면을 고릅니다.

| 주소 | 화면 |
|---|---|
| `#news` (기본) | 시장 흐름(기사는 10건씩 보이고, 목록 끝에 다가가면 다음 10건을 불러옴. '더 보기' 버튼도 있음): 기사 카드(회사·채널·날짜·배지 → 한국어 제목·원제 → 요약 2문장 → 면접 한 줄 → 태그 → 관련 단원), 회사·종류·기간 거르기(기간은 연도별 줄에 1~12월, 월을 누르면 그 달 기사만, 다시 누르면 해제. 다음 해 기사가 생기면 그해 줄이 위에 자동으로 생김), 검색. 옆에 '이번 주 공부할 단원'(최근 7일 소식의 관련 단원, 3건 미만이면 최근 10건 기준), 자주 나온 태그, 공부 진도 |
| `#tag/<태그>` | 그 표준 태그가 붙은 기사만 |
| `#article/<기사 id>` | 기사 페이지(기사 제목을 누르면 열림): 개요, 소제목 바로가기, 핵심 3줄, 소제목별 자세한 요약(영어 기사는 한국어로), 원문 그림, 필요할 때 새로 그린 그림, 용어, 같이 공부할 단원, 앞뒤 기사. 자세한 요약이 아직 없으면 짧은 요약과 원문 링크 |
| `#theory` | 이론 공부: 0~6층 층 지도, 단원마다 별·애니메이션·영상·이어진 소식 수·읽음 표시. ★★★만·애니메이션 있음·안 읽은 단원 거르기 |
| `#unit/<단원>` | 단원 페이지: 원고 본문(마크다운을 화면에서 그림), 뉴스 태그·이어지는 단원, '면접 단골 질문' 앞에 애니메이션(`animations/<파일>?embed`를 iframe으로), 이 단원과 이어진 소식, 읽음 표시, 앞뒤 단원 |
| `#guide` | 공부 안내(`theory/overview.md`: 읽는 법, 전체 지도, 학습 경로) |
| `#sources` | 출처: 기사 출처 4곳과 링크 전용 2곳, 배지 읽는 법, 저장·요약 원칙, 이론 원고 출처(`theory/sources.md`) |

- **배지:** `press` → 공식 발표, `fact` → 공식 해명, `tech` → 기술 해설. 카드에 `author`가 있으면(외부 필자) '외부 기고' 배지를 더 붙입니다. 공식 통계·언론 보도 배지는 2·3차에서 출처가 늘면 씁니다.
- **읽는 파일:** 처음에 `data/manifest.json`(모든 카드의 짧은 색인), `data/theory.json`, `data/tags.json`. 기사 본문 카드는 연도별 `data/feed/<연도>.json`을 그해 기사가 화면에 처음 나올 때 읽습니다(검색할 때는 전부). 단원을 열 때 `theory/units/<단원>.md`.
- **브라우저에 저장하는 값(기기마다 따로):** `st-read`(읽은 단원과 날짜), `st-co`·`st-kind`(시장 흐름 거르기), `st-tfilter`(층 지도 거르기).
- **보는 법:** 저장소 폴더에서 `python -m http.server` 후 `http://localhost:8000`. 파일을 직접 열면(`file://`) 데이터를 읽지 못합니다.
- **글꼴:** Pretendard(jsDelivr), 숫자는 IBM Plex Mono(Google Fonts). 색은 애니메이션(`animations/player.css`)과 같은 회색 바탕 + 구리색 하나이고, 기기의 밝은·어두운 설정을 따릅니다. 휴대폰(폭 760px 미만)에서는 탭이 아래로 내려갑니다.
- **배포 설정:** `vercel.json`(주소 끝 `.html` 생략, `data/`는 캐시하지 않음, 검색 엔진 색인 막음), `.vercelignore`(backend·tests·tools·.github 제외). 색인을 열려면 `index.html`의 `meta name="robots"`와 `vercel.json`의 `X-Robots-Tag`를 지웁니다.

## 구조

```
index.html               화면(시장 흐름, 이론 공부, 출처). 데이터 파일을 읽어 그림
vercel.json, .vercelignore   배포 설정
backend/config.py        출처 목록(SOURCES), 수집 시작 날짜, 요약 모델·건수 한도 등 설정
backend/feeds.py         RSS 페이지 읽기, 주소 정리, 기사 id, 카테고리 규칙, 본문 HTML → 글자
backend/collect.py       출처마다 페이지를 넘기며 새 기사를 대기열에 넣기, 출처 점검(selftest)
backend/bodies.py        요약할 기사의 본문 찾기(피드 → 기사 페이지). 본문은 메모리에서만 씀
backend/summarize.py     Claude 호출(구독 토큰 CLI 또는 API 키), 편집 원칙(RULES), 출력 형식
backend/guard.py         카드의 수치를 원문과 대조(단위 환산 실수 잡기)
backend/tags.py          표준 태그 사전, 동의어 정리, 관련 단원 고르기
backend/digest.py        요약 단계: 대기열 → 카드(data/news/<id>.json)
backend/humanize.py      문체 단계: im-not-ai 규칙을 요약 프롬프트에 넣고 쓴 뒤 연결어미 쉼표를 지우고 남은 신호가 있는 문장만 한 번 더 다듬기
backend/detail.py        자세한 요약 단계: 카드 → 기사 페이지(data/detail/<id>.json), 원문 그림 주소 찾기, 수치 점검
backend/figures.py       자세한 요약의 새로 그린 그림(명세 → SVG, 두 가지 틀)
backend/publish.py       data/manifest.json 만들기, 데이터 점검(validate)
backend/store.py         상태 파일 읽기·쓰기
backend/state/           seen.json(이미 본 기사), queue.json(요약 대기열), last-run.json(실행 보고서)
data/tags.json           표준 태그 55개(9개 그룹)와 동의어·영문 키워드
data/units.json          이론 59단원과 단원별 표준 태그(theory/에서 만듦, 직접 고치지 않음)
data/theory.json         사이트가 읽는 단원 목록: 층, 별, 이어지는 단원, 태그, 도식, 영상, 애니메이션
data/news/               요약 카드(기사 1건 = 파일 1개)
data/manifest.json       사이트가 처음 읽는 카드 색인(관련 단원 포함)과 연도 파일 목록
data/feed/<연도>.json    그해 카드 전체(사이트가 필요할 때 읽음)
theory/                  이론 원고: 단원별 마크다운 59개, 층 소개, 개요, 출처, 도식 SVG 80개(theory/README.md)
animations/              단계별 애니메이션 49개와 공통 플레이어, catalog.json, 목록 페이지
tools/build_theory.py    theory/ → data/theory.json·data/units.json
tools/build_animation_index.py  catalog.json → animations/index.html
tools/style_check.py     사이트 글의 'AI 티' 문체 점검(im-not-ai 규칙). --fix-c11로 연결어미 뒤 쉼표 지우기
.claude/skills/humanize-korean-site/  사이트 문체 규칙 스킬(im-not-ai v2.3.2, MIT). 릴리스 레이더와 같은 룰북
CLAUDE.md                Claude Code가 이 저장소에서 따를 규칙(볼 문서, 지킬 것, 함정)
tests/                   오프라인 테스트(실제 피드 구조를 본뜬 예제, 가짜 Claude, 애니메이션 목록, 이론 원고 형식·링크·도식 점검, 화면 파일 점검)
docs/DATA_SCHEMA.md      파일 형식 설명
.github/workflows/       하루 4번 수집·요약하는 GitHub Actions 워크플로
```

## 배포

**사이트: https://semicon-tracker.vercel.app/** (Vercel 프로젝트 `semicon-tracker`, Hobby 요금제, 2026-10-13 연결)

릴리스 레이더와 같이 Vercel이 GitHub 저장소를 직접 가져가 배포합니다(빌드 없음, 저장소 루트의 `index.html`이 첫 화면).

1. Vercel 대시보드 → **Add New → Project** → `IROHA0508/semicon-tracker` **Import**
2. Framework Preset은 **Other**, Build Command·Output Directory는 비워 둠(루트 그대로) → **Deploy**
3. 이후 main에 올라오는 커밋(코드 수정, 하루 4번 요약 봇의 데이터 커밋)마다 자동으로 다시 배포됩니다.

- 저장소가 공개라서 Vercel 무료(Hobby) 요금제에서도 봇 커밋이 배포됩니다. 비공개 저장소였다면 무료 요금제는 계정 주인이 아닌 작성자(봇 등)의 커밋을 배포하지 않습니다.
- GitHub Secret(`CLAUDE_CODE_OAUTH_TOKEN`)은 저장소를 공개해도 밖에 보이지 않습니다. 저장소 파일에는 토큰을 두지 않습니다.

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
문체    연결어미 뒤 쉼표를 지우고 'AI 티' 신호(콜론 부제, "A가 아니라 B" 반복, "핵심은 ~" 등)가 남으면
        걸린 문장만 Claude에게 한 번 더 다듬게 함 → 수치·영문 표기·따옴표 안 글이 바뀌었거나 절반 넘게 바뀐 수정은 버림
정리    태그는 표준 태그 이름으로 맞춤(동의어·영문 키워드도 인식), 한국어 기사 제목은 원제 그대로
저장    data/news/<id>.json, 대기열에서 빼고 seen.json에 summarized 표시
목록    data/manifest.json을 다시 만들며 카드마다 관련 단원 2개를 붙임
        (태그가 많이 겹치는 단원 → 면접 빈도 별이 많은 단원 → 번호가 큰 단원)
```

- 실패한 기사(본문을 못 찾음, 카드가 형식에 안 맞음 등)는 대기열에 남아 다음 실행에서 다시 하고, 3번 실패하면 대기열에서 빼고 seen.json에 `failed`로 남깁니다.
- 인증 오류나 구독 사용량 한도에 걸리면 그 자리에서 멈추고, 남은 기사는 다음 실행에서 이어 합니다(실패 횟수에 세지 않음).
- 한 번 실행에서 25분(ST_TIME_BUDGET)이 지나면 새 기사를 시작하지 않고 그때까지 한 것을 커밋합니다.
- 2026년 1월 1일 이후 기사 146건(1월 2일~10월 8일)은 2026-10-13에 모두 요약했습니다(수동 실행 `limit` 100). 이후에는 새 기사만 하루 4번 실행에서 요약합니다. 밀린 기사가 많을 때는 수동 실행의 `limit`을 늘리면 한 번에 줄일 수 있습니다.

## 문체

사이트의 한국어 글은 [im-not-ai](https://github.com/epoko77-ai/im-not-ai)(humanize-korean)의 'AI 티' 규칙을 따릅니다. 릴리스 레이더와 같은 룰북을 `.claude/skills/humanize-korean-site/`에 두었고 이 사이트에 맞춘 적용 범위는 그 폴더의 `SKILL.md`에 있습니다.

- **자동 요약:** 카드와 기사 페이지를 쓰는 프롬프트에 규칙을 함께 넣고 쓴 뒤 `backend/humanize.py`가 연결어미 뒤 쉼표를 지우고 남은 신호가 있는 문장만 한 번 더 다듬습니다. 결과는 카드·기사 페이지의 `checks.style`과 실행 보고서의 `styleNotes`에 남습니다.
- **손으로 고칠 때:** `python tools/style_check.py --spans`로 걸린 문장을 보고 그 문장만 고칩니다. Claude Code는 `CLAUDE.md`와 스킬을 읽고 같은 규칙을 따릅니다.
- **점검:** 푸시 테스트가 문체 신호를 경고로 보여 주고(`문체 점검` 단계), 연결어미 뒤 쉼표가 하나라도 있으면 테스트가 실패합니다(`tests/test_style.py`).
- 2026-10-22에 기존 글 전체를 이 규칙으로 다듬었습니다(연결어미 뒤 쉼표 2,346개, 걸린 문장 300여 개). 따옴표 안 인용, 수치, 제품명, 영상·자료 제목, 원고의 단원·절 제목은 바꾸지 않았습니다.

## 자동 실행

`.github/workflows/collect.yml` (이름: 기사 수집·요약)

- **하루 4번(한국 시간 07:10·13:10·19:10·01:10):** 수집 → 요약 → manifest 갱신 후 바뀐 파일(`data`, `backend/state`)을 커밋합니다. 릴리스 레이더(00·06·12·18시)와 시간을 엇갈렸습니다.
- **수동 실행:** **Actions → 기사 수집·요약 → Run workflow**에서 `update`(수집+요약), `collect`(수집만), `detect`(결과만 보기), `selftest`(출처 점검)를 고르고, `limit`에 이번에 요약할 건수를 넣을 수 있습니다.
- **코드를 고쳐 main에 푸시하면:** 오프라인 테스트, 데이터 점검, 문체 점검(경고만), 출처 점검만 돌고 수집·요약은 하지 않습니다(`backend/`, `tests/`, `index.html`, `theory/`, `animations/`, 태그·단원 파일, 문체 규칙·점검 도구, 워크플로를 고쳤을 때).
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
python -m backend details --limit 3     # 자세한 요약이 없는 기사 3건(최신부터)에 기사 페이지 내용 쓰기
python -m backend update           # 수집 + 요약 + manifest(워크플로가 하는 일)
python -m backend publish          # data/news로 manifest 다시 만들기
python -m backend requeue --outdated    # 편집 원칙(RULES_VERSION)이 바뀐 뒤 옛 카드를 대기열로 되돌려 다시 요약
python -m backend validate         # 데이터 점검
python tools/build_theory.py       # 이론 원고를 고친 뒤 data/theory.json·units.json 다시 만들기
python tools/style_check.py --spans    # 사이트 글의 'AI 티' 문체 신호와 걸린 문장 보기(--only theory처럼 한 종류만도)
python tools/style_check.py --fix-c11  # 연결어미 뒤 쉼표만 파일에서 지우기
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
