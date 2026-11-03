"""파일명 생성 규칙: 순수 함수만 두어 GUI/AI 없이 테스트 가능하게 유지한다."""
import re
from datetime import datetime
from pathlib import Path

from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
_EXIF_DATETIME_ORIGINAL = 36867  # DateTimeOriginal
_EXIF_IFD = 0x8769
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def list_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def get_taken_date(path: Path) -> str | None:
    """EXIF 촬영일을 YYYY-MM-DD로 반환. 없으면 None."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            raw = exif.get_ifd(_EXIF_IFD).get(_EXIF_DATETIME_ORIGINAL) or exif.get(306)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def sanitize(desc: str, max_len: int = 40) -> str:
    desc = _INVALID_CHARS.sub("", desc).strip().strip(".")
    desc = re.sub(r"\s+", "_", desc)
    return desc[:max_len].rstrip("_")


def build_name(desc: str, date: str | None, ext: str) -> str:
    stem = "_".join(x for x in (date, sanitize(desc)) if x) or "untitled"
    return stem + ext.lower()


def unique_path(target: Path, taken: set[Path] = frozenset()) -> Path:
    """이미 존재하거나 예약된 이름이면 _2, _3... 을 붙인다."""
    cand, n = target, 2
    while cand.exists() or cand in taken:
        cand = target.with_name(f"{target.stem}_{n}{target.suffix}")
        n += 1
    return cand
