# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트
PhotoAI Organizer: 사진의 EXIF 촬영일, GPS, AI 분석 결과로 파일명을 자동 변경하고 폴더로 정리하는 Windows 프로그램 (Python 3.11, 개인 사용).

```
IMG_20210216_191725.jpg → 20210216_191725_연수구송도동_산책중.jpg
```

상세 기능·정책의 기준 문서는 `docs/기획서.md`다. 이 파일과 충돌하면 기획서를 따르고, 기획서를 먼저 고친다.

## 개발 범위
- **V1까지만 개발한다.** 다국어 UI, 날짜별 폴더, 다중 AI, 클라우드 연동, 얼굴 인식, 사진 품질 분석 등 V2 이후 기능은 만들지 않는다.
- 서버 동기화는 V1에서 구현하지 않는다. 데이터는 로컬 SQLite에만 저장하되, 테이블마다 `id`(UUID), `updated_at`, `synced` 컬럼을 둬서 나중에 동기화할 수 있게 한다.

## 핵심 원칙
- 확인 가능한 정보만 쓴다. 촬영일 없음 → 날짜 제외, GPS 없음 → 장소 제외, AI 실패 → 설명어("상태명") 제외.
- **파일 생성일·수정일, AI가 추정한 촬영일은 절대 쓰지 않는다.**
- 촬영일이 없는 사진은 `정리완료/분류불가`로 이동한다.
- 처리에 실패한 파일은 원본 위치에 그대로 둔다. 원본은 복사 후 크기·SHA-256을 검증한 뒤에만 삭제한다.

## 파일명 규칙
| 촬영일 | GPS | AI | 파일명 |
|---|---|---|---|
| O | O | O | `날짜_장소_설명어.jpg` |
| O | O | X | `날짜_장소.jpg` |
| O | X | O | `날짜_설명어.jpg` |
| O | X | X | `날짜.jpg` |

- 날짜는 `YYYYMMDD_HHMMSS`. 설명어는 최대 10자, 공백·특수문자 금지. 장소는 최대 10자.
- **장소는 건물명이 아니라 주소명**이다: 카카오 행정구역 API로 `구/시 + 동/읍/면`을 이어 붙인다 (예: `연수구송도동`).
- GPS 좌표 → 장소명은 SQLite에 캐시한다(좌표를 소수점 4~5자리로 반올림해 키로 사용). 캐시에 있으면 API를 호출하지 않는다.

## 중복 파일
"동일 파일 검사" 옵션(기본 ON, `config.ini`의 `[Duplicate] CheckSameFile`).
- OFF: 이름이 같으면 `_001`, `_002`를 붙인다.
- ON: 이름 동일 + SHA-256 동일 → `정리완료/중복파일`로 이동, 이름 동일 + SHA-256 다름 → `_001`, `_002`.

## 폴더·설정
- 자동 생성: `정리완료/`, `정리완료/분류불가/`, `정리완료/중복파일/`
- `config.ini`: `[AI] Enabled`, `[Ollama] Url`, `[Kakao] ApiKey`, `[Duplicate] CheckSameFile`. 카카오 API 키는 INI에 두므로 `config.ini`를 git이나 공유 대상에 넣지 않는다.
- SQLite에 저장: GPS 캐시, 사용량 통계, 작업 로그, 작업 이력(원래 경로 → 새 경로, 되돌리기용).

## 기술 스택
Python 3.11, CustomTkinter(GUI), SQLite, Ollama + Qwen2.5-VL(AI, 선택 사용), 카카오 로컬 API, Pillow·pillow-heif(EXIF/이미지), PyInstaller(포터블 `PhotoAI.exe` 빌드). OpenCV·ImageHash는 V1에서 쓰지 않는다.

## 명령어 (Windows, venv)
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # 개발 도구(graphify), exe 빌드에는 불필요
python main.py   # WSL에서는 ./venv/Scripts/python.exe main.py
pytest                                  # 전체 테스트
pytest tests/test_core.py::test_pipeline   # 단일 테스트
pyinstaller ...                         # 빌드 (설정은 Phase 9에서 확정)
```
Ollama가 별도로 실행 중이어야 하고 모델(`ollama pull qwen2.5vl:7b`)이 설치돼 있어야 AI 분석이 동작한다. AI가 없어도 앱은 "AI 미사용" 모드로 동작해야 한다.

## 구조
- `photo_ai/namer.py`(파일명·설명어·장소 규칙, 순수 함수) / `exif.py`(촬영일·GPS) / `geo.py`(카카오 주소명 + SQLite 캐시) / `ai.py`(Ollama 설명어) / `db.py`(SQLite) / `config.py`(config.ini)
- `organizer.py`: 파이프라인 본체. `run()`이 스캔 → 처리 → 검증 이동을 하고, geo/labeler는 주입식이라 테스트에서 가짜로 대체한다. `undo()`가 작업 이력으로 되돌린다.
- `app.py`: CustomTkinter GUI. 처리는 백그라운드 스레드, 진행 상황은 `queue`로 받아 메인 스레드가 갱신한다.
- 촬영일이 없으면 AI·장소 조회 없이 원본 이름 그대로 `분류불가`로 이동한다.
- 개발 환경: WSL에서는 Windows Python으로 실행한다 (`./venv/Scripts/python.exe`, WSL Python에는 tkinter/pip 없음).

## 개발 단계 (진행 시 체크)
- [x] Phase 0: venv, requirements.txt, Git
- [x] Phase 1: UI(폴더 선택, 통계 영역, 진행률)
- [x] Phase 2: SQLite(GPS 캐시, 통계 테이블)
- [x] Phase 3: EXIF·GPS 분석, 카카오 API (실제 카카오 API 키로는 미검증)
- [x] Phase 4: Ollama 연동, 설명어 생성 (실제 Ollama 서버로는 미검증)
- [x] Phase 5: 파일명 생성, 중복 검사(SHA-256)
- [x] Phase 6: 파일 이동, 분류불가·중복파일 처리
- [x] Phase 7: 통계·작업 로그 저장
- [ ] Phase 8: 100 / 1,000 / 10,000장 테스트
- [ ] Phase 9: PyInstaller 빌드, 포터블 배포

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
