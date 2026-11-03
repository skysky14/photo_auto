# Graph Report - photo_ai  (2026-11-03)

## Corpus Check
- Corpus is ~6,400 words - fits in a single context window. You may not need a graph.

## Summary
- 192 nodes · 360 edges · 10 communities (8 shown, 2 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Docs and Policies
- Ollama AI Labeler
- GUI and Config
- GUI and Config 2
- SQLite DB
- EXIF Reader
- GUI and Config 3
- Kakao Geo Lookup
- Naming Rules
- Build Script

## God Nodes (most connected - your core abstractions)
1. `DB` - 18 edges
2. `App` - 12 edges
3. `PhotoAI Organizer 프로젝트 (CLAUDE.md)` - 11 edges
4. `run()` - 9 edges
5. `diagnose()` - 8 edges
6. `prepare()` - 8 edges
7. `test_pipeline()` - 8 edges
8. `Settings` - 6 edges
9. `_now()` - 6 edges
10. `_id()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `개발 범위 V1 (CLAUDE.md)` --semantically_similar_to--> `개발 범위 V1 / 동기화 방침`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `핵심 원칙 (CLAUDE.md)` --semantically_similar_to--> `기본 원칙 (확인 가능한 정보만, 추정 금지)`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `파일명 규칙 (CLAUDE.md)` --semantically_similar_to--> `파일명 규칙`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `중복 파일 정책 (CLAUDE.md)` --semantically_similar_to--> `중복 파일 처리`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `폴더·config.ini 설정` --semantically_similar_to--> `저장소·config 정책 (INI, 키 코드 고정)`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **파일명 생성 입력 (EXIF 촬영일 + 카카오 장소 + AI 설명어)** — docs_기획서_exif정책, docs_기획서_gps장소명정책, docs_기획서_ai분석정책, docs_기획서_파일명규칙 [EXTRACTED 0.95]
- **안전한 이동·중복 처리** — docs_기획서_검증후원본삭제, docs_기획서_중복파일처리, docs_기획서_자동생성폴더, docs_기획서_통계이력 [INFERRED 0.75]

## Communities (10 total, 2 thin omitted)

### Community 0 - "Docs and Policies"
Cohesion: 0.07
Nodes (42): graphify 스킬 트리거 (.claude/CLAUDE.md), GPS 좌표 캐시 (CLAUDE.md), graphify 사용 규칙, Ollama 자동 설치 (CLAUDE.md), 개발 단계 Phase 0-9, 개발 범위 V1 (CLAUDE.md), 코드 구조 (namer, exif, geo, ai, db, config, organizer, app), 기술 스택 (CLAUDE.md) (+34 more)

### Community 1 - "Ollama AI Labeler"
Cohesion: 0.13
Nodes (13): diagnose(), find_ollama(), _install(), _jpeg(), _local(), make_labeler(), label(), _models() (+5 more)

### Community 2 - "GUI and Config"
Cohesion: 0.16
Nodes (6): App, fmt_sec(), load(), save(), Settings, test_config_roundtrip()

### Community 3 - "GUI and Config 2"
Cohesion: 0.18
Nodes (9): choose_target(), move_verified(), _process_one(), Result, run(), scan(), sha256(), undo() (+1 more)

### Community 4 - "SQLite DB"
Cohesion: 0.23
Nodes (4): DB, _id(), _now(), test_geo_cache()

### Community 5 - "EXIF Reader"
Cohesion: 0.18
Nodes (9): _deg(), read_meta(), make_jpg(), settings(), test_ai_diagnose(), test_cancel(), test_dup_off_adds_suffix(), test_pipeline() (+1 more)

### Community 7 - "Kakao Geo Lookup"
Cohesion: 0.15
Nodes (3): Geo, parse_regions(), test_parse_regions()

### Community 8 - "Naming Rules"
Cohesion: 0.20
Nodes (6): build_name(), clean_label(), place_name(), test_build_name_variants(), test_clean_label(), test_place_name()

## Knowledge Gaps
- **8 isolated node(s):** `graphify 스킬 트리거 (.claude/CLAUDE.md)`, `코드 구조 (namer, exif, geo, ai, db, config, organizer, app)`, `개발 단계 Phase 0-9`, `README photo_auto 사진분류`, `복사 후 크기·해시 검증 뒤 원본 삭제` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 48 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DB` connect `SQLite DB` to `GUI and Config`, `EXIF Reader`, `GUI and Config 3`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **What connects `graphify 스킬 트리거 (.claude/CLAUDE.md)`, `코드 구조 (namer, exif, geo, ai, db, config, organizer, app)`, `개발 단계 Phase 0-9` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Docs and Policies` be split into smaller, more focused modules?**
  _Cohesion score 0.06620209059233449 - nodes in this community are weakly interconnected._
- **Why does `App` connect `GUI and Config` to `Ollama AI Labeler`, `GUI and Config 2`, `GUI and Config 3`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Should `Ollama AI Labeler` be split into smaller, more focused modules?**
  _Cohesion score 0.13105413105413105 - nodes in this community are weakly interconnected._
- **Why does `test_geo_cache()` connect `SQLite DB` to `EXIF Reader`, `Kakao Geo Lookup`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._