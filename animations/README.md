# 단계별 애니메이션

이론 원고에서 흐름을 따라가야 이해되는 단원을 단계별로 움직이는 그림으로 만든 폴더입니다. 빌드 없이 정적 파일 그대로 열립니다.

| 파일 | 단원 | 내용 |
|---|---|---|
| `index.html` | | 목록 |
| `cmos-inverter.html` | 2-4 | CMOS 인버터: 동작·전력·단면과 래치업(모드 3개) |
| `dram-cell.html` | 2-10 | D램 셀 읽기·쓰기·리프레시(모드 3개, 저장 값 1·0 전환) |
| `nand-ispp.html` | 2-11 | 낸드 ISPP·쓰기 금지·읽기·분포 변화(모드 4개) |
| `dram-process.html` | 3-15 | D램 공정 흐름 15단계 |
| `nand-process.html` | 3-16 | 3D 낸드 공정 흐름 15단계 |
| `dram-evolution.html` | 4-3 | D램 셀 면적·구조·세대(모드 3개) |
| `hbm-stack.html` | 4-5 | HBM 패키지·TSV·본딩(모드 3개) |
| `player.js`, `player.css` | | 공통 플레이어와 스타일 |
| `catalog.json` | | 사이트가 단원 코드로 애니메이션을 찾는 목록 |

## 보는 법

`python -m http.server -d animations` 후 `http://localhost:8000`을 엽니다. ← → 키로 단계 이동, Space로 자동 재생, Home·End로 처음·끝. 모드가 있는 페이지는 `dram-cell.html#write`처럼 주소 끝에 모드를 붙여 바로 열 수 있습니다.

## 새 애니메이션 만들기

1. SVG에 바뀌는 요소마다 `id`와 `class="t"`를 붙입니다.
2. 페이지 스크립트에서 `StepPlayer.create({ root, base, steps })`를 부릅니다. 모드가 여럿이면 `modes: [{ id, label, base, steps }]`.
3. 각 단계는 `{ short, title, text, cmd, set, hl }`입니다. `set`은 그 단계부터 유지되는 상태이고, 단계 k의 그림은 base + 0..k 단계의 `set`을 차례로 합친 결과라서 어느 단계로 건너뛰어도 같은 그림이 나옵니다.
   - `s`: `data-s` 값. `off`는 숨김이고, 나머지 값(`on`, `void`, `idle` 등)은 페이지 CSS가 모양을 정합니다.
   - `style`: 인라인 스타일(주로 `transform`). CSS 전환으로 움직입니다.
   - `attr`, `text`, `num`(숫자를 세면서 바꿈).
   - 값 자리에 `(ctx) => ...` 함수를 쓰면 토글(예: 저장 값 1·0)에 따라 다시 그립니다.
4. `catalog.json`에 추가하고 `python -m pytest tests/test_animations.py`로 확인합니다.

렌더링은 헤드리스 브라우저로 단계마다 화면을 찍어 확인했습니다(밝은·어두운 테마, 폭 1280·390).
