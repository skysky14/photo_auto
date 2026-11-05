"""좌표 → 주소명(구/시 + 동). 공공 행정동 경계 데이터를 SQLite에 저장해 두고 점-다각형 판정으로 찾는다. 키·인터넷 불필요."""
import hashlib
import json
import logging
import tempfile
import urllib.request
from pathlib import Path

from . import namer

log = logging.getLogger("photoai.geo")

# 출처: GitHub vuski/admdongkor (MIT). 데이터를 갱신하려면 URL과 해시를 같이 바꾼다.
DATA_URL = "https://raw.githubusercontent.com/vuski/admdongkor/master/ver20261001/HangJeongDong_ver20261001.geojson"
DATA_SHA256 = "843ece3a0b3429742cd4a1b699cc13987a88b5e5401f382e7fdaaa194ea5e605"


def parse_geojson(data: dict) -> list[tuple]:
    """GeoJSON → db.replace_regions 행. 좌표는 소수 5자리(약 1m)로 줄인다."""
    rows = []
    for f in data["features"]:
        p, g = f["properties"], f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        polys = [[[[round(x, 5), round(y, 5)] for x, y in ring] for ring in poly] for poly in polys]
        xs = [x for poly in polys for x, _ in poly[0]]
        ys = [y for poly in polys for _, y in poly[0]]
        rows.append((p.get("adm_cd", ""), p.get("sggnm", ""), p["adm_nm"].split()[-1].replace("·", "."),
                     min(xs), min(ys), max(xs), max(ys), json.dumps(polys, separators=(",", ":"))))
    return rows


def download_regions(db, progress, url: str = DATA_URL, sha256: str = DATA_SHA256) -> int:
    """경계 데이터를 내려받아 해시를 확인하고 DB에 저장한다. 저장한 행정동 수를 돌려준다. 해시가 다르면 저장하지 않는다."""
    h = hashlib.sha256()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
        path = Path(tmp.name)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                total, done = int(r.headers.get("Content-Length") or 0), 0
                while chunk := r.read(1 << 20):
                    tmp.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    progress(f"행정구역 데이터 다운로드 중 ({done >> 20}/{total >> 20} MB)", done / total if total else None)
            if h.hexdigest() != sha256:
                raise RuntimeError("행정구역 데이터의 해시가 달라 저장하지 않았습니다.")
            tmp.flush()
            progress("행정구역 데이터 저장 중...", None)
            rows = parse_geojson(json.loads(path.read_text(encoding="utf-8")))
            db.replace_regions(rows)
            log.info("행정구역 %d개 저장", len(rows))
            return len(rows)
        finally:
            tmp.close()
            path.unlink(missing_ok=True)


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi, xj, yj = *ring[i], *ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _in_polys(x: float, y: float, polys: list) -> bool:
    """폴리곤의 바깥 고리 안이고 구멍(안쪽 고리) 밖이면 True."""
    return any(_in_ring(x, y, p[0]) and not any(_in_ring(x, y, h) for h in p[1:]) for p in polys)


class Geo:
    def __init__(self, db):
        self.db = db
        self.boxes = db.region_bboxes()  # 약 3,500개라 사진마다 훑어도 ms 단위
        self._cache: dict[str, tuple[str, list]] = {}

    def place(self, lat: float, lon: float) -> str | None:
        """주소명. 어느 행정동에도 없으면(바다 등) None."""
        for rid, minx, miny, maxx, maxy in self.boxes:
            if minx <= lon <= maxx and miny <= lat <= maxy:
                if rid not in self._cache:
                    sgg, dong, geom = self.db.region_geom(rid)
                    self._cache[rid] = (namer.place_name(sgg), json.loads(geom))
                name, polys = self._cache[rid]
                if _in_polys(lon, lat, polys):
                    self.db.add_stat("geo_hits")
                    return name or None
        self.db.add_stat("geo_miss")
        return None
