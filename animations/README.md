# 단계별 애니메이션

이론 원고에서 흐름을 따라가야 이해되는 단원을 단계별로 움직이는 그림으로 만든 폴더입니다. 빌드 없이 정적 파일 그대로 열립니다.

| 파일 | 단원 | 내용 |
|---|---|---|
| `index.html` | | 목록(`tools/build_animation_index.py`가 catalog.json으로 만듦) |
| `semiconductor-basics.html` | 0-1 | 반도체란 무엇인가 (6단계) |
| `chip-life.html` | 0-2 | 칩의 일생 (8단계) |
| `chip-types.html` | 0-3 | 반도체의 종류: 메모리와 시스템 반도체 (모드 2개: 분류 트리, 비교·경계) |
| `chip-map.html` | 0-4 | 반도체는 어디에 쓰이나: 스마트폰과 AI 서버 (모드 3개: 칩 지도, 데이터 이동, 메모리 이름) |
| `electricity-basics.html` | 1-1 | 전기 기초: 전압·전류·저항 (6단계) |
| `capacitor.html` | 1-2 | 커패시터와 전하 (모드 3개: 충전과 저장, 용량 키우기, RC 지연·기생) |
| `energy-band.html` | 1-3 | 에너지 밴드 (모드 2개: 밴드가 생기는 과정, 도체·반도체·절연체) |
| `why-silicon.html` | 1-4 | 왜 실리콘인가 (6단계) |
| `doping.html` | 1-5 | 도핑과 캐리어 (모드 2개: N형·P형, 드리프트·확산) |
| `logic-gates.html` | 1-6 | 0과 1의 세계 (모드 2개: 스위치와 게이트, 계산과 저장) |
| `pn-junction.html` | 2-1 | PN 접합·다이오드·BJT (모드 3개: 접합과 공핍층, 바이어스와 항복, BJT) |
| `mosfet.html` | 2-2 | MOSFET 구조와 동작 (모드 2개: NMOS 켜기, PMOS) |
| `mosfet-iv.html` | 2-3 | MOSFET 특성: 선형·포화, 문턱전압, 누설 (모드 3개: 선형·포화, Vth·SS·누설, C-V 곡선) |
| `cmos-inverter.html` | 2-4 | CMOS 인버터 (모드 3개: 인버터 동작, 전력, 단면·래치업) |
| `scaling.html` | 2-5 | 미세화와 한계 (모드 3개: 무어·데나드, 단채널 효과, 해법) |
| `transistor-evolution.html` | 2-6 | 트랜지스터 구조 진화: 플래너 → FinFET → GAA → CFET (모드 2개: 네 가지 구조, GAA 만들기) |
| `memory-hierarchy.html` | 2-7 | 메모리 계층과 SRAM·DRAM (모드 3개: 메모리 계층, SRAM 6T, DRAM 1T1C) |
| `nand-flash.html` | 2-8 | NAND 플래시: 셀, 스트링, SLC~QLC (모드 3개: 셀 동작, 스트링·페이지·블록, SLC~QLC) |
| `other-devices.html` | 2-9 | 차세대 메모리·이미지센서·전력반도체 (모드 3개: 차세대 메모리, 이미지센서, 전력반도체) |
| `dram-cell.html` | 2-10 | D램 셀 읽기·쓰기·리프레시 (모드 3개: 읽기, 쓰기, 리프레시) |
| `nand-ispp.html` | 2-11 | 낸드 ISPP와 문턱전압 분포 (모드 4개: 쓰기(ISPP), 쓰기 금지, 읽기, 분포가 무너질 때) |
| `fab-intro.html` | 3-0 | 팹 입문: 8대 공정, FEOL·BEOL, 클린룸 (모드 2개: 공정 흐름, 클린룸) |
| `wafer-making.html` | 3-1 | 웨이퍼 제조: 잉곳에서 웨이퍼까지 (모드 2개: 만드는 순서, 웨이퍼 크기·구조) |
| `cleaning.html` | 3-2 | 세정: 오염원 5가지와 RCA 세정 (모드 3개: 오염원 5가지, RCA 세정, 건조) |
| `oxidation.html` | 3-3 | 산화: 건식·습식 산화와 게이트 절연막 (모드 3개: 자라는 원리, 쓰임 4가지, 평가 방법) |
| `photo.html` | 3-4 | 포토: 노광 공정 순서와 해상도 (모드 3개: 공정 순서, 해상도, EUV) |
| `plasma.html` | 3-5 | 플라즈마 기초: 식각과 증착의 공통 기반 (모드 2개: 플라즈마 만들기, 시스와 바이어스) |
| `etching.html` | 3-6 | 식각: 습식·건식, RIE, 고종횡비 (모드 3개: 습식·건식·RIE, 지표와 문제, 첨단 식각) |
| `deposition.html` | 3-7 | 증착: CVD·ALD·PVD와 에피택시 (모드 4개: 단차 피복, CVD, ALD, 응력·에피) |
| `ion-implant.html` | 3-8 | 이온주입과 열처리 (모드 3개: 원리와 장비, 손상·채널링, 열처리) |
| `metallization.html` | 3-9 | 금속배선: 다마신, 플러그, 살리사이드, HKMG (모드 4개: 구리 다마신, 텅스텐 플러그, RC 지연·EM, 살리사이드·HKMG) |
| `cmp.html` | 3-10 | CMP: 화학적·기계적 연마 (모드 2개: 필요성과 장비, 종류와 불량) |
| `eds-test.html` | 3-11 | EDS와 테스트: 웨이퍼 테스트, 리페어, 패키지 테스트 (모드 2개: EDS 6단계, 패키지 테스트·수율) |
| `packaging.html` | 3-12 | 패키징 공정: 자르고, 붙이고, 연결하고, 감싸기 (모드 3개: BGA 만들기, 플립칩, 패키지 변천) |
| `yield.html` | 3-13 | 수율·결함·계측·데이터: 공정 엔지니어가 일하는 방식 (모드 3개: 관리도·공정능력, 불량 세 종류, 수율 대응) |
| `cmos-flow.html` | 3-14 | CMOS 전체 공정 흐름: 10개 모듈로 칩 하나 완성하기 (11단계) |
| `dram-process.html` | 3-15 | D램 공정 흐름 (15단계) |
| `nand-process.html` | 3-16 | 3D 낸드 공정 흐름 (15단계) |
| `memory-test.html` | 3-17 | 메모리 테스트와 불량 분석: PE가 하는 일 (모드 2개: 테스트, 불량 분석) |
| `euv-litho.html` | 4-2 | 노광 심화: EUV, 멀티 패터닝, High-NA (모드 4개: 빛의 길, 멀티 패터닝, 확률적 결함, High-NA) |
| `dram-evolution.html` | 4-3 | D램 셀 구조 진화 (모드 3개: 셀 면적, 셀 구조, 세대 이름) |
| `nand-deep.html` | 4-4 | 낸드 심화: 300단 이상 적층과 채널홀 식각 (모드 3개: 셀 구조, 채널홀 식각, 경쟁 포인트) |
| `hbm-stack.html` | 4-5 | HBM 적층과 본딩 (모드 3개: 패키지·대역폭, TSV 만들기, 본딩 3가지) |
| `adv-packaging.html` | 4-6 | 첨단 패키징: 2.5D, 3D, 하이브리드 본딩, 칩렛 (모드 4개: 왜 필요한가, 네 가지 방식, 하이브리드 본딩, 칩렛) |
| `ai-memory.html` | 4-7 | AI 반도체와 메모리: 메모리 벽, CXL, PIM, HBF (모드 2개: 메모리 벽, 해법) |
| `company-map.html` | 5-4 | 기업 지형도: 분야별 주요 기업과 한국 기업의 위치 (모드 2개: 분야별, 한국·분석법) |
| `geopolitics.html` | 5-5 | 지정학과 정책: 보조금, 수출 통제, 관세 (모드 2개: 지역별, 연표) |
| `esg.html` | 5-7 | ESG와 안전: 전력·물·온실가스·화학물질 (모드 3개: 자원과 배출, 안전, S와 G) |
| `job-map.html` | 6-1 | 직무별 지식 지도: 내 직무에는 어떤 단원이 중요한가 (모드 3개: 직무 지도, PE 경로, 공부 순서) |
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
