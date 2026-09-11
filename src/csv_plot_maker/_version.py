"""Single source of truth for the version/build-date shown in the window title.

Keep __version__ in sync with pyproject.toml's [project].version, and bump
BUILD_DATE whenever a new standalone executable is built (see scripts in the
project root / DESIGN.md appendix A for the PyInstaller build command).
"""

__version__ = "1.9.0"
BUILD_DATE = "2026-09-11"

# (version, date, bullet points) -- newest first, shown verbatim in
# Info > Version History (see ui/version_history_dialog.py). Add a new entry
# here whenever __version__ is bumped; keep each bullet short (개조식) rather
# than a full sentence.
VERSION_HISTORY: list[tuple[str, str, list[str]]] = [
    (
        "1.9.0",
        "2026-09-11",
        [
            "여러 CSV 파일을 동시에 열어 비교 (파일별 색상 구분, 닫기/전체 닫기, 우클릭으로 닉네임 설정)",
            "한 subplot에 서로 다른 CSV 파일의 데이터를 섞어서 표시 가능",
            "X축 컬럼/오프셋을 시리즈(데이터)마다 개별 설정 -- Style 패널에서 편집",
            "\"Set All to X column config\" 버튼: 선택한 시리즈의 X축 설정을 같은 파일의 다른 시리즈에 일괄 적용",
            "subplot끼리 원하는 조합만 X축 팬/줌을 동기화하는 \"Link X axis\" 기능 추가",
            "레전드/시리즈 목록에 파일명(닉네임) 표시 (파일이 하나뿐이면 생략)",
            "큰 CSV 로딩 전 메모리 부족 경고",
            "좌측 CSV 경로 표시를 폴더 이름까지만 축약",
            "내부 코드 구조 정리 (동작 변화 없음)",
        ],
    ),
    (
        "1.0.0",
        "2026-09-11",
        [
            "정식 배포 버전 번호 부여",
            "시리즈(데이터)별 Scale/Offset 기능 추가",
            "좌측 CSV 창 폭 축소, 설명 문서(DESIGN.md/HowToUse.md) 정비",
        ],
    ),
    (
        "0.4.0",
        "2026-09-09",
        [
            "Header Trimming 키워드 목록 전체 삭제 버튼 추가",
            "데이터 리스트 다중 선택(Ctrl/Shift), 전체 선택(Ctrl+A)",
            "데이터 리스트를 다른 subplot으로 드래그해서 이동",
            "레이아웃 저장 시 Y축 범위/legend 크기도 함께 저장",
            "legend 크기에 \"Tiny\" 옵션 추가",
            "여러 subplot이 같은 X축 데이터를 쓰면 맨 아래 subplot에만 X축 제목 표시",
        ],
    ),
    (
        "0.3.1",
        "2026-08-28",
        [
            "희소(대부분 비어있는) 데이터 컬럼은 선 대신 점(marker)으로 기본 표시",
            "X축 오프셋 기능 및 \"영점 맞추기(Zero at start)\" 자동 계산 추가",
            "X축 설정을 모든 subplot에 한 번에 적용하는 버튼 추가",
            "값이 없는 열도 안전하게 처리 (콤마 누락 데이터 대응)",
            "헤더가 긴 컬럼명을 키워드 목록 기준으로 축약 표시 (Header Trimming 추가)",
            "키워드 이름 중복 시 로딩 실패하던 문제 수정",
        ],
    ),
    (
        "0.2.0 이하",
        "2026-08-24 이전, 초기 버전",
        [
            "CSV 로딩 메모리 사용량 대폭 절감",
            "subplot 격자 크기 변경 시 이중 Y축 잔상 버그 수정",
            "라이트/다크 테마 전환 크래시 수정",
            "Legend 크기 옵션(소/중/대) 추가, 2열 이상일 때 이중 Y축 제목 표시 문제 해결",
            "Y축 라벨 겹침/미표시 문제 수정, 레이아웃 로딩 시 X축 범위 초기화 문제 해결",
            "라이선스 안내 팝업 추가",
            "최초 배포",
        ],
    ),
]
