# CSV Plot Maker

CSV 데이터를 불러와 여러 개의 subplot으로 구성된 그래프를 그리는 데스크톱 분석 도구입니다. 컬럼을 여러 subplot에 중복 선택해 시리즈로 추가하고, 시리즈별 색상/선모양/마커/굵기를 즉시 바꾸고, subplot마다 이중 Y축과 축 라벨을 설정할 수 있습니다. 수십만~수백만 행 규모의 CSV도 빠르게 로딩·렌더링하도록 만들어졌습니다.

전체 요구사항과 설계 배경은 [DESIGN.md](DESIGN.md)를 참고하세요.

## 요구 사항

- Python 3.10 이상
- Windows에서 개발/검증됨. PySide6·pyqtgraph·polars 모두 Linux용 wheel을 제공하므로 소스로 실행하는 것은 Linux에서도 가능할 것으로 예상되지만, 아직 별도로 빌드/검증하지는 않았습니다. Linux용 standalone 실행 파일은 Linux 환경(WSL/Docker/실제 Linux 머신)에서 PyInstaller를 직접 실행해야 만들 수 있습니다 — PyInstaller는 크로스컴파일을 지원하지 않습니다.

## 설치 및 실행

### uv 사용 (권장)

```powershell
uv sync
uv run csv-plot-maker
```

### pip 사용

```powershell
pip install -r requirements.txt
python -m csv_plot_maker.main
```

## 개발자용

### 테스트

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest -q
```

GUI를 실제로 띄우지 않는 헤드리스 테스트를 위해 `QT_QPA_PLATFORM=offscreen`을 사용합니다.

### 합성 CSV 생성 (성능 테스트용)

```powershell
uv run python scripts/gen_synthetic_csv.py
```

대용량(수백만 행) CSV를 만들어 로딩/렌더링 성능을 확인할 때 사용합니다.

## Windows 실행 파일(standalone .exe) 빌드

```powershell
uv add --dev pyinstaller   # 최초 1회
uv run pyinstaller --name "CSV Plot Maker" --windowed --onedir --noconfirm --clean --paths src src\csv_plot_maker\main.py
```

- `--onedir`: 실행 파일 하나가 아니라 exe + 의존 파일 폴더로 생성합니다. PySide6가 LGPLv3이므로 `--onefile`로 모든 것을 하나의 실행 파일에 정적으로 압축하면 라이선스 경계가 모호해질 수 있어 onedir을 기본으로 사용합니다.
- 결과물은 `dist\CSV Plot Maker\CSV Plot Maker.exe`이며, `dist\CSV Plot Maker` 폴더 전체를 그대로 옮기면 Python 설치 없이 다른 Windows PC에서도 실행됩니다.
- 재빌드 시 프로젝트 루트의 `CSV Plot Maker.spec` 파일로도 동일한 설정으로 다시 빌드할 수 있습니다: `uv run pyinstaller "CSV Plot Maker.spec" --noconfirm --clean`
- 새 실행 파일을 빌드할 때는 `src/csv_plot_maker/_version.py`의 `BUILD_DATE`도 함께 갱신해 주세요(창 제목에 표시됨).

## 프로젝트 구조

```
src/csv_plot_maker/
  main.py                    # QApplication 진입점
  _version.py                # 창 제목에 표시되는 버전/빌드일자
  data/
    loader.py                 # polars 기반 CSV 로딩 (스키마 peek + 백그라운드 전체 로드)
    column_store.py           # 컬럼별 numpy 배열 캐시
  models/
    series.py                 # Series: 컬럼, 축, 스타일
    subplot.py                # SubplotConfig: subplot 하나의 설정
    project.py                # ProjectState: 전체 프로젝트 상태
    serialization.py          # 레이아웃 JSON 저장/불러오기
  ui/                          # 좌측 CSV 패널, 우측 설정 패널 등 Qt 위젯
  plotting/                    # pyqtgraph 기반 subplot grid 렌더링
  utils/
    workers.py                 # QThreadPool 백그라운드 작업 헬퍼
tests/                          # pytest 스위트
scripts/                        # 합성 CSV 생성, 수동 스모크 테스트 스크립트
```

## 라이선스 관련 참고

PySide6는 LGPLv3로 배포됩니다. 동적 링크 조건 하에서는 상업적 배포에도 일반적으로 문제가 없으나, 이 프로젝트를 상업적으로 배포할 계획이 있다면 라이선스 조건을 별도로 검토하세요.
