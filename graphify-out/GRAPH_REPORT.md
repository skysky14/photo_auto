# Graph Report - photo_ai  (2026-11-03)

## Corpus Check
- Corpus is ~5,125 words - fits in a single context window. You may not need a graph.

## Summary
- 163 nodes · 294 edges · 10 communities (8 shown, 2 thin omitted)
- Extraction: 91% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 24 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CLAUDE.md (프로젝트 지침) / organizer.py (파이프라인 
- DB / db.py
- organizer.py / choose_target()
- geo.py / Geo
- config.py / pathlib
- app.py / App
- ai.py / make_labeler()
- namer.py / place_name()
- test_core.py / run()
- exif.py / read_meta()

## God Nodes (most connected - your core abstractions)
1. `DB` - 18 edges
2. `App` - 12 edges
3. `CLAUDE.md (프로젝트 지침)` - 10 edges
4. `run()` - 9 edges
5. `test_pipeline()` - 8 edges
6. `organizer.py (파이프라인 run/undo)` - 7 edges
7. `Settings` - 6 edges
8. `_now()` - 6 edges
9. `_id()` - 6 edges
10. `read_meta()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `핵심 원칙` --semantically_similar_to--> `기본 원칙 (확인 가능한 정보만, 추정 금지)`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `파일명 규칙` --semantically_similar_to--> `파일명 규칙`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `중복 파일 (CheckSameFile)` --semantically_similar_to--> `중복 파일 처리 (SHA-256)`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `개발 범위 (V1까지)` --semantically_similar_to--> `개발 범위 V1 및 동기화 방침`  [INFERRED] [semantically similar]
  CLAUDE.md → docs/기획서.md
- `settings()` --calls--> `Settings`  [EXTRACTED]
  tests/test_core.py → photo_ai/config.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **파일명 생성 정책 묶음** — docs_기획서_exif_정책, docs_기획서_gps_장소명_정책, docs_기획서_설명어_규칙, docs_기획서_파일명_규칙 [EXTRACTED 1.00]
- **파이프라인 모듈 구성 (organizer 중심)** — claude_organizer, photo_ai_exif, claude_geo, claude_ai, claude_namer, claude_db [EXTRACTED 1.00]

## Communities (10 total, 2 thin omitted)

### Community 0 - "CLAUDE.md (프로젝트 지침) / organizer.py (파이프라인 "
Cohesion: 0.08
Nodes (35): CLAUDE.md (프로젝트 지침), ai.py (Ollama 설명어), app.py (CustomTkinter GUI), .claude/CLAUDE.md (graphify 트리거), graphify 스킬, config.py (config.ini), db.py (SQLite), geo.py (카카오 + 캐시) (+27 more)

### Community 1 - "DB / db.py"
Cohesion: 0.17
Nodes (3): DB, _id(), _now()

### Community 2 - "organizer.py / choose_target()"
Cohesion: 0.17
Nodes (7): choose_target(), move_verified(), _process_one(), Result, sha256(), undo(), _variant()

### Community 3 - "geo.py / Geo"
Cohesion: 0.16
Nodes (4): Geo, parse_regions(), test_geo_cache(), test_parse_regions()

### Community 4 - "config.py / pathlib"
Cohesion: 0.22
Nodes (4): load(), save(), Settings, test_config_roundtrip()

### Community 6 - "ai.py / make_labeler()"
Cohesion: 0.21
Nodes (4): check(), _jpeg(), make_labeler(), label()

### Community 7 - "namer.py / place_name()"
Cohesion: 0.20
Nodes (6): build_name(), clean_label(), place_name(), test_build_name_variants(), test_clean_label(), test_place_name()

### Community 8 - "test_core.py / run()"
Cohesion: 0.32
Nodes (8): run(), scan(), make_jpg(), settings(), test_cancel(), test_dup_off_adds_suffix(), test_pipeline(), test_read_meta()

## Ambiguous Edges - Review These
- `CLAUDE.md (프로젝트 지침)` → `README.md (photo_auto 사진분류)`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **5 isolated node(s):** `동영상 지원 (확인필요)`, `메인 화면`, `개발 단계 Phase 0-9`, `.claude/CLAUDE.md (graphify 트리거)`, `README.md (photo_auto 사진분류)`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 43 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DB` connect `DB / db.py` to `test_core.py / run()`, `geo.py / Geo`, `app.py / App`?**
  _High betweenness centrality (0.104) - this node is a cross-community bridge._
- **What connects `동영상 지원 (확인필요)`, `메인 화면`, `개발 단계 Phase 0-9` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLAUDE.md (프로젝트 지침) / organizer.py (파이프라인 ` be split into smaller, more focused modules?**
  _Cohesion score 0.07777777777777778 - nodes in this community are weakly interconnected._
- **Why does `App` connect `app.py / App` to `organizer.py / choose_target()`, `config.py / pathlib`, `ai.py / make_labeler()`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `test_pipeline()` connect `test_core.py / run()` to `DB / db.py`, `organizer.py / choose_target()`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `CLAUDE.md (프로젝트 지침)` and `README.md (photo_auto 사진분류)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._