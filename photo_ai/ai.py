"""Ollama 비전 모델로 사진 설명어 생성."""
import logging
import os
import re
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
PROMPT = ("이 사진의 상황을 한국어 20자 이내로 말해라. "
          "전체적인 상황을 잘 파악 해서 사람중심의 분위기를 말해라. "
          "단어만 출력하고 공백·기호·설명은 쓰지 마라.")


# 화면 선택 목록이자 자동 다운로드 허용 목록. (모델, 설명, 내려받기 크기 GB 대략)
MODELS = [
    ("gemma3:4b", "균형형, 가벼움", 3.4),
    ("gemma3n:e2b", "경량", 5.6),
    ("gemma3n:e4b", "경량, 정확도 높음", 7.5),
    ("qwen2.5vl:3b", "가벼움", 3.2),
    ("qwen2.5vl:7b", "한국어 좋음", 6.0),
    ("qwen3-vl:4b", "신형, 가벼움", 3.3),
    ("llava:7b", "범용, 한국어 약함", 4.7),
    ("minicpm-v:8b", "이미지 이해력 좋음", 5.5),
    ("moondream", "매우 가벼움", 1.7),
    ("granite3.2-vision", "문서·표에 강함", 2.4),
]
MODEL_NAMES = [m[0] for m in MODELS]
# 화면 [?] 안내표용: (이미지 분석, 한국어, 속도, 특징). 직접 측정한 값이 아니라 일반적으로 알려진 평가다.
MODEL_INFO = {
    "gemma3:4b": ("보통~좋음", "좋음", "보통", "균형형, 기본값"),
    "gemma3n:e2b": ("보통", "좋음", "빠른 편", "저사양용으로 설계됨"),
    "gemma3n:e4b": ("보통~좋음", "좋음", "보통", "e2b보다 정확하지만 무거움"),
    "qwen2.5vl:3b": ("보통~좋음", "좋음", "빠른 편", "작은 크기에 비해 인식이 좋음"),
    "qwen2.5vl:7b": ("좋음", "좋음", "느린 편", "사물·글자 인식이 강함"),
    "qwen3-vl:4b": ("좋음", "좋음", "보통", "신형 (Ollama 제공 여부 미확인)"),
    "llava:7b": ("보통", "약함", "보통", "오래된 모델, 한국어 단어 품질이 낮음"),
    "minicpm-v:8b": ("좋음", "보통", "느린 편", "크기에 비해 이미지 이해력이 높음"),
    "moondream": ("낮음", "약함", "매우 빠름", "아주 가벼움, 설명이 단순함"),
    "granite3.2-vision": ("보통", "보통", "빠른 편", "문서·표·차트에 강함"),
}

DEFAULT_MODEL = "gemma3:4b"  # 사양과 상관없이 맨 위에 두는 무난한 기본 모델
_SCORE = {"낮음": 0, "약함": 0, "보통": 1, "보통~좋음": 1.5, "좋음": 2}


def recommend(ram_gb: float | None, vram_gb: float | None, n: int = 4) -> list[str]:
    """PC 사양에 맞는 추천 모델(기본 모델 제외). 모델 크기×1.5가 메모리 예산 안이어야 하고, GPU가 없으면 느린 모델은 뺀다.
    사양을 모르면(None) 목록 앞쪽부터. 필요 사양은 대략적인 추정이다."""
    budget = vram_gb if vram_gb else (ram_gb * 0.6 if ram_gb else None)
    ok = []
    for name, _, gb in MODELS:
        info = MODEL_INFO[name]
        if name == DEFAULT_MODEL or (budget is not None and gb * 1.5 > budget) or (not vram_gb and info[2] == "느린 편"):
            continue
        ok.append((name, _SCORE[info[0]] + _SCORE[info[1]]))
    ok.sort(key=lambda t: -t[1])  # 정렬은 안정적이라 점수가 같으면 목록 순서
    return [name for name, _ in ok[:n]]


KEEP_ALIVE = "30m"  # 분석 사이 모델을 메모리에 유지하는 시간
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


def _models_on_disk() -> set[str] | None:
    """서버가 꺼져 있어도 모델 폴더의 manifests에서 설치된 모델을 읽는다. 폴더가 없으면 None."""
    root = Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models") / "manifests"
    if not root.is_dir():
        return None
    names = set()
    for f in root.glob("*/*/*/*"):  # 레지스트리/네임스페이스/모델/태그
        if f.is_file() and f.parts[-4:-2] == ("registry.ollama.ai", "library"):
            names.add(f"{f.parent.name}:{f.name}")
    return names


def installed_models(url: str) -> set[str] | None:
    """설치된 모델 이름 집합. 서버에 연결되면 서버 기준, 안 되고 로컬이면 디스크 기준, 그 외엔 None(알 수 없음)."""
    try:
        return set(_models(url))
    except Exception:
        return _models_on_disk() if _local(url) else None


def is_installed(names: set[str], model: str) -> bool:
    return model in names or f"{model}:latest" in names


def model_size_gb(model: str) -> float:
    return next((g for n, _, g in MODELS if n == model), 0.0)


# 직접 입력한 모델 이름: Ollama 기본 라이브러리 이름(이름[:태그])만 허용한다. '/'나 '.com' 같은 다른 레지스트리 주소는 막는다.
_CUSTOM_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*(:[A-Za-z0-9._-]+)?")
UNKNOWN_SIZE_GB = 8.0  # 목록 밖 모델은 크기를 몰라 넉넉히 잡는다


def valid_model_name(name: str) -> bool:
    return name in MODEL_NAMES or bool(_CUSTOM_NAME.fullmatch(name))


def diagnose(url: str, model: str) -> str | None:
    """사용 가능하면 None, 아니면 MESSAGES의 키."""
    try:
        names = _models(url)
    except Exception:
        if not _local(url):
            return "unreachable"
        return "no_server" if find_ollama() else "no_install"
    return None if any(n == model or n.split(":")[0] == model for n in names) else "no_model"


def ensure_server(url: str, progress) -> None:
    """이 PC의 Ollama가 꺼져 있으면 실행한다(설치·다운로드는 하지 않음). 이미 켜져 있으면 아무것도 안 한다."""
    if not _local(url):
        raise RuntimeError("원격 Ollama는 실행할 수 없습니다.")
    try:
        _models(url)
    except Exception:
        _serve(url, progress)


def pull_model(url: str, model: str, progress) -> None:
    """화면에서 고른 모델을 내려받는다. 로컬 Ollama만 허용."""
    if not _local(url):
        raise RuntimeError("원격 Ollama에는 모델을 자동 설치하지 않습니다.")
    _pull(url, model, progress)


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
    if not valid_model_name(model):  # 임의 레지스트리 주소·이상한 이름은 내려받지 않는다
        raise RuntimeError(f"모델 이름 '{model}'이 올바르지 않아 자동 설치하지 않습니다. 직접 `ollama pull`로 설치하세요.")
    need = (model_size_gb(model) or UNKNOWN_SIZE_GB) * 1.5 + 1  # shortcut: Ollama 모델 폴더를 홈 드라이브로 가정, OLLAMA_MODELS를 바꿨다면 틀림
    if shutil.disk_usage(Path.home()).free < need * (1 << 30):
        raise RuntimeError(f"디스크 여유 공간이 부족합니다 (약 {need:.0f}GB 필요).")
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


class AIUnavailable(Exception):
    """Ollama가 연속으로 응답하지 않을 때. 작업을 멈추는 신호로 쓴다."""


def warm_up(url: str, model: str) -> None:
    """모델을 미리 메모리에 올린다. 한동안 안 쓰면 Ollama가 모델을 내려서 첫 분석이 매우 느려지기 때문이다."""
    ollama.Client(host=url, timeout=None).generate(model=model, prompt="", keep_alive=KEEP_ALIVE)


def make_labeler(url: str, model: str, give_up_after: int = 2):
    """path → 설명어 또는 None(실패). 1회 재시도. 사진 give_up_after장이 연속으로 응답 없이 실패하면 AIUnavailable."""
    client = ollama.Client(host=url, timeout=None)  # 시간 제한 없음: 느린 PC에서 제한 때문에 실패하지 않게
    dead = 0  # 연속으로 서버 오류(시간 초과 등)로 실패한 사진 수

    def label(path) -> str | None:
        nonlocal dead
        image = _jpeg(path)
        errors = 0
        for _ in range(2):
            try:
                r = client.chat(model=model, messages=[{"role": "user", "content": PROMPT, "images": [image]}],
                                keep_alive=KEEP_ALIVE)
                dead = 0
                got = namer.clean_label(r["message"]["content"])
                if got:
                    return got
            except Exception:
                errors += 1
                log.exception("Ollama 분석 실패: %s", path)
        if errors == 2:
            dead += 1
            if dead >= give_up_after:
                raise AIUnavailable(f"Ollama가 {dead}장 연속으로 응답하지 않았습니다.")
        return None
    return label
