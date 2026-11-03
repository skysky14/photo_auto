"""카카오 로컬 API로 좌표 → 주소명(구/시 + 동/읍/면). 조회 결과는 SQLite에 캐시한다."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from . import namer

log = logging.getLogger("photoai.geo")
GRID = 0.002  # 도 단위. 위도 약 220m, 경도 약 180m(위도 37도). shortcut: 동 경계 근처 사진은 이웃 동 이름이 붙을 수 있다, 정확도가 중요하면 줄일 것
URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"


class Geo:
    def __init__(self, api_key: str, db):
        self.key, self.db = api_key, db

    def place(self, lat: float, lon: float) -> str | None:
        """주소명. 좌표가 같은 곳이면 캐시 사용. 조회 실패는 None(캐시하지 않음)."""
        if not self.key:
            return None
        ck = f"{round(lat / GRID) * GRID:.3f},{round(lon / GRID) * GRID:.3f}"  # 격자 중심 좌표(약 200m)
        hit = self.db.cache_get(ck)
        if hit is not None:
            self.db.add_stat("gps_cache_hits")
            return hit or None
        place = self._fetch(lat, lon)
        if place is not None:
            self.db.cache_put(ck, place)
        return place or None

    def _fetch(self, lat: float, lon: float) -> str | None:
        req = urllib.request.Request(f"{URL}?{urllib.parse.urlencode({'x': lon, 'y': lat})}",
                                     headers={"Authorization": f"KakaoAK {self.key}"})
        self.db.add_stat("kakao_calls")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                docs = json.load(r).get("documents", [])
        except urllib.error.HTTPError as e:  # 키/서비스 설정 오류는 본문에 이유가 있다
            log.error("카카오 API HTTP %s (%s,%s): %s", e.code, lat, lon, e.read().decode("utf-8", "replace"))
            return None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            log.error("카카오 API 호출 실패 (%s,%s): %r", lat, lon, e)
            return None
        return parse_regions(docs)


def parse_regions(docs: list[dict]) -> str:
    """행정동(H) 우선, 없으면 법정동(B). 결과가 없으면 ''(바다 등)."""
    for kind in ("H", "B"):
        for d in docs:
            if d.get("region_type") == kind and d.get("region_3depth_name"):
                return namer.place_name(d.get("region_2depth_name", ""), d["region_3depth_name"])
    return ""
