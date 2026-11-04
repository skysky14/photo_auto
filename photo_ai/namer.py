"""파일명 생성 규칙. 순수 함수만 둔다(GUI/AI/네트워크 의존 없음)."""
import re
from datetime import datetime

MAX_LEN = 10
_LABEL_OK = re.compile(r"[^0-9A-Za-z가-힣]")


def clean_label(text: str) -> str | None:
    """AI 설명어 정리. 공백·특수문자를 지우고 10자를 넘으면 앞 10자로 자른다. 빈 값이면 실패(None)."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    label = _LABEL_OK.sub("", first)
    return label[:MAX_LEN] or None


def place_name(region2: str, region3: str) -> str:
    """'구/시' + '동/읍/면'. 10자를 넘으면 뒤(동/읍/면)를 남기고 앞을 줄인다."""
    s = re.sub(r"\s+", "", region2 + region3)
    return s[-MAX_LEN:]


def build_name(taken: datetime, place: str | None, label: str | None, ext: str) -> str:
    parts = [taken.strftime("%Y%m%d_%H%M%S"), place, label]
    return "_".join(p for p in parts if p) + ext.lower()
