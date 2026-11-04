"""SQLite 저장소. 모든 테이블에 id(UUID)/updated_at/synced를 둬서 나중에 서버 동기화가 가능하게 한다."""
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

STAT_NAMES = (
    "processed", "geo_hits", "geo_miss", "ollama_calls", "ai_success", "ai_fail",
    "unclassified", "duplicates", "failed", "elapsed_sec",
)

_SCHEMA = """
DROP TABLE IF EXISTS gps_cache;  -- 예전 GPS 캐시(더 이상 쓰지 않음)
CREATE TABLE IF NOT EXISTS regions(
  id TEXT PRIMARY KEY, adm_cd TEXT NOT NULL, sgg TEXT NOT NULL, dong TEXT NOT NULL,
  minx REAL NOT NULL, miny REAL NOT NULL, maxx REAL NOT NULL, maxy REAL NOT NULL, geom TEXT NOT NULL,
  updated_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS file_index(
  id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, size INTEGER NOT NULL, mtime REAL NOT NULL, sha256 TEXT,
  taken TEXT, lat REAL, lon REAL, updated_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_file_index_size ON file_index(size);
CREATE TABLE IF NOT EXISTS stats(
  id TEXT PRIMARY KEY, day TEXT NOT NULL, name TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0, UNIQUE(day, name));
CREATE TABLE IF NOT EXISTS history(
  id TEXT PRIMARY KEY, job_id TEXT NOT NULL, src TEXT NOT NULL, dst TEXT NOT NULL,
  kind TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS log(
  id TEXT PRIMARY KEY, job_id TEXT, level TEXT NOT NULL, msg TEXT NOT NULL,
  updated_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex


class DB:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, timeout=30, check_same_thread=False)  # DB 툴이 잠깐 잡고 있어도 기다린다
        self.lock = threading.Lock()
        with self.lock:
            self.con.execute("PRAGMA journal_mode=WAL")
            self.con.execute("PRAGMA synchronous=NORMAL")
            self.con.executescript(_SCHEMA)

    def _exec(self, sql, args=()):
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur

    def _query(self, sql, args=()):
        with self.lock:
            return self.con.execute(sql, args).fetchall()

    # 행정동 경계 (geo.download_regions가 채운다)
    def region_count(self) -> int:
        return self._query("SELECT COUNT(*) FROM regions")[0][0]

    def region_bboxes(self) -> list[tuple]:
        return self._query("SELECT id,minx,miny,maxx,maxy FROM regions")

    def region_geom(self, rid: str) -> tuple[str, str, str]:
        """(시군구, 동, 좌표 JSON)"""
        return self._query("SELECT sgg,dong,geom FROM regions WHERE id=?", (rid,))[0]

    def replace_regions(self, rows) -> None:
        """rows: (adm_cd, sgg, dong, minx, miny, maxx, maxy, geom_json). 한 트랜잭션으로 통째 교체."""
        now = _now()
        with self.lock, self.con:
            self.con.execute("DELETE FROM regions")
            self.con.executemany(
                "INSERT INTO regions(id,adm_cd,sgg,dong,minx,miny,maxx,maxy,geom,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                [(_id(), *r, now) for r in rows])

    # 정리된(정상 분류) 파일 색인: 중복 판별용. sha256은 필요할 때 계산해 채운다.
    def index_get(self, path) -> tuple[int, float] | None:
        rows = self._query("SELECT size,mtime FROM file_index WHERE path=?", (str(path),))
        return rows[0] if rows else None

    def index_upsert(self, path, size: int, mtime: float, taken, pos, sha: str | None = None) -> None:
        lat, lon = pos if pos else (None, None)
        self._exec(
            "INSERT INTO file_index(id,path,size,mtime,sha256,taken,lat,lon,updated_at) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime, sha256=excluded.sha256, "
            "taken=excluded.taken, lat=excluded.lat, lon=excluded.lon, updated_at=excluded.updated_at, synced=0",
            (_id(), str(path), size, mtime, sha, taken.isoformat() if taken else None, lat, lon, _now()))

    def index_by_size(self, size: int) -> list[tuple[str, str | None]]:
        return self._query("SELECT path,sha256 FROM file_index WHERE size=?", (size,))

    def index_set_sha(self, path, sha: str) -> None:
        self._exec("UPDATE file_index SET sha256=?, updated_at=?, synced=0 WHERE path=?", (sha, _now(), str(path)))

    def index_prune(self, keep: set[str]) -> None:
        """색인에서 keep에 없는 경로(지워졌거나 옮겨진 파일)를 지운다."""
        gone = [(p,) for (p,) in self._query("SELECT path FROM file_index") if p not in keep]
        if gone:
            with self.lock, self.con:
                self.con.executemany("DELETE FROM file_index WHERE path=?", gone)

    # 통계
    def add_stat(self, name: str, n: int = 1) -> None:
        self._exec(
            "INSERT INTO stats(id,day,name,value,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(day,name) DO UPDATE SET value=value+excluded.value, updated_at=excluded.updated_at, synced=0",
            (_id(), datetime.now().strftime("%Y-%m-%d"), name, n, _now()))

    def stats(self) -> tuple[dict, dict]:
        """(오늘, 누적) 통계 dict."""
        today = datetime.now().strftime("%Y-%m-%d")
        t = dict.fromkeys(STAT_NAMES, 0)
        a = dict.fromkeys(STAT_NAMES, 0)
        for day, name, value in self._query("SELECT day,name,value FROM stats"):
            if name in a:
                a[name] += value
                if day == today:
                    t[name] += value
        return t, a

    # 이력/로그
    def add_history(self, job_id: str, src, dst, kind: str) -> None:
        self._exec("INSERT INTO history(id,job_id,src,dst,kind,updated_at) VALUES(?,?,?,?,?,?)",
                   (_id(), job_id, str(src), str(dst), kind, _now()))

    def last_job(self) -> str | None:
        rows = self._query("SELECT job_id FROM history WHERE undone=0 ORDER BY rowid DESC LIMIT 1")
        return rows[0][0] if rows else None

    def job_history(self, job_id: str) -> list[tuple[str, str, str]]:
        """되돌리기 대상(id, src, dst). 나중에 이동한 것부터."""
        return self._query("SELECT id,src,dst FROM history WHERE job_id=? AND undone=0 ORDER BY rowid DESC", (job_id,))

    def mark_undone(self, hid: str) -> None:
        self._exec("UPDATE history SET undone=1, updated_at=?, synced=0 WHERE id=?", (_now(), hid))

    def log(self, job_id: str | None, level: str, msg: str) -> None:
        self._exec("INSERT INTO log(id,job_id,level,msg,updated_at) VALUES(?,?,?,?,?)",
                   (_id(), job_id, level, msg, _now()))
