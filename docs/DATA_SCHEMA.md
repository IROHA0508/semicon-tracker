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
| `summarizedAt`, `model` | 요약한 시각과 모델 |
| `bodyVia` | 본문을 읽은 곳: `feed`(RSS 본문) 또는 `page`(기사 페이지) |
| `checks` | 점검 기록(있을 때만). `retriedFor`: 다시 쓰게 한 수치, `removed`: 수치가 원문과 안 맞아 지운 문장, `unknownTags`: 표준 태그가 아니라 버린 태그 |

## `data/manifest.json`: 사이트가 읽는 목록

요약 카드 전체를 발행 시각이 최근인 순서로 담고, 카드마다 `relatedUnits`(관련 이론 단원 코드 최대 2개)를 붙입니다. 관련 단원은 만들 때마다 `data/units.json`으로 다시 계산합니다(태그가 많이 겹치는 단원 → 면접 빈도 별이 많은 단원 → 번호가 큰 단원).

```json
{
  "generatedAt": "2026-10-12T07:16:40+09:00",
  "count": 10,
  "tagsVersion": "2026-10-06",
  "unitsVersion": "2026-10-06",
  "kinds": {"press": "보도자료", "fact": "공식 해명", "tech": "기술 해설"},
  "sources": [{"key": "sk-fact", "name": "SK하이닉스 뉴스룸 FACT", "company": "skhynix", "lang": "en",
               "page": "https://news.skhynix.co.kr/category/fact/", "channels": ["FACT"]}],
  "linkOnly": [{"name": "삼성반도체 뉴스", "url": "https://semiconductor.samsung.com/kr/news-events/news/"}],
  "items": [{"id": "...", "title": "...", "summary": ["..."], "tags": ["..."], "relatedUnits": ["4-5", "2-10"]}]
}
```

카드 필드 중 `checks`, `model`, `summarizedAt`, `bodyVia`, `categories`는 manifest에 넣지 않습니다. 내용이 바뀌지 않으면 파일을 다시 쓰지 않습니다(`generatedAt`만 바뀌는 커밋을 막기 위해).

## `data/tags.json`, `data/units.json`

- `tags.json`: `groups[].tags[]`마다 `name`(표준 태그), `synonyms`(한국어 동의어), `keywords`(영문 키워드). 요약할 때 Claude에게 목록으로 주고, 받은 태그를 이 사전으로 표준 이름에 맞춥니다.
- `units.json`: `units[]`마다 `code`(예: `4-5`), `floor`, `title`, `stars`(면접 빈도 별 1~3), `freq`, `tags`(표준 태그).
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
