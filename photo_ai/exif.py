"""촬영일(DateTimeOriginal)과 GPS 읽기. 파일 생성/수정일은 절대 쓰지 않는다."""
from datetime import datetime
from pathlib import Path

from PIL import Image

try:  # HEIC 지원(선택)
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
_EXIF_IFD, _GPS_IFD, _DTO = 0x8769, 0x8825, 36867


def _deg(v, ref) -> float:
    d, m, s = (float(x) for x in v)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def read_meta(path: Path) -> tuple[datetime | None, tuple[float, float] | None]:
    with Image.open(path) as img:
        exif = img.getexif()
        raw = exif.get_ifd(_EXIF_IFD).get(_DTO)
        gps = exif.get_ifd(_GPS_IFD)
    taken = None
    if raw:
        try:
            taken = datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    pos = None
    if gps.get(2) and gps.get(4):
        try:
            lat, lon = _deg(gps[2], gps.get(1)), _deg(gps[4], gps.get(3))
            if (lat, lon) != (0.0, 0.0):  # 일부 기기가 GPS 없을 때 0,0을 기록한다
                pos = (lat, lon)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return taken, pos
