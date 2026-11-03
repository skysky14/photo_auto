"""Ollama 비전 모델로 사진 설명어 생성."""
from io import BytesIO

import ollama
from PIL import Image, ImageOps

from . import namer

PROMPT = ("이 사진의 핵심 내용을 한국어 명사 하나로 10자 이내로 말해라. "
          "예: 산책중, 가족사진, 일몰풍경, 반려견, 커피사진. 단어만 출력하고 공백·기호·설명은 쓰지 마라.")


def check(url: str, model: str) -> str | None:
    """사용 가능하면 None, 아니면 사유."""
    try:
        names = [m.model for m in ollama.Client(host=url).list().models]
    except Exception as e:
        return f"Ollama에 연결할 수 없습니다: {e}"
    if not any(n == model or n.split(":")[0] == model for n in names):
        return f"모델 '{model}'이 설치되어 있지 않습니다. `ollama pull {model}`을 실행하세요."
    return None


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
                pass
        return None
    return label
