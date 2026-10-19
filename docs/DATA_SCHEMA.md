# 데이터 형식

`backend/`가 만드는 파일의 형식입니다. 수집 단계가 새 기사를 `backend/state/queue.json`(요약 대기열)에 넣고, 요약 단계가 대기열에서 기사를 꺼내 `data/news/<id>.json`(요약 카드)로 만든 뒤 `data/manifest.json`(사이트가 읽는 목록)을 다시 만듭니다.

## 저장 원칙

- 기사마다 제목, 링크, 발행 시각, 피드의 카테고리와 직접 쓴 한국어 요약 카드만 저장합니다.
- RSS 피드에 들어 있는 기사 본문(`description`, `content:encoded`)과 기사 페이지 본문은 저장하지 않습니다. 요약하는 동안 메모리에서만 읽습니다.

## `data/news/<id>.json`: 요약 카드

```json
{
  "id": "skhynix-fact-11",
  "company": "skhynix",
  "source": "sk-fact",
  "channel": "FACT",
  "kind": "fact",
  "lang": "en",
  "title": "SK하이닉스, 솔리다임 관련 보도에 대한 입장",
  "originalTitle": "Clarification Regarding Recent Media Reports on Solidigm",
  "url": "https://news.skhynix.com/en/fact-11/",
  "published": "2026-10-01T10:22:33+09:00",
  "date": "2026-10-01",
  "summary": ["첫 문장입니다.", "둘째 문장입니다."],
  "interview": "면접에서 쓸 한 문장입니다.",
  "tags": ["eSSD·SSD", "밸류체인"],
  "companies": ["SK하이닉스", "솔리다임"],
  "categories": ["FACT", "semiconductor industry"],
  "alsoIn": [],
  "summarizedAt": "2026-10-12T07:14:02+09:00",
  "model": "claude-sonnet-5-5",
  "rules": "2026-10-12",
  "bodyVia": "feed"
}
```

| 필드 | 뜻 |
|---|---|
| `id` ~ `date`, `categories`, `alsoIn` | 대기열의 같은 필드를 그대로 옮김(아래 queue.json 표 참고) |
| `title` | 한국어 제목. 영문 기사는 번역한 제목, 한국어 기사는 원제 그대로 |
| `originalTitle` | 영문 기사의 원제(영문 기사에만 있음) |
| `summary` | 요약 문장 배열. 보통 2문장이고, 수치 점검에서 문장이 지워지면 1문장 |
| `interview` | 면접에서 이 기사를 근거로 말할 때 쓸 한 문장. 반도체 사업과 관계가 적은 글이면 빈 문자열 |
| `tags` | 표준 태그(`data/tags.json`의 이름) 0~4개, 글의 중심 주제부터. 맞는 태그가 없으면 빈 배열(미분류) |
| `companies` | 글에 나온 기업(한국어 통용 표기), 최대 6개 |
| `author` | 피드의 필자가 회사 계정이 아닐 때만 있음(외부 기고 배지 판단용) |
| `summarizedAt`, `model`, `rules` | 요약한 시각, 모델, 편집 원칙 버전(`summarize.RULES_VERSION`). 원칙을 고친 뒤 `requeue --outdated`로 옛 카드를 다시 요약 |
| `bodyVia` | 본문을 읽은 곳: `feed`(RSS 본문) 또는 `page`(기사 페이지) |
| `checks` | 점검 기록(있을 때만). `retriedFor`: 다시 쓰게 한 수치, `removed`: 수치가 원문과 안 맞아 지운 문장, `unknownTags`: 표준 태그가 아니라 버린 태그 |

## `data/manifest.json`과 `data/feed/<연도>.json`: 사이트가 읽는 목록

기사가 쌓여도 첫 화면이 가볍도록 두 가지로 나눕니다(2026-10-19).

- `data/manifest.json`: 출처·배지 이름 등 공통 정보, 연도 파일 목록(`years`), 그리고 **모든 카드의 짧은 색인**(`index`: `id`, `date`, `published`, `company`, `source`, `kind`, `tags`, `relatedUnits`). 사이트는 처음에 이 파일만 읽고 거르기·건수·태그 순위·단원 페이지의 '이어진 소식' 목록을 만듭니다.
- `data/feed/<연도>.json`: 그해 카드 전체(요약·면접 한 줄 포함), 발행 시각이 최근인 순서. 사이트는 화면에 그해 카드가 처음 필요할 때 이 파일을 읽습니다(검색할 때는 모든 연도를 읽음).

카드마다 붙는 `relatedUnits`(관련 이론 단원 코드 최대 2개)는 만들 때마다 `data/units.json`으로 다시 계산합니다(태그가 많이 겹치는 단원 → 면접 빈도 별이 많은 단원 → 번호가 큰 단원).

```json
{
  "generatedAt": "2026-10-19T09:48:00+09:00",
  "count": 150,
  "tagsVersion": "2026-10-06",
  "unitsVersion": "2026-10-13",
  "kinds": {"press": "보도자료", "fact": "공식 해명", "tech": "기술 해설"},
  "sources": [{"key": "sk-fact", "name": "SK하이닉스 뉴스룸 FACT", "company": "skhynix", "lang": "en",
               "page": "https://news.skhynix.co.kr/category/fact/", "channels": ["FACT"]}],
  "linkOnly": [{"name": "삼성반도체 뉴스", "url": "https://semiconductor.samsung.com/kr/news-events/news/"}],
  "years": [{"year": "2026", "file": "feed/2026.json", "count": 150}],
  "index": [{"id": "...", "date": "2026-10-08", "published": "...", "company": "samsung", "source": "samsung-newsroom",
             "kind": "press", "tags": ["실적"], "relatedUnits": ["5-6", "5-2"]}]
}
```

```json
{"year": "2026", "count": 150, "items": [{"id": "...", "title": "...", "summary": ["..."], "interview": "...", "relatedUnits": ["4-5", "2-10"]}]}
```

연도 파일의 카드 필드는 요약 카드와 같고, `checks`, `model`, `rules`, `summarizedAt`, `bodyVia`, `categories`는 넣지 않습니다. 내용이 바뀐 파일만 다시 쓰고(`generatedAt`만 바뀌는 커밋을 막기 위해), 카드가 없어진 연도 파일은 지웁니다. `python -m backend validate`가 색인·연도 파일·`data/news`가 서로 맞는지 점검합니다.

## `data/tags.json`, `data/units.json`

- `tags.json`: `groups[].tags[]`마다 `name`(표준 태그), `synonyms`(한국어 동의어), `keywords`(영문 키워드). 요약할 때 Claude에게 목록으로 주고, 받은 태그를 이 사전으로 표준 이름에 맞춥니다.
- `units.json`: `units[]`마다 `code`(예: `4-5`), `floor`, `title`, `stars`(면접 빈도 별 0~3, 6층은 0), `freq`(면접 빈도 원문), `manuscriptTags`(원고의 '관련 뉴스 태그' 그대로), `tags`(표준 태그). `theory/units/*.md`에서 `tools/build_theory.py`가 만들고, 직접 고치지 않습니다. 단원 태그를 바꾸면 `version`을 그날 날짜로 바꿉니다.
- `python -m backend validate`가 두 파일의 태그가 서로 맞는지 점검합니다.

## `backend/state/queue.json`: 요약 대기열

```json
{
  "updatedAt": "2026-10-07T07:10:04+09:00",
  "items": [
    {
      "id": "skhynix-fact-11",
      "company": "skhynix",
      "source": "sk-fact",
      "channel": "FACT",
      "kind": "fact",
      "lang": "en",
      "title": "Clarification Regarding Recent Media Reports on Solidigm",
      "url": "https://news.skhynix.com/en/fact-11/",
      "published": "2026-10-01T10:22:33+09:00",
      "date": "2026-10-01",
      "categories": ["FACT", "semiconductor industry"],
      "alsoIn": [],
      "collectedAt": "2026-10-07T07:10:02+09:00"
    }
  ]
}
```

| 필드 | 뜻 |
|---|---|
| `id` | 기사 id. 영문 주소는 `회사-주소끝부분`(예: `skhynix-fact-11`), 한글 주소는 `회사-해시10자리`(예: `samsung-3f9a0c12be`) |
| `company` | `skhynix` 또는 `samsung` |
| `source` | 처음 찾은 출처 키(`sk-fact`, `sk-tech`, `sk-press`, `samsung-newsroom`) |
| `channel` | 화면에 쓸 채널 이름: `FACT`, `TECH&AI`, `PRESS`, `보도자료`, `기술` |
| `kind` | `press`(보도자료), `fact`(공식 해명), `tech`(기술 해설·기고). 신뢰도 배지는 화면 단계에서 이 값으로 정합니다 |
| `lang` | 원문 제목의 언어. `en`이면 3단계에서 한국어로 번역하고 원제를 함께 보여 줍니다 |
| `title` | 원문 제목 그대로 |
| `url` | 원문 주소. 추적용 `?utm_...` 같은 쿼리는 지웁니다 |
| `published` | 발행 시각(한국 시간) |
| `date` | 발행 날짜(한국 시간 기준) |
| `categories` | 피드에 붙은 카테고리와 태그. 3단계 태그 분류의 참고 자료 |
| `alsoIn` | 같은 기사가 같은 뉴스룸의 다른 채널에도 올라온 경우 그 출처 키 |
| `collectedAt` | 수집한 시각 |

| `attempts`, `lastError` | 요약에 실패한 횟수와 마지막 실패 이유(실패한 적이 있을 때만). 3번 실패하면 대기열에서 뺌 |

대기열은 발행 시각이 최근인 순서로 정렬합니다. 요약이 끝난 기사는 대기열에서 빠집니다.

## `backend/state/seen.json`: 이미 본 기사

```json
{
  "backfill": {"sk-fact": {"done": true, "finishedAt": "2026-10-07"}},
  "urls": {
    "https://news.skhynix.com/en/fact-11": {
      "id": "skhynix-fact-11", "status": "queued", "title": "...", "date": "2026-10-01",
      "sources": ["sk-fact"], "checkedAt": "2026-10-07"
    }
  }
}
```

- `urls`의 키는 비교용 주소입니다(https, `www.` 없음, 한글 주소는 풀어서, 끝의 `/`와 쿼리 없음).
- `status`: `queued`(대기열에 넣음), `skipped`(삼성 뉴스룸의 문화·ESG처럼 수집 대상이 아닌 카테고리), `summarized`(요약 카드를 만듦), `failed`(3번 실패해 포기함, `reason`에 이유).
- `backfill`: 출처마다 2026년 1월까지 거슬러 올라가는 첫 채우기를 끝냈는지. 끝나기 전에는 매번 첫 페이지부터 2026년 1월까지 다시 훑고, 끝난 뒤에는 이미 본 기사가 나오는 페이지에서 멈춥니다.

## `backend/state/last-run.json`: 마지막 실행 보고서

수집 부분: 출처별 읽은 페이지 수, 새 기사 수, 카테고리로 건너뛴 수, 멈춘 이유(`stoppedBy`), 오류(`errors`), 새로 넣은 기사 목록(`added`), 대기열 크기(`queueSize`), 출처별 첫 채우기 완료 여부(`backfillDone`).

요약 부분(`summary`, `update` 실행 때): 쓴 방식(`backend`: `cli`/`api`), 모델, 한도(`limit`), 요약한 기사(`summarized`), 실패한 기사와 이유(`failed`), 포기한 기사(`gaveUp`), 인증 오류(`authError`), 사용량 한도(`limitHit`), 멈춘 이유(`stoppedBy`: `limit`, `queue done`, `time budget`, `auth error`, `usage limit`, `no credentials`, `nothing to do`), 남은 대기열(`queueLeft`).

`manifest`: 카드 수(`count`)와 이번에 manifest를 다시 썼는지(`changed`).

`errors`가 비어 있지 않거나 `summary.authError`가 참이면 GitHub Actions 실행이 실패로 표시됩니다.

## `data/theory.json`: 이론 원고 목록

`theory/` 폴더의 원고(단원별 마크다운)에서 `tools/build_theory.py`가 만듭니다. 본문은 넣지 않고 파일 경로만 담습니다. 만든 시각을 넣지 않아서 원고가 그대로면 파일도 그대로입니다.

```json
{
 "version": "2026-10-13",
 "overview": {"file": "theory/overview.md", "figures": [{"file": "theory/figures/overview-1.svg", "caption": "전체 지도 · …"}]},
 "sources": {"file": "theory/sources.md"},
 "floors": [{"floor": 0, "title": "0층 · 입문", "name": "입문", "intro": "…", "file": "theory/floors/0.md", "units": ["0-1", "0-2", "0-3", "0-4"]}],
 "units": [{
   "code": "4-5", "floor": 4, "title": "HBM: TSV로 쌓은 D램과 …", "stars": 3, "freq": "★★★(SK하이닉스 면접 최빈출)",
   "related": ["3-11", "3-12", "4-3", "4-6", "4-7"],
   "tags": ["HBM", "HBM 적층(TSV·MR-MUF)", "하이브리드 본딩"], "manuscriptTags": ["HBM4", "HBM3E", "…"],
   "file": "theory/units/4-5.md",
   "figures": [{"file": "theory/figures/4-5-1.svg", "caption": "…"}],
   "videos": [{"title": "…", "url": "https://www.youtube.com/watch?v=…", "note": "채널 · 수준. 메모"}],
   "animations": [{"file": "animations/hbm-stack.html", "title": "HBM 적층과 본딩", "modes": [{"id": "package", "label": "패키지·대역폭", "steps": 4}, "…"], "steps": 17}]
 }],
 "counts": {"units": 59, "figures": 80, "videoLinks": 111, "videoUrls": 88, "unitsWithVideos": 48, "animations": 49}
}
```

| 필드 | 뜻 |
|---|---|
| `stars`, `freq` | 단원 둘째 줄 '면접 빈도' 원문과 그 맨 앞 별 개수(괄호 안 직무별 별은 세지 않음) |
| `related` | 둘째 줄 '이어지는 단원'에 나온 단원 코드(범위 `3-1~3-10`은 펼침, 자기 자신 제외) |
| `tags` | 단원 파일 머리말의 표준 태그(기사 카드의 관련 단원 계산에 쓰는 값과 같음) |
| `figures` | 본문의 도식 순서대로. SVG는 밝은·어두운 테마를 스스로 처리함(`theory/README.md`) |
| `videos` | '영상으로 보기' 아래 링크 줄. 링크 없는 메모 줄은 넣지 않음 |
| `animations` | `animations/catalog.json`에서 같은 단원 코드를 가진 애니메이션 |

