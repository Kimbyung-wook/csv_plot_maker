# CSV Plot Maker — 요구사항 정리

CSV 데이터를 불러와 다중 subplot 그래프로 시각화하는 데스크톱 분석 도구. 아래는 지금까지 논의된 모든 요구사항을 최상위 / UI / 기능 / 운용기능 4개 범주로 정리한 것이다. (기술 스택·아키텍처·성능 전략 등 설계 배경은 문서 하단 [부록]에 유지.)

---

## 1. 최상위 요구사항

1. CSV 파일을 불러와 여러 개의 subplot으로 구성된 그래프를 그리는 데스크톱 GUI 분석 도구
2. 데이터(컬럼)를 1개 이상 중복 선택 가능 (같은 컬럼을 여러 시리즈/여러 subplot에 재사용 가능)
3. 사용자가 rows x cols 형태로 subplot grid를 자유롭게 구성 (예: 2x2)
4. 시리즈(라인)별 스타일(색상/선모양/마커/굵기)을 동적으로, 재시작 없이 즉시 변경
5. subplot별 X/Y축 라벨을 사용자가 입력
6. subplot별 이중 Y축(주축/보조축) 지원
7. 수십만~수백만 행 규모 CSV도 빠르게 로딩·렌더링

---

## 2. UI 요구사항

### 2.1 전체 레이아웃
- **Default window 구성: 좌측 = "Load CSV and View datalist" 도크, 우측 = "Configure subplot" 도크.** 중앙은 subplot grid 캔버스(`PlotGridWidget`). *(2026-08-23 확정 — 이전에 좌/우가 반대로 배치된 적이 있었는데, 사용자가 원래 의도했던 배치는 좌측 CSV/우측 설정임)*
- **창 제목에 버전/빌드일자 표시** *(2026-08-23 추가)*: `CSV Plot Maker v{버전} ({빌드일자})` 형식. `src/csv_plot_maker/_version.py`가 단일 소스 — `__version__`은 `pyproject.toml`의 버전과 맞춰 수동 관리, `BUILD_DATE`는 실행 파일(exe)을 새로 빌드할 때마다 함께 갱신
- 좌측(Load CSV and View datalist) 도크: CSV 열기, 컬럼 리스트 표시
- 우측(Configure subplot) 도크는 세 영역이 위→아래로 쌓인 구조:
  1. 상단: Rows/Cols 스핀박스만 존재 — Apply 버튼 없이 값 변경 즉시 grid 재구성(live-apply), Clear This Subplot / Clear All Subplots 버튼
     - **grid 재구성 후에도 기존 subplot들의 X축 범위(팬/줌 상태)를 그대로 유지** *(2026-08-23 추가)*: rows/cols를 바꾸면 내부적으로 모든 subplot의 PlotItem이 새로 만들어져 X 범위가 기본값(0~1)으로 초기화되는데, 재구성 직전 각 subplot의 X 범위를 위치(row, col) 기준으로 기억해뒀다가 재구성 후 그대로 복원함 — "Link X axis across subplots"가 켜져 있을 때도 동일하게 적용(재구성 도중 참조 subplot의 아직-비어있는 기본 범위가 다른 subplot에 잘못 전파되던 문제도 같이 해결됨)
  2. 중단: 활성 subplot의 X축 컬럼 선택 + Y 시리즈 목록 + 범례 표시 토글
  3. 하단: 기본적으로 숨김. Y 시리즈를 선택했을 때만 나타나며 스타일 컨트롤(색상/선모양/마커/굵기), 이중축(주/보조) 선택, 해당 시리즈 삭제 버튼을 포함

### 2.2 데이터 선택 & 컬럼 리스트
- CSV 로드 시 컬럼 목록에 원본 컬럼 외에 `Sequential`(1..N 정수) 컬럼이 최상단에 추가되어 항상 안전한 X축 대안으로 제공됨
- Ctrl+F로 컬럼 검색 팝업을 열어 목록 내 검색 및 일치 항목으로 스크롤
- Shift+Click: 마지막으로 클릭한 컬럼과 새로 클릭한 컬럼 사이 범위를 모두 선택
- Ctrl+Click: 개별 컬럼을 토글 방식으로 다중 선택
- 컬럼(단일 또는 다중 선택)을 subplot 위로 드래그&드롭하면 해당 컬럼들이 한 번에 Y 시리즈로 추가됨
- 시리즈 목록에서 Delete 키로 선택된 시리즈 제거

### 2.3 상호작용
- subplot(그래프 영역)을 클릭하면 해당 subplot이 활성 subplot으로 전환되고, 우측 패널이 그 subplot의 설정을 표시
- Y 시리즈를 선택하면 하단 스타일 패널이 나타나고, 선택 해제 시 다시 숨겨짐
- X/Y축 라벨은 그래프의 해당 축을 더블클릭하면 입력 팝업이 뜸
- **"Link X axis across subplots" 옵션** *(2026-08-23 추가)*: 우측 패널 상단(Rows/Cols 아래)의 체크박스. 켜면 어느 한 subplot에서 팬/줌으로 X축 범위를 바꿀 때 다른 모든 subplot의 X축 범위도 동일하게 맞춰짐(각 subplot의 Y축은 그대로 유지). 레이아웃 저장/불러오기 시 이 설정도 함께 저장됨

### 2.4 CSV 로딩 중 상태 표시 *(2026-08-23 추가, 같은 날 Cancel 버튼 제거)*
- 큰 CSV는 컬럼 목록이 즉시 뜬 뒤에도 실제 데이터 파싱이 끝나기 전까지 subplot에 드래그&드롭해도 시리즈가 추가되지 않음(파싱된 데이터가 아직 없기 때문) — 이 경우 상태 표시줄에 "Still loading the CSV -- please wait before adding series" 메시지로 안내
- 로딩 중에는 "Loading CSV data..." 진행 팝업(바쁨 표시, 진행률 미표시)이 즉시 뜨고, 로딩이 끝나면 자동으로 사라짐
- **Cancel 버튼 없음**: 원래는 있었으나 제거함 — polars의 `read_csv`는 한 번의 블로킹 호출이라 파싱 자체를 중간에 강제로 멈출 수 없어서, 있었던 Cancel도 실제로는 "결과를 기다리지 않고 무시"하는 소프트 취소일 뿐 로딩 시간을 줄여주지 못했음. 혼란만 줄 뿐 실질적 이득이 없다고 판단해 삭제(팝업 자체는 진행 상태 안내 용도로 유지, ESC/닫기로도 닫히지 않음)

### 2.5 이중 Y축 UI
- subplot은 기본적으로 단일(주) Y축만 사용
- 이중축 선택 UI(주/보조 axis combo)는 "시리즈가 2개 이상"일 때가 아니라, **선택된 시리즈의 axis가 이미 secondary로 설정되어 있거나 시리즈가 2개 이상**일 때만 노출 (단일 시리즈라도 이미 secondary로 지정했다면 계속 보여야 재변경 가능하므로)
- **우측(보조) Y축의 눈금·grid는 그 subplot에 secondary axis로 배정된 시리즈가 하나라도 있을 때만 표시** *(2026-08-23 수정)*. 근본 원인은 pyqtgraph의 `PlotItem.setLabel()`이 라벨이 빈 문자열이어도 항상 해당 축을 `showAxis()`로 강제 표시하는 부수효과였음 — X 라벨 편집, 시리즈 추가 등 축 라벨을 다시 세팅하는 모든 replot 경로에서 매번 우측 축이 되살아나고 있었음. 라벨을 세팅한 직후 축 표시 상태를 다시 계산해 되돌리는 방식으로 수정

### 2.6 범례(Legend)
- 표시/숨김 토글 가능 (기본 표시)
- 배경은 투명이 아니라 **현재 테마 배경색과 동일한 완전 불투명 박스 + 테두리**로 표시 — 반투명이면 겹치는 grid/곡선이 비쳐 보여 가독성이 떨어지므로 alpha 없이 배경색 그대로 채움
- 텍스트 색상은 Dark/Light 테마 전환 시 함께 recolor
- **subplot에 시리즈가 하나도 없으면(빈 그래프) 범례는 토글 상태와 무관하게 자동으로 숨김** — 빈 박스만 떠 있는 상태 방지
- **grid/곡선이 범례 위로 겹쳐 그려지지 않도록 항상 최상단에 렌더링** *(2026-08-23 수정)*. pyqtgraph에서 grid는 ViewBox와 형제 관계인 축 아이템이 그리고, ViewBox가 축보다 먼저 씬에 추가되어 기본값으로는 축(grid)이 ViewBox의 모든 자식(곡선, 범례)보다 위에 그려짐 — 축 아이템의 z-value를 낮춰 grid를 항상 배경으로 고정하고, 범례의 z-value는 ViewBox 내부에서 가장 높게 두어 나중에 추가되는 곡선에도 항상 덮이지 않게 함

### 2.7 subplot 간 좌측 축 정렬 *(2026-08-23 추가)*
- 같은 grid 안의 subplot들은 Y축 눈금 값의 자릿수가 서로 달라도(예: 하나는 0~1, 다른 하나는 0~1,000,000) **좌측 축의 폭을 모두 동일하게 맞춰** 그래프 영역의 좌측 벽이 세로로 정렬되도록 함
- Y축 범위가 바뀌거나(줌/팬/데이터 갱신) grid가 재구성될 때마다, 각 subplot의 좌측 축이 실제로 필요로 하는 폭 중 최댓값을 다시 계산해 모든 subplot에 동일하게 적용
- **폭 재계산은 실제 tick 그리기 연산을 강제로 한 번 실행해서 얻은 값 사용** *(2026-08-23 보강)*: pyqtgraph의 AxisItem은 Qt가 실제로 paint()를 호출해줘야만 "지금 눈금 텍스트에 필요한 폭"을 갱신하는데, 줌/데이터 변경 직후 이 폭을 바로 읽으면 아직 그 paint가 안 일어나 이전(더 작은) 폭 값을 읽어올 수 있음 — 한 번 폭을 고정(pin)하면 이후로는 자동 재계산이 멈추는 pyqtgraph 특성과 겹치면 영구적으로 너무 좁게 고정될 위험이 있어, 매번 그리기 연산을 직접 한 번 실행해 최신 폭을 강제로 갱신한 뒤 읽음
- **Y축 눈금 밀도(tick density) 상향** *(2026-08-23 추가)*: subplot을 여러 개 세로로 쌓으면(grid rows가 많을수록) 각 subplot의 세로 픽셀 높이가 줄어들고, pyqtgraph는 축 길이가 짧을수록 눈금 개수를 적극적으로 줄여서 — 눈금이 "0"과 "10" 두 개만 표시되고 실제 보이는 데이터 범위(예: 수백~수천 단위)의 상당 부분에는 라벨이 전혀 안 붙는 것처럼 보이는 문제가 있었음. 모든 축에 `setTickDensity(1.75)`를 적용해 좁은 subplot에서도 범위 전체를 충분히 읽을 수 있을 만큼 눈금이 나오도록 함

### 2.8 테마
- Settings 메뉴 → Theme 서브메뉴에서 Light mode / Dark mode / System mode 중 택1 (배타적 선택)
- 테마 전환 시 배경/전경/축/범례 색상이 모두 함께 갱신

### 2.9 Info 메뉴 — 라이선스 안내 *(2026-08-23 추가)*
- 메뉴바에 **Info → License Info**로 팝업(`LicenseDialog`)을 띄움
- 내용: 앱 버전/빌드일자, 번들된 서드파티 라이브러리별 라이선스 표(PySide6/shiboken6=LGPL-3.0-only, pyqtgraph=MIT, polars=MIT, NumPy=BSD-3-Clause), 그리고 **사내/상업적 사용 관련 안내**: PySide6는 LGPLv3라 동적 링크(이 프로젝트의 PyInstaller `--onedir` 빌드가 이 조건에 해당)를 유지하면 소스 공개 없이 사내/상업적 배포가 가능하다는 요지와, 이는 법률 자문이 아니므로 조직 외부·대규모 배포 시 라이선스 조건을 다시 확인하라는 면책 문구
- 이 앱 자체(csv-plot-maker)의 라이선스는 별도로 지정하지 않았음을 명시

### 2.10 저장/불러오기 진입점 (File 메뉴)
- Save Layout: CSV 파일명 기반 고정 경로에 JSON으로 저장
- Save Layout As...: 사용자가 파일명을 직접 선택해 저장 (기본값 = CSV 이름)
- Load Layout: 저장된 JSON을 불러와 현재 프로젝트를 대체
- **Load Layout As...** *(2026-08-23 추가)*: 파일 선택 다이얼로그로 **임의의** 레이아웃 JSON을 골라 현재 열려있는 CSV에 적용. 레이아웃 JSON은 컬럼을 이름(문자열)으로만 참조하므로 원래 저장했던 CSV가 아닌 다른 CSV에도 재사용 가능 — 단, 현재 CSV에 없는 컬럼을 참조하는 시리즈는 조용히 걸러내고(해당 subplot의 X 컬럼도 현재 CSV의 첫 컬럼으로 대체), 상태 표시줄에 몇 개가 제외됐는지 안내. 불러온 프로젝트의 `csv_path`는 항상 지금 열려있는 CSV로 재설정되어, 그 이후 Save Layout은 원래 레이아웃 파일이 아니라 현재 CSV 기준 경로에 저장됨

---

## 3. 기능 요구사항

### 3.1 CSV 로딩
- 컬럼 목록은 전체 파싱 없이 스키마만 즉시(near-instant) 조회해서 표시
- 전체 데이터 파싱은 3단계 폴백으로 처리 (속도와 정확성의 균형):
  1. polars 기본 샘플 기반 스키마 추론으로 우선 시도 (빠름 — 대다수의 정상적인 CSV는 이 경로로 처리)
  2. 실패 시 `infer_schema_length=None`으로 전체 행을 스캔해 재시도 — 앞부분 몇백 행은 정수처럼 보이다 뒤에서 소수점 값이 나오는 컬럼(예: `EGI_TX.GnssVelUncertainty`) 등, 샘플 추론으로는 못 잡아내는 dtype 문제를 해결. 다만 파일 전체를 훑어야 하므로 1번보다 느림
  3. 그래도 실패하면 `ignore_errors=True`까지 추가해 문제 셀만 null로 처리하고 로드를 완주
  - *(2026-08-23 확정 — 이전엔 매번 2번부터 시작해 정상 CSV도 느려졌던 것을 1번 우선 시도로 되돌려 정상 케이스의 로딩 속도를 회복)*
- 다른 CSV 파일을 열면 이전에 열려있던 CSV의 subplot 구성/시리즈는 모두 초기화됨 (컬럼 스키마가 다른 파일 간 충돌 방지). 단, 새로 여는 CSV와 같은 이름의 저장된 레이아웃(JSON)이 있으면 그것을 자동 로드

### 3.2 시리즈/스타일
- 시리즈별 색상, 선 스타일(solid/dash/dot/dashdot/**none**), 마커 종류, 선 굵기를 독립적으로 설정
- "None" 선 스타일 선택 시 선을 그리지 않고 마커만 표시(점만 찍는 산점도 형태)
- 모든 마커는 테두리(outline) 없이 채움만 표시
- 스타일 변경은 데이터 재전송 없이 해당 시리즈만 즉시(setPen/setSymbol) 갱신되어 대용량에서도 지연 없음

### 3.3 이중 Y축
- 시리즈별로 주축(primary)/보조축(secondary) 배정 가능, 두 축은 독립적으로 스케일링
- 보조축을 쓰는 시리즈가 하나라도 있으면 우측 축이 자동으로 표시되고, 없으면 숨겨짐

### 3.4 데이터 무결성
- `Sequential` 컬럼은 CSV 실제 데이터를 건드리지 않는 합성 컬럼(1..row_count)으로, timestamp 등 원본 X 후보가 없거나 손상됐을 때의 안전한 대안
- **기본 X 컬럼은 `timestamp`** *(2026-08-23 추가)*: CSV 로드 시(그리고 grid 크기 변경으로 새 subplot이 생길 때) 각 subplot의 X 컬럼 초기값은 `timestamp` 컬럼이 존재하면 그것으로, 없으면(컬럼명이 다르거나 숫자/시간으로 파싱되지 않는 경우) `Sequential`로 자동 지정

---

## 4. 운용기능 요구사항

- **Save Layout / Save Layout As... / Load Layout / Load Layout As...**: subplot 구성(그리드 크기, 각 subplot의 X컬럼/라벨/범례 표시 여부/시리즈 목록과 스타일)을 JSON으로 직렬화. 기본 경로는 CSV 파일명 기반(`<csv 이름>.json`). 컬럼을 이름으로만 참조하는 범용 포맷이라 Load Layout As...로 다른 CSV에도 재사용 가능(없는 컬럼은 자동으로 걸러짐)
  - **JSON 파일 자체에는 `csv_path`를 저장하지 않음** *(2026-08-23 정리)*: 어느 CSV에서 저장했는지는 런타임 상태일 뿐 레이아웃의 일부가 아니고, 실제로도 로드 시 항상 현재 열려있는 CSV 경로로 즉시 덮어써져서 한 번도 "이 값으로 CSV를 자동으로 연다"는 용도로 쓰인 적이 없었음 — 파일에 남겨두면 마치 그런 용도가 있는 것처럼 오해를 줄 뿐이라 직렬화에서 제외. 예전 파일에 남아있는 `csv_path` 키는 무시하고 무해하게 로드됨(하위호환)
- **Clear This Subplot**: 현재 활성 subplot의 시리즈/라벨만 초기화
- **Clear All Subplots**: 모든 subplot을 동시에 초기화
- **Ctrl+F 컬럼 검색**: 컬럼이 매우 많은 CSV에서 원하는 컬럼을 빠르게 찾기 위한 팝업 검색
- **Shift/Ctrl 다중 선택 + 드래그&드롭**: 여러 컬럼을 한 번의 드래그로 한 subplot에 동시에 시리즈로 추가해 반복 작업을 줄임
- **Delete 키 시리즈 삭제**: 마우스로 스타일 패널의 삭제 버튼을 누르지 않고도 목록에서 바로 삭제

---

## 부록 A. 기술 스택 (결정 및 근거)

| 영역 | 선택 | 근거 |
|---|---|---|
| 언어 | Python 3.11+ | 데이터 처리·시각화 생태계, 빠른 개발 속도 |
| GUI | PySide6 (Qt for Python) | LGPLv3, 데스크톱 네이티브 반응성, 풍부한 위젯 |
| 플로팅 | pyqtgraph | OpenGL 가속, `setDownsampling`/`setClipToView`로 대용량 인터랙션 처리, `GraphicsLayoutWidget`으로 임의 grid 구성, `ViewBox` 기반 이중 Y축, pen/symbol 변경이 즉시 반영되어 동적 스타일 요구사항에 최적 |
| CSV 파싱 | polars | 멀티스레드 Rust 파서, `scan_csv().collect_schema()`로 컬럼 목록 즉시 조회, `infer_schema_length` 조절로 속도/정확성 트레이드오프 제어 가능 |

matplotlib은 스타일 변경마다 사실상 전체 캔버스 재드로우가 필요해 대용량+동적 스타일 요구사항과 상충하여 채택하지 않음.

## 부록 B. 아키텍처

```
csv_plot_maker/
  src/csv_plot_maker/
    data/
      loader.py            # polars 기반 CSV 로딩 (스키마 peek + 3단계 폴백 전체 로드)
      column_store.py      # {컬럼명: numpy array} 캐시
    models/
      series.py            # Series: id, y_column, axis, color, line_style, marker, width
      subplot.py            # SubplotConfig: row, col, x_column, labels, show_legend, series[]
      project.py             # ProjectState: csv_path, grid_rows, grid_cols, active_subplot_id, subplots[]
      serialization.py       # JSON 저장/불러오기
    ui/
      main_window.py        # QMainWindow: 좌측 CSV 도크 + 중앙 캔버스 + 우측 설정 도크
      csv_panel.py            # CSV 열기, 컬럼 리스트(검색/다중선택/드래그)
      grid_config_panel.py    # rows/cols + 활성 subplot + Clear 버튼
      series_panel.py          # X 컬럼, 시리즈 목록, 범례 토글
      style_panel.py            # 선택된 시리즈의 색상/스타일/마커/굵기/축/삭제
      theme.py                   # Light/Dark/System 팔레트
    plotting/
      plot_grid_widget.py    # GraphicsLayoutWidget 래핑, 클릭/드롭/축더블클릭 시그널
      subplot_view.py          # PlotItem + 보조 ViewBox, 시리즈 증분 갱신, 범례/테마 처리
      style_map.py               # Style -> QPen/symbol 변환
  tests/
```

- `data/`, `models/`는 Qt 비의존 순수 로직 → 단위 테스트 용이
- X축 컬럼은 시리즈가 아닌 subplot 단위로 공유
- 증분 렌더링 원칙: 스타일 변경은 `setPen`/`setSymbol`만, 라벨 변경은 `setLabel`만, 시리즈 추가/변경은 해당 시리즈만 `setData`, grid 크기 변경만 구조적 재구성

## 부록 C. 성능 전략

1. CSV 열기 시 `scan_csv().collect_schema()`로 컬럼 목록 즉시 표시
2. 전체 파싱은 3단계 폴백(기본 샘플 추론 → 전체 스캔 → ignore_errors)으로 정상 케이스의 속도와 이상 케이스의 안정성을 동시에 확보
3. `setDownsampling(auto=True, method='peak')`, `setClipToView(True)`로 화면에 보이는 범위만 실제 렌더링
4. 원본 numpy 데이터는 항상 전체 보존 — 다운샘플링은 렌더링 시점 연산일 뿐

## 부록 D. 검증 방법

- **자동화**: `data/loader.py`(엣지케이스 CSV로 `ColumnStore` 검증, 스키마 추론 폴백 검증), `models/`(상태 전이 단위 테스트), 시그널 배선은 헤드리스 스크립트(`QT_QPA_PLATFORM=offscreen`)로 실제 신호/슬롯 호출 검증
- **수동/시각적**: 렌더링, 이중축 정렬, 테마 전환, 범례 표시/숨김은 스크린샷 캡처로 육안 확인
- **성능**: 합성 대용량 CSV(수십만~수백만 행)로 로딩 시간 및 팬/줌 반응성 확인
