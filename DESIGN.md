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
     - **grid 재구성 후에도 기존 subplot들의 X축 범위(팬/줌 상태)를 그대로 유지** *(2026-08-23 추가)*: rows/cols를 바꾸면 내부적으로 모든 subplot의 PlotItem이 새로 만들어져 X 범위가 기본값(0~1)으로 초기화되는데, 재구성 직전 각 subplot의 X 범위를 위치(row, col) 기준으로 기억해뒀다가 재구성 후 그대로 복원함 — "Link X axis across subplots"가 켜져 있을 때도 동일하게 적용(재구성 도중 참조 subplot의 아직-비어있는 기본 범위가 다른 subplot에 잘못 전파되던 문제도 같이 해결됨). 단, 아직 시리즈가 하나도 없는(빈) subplot은 범위를 기억/복원 대상에서 제외 — 안 그러면 그 의미 없는 기본 범위가 고정돼버려서, 나중에 그 subplot에 데이터를 넣어도 자동 범위 조정이 다시는 안 되는 문제가 있었음
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
- **내부 여백 축소** *(2026-08-24 추가)*: pyqtgraph `LegendItem`의 기본값(사방 9px 여백 + 색상 스와치-텍스트 간 5px)은 subplot 하나짜리 큰 그래프에는 적당하지만, grid에 subplot이 여러 개 있어 각 subplot이 작아지면 범례 박스가 그래프 대비 상대적으로 과도하게 커 보임 — 여백을 사방 4px, 스와치-텍스트 간격을 3px로 줄임
- **범례 글자 크기 옵션 (Small/Medium/Large)** *(2026-08-24 추가)*: Settings 메뉴 → Legend Font Size 서브메뉴에서 3단계(7pt/9pt/11pt, 기본 Medium=9pt) 중 택1. Theme 설정과 동일하게 앱 전역(모든 subplot에 동시 적용) 설정이며 저장 레이아웃(JSON)에는 포함되지 않는 런타임 전용 설정. pyqtgraph의 `LegendItem.setLabelTextSize()`는 각 항목의 저장된 옵션만 바꿀 뿐 이미 그려진 텍스트를 다시 렌더링하지 않으므로(테마 전환 시 텍스트 색상 갱신에 썼던 것과 동일한 재렌더링 트릭으로) 각 라벨에 대해 `setText()`를 다시 호출해 실제로 반영되게 함
- **버그: 같은 글자 크기를 반복 선택하면 범례 박스가 계속 작아짐** *(2026-08-25 발견 및 수정)*: 위 항목의 최초 구현은 크기 변경 후 pyqtgraph 자신의 `LegendItem.updateSize()`를 호출했는데, 이 메서드가 각 항목의 *현재* `item.width()`/`height()`만 합산할 뿐 레이아웃에 설정해 둔 `contentsMargins`(여백 축소 항목 참고)를 전혀 반영하지 않는다는 결함이 있었음 — 그 결과 박스를 "필요한 만큼보다 여백만큼 항상 더 좁게" 설정하게 되고, 이후 아이템들이 그 좁아진 박스 안에 억지로 맞춰지며 실제로 작아진 채 다음 계산의 입력값이 되는 식으로 반복 호출할 때마다 조금씩 더 줄어드는 구조였음(자기 자신이 만든 결과를 다시 입력으로 쓰는 전형적인 ratchet). `SubplotView._resize_legend_to_fit()`을 새로 만들어, 각 항목의 `effectiveSizeHint(PreferredSize)`(현재 지오메트리와 무관하게 텍스트 고유의 "필요한" 크기)로 직접 계산하고 margin을 더해 박스 크기를 매번 처음부터 다시 확정하도록 교체 — 같은 크기를 몇 번을 눌러도 항상 동일한 값으로 수렴함

### 2.7.1 subplot 열(column) 폭 산정 방식 재설계 *(2026-08-25 재설계)*
- **버그: column을 2개 이상으로 늘린 뒤 데이터를 드래그 앤 드랍하면, 방금 드롭한 바로 그 subplot의 폭이 오히려 좁아짐** — grid 안 어딘가에 이중 Y축을 쓰는 subplot이 있을 때만 재현됨. 원인 추적 결과, `setColumnStretchFactor`(2.7 항목 참고)로 균등 배분되는 것은 각 열의 "최소 크기를 넘는 여유 공간"뿐이고, 어느 한 열의 최소 크기(왼쪽 축이 더 넓어지거나, 이중 Y축이 새로 생기는 등)가 커지면 Qt의 `QGraphicsGridLayout`이 내부적으로 최소/선호/최대 크기를 함께 고려해 압축polated된 공간 배분 계산을 하면서, 관련 없는 *다른* 열에서 픽셀을 가져와 재분배하는 경우가 실측으로 확인됨(예: 2열 그리드에서 한쪽 열의 왼쪽 축 폭이 커졌더니, 정작 커진 열이 아니라 반대쪽 열이 넓어지고 커진 열 쪽이 오히려 좁아짐). stretch factor 기반 자동 배분을 신뢰할 수 없다고 판단해 폐기
- **수정**: `PlotGridWidget._sync_column_widths()`를 새로 만들어 각 열의 폭을 직접 계산해 `setColumnFixedWidth()`로 고정. 계산식은 `열의 폭 = (좌측 축 공통 폭 + 그 열의 우측 축 폭) + (여유 공간 ÷ 열 개수)`이며, 여유 공간은 `현재 뷰포트 폭 - 모든 열의 축 폭 합계`로 산출 — 이제 한 열의 축 폭이 늘어나도 그 변화는 오직 그 열 자신의 몫에서만 반영되고 다른 열의 몫을 건드리지 않음
- **버그: 위 수정 직후, 창 크기를 실제로 바꿔도 열 폭이 엉뚱하게 반응(창을 키워도 거의 안 커지고, 줄여도 오히려 커짐)** *(2026-08-25 발견 및 수정)*: "여유 공간" 계산에 쓸 "현재 뷰포트 폭"을 처음엔 `self.ci.geometry().width()`(GraphicsLayoutWidget 내부의 central item 지오메트리)로 읽었는데, `setColumnFixedWidth()`를 호출하면 그 레이아웃 자신의 최소 크기가 (적어도) 설정한 열 폭의 합만큼 올라가고, `QGraphicsWidget`은 자신의 지오메트리를 레이아웃 최소 크기 아래로는 절대 줄이지 않으므로 — 한 번이라도 동기화가 실행된 뒤에는 `ci.geometry()`가 위젯의 실제 크기가 아니라 "직전에 우리가 직접 써넣은 값"을 반사하는 자기참조적 상태가 되어 버림. 창을 줄여도 그 값이 못 따라 내려가고, 다음 동기화가 그 부풀려진 값을 다시 입력으로 써서 계속 커지기만 하는 구조였음 — 외부에서 실제로 결정되는 크기인 `self.viewport().width()`로 교체해 해결
- **창 크기 변경 시에도 열 폭이 다시 계산되도록 `PlotGridWidget.resizeEvent()` 추가** *(2026-08-25, 위와 함께)*: 열 폭을 Qt의 stretch factor 대신 고정 픽셀 값으로 직접 관리하게 되면서, 기존에는 stretch factor가 "공짜로" 처리해주던 창/도크 크기 변경 대응을 직접 챙겨야 하게 됨 — 위젯 리사이즈마다 `schedule_axis_width_sync()`를 호출해 새 뷰포트 크기에 맞춰 다시 계산하도록 함
- **버그: 2번째 이상 열의 이중 Y축 title이 안 보임** *(2026-08-25 발견 및 수정)*: 위 재설계로 열 폭을 `합계 = 뷰포트 폭`이 되도록 직접 계산했는데, `GraphicsLayout`이 자체적으로 갖고 있는 바깥쪽 여백(상하좌우 9px)과 열 사이 간격(6px)을 전혀 고려하지 않은 채 계산했음 — 그 결과 레이아웃이 실제로 필요로 하는 전체 크기(열 합계 + 여백 + 간격)가 뷰포트보다 매번 정확히 그 여백/간격만큼(2열 기준 24px) 더 커졌고, `ci`(central item)는 자기 레이아웃의 최소 크기보다 작아질 수 없다는 특성상 뷰포트 밖으로 그만큼 넘쳐버렸음. 눈금 숫자는 넘친 폭 안에 다 들어가서 멀쩡히 보였지만, 그보다 더 오른쪽에 그려지는 title 텍스트(`_TITLE_GUTTER`만큼 눈금 뒤에 위치)만 정확히 뷰포트 밖으로 잘려나가 안 보이는 것으로 확인됨 — 여러 subplot 스크린샷으로 직접 렌더링을 캡처해 픽셀 단위로 확인. `_sync_column_widths()`가 열에 나눠줄 공간을 계산하기 전에 `ci.layout.getContentsMargins()`와 `horizontalSpacing()`만큼을 뷰포트 폭에서 먼저 빼도록 수정

### 2.7 subplot 간 좌측 축 정렬 *(2026-08-23 추가)*
- 같은 grid 안의 subplot들은 Y축 눈금 값의 자릿수가 서로 달라도(예: 하나는 0~1, 다른 하나는 0~1,000,000) **좌측 축의 폭을 모두 동일하게 맞춰** 그래프 영역의 좌측 벽이 세로로 정렬되도록 함
- Y축 범위가 바뀌거나(줌/팬/데이터 갱신) grid가 재구성될 때마다, 각 subplot의 좌측 축이 실제로 필요로 하는 폭 중 최댓값을 다시 계산해 모든 subplot에 동일하게 적용
- **폭 재계산은 실제 tick 그리기 연산을 강제로 한 번 실행해서 얻은 값 사용** *(2026-08-23 보강)*: pyqtgraph의 AxisItem은 Qt가 실제로 paint()를 호출해줘야만 "지금 눈금 텍스트에 필요한 폭"을 갱신하는데, 줌/데이터 변경 직후 이 폭을 바로 읽으면 아직 그 paint가 안 일어나 이전(더 작은) 폭 값을 읽어올 수 있음 — 한 번 폭을 고정(pin)하면 이후로는 자동 재계산이 멈추는 pyqtgraph 특성과 겹치면 영구적으로 너무 좁게 고정될 위험이 있어, 매번 그리기 연산을 직접 한 번 실행해 최신 폭을 강제로 갱신한 뒤 읽음
- **Y축 눈금 밀도(tick density) 상향** *(2026-08-23 추가)*: subplot을 여러 개 세로로 쌓으면(grid rows가 많을수록) 각 subplot의 세로 픽셀 높이가 줄어들고, pyqtgraph는 축 길이가 짧을수록 눈금 개수를 적극적으로 줄여서 — 눈금이 "0"과 "10" 두 개만 표시되고 실제 보이는 데이터 범위(예: 수백~수천 단위)의 상당 부분에는 라벨이 전혀 안 붙는 것처럼 보이는 문제가 있었음. 모든 축에 `setTickDensity(1.75)`를 적용해 좁은 subplot에서도 범위 전체를 충분히 읽을 수 있을 만큼 눈금이 나오도록 함
- **Y축 title 여백은 반응형이 아니라 항상 고정 확보** *(2026-08-23 재설계)*: 처음엔 "Y축 title을 입력하면 그때 폭을 넓히고, 넓힌 뒤 라벨 위치를 재계산"하는 반응형 방식이었는데, 두 가지 문제가 있었음 — (1) 폭 재계산이 Y축 범위 변경(줌/팬)에도 연결되어 있어서 드래그할 때마다 반복 실행되며 다소 버벅였고, (2) 그 과정에서 "지금 폭이 얼마나 필요한지"를 `axis.width()`(Qt가 레이아웃을 실제 적용한 뒤에야 갱신되는, 한 박자 늦는 값)로 읽는 바람에 매 사이클 "아직 반영 안 된 이전 폭" 위에 여백을 또 얹어 고정 — 드래그할수록 subplot이 끝없이 좁아지는 버그로 이어짐. 최종적으로는 **Y축 눈금 폭 재계산을 줌/팬(Y축 범위 변경)에서 완전히 분리**하고 — 그래프를 움직이는 동안에는 아예 재계산이 일어나지 않음(구조가 바뀌는 순간: grid 재구성, 데이터/시리즈/라벨 변경 시에만 재계산) — **title 유무와 무관하게 항상 일정한 여백(20px)을 미리 확보**해두는 방식으로 바꿈. 그 결과 title을 나중에 입력하거나 지워도 축 폭이 전혀 바뀌지 않고, 다만 라벨의 세로 중앙 정렬은 축 폭이 안 바뀌면 Qt의 resizeEvent가 저절로 다시 안 불려서 어긋날 수 있어 라벨 텍스트가 바뀔 때마다 그 위치만 별도로 재계산함
- **버그: `axis.resizeEvent()`를 직접 호출하면 위젯 정리 시점에 재귀 크래시** *(2026-08-23 발견 및 회피)*: 위 재설계 과정에서 라벨 위치를 pyqtgraph의 `resizeEvent()`를 직접 호출해 맞추려 했으나, 실제 Qt 리사이즈 흐름 밖에서 수동 호출하면 sizeHint↔resizeEvent가 서로를 되부르는 재귀에 빠져 위젯이 정리되는 시점에 `RuntimeError`가 발생하는 경우를 발견 — `resizeEvent()`를 통째로 호출하는 대신 라벨의 세로 중앙 위치 계산 공식만 따로 떼어내 직접 적용하도록 수정
- **subplot 컬럼(열) 폭도 모두 동일하게 맞춤** *(2026-08-24 추가)*: 컬럼 수를 늘린 뒤 그래프를 그리면, 특정 subplot(특히 이중 Y축을 쓰는 subplot)이 속한 열이 다른 열보다 넓게 그려지는 문제가 있었음. 원인은 두 가지 — (1) `GraphicsLayoutWidget`이 내부적으로 사용하는 `QGraphicsGridLayout`은 명시적 stretch factor가 없으면 각 열의 폭을 그 열에 있는 subplot의 "필요한 만큼"(sizeHint)으로 결정하므로, `rebuild()`마다 모든 행/열에 동일한 stretch factor(1)를 명시적으로 지정해 여유 공간을 균등 배분하도록 함. (2) 그것만으로는 부족했는데, 이중 Y축(우측 축)을 실제로 쓰는 subplot만 우측 축 폭만큼 sizeHint 자체가 더 커서 — 여유 공간이 sizeHint 차이를 다 못 덮으면 stretch factor가 같아도 최소 크기 차이만큼 여전히 벌어짐. 좌측 축과 동일한 방식(`_TITLE_GUTTER`)으로 **우측 축도 grid 전체에서 실제 사용 중인 subplot이 하나라도 있으면 그 폭을 모든 subplot에 동일하게 고정**하도록 `PlotGridWidget._sync_right_axis_widths()`를 추가
- **우측 축을 완전히 숨기지 않고 "투명하게 비움"으로 변경** *(2026-08-24, 위와 함께)*: pyqtgraph의 `AxisItem`은 `isVisible()`이 `False`면 `setWidth()`로 고정폭을 줘도 실제 계산된 폭을 무조건 0으로 되돌려버려서, 이중 Y축을 안 쓰는 subplot의 우측 축에는 폭을 고정으로 예약해 둘 방법이 없었음 — 그래서 우측 축은 항상 `show()` 상태로 유지하되, 이중 Y축을 안 쓸 때는 눈금/라벨/선을 전부 완전 투명(pen alpha=0)으로 칠하고 `showValues=False`, 라벨도 강제로 숨겨서 "보이지는 않지만 폭은 차지하는" 상태로 만듦. 부작용 방지: 우측 축을 더블클릭해 라벨 편집 다이얼로그를 여는 히트테스트(`PlotGridWidget._axis_at_scene_pos`)는 축이 항상 `isVisible()`이게 된 것과 무관하게, 실제로 이중 Y축 시리즈가 있는 subplot에서만 반응하도록 `SubplotView.has_secondary_series()` 체크를 추가
- **버그: column을 늘린 뒤 새로 만든 subplot에 이중 Y축을 나중에 설정하면 다시 불균등해짐** *(2026-08-24 발견 및 수정)*: 위 두 항목의 폭 재계산은 `PlotGridWidget.schedule_axis_width_sync()`가 호출돼야 실행되는데, `MainWindow._replot_subplot()`(grid 재구성, CSV 재로딩 등 구조적 변경 시 항상 실행)에서는 호출하지만, 시리즈를 이중 Y축으로 재배정하는 `_on_series_axis_changed()`와 시리즈를 삭제하는 `_remove_series()`는 뷰를 직접 갱신할 뿐 이 재동기화를 호출하지 않았음 — grid를 먼저 늘리고 나중에(별도 조작으로) 이중 Y축을 켜는 실제 사용 순서에서 딱 이 두 경로를 타서 재현됨. 두 메서드 모두에 `self.plot_grid.schedule_axis_width_sync()` 호출을 추가해 해결
- **이중 Y축(우측 축) title도 좌측과 동일하게 여백을 미리 고정 확보** *(2026-08-24 추가)*: 좌측 축과 같은 이유로, 우측 축도 title 유무와 무관하게 `_TITLE_GUTTER`만큼 폭을 항상 얹어 고정하도록 `PlotGridWidget._sync_right_axis_widths()`를 수정하고, `SubplotView._recenter_right_axis_label()`(좌측용 메서드와 동일한 방식, `AxisItem.resizeEvent()`의 우측 축 중앙 정렬 공식만 따로 떼어 적용)을 추가해 `set_labels()`에서 우측 라벨을 설정한 직후 호출하도록 함
- **우측 축 여백은 grid 전체가 아니라 열(column) 단위로만 확보하도록 재설계** *(2026-08-24 재설계)*: 바로 위 항목까지는 grid 안에 이중 Y축을 쓰는 subplot이 하나라도 있으면 그 폭을 **grid의 모든 열**에 동일하게 고정했었는데, 실제로 subplot이 많아지면 이중 Y축을 전혀 안 쓰는 다른 열들까지 불필요하게 여백을 낭비하는 문제가 있었음. 좌측 축(모든 subplot이 항상 쓰는 주축이라 grid 전체 정렬이 의미 있음)과 달리, 우측 축은 열 하나가 이미 Qt의 실제 grid 구조상 폭을 공유하는 단위이므로 — `PlotGridWidget._sync_right_axis_widths()`를 열 인덱스별로 그룹화해서 **그 열에 실제로 이중 Y축을 쓰는 subplot이 있는 열만** 폭을 확보하고, 나머지 열은 원래 폭(사실상 0)을 유지하도록 변경. 그 결과 열마다 폭이 달라지는 것은 이제 의도된 동작(이중 Y축을 쓰는 열만 넓음)이고, 같은 이유로 폭이 달라지지 않아야 하는 열끼리는(둘 다 이중 Y축 미사용) 여전히 서로 동일

### 2.8 테마
- Settings 메뉴 → Theme 서브메뉴에서 Light mode / Dark mode / System mode 중 택1 (배타적 선택)
- 테마 전환 시 배경/전경/축/범례 색상이 모두 함께 갱신
- **버그: 복잡한 layout(다수 subplot + 이중 Y축) 로드 후 테마를 전환하면 프로그램이 튕김(네이티브 크래시)** *(2026-08-25 발견 및 수정)*: `tests/IAU_124_parsed0_impact.csv`(35,130행) + `tests/AxyzRpyCasAlt_ThrFuelFlowRPM2.json`(4행×2열, 여러 subplot이 이중 Y축 사용)을 불러온 뒤 Dark ↔ Light 전환 시 재현됨. `faulthandler`로 크래시 지점을 추적한 결과 `PlotGridWidget._sync_column_widths()`에서 "access violation"(Windows) 발생 — 실제 화면 렌더링(`QT_QPA_PLATFORM=offscreen`이 아닌 실제 창)에서만 재현되고 headless 환경에서는 재현 안 됨. 원인은 `theme.apply_app_theme()`가 테마를 바꿀 때마다(이미 "Fusion" 스타일이 적용되어 있어도) `QApplication.setStyle("Fusion")`을 매번 다시 호출하고 있었던 것 — 이 재적용 자체가 불필요한데도(스타일은 안 바뀌고 팔레트만 바뀜) subplot이 많고 이중 Y축까지 있는 복잡한 pyqtgraph scene에서는 두 번째 이상의 `setStyle()` 호출이 크래시를 유발함(Qt/PySide 쪽 스타일 재적용(polish/unpolish) 과정과 pyqtgraph의 커스텀 그래픽스씬 간 상호작용으로 추정, 근본 원인은 Qt/PySide 내부이므로 우리 쪽에서는 재호출 자체를 없애는 방식으로 회피). 수정: `app.style().objectName()`이 이미 `"fusion"`이면 `setStyle()`을 건너뛰도록 가드 추가 — 이후 동일 CSV+layout으로 dark/light/system을 14회 연속 전환해도 크래시 없음을 확인

### 2.9 Info 메뉴 — 라이선스 안내 *(2026-08-23 추가)*
- 메뉴바에 **Info → License Info**로 팝업(`LicenseDialog`)을 띄움
- 내용: 앱 버전/빌드일자, 번들된 서드파티 라이브러리별 라이선스 표(PySide6/shiboken6=LGPL-3.0-only, pyqtgraph=MIT, polars=MIT, NumPy=BSD-3-Clause), 그리고 **사내/상업적 사용 관련 안내**: PySide6는 LGPLv3라 동적 링크(이 프로젝트의 PyInstaller `--onedir` 빌드가 이 조건에 해당)를 유지하면 소스 공개 없이 사내/상업적 배포가 가능하다는 요지와, 이는 법률 자문이 아니므로 조직 외부·대규모 배포 시 라이선스 조건을 다시 확인하라는 면책 문구
- 이 앱 자체(csv-plot-maker)의 라이선스는 별도로 지정하지 않았음을 명시

### 2.10 저장/불러오기 진입점 (File 메뉴)
- Save Layout: CSV 파일명 기반 고정 경로에 JSON으로 저장
- Save Layout As...: 사용자가 파일명을 직접 선택해 저장 (기본값 = CSV 이름)
- Load Layout: 저장된 JSON을 불러와 현재 프로젝트를 대체
- **Load Layout As...** *(2026-08-23 추가)*: 파일 선택 다이얼로그로 **임의의** 레이아웃 JSON을 골라 현재 열려있는 CSV에 적용. 레이아웃 JSON은 컬럼을 이름(문자열)으로만 참조하므로 원래 저장했던 CSV가 아닌 다른 CSV에도 재사용 가능 — 단, 현재 CSV에 없는 컬럼을 참조하는 시리즈는 조용히 걸러내고(해당 subplot의 X 컬럼도 현재 CSV의 첫 컬럼으로 대체), 상태 표시줄에 몇 개가 제외됐는지 안내. 불러온 프로젝트의 `csv_path`는 항상 지금 열려있는 CSV로 재설정되어, 그 이후 Save Layout은 원래 레이아웃 파일이 아니라 현재 CSV 기준 경로에 저장됨
- **레이아웃/CSV 로드 후 X·Y축을 데이터에 맞게 자동 범위 설정** *(2026-08-23 수정)*: "Link X axis across subplots"가 켜진 상태로 저장된 레이아웃(또는 그런 레이아웃이 자동 복원되는 CSV)을 불러오면, 데이터가 아직 채워지기 전에 X축 연동 방송이 먼저 일어나 모든 subplot이 pyqtgraph 기본값인 (0, 1) 범위에 갇혀버리는 버그가 있었음(그 방송이 X축의 auto-range를 꺼버리기 때문에 그 뒤에 실제 데이터가 들어와도 다시 맞춰지지 않았음). subplot 좌하단의 "A"(auto range) 버튼을 누른 것과 같은 효과를 내도록, 레이아웃/CSV 로드가 끝난 직후 각 subplot의 실제 컬럼 데이터에서 직접 최소/최대값을 계산해 X·Y 범위를 맞춤 — pyqtgraph 자체의 `enableAutoRange()`/`autoRange()`도 시도해봤으나, replot 직후에는 곡선의 화면 표시용(다운샘플링/클리핑된) 형상이 아직 Qt 씬 그래프에 반영되기 전이라 엉뚱한(거의 빈) 범위로 계산되는 문제가 있어, Qt 레이아웃 타이밍에 의존하지 않는 이 방식을 택함

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
- **저사양(RAM 16GB급) 환경에서 4GB 이상 CSV 로드 시 OOM으로 컴퓨터가 멈추는 문제 개선** *(2026-08-25 추가, 부록 C.1 참고)*: 문자열 컬럼을 아예 메모리에 올리지 않고, 로딩 중 polars 쪽 메모리를 즉시 해제하고, 스키마 오류가 아닌 예외(`MemoryError` 등)는 재시도하지 않고, 로딩 시작 전 파일 크기 대비 가용 RAM을 미리 확인해 경고하도록 함
- **Ragged 행(끝 컬럼 생략) 지원** *(2026-08-27 추가)*: 행 끝의 데이터가 없을 때 trailing comma를 찍지 않는 CSV도 polars가 짧은 행을 null로 우측 패딩해 기본적으로 문제없이 로드됨. 단, 어떤 컬럼이 모든 행에서 예외 없이 비어있으면 dtype을 추론할 수 없어 String(all-null)으로 떨어지는데, 이 경우도 진짜 텍스트 컬럼처럼 버리지 않고 전부 NaN인 숫자 컬럼으로 취급해 그래프 후보 목록에 남김
- **`HH:MM:SS.fff` 시각 문자열 컬럼을 초 단위로 변환** *(2026-08-27 추가)*: `try_parse_dates=True`가 이런 컬럼을 `pl.Time`으로 정확히 파싱하지만 기존에는 temporal 판정에서 `pl.Time`이 빠져 비수치로 분류되어 버려지고 있었음. `pl.Time`을 temporal로 인정하고, 그 물리적 표현(자정 기준 나노초)을 초 단위로 나눠 저장 — `Date`/`Datetime` 컬럼의 기존 처리 방식(물리적 값 그대로)은 변경하지 않음
- **드물게 갱신되는(sparse) 숫자 컬럼이 통째로 String으로 오분류되어 사라지는 문제 수정** *(2026-08-27 추가)*: 어떤 컬럼이 polars의 스키마 추론 샘플 구간(파일 앞부분 일부 행)에서 전부 null이면(예: 주기적으로만 갱신되는 "echo" 상태 필드), polars는 숫자 dtype을 추측할 근거가 없어 String으로 확정하고, 그 뒤로 실제 숫자 값이 나와도 문자열 형태로 그냥 파싱해버려 스키마 오류를 내지 않음 — 기존 3단계 폴백은 `PolarsError` 예외 발생을 트리거로 삼기 때문에 이 경우엔 애초에 전체 재스캔(2/3단계)로 넘어갈 기회조차 없이 조용히 String(그래서 그래프에 안 나오는 비수치 컬럼)으로 남았음. 실제 사례: 정상 텔레메트리와 훨씬 낮은 빈도로만 갱신되는 "ECHO" 응답 메시지 필드(예: `..._SYSTEM_MODE_Value`, `..._FLIGHT_CONTROL_MODE_Value`)가 544개 컬럼 중 524개나 이 문제로 통째로 빠짐(`M1-LT-06-02_GCS-AVS_ALL_DATA.csv` 실측). 수정: dtype이 String으로 떨어진(그리고 전부 null은 아닌) 컬럼에 한해 `Int64` → `Float64` 순으로 `cast(strict=True)`를 시도해, 모든 non-null 값이 실제로 그 타입으로 파싱되면 되살리고(진짜 텍스트 컬럼은 두 캐스팅 모두 실패해 기존처럼 정상적으로 드롭됨), 파일을 다시 스캔하지 않고 이미 파싱된 String 컬럼 값 그대로 변환하므로 재파싱 비용이 들지 않음

### 3.2 시리즈/스타일
- 시리즈별 색상, 선 스타일(solid/dash/dot/dashdot/**none**), 마커 종류, 선 굵기를 독립적으로 설정
- "None" 선 스타일 선택 시 선을 그리지 않고 마커만 표시(점만 찍는 산점도 형태)
- 모든 마커는 테두리(outline) 없이 채움만 표시
- 스타일 변경은 데이터 재전송 없이 해당 시리즈만 즉시(setPen/setSymbol) 갱신되어 대용량에서도 지연 없음
- **마커가 켜진 시리즈는 auto-downsampling을 끔** *(2026-08-27 추가)*: pyqtgraph의 `peak` 다운샘플링은 여러 원본 샘플을 픽셀 하나로 압축할 때 그 구간의 `min()`/`max()`만 남기는데, numpy의 `min`/`max`처럼 NaN이 하나라도 섞이면 그 구간 전체가 NaN이 되어버림 — 드물게만 값이 있고 나머지는 NaN인 컬럼(예: 3.1의 sparse ECHO 필드)을 마커로 찍어도, 줌아웃해서 한 구간에 실제값과 NaN이 함께 묶이는 순간부터 그 값이 통째로 사라져 화면에 아무것도 안 보였음. 마커는 "개별 샘플을 정확히 보고 싶다"는 사용자의 명시적 의사이므로, 마커가 설정된 시리즈는 다운샘플링을 끄고 항상 원본 데이터 그대로 렌더링(`SubplotView._apply_downsampling`) — 마커 없는 대용량 연속 곡선은 기존처럼 다운샘플링 유지
- **마커 종류에 "Dot" 추가, 드문 데이터는 드래그 시 기본 마커+선 없음 적용** *(2026-08-27 추가)*: pyqtgraph에는 원(circle)과 별개인 작은 점 심볼이 없어서, "Dot"은 원 글리프('o')를 재사용하되 항상 작고 고정된 크기(4px, 선 굵기와 무관)로 그려 굵기에 비례해 커지는 "Circle"과 구분(`style_map.py`). 컬럼을 subplot에 드롭할 때(`ColumnStore.is_sparse`, 결측 비율 50% 초과) 값이 드문 컬럼이면 `marker="dot"` + `line_style="none"`을 기본 적용 — 기본 스타일(선만, 마커 없음)로는 위 downsampling 이슈 이전에 애초에 인접한 두 유효 샘플이 없어 화면에 아무것도 안 그려지므로 데이터를 추가했는데 아무 반응이 없어 보이는 상황 자체를 방지하고, 선을 아예 없애 마커만 남긴 것은 어쩌다 두 실제값이 인접한 행에 놓이더라도 서로 멀리 떨어진 두 시점 사이를 매끄럽게 잇는 것처럼 오해를 주지 않기 위함
- **Header Trimming: 컬럼명에서 특정 문자열을 일괄 제거** *(2026-08-27 추가, 저장 방식 2026-08-27 재수정)*: 실제 로그 포맷은 모든 컬럼에 공통 접두/접미가 붙는 경우가 많음(메시지 네임스페이스 `AVS_TC_AILDA::`, 디코딩 필드 표시 `_Value`, `", "` 구분자로 인한 선행 공백 등). Data 탭의 "Header Trimming" 버튼으로 관리 다이얼로그(`HeaderTrimDialog`)를 열어 제거할 키워드 목록을 편집. 키워드는 등록 순서대로 각 컬럼명에서 단순 부분 문자열 제거(정규식 아님)로 적용되며, `peek_schema()`(컬럼 목록 즉시 표시)와 `load_csv()`(실제 데이터) 양쪽에 동일하게 적용해 이름이 어긋나지 않도록 함(`data/header_trim.py::trim_headers`). 트리밍 결과 이름이 겹치면 `_1`, `_2`처럼 번호를 붙여 구분하고, 합성 `Sequential` 컬럼과 겹치는 경우도 동일하게 처리. **번호 충돌 버그 수정** *(2026-08-28)*: 기존 구현은 각 원본 이름마다 독립적인 카운터로 `_1`, `_2`, ... 를 붙였는데, 그렇게 만든 이름이 마침 다른 컬럼이 이미 트리밍으로 갖게 된 이름과 우연히 같아지는 경우(예: 두 컬럼이 `RESERVED`로 트리밍되고 세 번째 컬럼이 원래부터 `RESERVED_2`인 상황에서, 카운터가 2에 도달하면 그 이름과 충돌)를 검사하지 않아 `polars`에 중복 컬럼명을 넘겨 "column with name ... has more than one occurrence" 로딩 실패를 일으켰음. 지금까지 실제로 사용된 이름 전체를 추적하며 충돌이 없어질 때까지 번호를 계속 올리도록 수정(`trim_headers`). 다이얼로그를 닫을 때 키워드 목록이 실제로 바뀌었고 CSV가 이미 열려있으면, 그 CSV를 즉시 같은 경로로 다시 로드해 반영(`CsvPanel._on_header_trim_clicked`) — 바뀐 게 없으면 불필요한 재로딩은 하지 않음. 재로딩은 일반적으로 CSV를 다시 여는 것과 동일하게 동작하므로, 저장되지 않은 subplot 구성이 있다면 (저장된 레이아웃이 없는 한) 초기화됨
- **저장은 항상 사용자의 명시적 동작으로만** *(2026-08-27 확정)*: 처음엔 add/remove할 때마다 자동으로 파일(→ 처음엔 `QSettings`/Windows 레지스트리, 나중엔 실행파일 폴더의 JSON 파일)에 즉시 저장했는데, 사용자가 "프로그램이 마음대로 파일을 만들지 말고 불러오기/저장하기를 직접 하게 해달라"고 요청해 자동 저장을 완전히 제거. 지금은 다이얼로그의 Add/Remove가 그 창의 인메모리 목록만 바꾸고(디스크에 아무것도 안 씀), "Load from File..."/"Save to File..." 버튼(둘 다 `QFileDialog`, 기본 위치는 실행파일과 같은 폴더)으로만 파일을 읽고 쓸 수 있음(`ui/header_trim_dialog.py`). 앱 시작 시에는 실행파일과 같은 폴더의 기본 파일(`header_trim_keywords.json`, `ui/header_trim_settings.py::load_default_keywords`)이 있으면 한 번 읽어오되, 이 읽기 자체는 그 파일을 새로 만들거나 건드리지 않는 순수 조회임 — `CsvPanel.__init__`이 이걸로 세션의 활성 키워드 목록(`self._header_trim_keywords`)을 초기화하고, 이후로는 다이얼로그에서 편집한 값이 세션 동안 이 목록을 대체할 뿐 자동으로 파일에 반영되지 않음. `app_dir()`은 `sys.frozen`이 참이면 `sys.executable`이 있는 폴더(=실행파일과 같은 폴더), 소스 실행 중(개발 환경)이면 현재 작업 디렉터리를 가리킴

### 3.3 이중 Y축
- 시리즈별로 주축(primary)/보조축(secondary) 배정 가능, 두 축은 독립적으로 스케일링
- 보조축을 쓰는 시리즈가 하나라도 있으면 우측 축이 자동으로 표시되고, 없으면 숨겨짐

### 3.4 데이터 무결성
- `Sequential` 컬럼은 CSV 실제 데이터를 건드리지 않는 합성 컬럼(1..row_count)으로, timestamp 등 원본 X 후보가 없거나 손상됐을 때의 안전한 대안
- **기본 X 컬럼은 `timestamp`** *(2026-08-23 추가)*: CSV 로드 시(그리고 grid 크기 변경으로 새 subplot이 생길 때) 각 subplot의 X 컬럼 초기값은 `timestamp` 컬럼이 존재하면 그것으로, 없으면(컬럼명이 다르거나 숫자/시간으로 파싱되지 않는 경우) `Sequential`로 자동 지정

### 3.5 X축 offset *(2026-08-27 추가)*
- subplot마다 X축에 더할 offset 값을 설정 가능 (`SubplotConfig.x_offset`, 기본값 0) — 시간/타임스탬프 컬럼을 특정 시점 기준으로 재정렬해 보고 싶을 때 사용하지만, 컬럼 종류와 무관하게 항상 입력란이 표시됨
- Series 패널의 X 컬럼 선택 바로 아래 숫자 입력란("X offset")과 "Zero at start" 버튼 제공 — 버튼을 누르면 현재 X 데이터의 최솟값이 0이 되도록 offset을 자동 계산
- X 컬럼을 바꿔도 offset은 리셋되지 않음(여러 컬럼을 번갈아 시험할 때 유지되는 편이 유용) — 레이아웃 저장/불러오기에도 다른 subplot 필드와 동일하게 포함됨
- **"Apply X Column & Offset to All Subplots" 버튼** *(2026-08-27 추가)*: 활성 subplot에서 맞춰둔 X 컬럼/offset 조합을 그리드의 모든 subplot에 한 번에 복사(`MainWindow._on_apply_x_to_all_requested`). "Link X axis across subplots"(뷰의 확대/축소 범위만 동기화)와는 별개로, X 컬럼 선택 자체와 offset 값을 일괄 통일하고 싶을 때 사용 — 적용 후 전체 재도시 및 자동 범위 조정(autorange)까지 수행

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
      header_trim.py        # 컬럼명에서 키워드 문자열을 제거하는 순수 함수(trim_headers)
      column_store.py      # {컬럼명: numpy array} 캐시
    models/
      series.py            # Series: id, y_column, axis, color, line_style, marker, width
      subplot.py            # SubplotConfig: row, col, x_column, x_offset, labels, show_legend, series[]
      project.py             # ProjectState: csv_path, grid_rows, grid_cols, active_subplot_id, subplots[]
      serialization.py       # JSON 저장/불러오기
    ui/
      main_window.py        # QMainWindow: 좌측 CSV 도크 + 중앙 캔버스 + 우측 설정 도크
      csv_panel.py            # CSV 열기, 컬럼 리스트(검색/다중선택/드래그), Header Trimming 버튼
      header_trim_dialog.py   # Header Trimming 키워드 추가/삭제 관리 다이얼로그
      header_trim_settings.py # Header Trimming 기본 파일 위치(app_dir)와 JSON 파일 읽기/쓰기 함수 -- 자동 저장은 하지 않음
      grid_config_panel.py    # rows/cols + 활성 subplot + Clear 버튼
      series_panel.py          # X 컬럼, X offset, 시리즈 목록, 범례 토글
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

### 부록 C.1 대용량 CSV 로딩 메모리 개선 *(2026-08-25 추가)*

**문제**: RAM 16GB급 저사양 환경에서 4GB 이상 CSV를 불러오면 OOM으로 컴퓨터 자체가 응답 없음 상태가 되는 사례가 보고됨. 원인 분석(`src/csv_plot_maker/data/loader.py`):
1. 문자열(비숫자) 컬럼도 `.to_numpy()`로 변환해 영구 보관하고 있었는데, `ColumnStore.numeric_column_names()`가 모든 컬럼 선택 UI 경로의 유일한 게이트라 — 문자열 컬럼은 애초에 그래프에 절대 쓰일 수 없음에도 메모리만 차지. numpy object 배열(Python 문자열 객체마다 개별 오버헤드)은 원본 CSV 텍스트보다 훨씬 커지는 경우가 많아 순수 낭비.
2. `load_csv()`의 변환 루프가 polars `DataFrame` 전체(`df`)를 루프가 끝날 때까지 계속 참조하고 있어서, 이미 변환된 컬럼들의 numpy dict와 아직 안 지운 polars DataFrame이 루프 내내 동시에 메모리에 존재 — 한동안 최대 메모리 사용량이 최종 필요량의 최대 2배 가까이 치솟음.
3. 스키마 추론 실패 시 전체 파일을 최대 3번 재파싱하는 폴백 로직이 `except Exception:`으로 모든 예외를 재시도 대상으로 삼고 있어서, 첫 시도가 이미 메모리 부족으로 실패한 경우에도 무의미하게 2번 더(각각 전체 재파싱) 재시도하며 위험을 키움.
4. 로딩 시작 전 파일 크기나 가용 RAM을 전혀 확인하지 않아, 사용자가 위험을 인지하고 취소할 기회 자체가 없었음.

**수정** (`loader.py`, `ui/csv_panel.py`):
- 숫자/시간 컬럼이 아니면 `.to_numpy()` 자체를 생략 (`store.dtypes`/`store.numeric = False`만 기록, 컬럼 목록 UI 표시는 그대로 `peek_schema()`가 담당하므로 영향 없음).
- `df[name]` 대신 `df.drop_in_place(name)` 사용 — 컬럼을 추출함과 동시에 `df`에서 제거해, 변환하지 않고 버리는 문자열 컬럼이든 변환해서 저장하는 숫자 컬럼이든 처리 즉시 polars 쪽 메모리를 해제. 그 결과 `df`의 메모리가 루프 진행에 따라 점점 줄어듦.
- 재시도 폴백의 `except Exception:`을 `except pl.exceptions.PolarsError:`로 변경 (2곳) — 스키마/파싱 오류(`ComputeError`, `SchemaError` 등은 모두 `PolarsError` 상속)만 재시도 대상이 되고, `MemoryError`는 즉시 전파되어 불필요한 재파싱을 막음.
- `CsvPanel.load_path()`에 로딩 시작 전 `_confirm_memory_headroom()` 체크 추가: `os.path.getsize()`와 `psutil.virtual_memory().available`(재사용 가능한 OS 캐시를 감안하는 값이라 `.free`보다 현실적)을 비교해, 예상 필요 메모리(파일 크기 × 2배, 보수적 배수)가 가용 RAM을 넘으면 `QMessageBox`로 경고하고 사용자가 계속 진행할지 선택. `psutil` 조회 자체가 실패하는 경우는 체크를 건너뛰고 로딩을 막지 않음(fail open). 새 의존성 `psutil`을 `uv add psutil`로 추가.
- 검증: 숫자 4개+문자열 4개 컬럼, 200만 행(≈290MB) 합성 CSV로 실측 — 수정 전 피크 메모리 증가분 ≈1022MB(문자열 컬럼까지 전부 보관), 수정 후 ≈598MB(문자열 컬럼 없이 숫자만 보관), 최종 정상상태 메모리는 1022MB→444MB로 감소. 문자열 컬럼 비중이 더 큰 실제 파일일수록 개선 폭이 더 커짐. `tests/test_loader.py`에 문자열 컬럼 미저장 확인, `MemoryError` 무재시도 확인, 스키마 오류는 여전히 재시도됨을 확인하는 테스트 추가. `tests/test_csv_panel.py` 신규 — RAM 경고 로직(통과/경고+거부/경고+승인/조회 실패 시 fail-open) 단위 테스트.
- `scripts/gen_synthetic_csv.py`에 `--str-cols` 옵션 추가 (성능/메모리 테스트용 합성 CSV에 비숫자 컬럼을 섞을 수 있도록).

## 부록 D. 검증 방법

- **자동화**: `data/loader.py`(엣지케이스 CSV로 `ColumnStore` 검증, 스키마 추론 폴백 검증), `models/`(상태 전이 단위 테스트), 시그널 배선은 헤드리스 스크립트(`QT_QPA_PLATFORM=offscreen`)로 실제 신호/슬롯 호출 검증
- **수동/시각적**: 렌더링, 이중축 정렬, 테마 전환, 범례 표시/숨김은 스크린샷 캡처로 육안 확인
- **성능**: 합성 대용량 CSV(수십만~수백만 행)로 로딩 시간 및 팬/줌 반응성 확인
