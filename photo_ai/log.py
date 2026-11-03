"""로그 파일: logs/app.log(전체), logs/error.log(오류만). 개발 단계라 상세하게 남긴다."""
import logging
from logging.handlers import RotatingFileHandler

from .config import APP_DIR

LOG_DIR = APP_DIR / "logs"


def setup() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger("photoai")
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name, level in (("app.log", logging.DEBUG), ("error.log", logging.ERROR)):
        h = RotatingFileHandler(LOG_DIR / name, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        h.setLevel(level)
        h.setFormatter(fmt)
        root.addHandler(h)
