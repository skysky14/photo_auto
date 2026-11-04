import threading
from datetime import datetime
from pathlib import Path

from PIL import Image

from photo_ai import config, db as dbm, exif, geo, namer, organizer


def make_jpg(path: Path, taken: str | None = None, gps=None, color=(10, 20, 30)):
    img = Image.new("RGB", (8, 8), color)
    ex = Image.Exif()
    if taken:
        ex[0x8769] = {36867: taken}
    if gps:
        ex[0x8825] = {1: "N", 2: (gps[0], 0.0, 0.0), 3: "E", 4: (gps[1], 0.0, 0.0)}
    img.save(path, exif=ex)


def settings(tmp_path, **kw):
    (tmp_path / "src").mkdir(exist_ok=True)
    return config.Settings(source=str(tmp_path / "src"), result=str(tmp_path / "src" / "정리완료"), **kw)


def test_clean_label():
    assert namer.clean_label("산책중\n설명") == "산책중"
    assert namer.clean_label('"가족 사진!"') == "가족사진"
    assert namer.clean_label("열한글자를넘는설명어입니다만") is None
    assert namer.clean_label("") is None


def test_place_name():
    assert namer.place_name("연수구", "송도동") == "연수구송도동"
    assert namer.place_name("수원시 영통구", "영통동") == "수원시영통구영통동"[-10:]


def test_build_name_variants():
    t = datetime(2021, 2, 16, 19, 17, 25)
    assert namer.build_name(t, "연수구송도동", "산책중", ".JPG") == "20210216_191725_연수구송도동_산책중.jpg"
    assert namer.build_name(t, None, "가족사진", ".jpg") == "20210216_191725_가족사진.jpg"
    assert namer.build_name(t, None, None, ".jpg") == "20210216_191725.jpg"


def test_read_meta(tmp_path):
    p = tmp_path / "a.jpg"
    make_jpg(p, "2021:02:16 19:17:25", (37.5, 126.6))
    taken, pos = exif.read_meta(p)
    assert taken == datetime(2021, 2, 16, 19, 17, 25) and pos == (37.5, 126.6)
    make_jpg(p)
    assert exif.read_meta(p) == (None, None)


SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]


def geojson():
    def feat(nm, sgg, coords):
        return {"type": "Feature", "properties": {"adm_nm": nm, "sggnm": sgg, "adm_cd": "1"},
                "geometry": {"type": "MultiPolygon", "coordinates": coords}}
    return {"features": [feat("서울특별시 연수구 송도1·4동", "연수구", [[SQUARE, HOLE]]),  # 구멍이 있는 동
                         feat("서울특별시 연수구 송도2동", "연수구", [[[[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]]])]}  # 구멍 자리를 채운 동


def test_geo_place(tmp_path):
    db = dbm.DB(tmp_path / "t.db")
    db.replace_regions(geo.parse_geojson(geojson()))
    g = geo.Geo(db)  # 좌표는 (lon=x, lat=y)
    assert g.place(lat=2, lon=2) == "연수구송도1.4동"    # 안쪽, 가운뎃점은 .으로
    assert g.place(lat=5, lon=5) == "연수구송도2동"      # 1동의 구멍 안은 2동
    assert g.place(lat=2, lon=11) is None                # 경계 밖
    assert g.place(lat=11, lon=2) is None
    hits, miss = db.stats()[1]["geo_hits"], db.stats()[1]["geo_miss"]
    assert (hits, miss) == (2, 2)


def test_download_regions_checks_hash(tmp_path, monkeypatch):
    import hashlib
    import io
    import json

    body = json.dumps(geojson()).encode()

    class Resp(io.BytesIO):
        headers = {"Content-Length": str(len(body))}

    monkeypatch.setattr(geo.urllib.request, "urlopen", lambda url, timeout=0: Resp(body))
    db = dbm.DB(tmp_path / "t.db")
    try:
        geo.download_regions(db, lambda *a: None, "http://x", "0" * 64)
        raise AssertionError("해시가 달라도 저장됨")
    except RuntimeError:
        pass
    assert db.region_count() == 0
    n = geo.download_regions(db, lambda *a: None, "http://x", hashlib.sha256(body).hexdigest())
    assert n == 2 and db.region_count() == 2


def test_pipeline(tmp_path):
    st = settings(tmp_path, check_same=True)
    src = Path(st.source)
    make_jpg(src / "IMG_1.jpg", "2021:02:16 19:17:25")
    make_jpg(src / "IMG_2.jpg", "2021:02:16 19:17:25")                      # 같은 이름, 같은 내용 → 중복
    make_jpg(src / "IMG_3.jpg", "2021:02:16 19:17:25", color=(200, 0, 0))    # 같은 이름, 다른 내용 → _001
    make_jpg(src / "no_date.jpg")
    (src / "broken.jpg").write_bytes(b"not an image")
    db = dbm.DB(tmp_path / "t.db")

    res = organizer.run(st, db, labeler=lambda p: "산책중")
    root = Path(st.result)
    assert sorted(x.name for x in root.glob("*.jpg")) == ["20210216_191725_산책중.jpg", "20210216_191725_산책중_001.jpg"]
    assert [x.name for x in (root / "중복파일").glob("*")] == ["IMG_2.jpg"]  # 중복은 원본 이름 그대로
    assert (root / "분류불가" / "no_date.jpg").exists()
    assert (src / "broken.jpg").exists()  # 실패 파일은 원본 유지
    assert (res.ok, res.unclassified, res.duplicates, res.failed) == (2, 1, 1, 1)
    today, total = db.stats()
    assert total["processed"] == 4 and total["ai_success"] == 2 and total["failed"] == 1  # 중복은 AI를 건너뜀

    # 되돌리기
    done, skipped = organizer.undo(db, res.job_id)
    assert done == 4 and skipped == 0
    assert (src / "IMG_1.jpg").exists() and (src / "no_date.jpg").exists()

    # 재실행해도 결과 폴더는 다시 스캔되지 않는다
    assert organizer.scan(src, root, True) == sorted(p for p in src.glob("*.jpg"))


def test_dup_off_adds_suffix(tmp_path):
    st = settings(tmp_path, check_same=False)
    src = Path(st.source)
    make_jpg(src / "a.jpg", "2021:02:16 19:17:25")
    make_jpg(src / "b.jpg", "2021:02:16 19:17:25")
    organizer.run(st, dbm.DB(tmp_path / "t.db"))
    assert sorted(p.name for p in Path(st.result).glob("*.jpg")) == ["20210216_191725.jpg", "20210216_191725_001.jpg"]


def test_cancel(tmp_path):
    st = settings(tmp_path)
    make_jpg(Path(st.source) / "a.jpg", "2021:02:16 19:17:25")
    ev = threading.Event()
    ev.set()
    assert organizer.run(st, dbm.DB(tmp_path / "t.db"), cancel=ev).cancelled


def test_config_roundtrip(tmp_path):
    p = tmp_path / "c.ini"
    s = config.Settings(source="a", ai_enabled=False, check_same=False)
    config.save(s, p)
    assert config.load(p) == s


def test_ai_diagnose(monkeypatch):
    from photo_ai import ai

    def down(url):
        raise ConnectionError

    monkeypatch.setattr(ai, "_models", down)
    monkeypatch.setattr(ai, "find_ollama", lambda: None)
    assert ai.diagnose("http://localhost:11434", "m") == "no_install"
    monkeypatch.setattr(ai, "find_ollama", lambda: Path("x"))
    assert ai.diagnose("http://localhost:11434", "m") == "no_server"
    assert ai.diagnose("http://10.0.0.5:11434", "m") == "unreachable"
    monkeypatch.setattr(ai, "_models", lambda url: ["llava:7b"])
    assert ai.diagnose("http://localhost:11434", "qwen2.5vl:7b") == "no_model"
    monkeypatch.setattr(ai, "_models", lambda url: ["qwen2.5vl:7b"])
    assert ai.diagnose("http://localhost:11434", "qwen2.5vl:7b") is None


def test_ai_prepare_runs_missing_steps(monkeypatch):
    from photo_ai import ai

    states = iter(["no_install", "no_server", "no_model", None])
    calls = []
    monkeypatch.setattr(ai, "diagnose", lambda u, m: next(states))
    monkeypatch.setattr(ai, "_install", lambda p: calls.append("install"))
    monkeypatch.setattr(ai, "_serve", lambda u, p: calls.append("serve"))
    monkeypatch.setattr(ai, "_pull", lambda u, m, p: calls.append("pull"))
    ai.prepare("http://localhost:11434", "m", lambda *a: None)
    assert calls == ["install", "serve", "pull"]


def test_ai_model_list_and_pull_guards(monkeypatch):
    import pytest
    from photo_ai import ai

    assert len(ai.MODEL_NAMES) == 10 and len(set(ai.MODEL_NAMES)) == 10
    assert ai.is_installed({"gemma3:4b"}, "gemma3:4b") and ai.is_installed({"moondream:latest"}, "moondream")
    assert not ai.is_installed({"gemma3:4b"}, "llava:7b")
    with pytest.raises(RuntimeError):  # 원격 Ollama에는 설치하지 않는다
        ai.pull_model("http://10.0.0.5:11434", "gemma3:4b", lambda *a: None)
    with pytest.raises(RuntimeError):  # 목록 밖 이름은 내려받지 않는다
        ai._pull("http://localhost:11434", "evil.example.com/x/y", lambda *a: None)


def test_installed_models_falls_back_to_disk(tmp_path, monkeypatch):
    from photo_ai import ai

    d = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "gemma3"
    d.mkdir(parents=True)
    (d / "4b").write_text("{}")
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path))
    monkeypatch.setattr(ai, "_models", lambda url: (_ for _ in ()).throw(ConnectionError()))
    assert ai.installed_models("http://localhost:11434") == {"gemma3:4b"}  # 서버 꺼짐 → 디스크
    assert ai.installed_models("http://10.0.0.5:11434") is None            # 원격은 알 수 없음


def test_ensure_server(monkeypatch):
    import pytest
    from photo_ai import ai

    calls = []
    monkeypatch.setattr(ai, "_serve", lambda u, p: calls.append("serve"))
    monkeypatch.setattr(ai, "_models", lambda url: [])
    ai.ensure_server("http://localhost:11434", lambda *a: None)
    assert calls == []                                    # 이미 켜져 있으면 그대로
    monkeypatch.setattr(ai, "_models", lambda url: (_ for _ in ()).throw(ConnectionError()))
    ai.ensure_server("http://localhost:11434", lambda *a: None)
    assert calls == ["serve"]                             # 꺼져 있으면 실행
    with pytest.raises(RuntimeError):                     # 원격은 건드리지 않는다
        ai.ensure_server("http://10.0.0.5:11434", lambda *a: None)


def test_model_info_covers_all_models():
    from photo_ai import ai

    assert set(ai.MODEL_INFO) == set(ai.MODEL_NAMES)
    assert all(len(v) == 4 for v in ai.MODEL_INFO.values())


def test_labeler_gives_up_when_ollama_is_dead(tmp_path, monkeypatch):
    import pytest
    from photo_ai import ai

    class Dead:
        def __init__(self, **kw): pass
        def chat(self, **kw): raise TimeoutError

    monkeypatch.setattr(ai.ollama, "Client", Dead)
    p = tmp_path / "a.jpg"
    make_jpg(p, "2021:02:16 19:17:25")
    lab = ai.make_labeler("http://localhost:11434", "m", give_up_after=2)
    assert lab(p) is None                  # 1장째 실패는 설명어만 생략
    with pytest.raises(ai.AIUnavailable):  # 연속 2장째에서 포기
        lab(p)


def test_run_stops_when_ai_unavailable(tmp_path):
    from photo_ai import ai

    st = settings(tmp_path, check_same=True)
    src = Path(st.source)
    for i in range(3):
        make_jpg(src / f"IMG_{i}.jpg", f"2021:02:16 19:17:2{i}")

    def dead(p): raise ai.AIUnavailable("응답 없음")

    res = organizer.run(st, dbm.DB(tmp_path / "t.db"), labeler=dead)
    assert res.cancelled and res.reason == "응답 없음" and res.ok == 0
    assert len(list(src.glob("*.jpg"))) == 3  # 아무것도 옮기지 않았다


def test_result_lists(tmp_path):
    st = settings(tmp_path, check_same=True)
    src = Path(st.source)
    make_jpg(src / "IMG_1.jpg", "2021:02:16 19:17:25")
    make_jpg(src / "IMG_2.jpg", "2021:02:16 19:17:25")                      # IMG_1과 같은 내용 → 중복
    make_jpg(src / "no_date.jpg")
    (src / "broken.jpg").write_bytes(b"not an image")
    seen = []
    res = organizer.run(st, dbm.DB(tmp_path / "t.db"), progress=lambda i, n, p, msg: seen.append((p.name, msg)))
    assert res.ok_items == [("IMG_1.jpg", "20210216_191725.jpg")]
    assert res.unclassified_items == ["no_date.jpg"] and res.failed_items == ["broken.jpg"]
    assert res.dup_items == [("IMG_2.jpg", "IMG_2.jpg", "20210216_191725.jpg")]
    assert ("IMG_1.jpg", "분석 중") in seen                                  # 처리 전에도 파일명을 알린다
    text = organizer.format_result(res)
    for part in ("■ 성공 (1)", "IMG_1.jpg  →  20210216_191725.jpg", "■ 실패 (1)", "broken.jpg", "■ 분류불가 (1)", "■ 중복 (1)"):
        assert part in text


def test_db_creates_folder_and_migrates_old_file(tmp_path):
    new = tmp_path / "data" / "photoai.db"
    dbm.DB(new)                                   # data 폴더를 스스로 만든다
    assert new.exists()
    old_dir, new2 = tmp_path / "app", tmp_path / "app" / "data" / "photoai.db"
    old_dir.mkdir()
    (old_dir / "photoai.db").write_text("x")
    (old_dir / "photoai.db-wal").write_text("w")
    config.migrate_old_db(old_dir, new2)
    assert new2.read_text() == "x" and (new2.parent / "photoai.db-wal").exists() and not (old_dir / "photoai.db").exists()
    (old_dir / "photoai.db").write_text("again")   # 새 위치에 이미 있으면 덮어쓰지 않는다
    config.migrate_old_db(old_dir, new2)
    assert new2.read_text() == "x" and (old_dir / "photoai.db").exists()


def _dup_setup(tmp_path, **kw):
    st = settings(tmp_path, **kw)
    return st, Path(st.source), Path(st.result), dbm.DB(tmp_path / "t.db")


def test_duplicate_found_even_if_name_differs_and_skips_ai(tmp_path):
    st, src, root, db = _dup_setup(tmp_path, check_same=True)
    make_jpg(src / "A.jpg", "2021:02:16 19:17:25")
    organizer.run(st, db, labeler=lambda p: "산책중")           # 정리됨: 20210216_191725_산책중.jpg
    make_jpg(src / "B.jpg", "2021:02:16 19:17:25")              # 같은 내용의 사본
    asked = []
    res = organizer.run(st, db, labeler=lambda p: asked.append(p) or "가족사진")  # 설명어가 달라도(이름이 달라도)
    assert res.duplicates == 1 and res.ok == 0 and asked == []  # 중복이라 AI 호출 없음
    assert [x.name for x in (root / "중복파일").glob("*")] == ["B.jpg"]
    assert res.dup_items == [("B.jpg", "B.jpg", "20210216_191725_산책중.jpg")]
    assert [x.name for x in root.glob("*.jpg")] == ["20210216_191725_산책중.jpg"]


def test_same_size_different_content_is_not_duplicate(tmp_path):
    st, src, root, db = _dup_setup(tmp_path, check_same=True)
    make_jpg(src / "A.jpg", "2021:02:16 19:17:25", color=(10, 20, 30))
    make_jpg(src / "B.jpg", "2021:02:16 19:17:25", color=(200, 0, 0))
    a, b = (src / "A.jpg").stat().st_size, (src / "B.jpg").stat().st_size
    res = organizer.run(st, db)
    assert res.duplicates == 0 and res.ok == 2, (a, b)


def test_index_ignores_special_folders_and_prunes_missing(tmp_path):
    st, src, root, db = _dup_setup(tmp_path, check_same=True)
    for sub in (root, root / "분류불가", root / "중복파일"):
        sub.mkdir(parents=True, exist_ok=True)
    make_jpg(root / "keep.jpg", "2021:02:16 19:17:25")
    make_jpg(root / "분류불가" / "u.jpg")
    make_jpg(root / "중복파일" / "d.jpg", "2021:02:16 19:17:25")
    organizer.index_folder(db, root)
    paths = [p for p, in db._query("SELECT path FROM file_index")]
    assert [Path(p).name for p in paths] == ["keep.jpg"]
    (root / "keep.jpg").unlink()
    organizer.index_folder(db, root)
    assert db._query("SELECT COUNT(*) FROM file_index")[0][0] == 0


def test_index_stores_metadata(tmp_path):
    st, src, root, db = _dup_setup(tmp_path, check_same=True)
    make_jpg(src / "A.jpg", "2021:02:16 19:17:25", (37.5, 126.6))
    organizer.run(st, db)
    row = db._query("SELECT taken,lat,lon,size FROM file_index")[0]
    assert row[0] == "2021-02-16T19:17:25" and (round(row[1], 3), round(row[2], 3)) == (37.5, 126.6) and row[3] > 0


def test_no_checksum_dedup_when_option_off(tmp_path):
    st, src, root, db = _dup_setup(tmp_path, check_same=False)
    make_jpg(src / "A.jpg", "2021:02:16 19:17:25")
    organizer.run(st, db, labeler=lambda p: "산책중")
    make_jpg(src / "B.jpg", "2021:02:16 19:17:25")
    res = organizer.run(st, db, labeler=lambda p: "가족사진")
    assert res.duplicates == 0 and res.ok == 1 and db._query("SELECT COUNT(*) FROM file_index")[0][0] == 0
