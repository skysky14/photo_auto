"""config.ini 읽기/쓰기. exe로 빌드되면 exe 옆, 개발 중에는 프로젝트 루트에 둔다."""
import configparser
import sys
from dataclasses import dataclass, fields
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.ini"
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "photoai.db"


def migrate_old_db(old_dir: Path = APP_DIR, new_path: Path = DB_PATH) -> None:
    """예전 위치(실행 폴더 바로 아래)의 DB가 있고 새 위치에 없으면 data 폴더로 옮긴다. -wal/-shm도 함께."""
    old = old_dir / new_path.name
    if not old.exists() or new_path.exists():
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        f = old.with_name(old.name + suffix)
        if f.exists():
            f.replace(new_path.with_name(new_path.name + suffix))


@dataclass
class Settings:
    source: str = ""
    result: str = ""
    ai_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    check_same: bool = True
    recursive: bool = True


# (섹션, 키) 매핑. 필드 순서와 무관하게 INI 구조를 한곳에서 정의한다.
_MAP = {
    "source": ("Folders", "Source"), "result": ("Folders", "Result"),
    "ai_enabled": ("AI", "Enabled"), "ollama_url": ("Ollama", "Url"), "ollama_model": ("Ollama", "Model"),
    "check_same": ("Duplicate", "CheckSameFile"), "recursive": ("Scan", "Recursive"),
}


def load(path: Path = CONFIG_PATH) -> Settings:
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")
    s = Settings()
    for f in fields(s):
        sec, key = _MAP[f.name]
        if not cp.has_option(sec, key):
            continue
        v = cp.get(sec, key)
        setattr(s, f.name, cp.getboolean(sec, key) if f.type is bool else v)
    return s


def save(s: Settings, path: Path = CONFIG_PATH) -> None:
    cp = configparser.ConfigParser()
    for f in fields(s):
        sec, key = _MAP[f.name]
        if not cp.has_section(sec):
            cp.add_section(sec)
        cp.set(sec, key, str(getattr(s, f.name)))
    with open(path, "w", encoding="utf-8") as fh:
        cp.write(fh)
