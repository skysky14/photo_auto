# Graph Report - photo_ai  (2026-11-04)

## Corpus Check
- 19 files · ~9,194 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 1 file(s) not represented in the graph (top: (none) 1)

## Summary
- 247 nodes · 475 edges · 11 communities (9 shown, 2 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4df7d832`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- PhotoAI Organizer 프로젝트 (CLAUDE.md)
- ai.py
- config.py
- organizer.py
- DB
- test_core.py
- app.py
- geo.py
- run
- build.sh
- App

## God Nodes (most connected - your core abstractions)
1. `App` - 25 edges
2. `DB` - 24 edges
3. `run()` - 11 edges
4. `PhotoAI Organizer 프로젝트 (CLAUDE.md)` - 11 edges
5. `make_jpg()` - 9 edges
6. `installed_models()` - 8 edges
7. `diagnose()` - 8 edges
8. `ensure_server()` - 8 edges
9. `prepare()` - 8 edges
10. `download_regions()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Ollama 자동 설치 (CLAUDE.md)` --semantically_similar_to--> `Ollama 자동 준비 (ai.diagnose/ai.prepare)`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `개발 범위 V1 (CLAUDE.md)` --semantically_similar_to--> `개발 범위 V1 / 동기화 방침`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `기술 스택 (CLAUDE.md)` --semantically_similar_to--> `기술 스택`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `중복 파일 정책 (CLAUDE.md)` --semantically_similar_to--> `중복 파일 처리`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `파일명 규칙 (CLAUDE.md)` --semantically_similar_to--> `파일명 규칙`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **파일명 생성 입력 (EXIF 촬영일 + 카카오 장소 + AI 설명어)** — docs_기획서_exif정책, docs_기획서_gps장소명정책, docs_기획서_ai분석정책, docs_기획서_파일명규칙 [EXTRACTED 0.95]
- **안전한 이동·중복 처리** — docs_기획서_검증후원본삭제, docs_기획서_중복파일처리, docs_기획서_자동생성폴더, docs_기획서_통계이력 [INFERRED 0.75]

## Communities (11 total, 2 thin omitted)

### Community 0 - "PhotoAI Organizer 프로젝트 (CLAUDE.md)"
Cohesion: 0.07
Nodes (42): graphify 스킬 트리거 (.claude/CLAUDE.md), GPS 좌표 캐시 (CLAUDE.md), graphify 사용 규칙, Ollama 자동 설치 (CLAUDE.md), 개발 단계 Phase 0-9, 개발 범위 V1 (CLAUDE.md), 코드 구조 (namer, exif, geo, ai, db, config, organizer, app), 기술 스택 (CLAUDE.md) (+34 more)

### Community 1 - "ai.py"
Cohesion: 0.09
Nodes (18): diagnose(), ensure_server(), find_ollama(), _install(), installed_models(), _local(), model_size_gb(), _models() (+10 more)

### Community 2 - "config.py"
Cohesion: 0.21
Nodes (6): load(), migrate_old_db(), save(), Settings, test_config_roundtrip(), test_db_creates_folder_and_migrates_old_file()

### Community 3 - "organizer.py"
Cohesion: 0.16
Nodes (7): choose_target(), move_verified(), _process_one(), scan(), sha256(), undo(), _variant()

### Community 4 - "DB"
Cohesion: 0.16
Nodes (7): DB, _id(), _now(), geojson(), test_download_regions_checks_hash(), test_geo_place(), test_pipeline()

### Community 5 - "test_core.py"
Cohesion: 0.10
Nodes (8): _deg(), read_meta(), build_name(), place_name(), test_ai_diagnose(), test_build_name_variants(), test_place_name(), test_read_meta()

### Community 6 - "app.py"
Cohesion: 0.22
Nodes (3): fmt_sec(), main(), setup()

### Community 7 - "geo.py"
Cohesion: 0.13
Nodes (6): warm_up(), download_regions(), Geo, _in_polys(), _in_ring(), parse_geojson()

### Community 8 - "run"
Cohesion: 0.10
Nodes (17): AIUnavailable, _jpeg(), make_labeler(), label(), clean_label(), format_result(), Result, run() (+9 more)

## Knowledge Gaps
- **8 isolated node(s):** `개발 단계 Phase 0-9`, `코드 구조 (namer, exif, geo, ai, db, config, organizer, app)`, `복사 후 크기·해시 검증 뒤 원본 삭제`, `메인 화면 (설정·통계·시간·실행)`, `분류불가 설명어 부여 여부 (확인필요)` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 68 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `App` connect `App` to `ai.py`, `organizer.py`, `app.py`, `geo.py`, `run`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **What connects `개발 단계 Phase 0-9`, `코드 구조 (namer, exif, geo, ai, db, config, organizer, app)`, `복사 후 크기·해시 검증 뒤 원본 삭제` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `PhotoAI Organizer 프로젝트 (CLAUDE.md)` be split into smaller, more focused modules?**
  _Cohesion score 0.06620209059233449 - nodes in this community are weakly interconnected._
- **Why does `DB` connect `DB` to `run`, `App`, `config.py`, `test_core.py`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Should `ai.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09411764705882353 - nodes in this community are weakly interconnected._
- **Why does `test_geo_place()` connect `DB` to `test_core.py`, `geo.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Should `test_core.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10317460317460317 - nodes in this community are weakly interconnected._