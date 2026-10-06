# 데이터 형식

수집기(`backend/`)가 만드는 파일의 형식입니다. 지금은 2단계(수집)까지 만들어져 있어서, 기사는 `backend/state/queue.json`의 요약 대기열에 쌓입니다. 3단계(요약·번역·태그 분류)가 대기열에서 기사를 꺼내 사이트에 보여 줄 파일로 만듭니다.

## 저장 원칙

- 기사마다 제목, 링크, 발행 시각, 피드의 카테고리만 저장합니다.
- RSS 피드에 들어 있는 기사 본문(`description`, `content:encoded`)은 저장하지 않습니다. 요약은 3단계에서 원문을 읽어 직접 씁니다.

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

대기열은 발행 시각이 최근인 순서로 정렬합니다.

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
- `status`: `queued`(대기열에 넣음), `skipped`(삼성 뉴스룸의 문화·ESG처럼 수집 대상이 아닌 카테고리). 3단계부터 `summarized`가 추가됩니다.
- `backfill`: 출처마다 2026년 1월까지 거슬러 올라가는 첫 채우기를 끝냈는지. 끝나기 전에는 매번 첫 페이지부터 2026년 1월까지 다시 훑고, 끝난 뒤에는 이미 본 기사가 나오는 페이지에서 멈춥니다.

## `backend/state/last-run.json`: 마지막 실행 보고서

출처별 읽은 페이지 수, 새 기사 수, 카테고리로 건너뛴 수, 멈춘 이유(`stoppedBy`), 오류(`errors`), 새로 넣은 기사 목록(`added`), 대기열 크기(`queueSize`), 출처별 첫 채우기 완료 여부(`backfillDone`)가 들어 있습니다. `errors`가 비어 있지 않으면 GitHub Actions 실행이 실패로 표시됩니다.
