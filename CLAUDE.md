# 반도체 뉴스 트래커 (semicon-tracker)

삼성전자·SK하이닉스 공식 뉴스룸 소식을 한국어로 요약하는 시장 흐름 페이지와, 반도체 기초를 비전공자 눈높이로 설명하는 이론 공부(0~6층 59단원, 도식, 단계 애니메이션, 영상)를 함께 둔 반도체 면접 준비용 정적 사이트(https://semicon-tracker.vercel.app/). 설명과 커밋 메시지는 한국어로 쓴다.

## 상황별로 볼 문서
- 구조, 수집·요약 방식, 자동 실행, 배포: `README.md`
- `data/` 아래 JSON(카드, 기사 페이지, manifest, 태그, 단원)을 만들거나 고칠 때: `docs/DATA_SCHEMA.md`
- 이론 원고(`theory/`)를 고칠 때: `theory/README.md`
- 애니메이션·영상(`animations/`)을 만들거나 고칠 때: `animations/README.md`
- 한국어 글(카드·기사 페이지, 이론 원고와 도식 글자, 애니메이션 설명·자막, 화면 문구, backend 프롬프트)을 쓰거나 고칠 때: `.claude/skills/humanize-korean-site/SKILL.md` (im-not-ai 문체 규칙)

## 반드시 지킬 것
- 사실·수치는 원문(공식 뉴스룸, 원고의 반영 자료)에 있는 것만. 기사 본문은 저장하지 않고 제목·링크·날짜·직접 쓴 요약만 둔다. 한국어 기사의 제목은 원제 그대로다.
- 글을 고친 뒤 `python3 tools/style_check.py --spans`로 'AI 티' 신호를 확인하고 걸린 문장만 고친다. 연결어미(-고/-며/-지만/-면서/-아서/-어서) 바로 뒤 쉼표는 `python3 tools/style_check.py --fix-c11`이 지운다(테스트가 0건을 확인). 기사 제목·소제목에 "X: Y" 콜론 부제를 쓰지 않는다.
- 고친 곳에 맞춰 다시 만든다: 카드 → `python -m backend publish`, 원고 → `python tools/build_theory.py`, 애니메이션 목록 → `python tools/build_animation_index.py`. 그다음 `python -m backend validate`와 `python -m pytest tests -q`가 모두 통과해야 커밋한다.
- 큰 변경은 브랜치와 PR로. `main`에는 하루 4번 자동 커밋(`semicon-tracker-bot`)이 올라오므로 직접 푸시하지 않는다.
- 토큰·API 키는 GitHub Secrets에만. 요약은 구독 토큰(`CLAUDE_CODE_OAUTH_TOKEN`)을 쓰고 릴리스 레이더와 사용량을 나눠 쓴다.

## 함정
- 빌드 없는 정적 사이트다. 화면은 `index.html` 한 파일이고 데이터는 `fetch`로 읽는다. 로컬 확인은 `python3 -m http.server 8000` (파일로 직접 열면 `data/`를 못 읽음).
- 만들어지는 파일은 손으로 고치지 않는다: `data/manifest.json`·`data/feed/<연도>.json`(카드에서), `data/theory.json`·`data/units.json`(원고에서), `animations/index.html`(`catalog.json`에서).
- 따옴표 안 글(발언 인용, 행사·제품 이름)과 링크 글자(영상·자료 제목)는 문체 점검에서 빠지고 고치지도 않는다. 원고 단원 제목·절 제목과 애니메이션 단계 제목("ACT: …")의 콜론은 교재 절 제목이라 그대로 둔다.
- 자동 요약(`backend/digest.py`, `backend/detail.py`)은 쓴 뒤 `backend/humanize.py`로 문체를 한 번 더 다듬는다. 수치·영문 표기·따옴표 안 글이 바뀐 수정은 버리므로, 프롬프트를 고쳐도 수치 점검(`backend/guard.py`)은 그대로 통과해야 한다.
- `.claude/skills/humanize-korean-site/references/quick-rules.md`는 im-not-ai 원본을 통째로 복사한 파일이라 직접 고치지 않는다(테스트가 해시를 확인). 원본이 바뀌면 통째로 다시 복사하고 테스트의 해시를 바꾼다.
