"""Ollama 비전 모델로 사진 설명어 생성."""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import ollama
from PIL import Image, ImageOps

from . import namer

log = logging.getLogger("photoai.ai")
PROMPT = ("이 사진의 핵심 내용을 한국어 명사 하나로 10자 이내로 말해라. "
          "예: 산책중, 가족사진, 일몰풍경, 반려견, 커피사진. 단어만 출력하고 공백·기호·설명은 쓰지 마라.")


SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"
MESSAGES = {
    "no_install": "Ollama가 설치되어 있지 않습니다.",
    "no_server": "Ollama가 실행 중이 아닙니다.",
    "no_model": "모델 '{model}'이 설치되어 있지 않습니다.",
    "unreachable": "Ollama 서버({url})에 연결할 수 없습니다.",
}


def _local(url: str) -> bool:
    return urlparse(url).hostname in ("localhost", "127.0.0.1", "::1")


def find_ollama() -> Path | None:
    exe = shutil.which("ollama")
    if exe:
        return Path(exe)
    p = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return p if p.exists() else None


def _models(url: str) -> list[str]:
    return [m.model for m in ollama.Client(host=url).list().models]


def diagnose(url: str, model: str) -> str | None:
    """사용 가능하면 None, 아니면 MESSAGES의 키."""
    try:
        names = _models(url)
    except Exception:
        if not _local(url):
            return "unreachable"
        return "no_server" if find_ollama() else "no_install"
    return None if any(n == model or n.split(":")[0] == model for n in names) else "no_model"


def prepare(url: str, model: str, progress) -> None:
    """부족한 것을 설치/실행/다운로드한다. progress(text, fraction|None). 실패하면 RuntimeError."""
    s = diagnose(url, model)
    if s == "unreachable":
        raise RuntimeError(MESSAGES[s].format(url=url, model=model))
    if s == "no_install":
        _install(progress)
        s = diagnose(url, model)
    if s in ("no_install", "no_server"):
        _serve(url, progress)
        s = diagnose(url, model)
    if s == "no_model":
        _pull(url, model, progress)
        s = diagnose(url, model)
    if s:
        raise RuntimeError(MESSAGES[s].format(url=url, model=model))


def _install(progress) -> None:
    if sys.platform != "win32":
        raise RuntimeError("자동 설치는 Windows에서만 지원합니다. https://ollama.com 에서 직접 설치하세요.")
    setup = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
    with urllib.request.urlopen(SETUP_URL, timeout=30) as r, open(setup, "wb") as f:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            progress(f"Ollama 설치 파일 다운로드 중 ({done >> 20}/{total >> 20} MB)", done / total if total else None)
    progress("Ollama 설치 중... (잠시 기다려 주세요)", None)
    subprocess.run([str(setup), "/SILENT"], check=True)
    setup.unlink(missing_ok=True)


def _wait_up(url: str, seconds: int) -> bool:
    for _ in range(seconds):
        try:
            _models(url)
            return True
        except Exception:
            time.sleep(1)
    return False


def _serve(url: str, progress) -> None:
    progress("Ollama 시작 중...", None)
    if _wait_up(url, 8):  # 설치 직후에는 Ollama가 스스로 시작한다
        return
    exe = find_ollama()
    if not exe:
        raise RuntimeError(MESSAGES["no_install"])
    subprocess.Popen([str(exe), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not _wait_up(url, 20):
        raise RuntimeError(MESSAGES["no_server"])


def _pull(url: str, model: str, progress) -> None:
    for ev in ollama.Client(host=url, timeout=None).pull(model, stream=True):
        total, done = ev.total or 0, ev.completed or 0
        progress(f"모델 '{model}' 다운로드 중 ({ev.status})", done / total if total else None)


def _jpeg(path, max_side=1024) -> bytes:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def make_labeler(url: str, model: str):
    """path → 설명어 또는 None(실패). 1회 재시도."""
    client = ollama.Client(host=url, timeout=120)

    def label(path) -> str | None:
        image = _jpeg(path)
        for _ in range(2):
            try:
                r = client.chat(model=model, messages=[{"role": "user", "content": PROMPT, "images": [image]}])
                got = namer.clean_label(r["message"]["content"])
                if got:
                    return got
            except Exception:
                log.exception("Ollama 분석 실패: %s", path)
        return None
    return label
