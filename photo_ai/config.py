"""config.ini 읽기/쓰기. exe로 빌드되면 exe 옆, 개발 중에는 프로젝트 루트에 둔다."""
import configparser
import sys
from dataclasses import dataclass, fields
from pathlib import Path

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.ini"
DB_PATH = APP_DIR / "photoai.db"
# 카카오 REST API 키(내장). 로컬 API는 이 키만 쓴다. JavaScript/네이티브 앱 키는 쓰지 않는다.
KAKAO_REST_KEY = "3e38ad2f80c7c5c1d94cd2af61d8fa5b"


@dataclass
class Settings:
    # kakao_key는 비어 있으면 load()가 내장 키로 채운다
    source: str = ""
    result: str = ""
    ai_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:7b"
    kakao_key: str = ""
    check_same: bool = True
    recursive: bool = True


# (섹션, 키) 매핑. 필드 순서와 무관하게 INI 구조를 한곳에서 정의한다.
_MAP = {
    "source": ("Folders", "Source"), "result": ("Folders", "Result"),
    "ai_enabled": ("AI", "Enabled"), "ollama_url": ("Ollama", "Url"), "ollama_model": ("Ollama", "Model"),
    "kakao_key": ("Kakao", "ApiKey"),
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
    s.kakao_key = s.kakao_key or KAKAO_REST_KEY
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
