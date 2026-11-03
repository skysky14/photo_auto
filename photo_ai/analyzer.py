"""Ollama 비전 모델로 사진 내용을 짧게 설명한다."""
import ollama

DEFAULT_MODEL = "qwen2.5vl:7b"
PROMPT = (
    "이 사진의 핵심 내용을 한국어 명사구로 3~6단어, 20자 이내로 설명해라. "
    "예: 해변 일몰, 생일 케이크. 설명 문구만 출력하고 따옴표·마침표·부연은 쓰지 마라."
)


def describe(path, model: str = DEFAULT_MODEL) -> str:
    resp = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": PROMPT, "images": [str(path)]}],
    )
    return resp["message"]["content"].strip().splitlines()[0]
