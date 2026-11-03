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


def test_parse_regions():
    docs = [{"region_type": "B", "region_2depth_name": "연수구", "region_3depth_name": "옥련동"},
            {"region_type": "H", "region_2depth_name": "연수구", "region_3depth_name": "송도동"}]
    assert geo.parse_regions(docs) == "연수구송도동"
    assert geo.parse_regions([]) == ""


def test_geo_cache(tmp_path, monkeypatch):
    db = dbm.DB(tmp_path / "t.db")
    g = geo.Geo("key", db)
    calls = []
    monkeypatch.setattr(g, "_fetch", lambda lat, lon: calls.append(1) or "연수구송도동")
    assert g.place(37.5, 126.6) == "연수구송도동"
    assert g.place(37.50001, 126.60001) == "연수구송도동"  # 같은 캐시 키
    assert g.place(37.5009, 126.6009) == "연수구송도동"  # 약 100m 이내는 같은 격자
    assert len(calls) == 1
    assert db.stats()[1]["gps_cache_hits"] == 2
    assert db.cache_get("37.500,126.600") == "연수구송도동"  # 키는 격자 중심 좌표
    g.place(37.52, 126.6)  # 약 2km 떨어지면 새로 조회
    assert len(calls) == 2


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
    assert [x.name for x in (root / "중복파일").glob("*")] == ["20210216_191725_산책중.jpg"]
    assert (root / "분류불가" / "no_date.jpg").exists()
    assert (src / "broken.jpg").exists()  # 실패 파일은 원본 유지
    assert (res.ok, res.unclassified, res.duplicates, res.failed) == (2, 1, 1, 1)
    today, total = db.stats()
    assert total["processed"] == 4 and total["ai_success"] == 3 and total["failed"] == 1

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
