"""전체 처리 파이프라인: 스캔 → EXIF → 주소명 → AI → 파일명 → 중복 검사 → 검증 후 이동."""
import hashlib
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import ai, exif, namer

log = logging.getLogger("photoai.organizer")
DONE, UNCLASSIFIED, DUPLICATE = "정리완료", "분류불가", "중복파일"


@dataclass
class Result:
    job_id: str
    found: int = 0
    ok: int = 0
    unclassified: int = 0
    duplicates: int = 0
    failed: int = 0
    cancelled: bool = False
    reason: str = ""  # 도중에 멈춘 이유(AI 무응답 등)
    ok_items: list = field(default_factory=list)            # (원본 이름, 바뀐 이름)
    failed_items: list = field(default_factory=list)        # 원본 이름
    unclassified_items: list = field(default_factory=list)  # 원본 이름
    dup_items: list = field(default_factory=list)           # (원본 이름, 중복파일 폴더의 이름, 동일한 기존 파일 이름)
    total_sec: float = 0.0
    avg_sec: float = 0.0


def scan(src: Path, result: Path, recursive: bool) -> list[Path]:
    """이미지 목록. 결과 폴더가 원본 폴더 안에 있어도 다시 읽지 않는다."""
    it = src.rglob("*") if recursive else src.glob("*")
    out = []
    for p in it:
        if p.is_file() and p.suffix.lower() in exif.IMAGE_EXTS and result not in p.parents:
            out.append(p)
    return sorted(out)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _variant(target: Path, n: int) -> Path:
    return target if n == 0 else target.with_name(f"{target.stem}_{n:03d}{target.suffix}")


def choose_target(src: Path, folder: Path, name: str, check_same: bool) -> tuple[Path, bool]:
    """(최종 경로, 중복 여부). 중복이면 호출자가 중복파일 폴더로 다시 부른다."""
    base, n = folder / name, 0
    src_hash = None
    while _variant(base, n).exists():
        if check_same:
            src_hash = src_hash or sha256(src)
            if sha256(_variant(base, n)) == src_hash:
                return _variant(base, n), True
        n += 1
    return _variant(base, n), False


def move_verified(src: Path, dst: Path) -> None:
    """같은 드라이브면 rename, 아니면 복사 → 크기·해시 검증 → 원본 삭제. 실패 시 원본 유지."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.stat(src).st_dev == os.stat(dst.parent).st_dev:
        os.replace(src, dst)
        return
    tmp = dst.with_name(dst.name + ".part")
    try:
        shutil.copy2(src, tmp)
        if tmp.stat().st_size != src.stat().st_size or sha256(tmp) != sha256(src):
            raise OSError("복사본 검증 실패")
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)
    src.unlink()


def _process_one(path, st, root, db, job, geo, labeler, res):
    taken, pos = exif.read_meta(path)
    if taken is None:  # 촬영일 없음 → 원본 이름 그대로 분류불가
        folder, name, kind = root / UNCLASSIFIED, path.name, "unclassified"
    else:
        place = geo.place(*pos) if geo and pos else None
        label = None
        if labeler:
            db.add_stat("ollama_calls")
            label = labeler(path)
            db.add_stat("ai_success" if label else "ai_fail")
        folder, name, kind = root, namer.build_name(taken, place, label, path.suffix), "ok"
    dst, dup = choose_target(path, folder, name, st.check_same)
    existing = dst.name  # dup이면 내용이 같은 기존 파일
    if dup:
        dst, _ = choose_target(path, root / DUPLICATE, name, False)
        kind = "duplicate"
    move_verified(path, dst)
    db.add_history(job, path, dst, kind)
    log.info("%s → %s [%s]", path, dst, kind)
    if kind == "ok":
        res.ok_items.append((path.name, dst.name))
    elif kind == "unclassified":
        res.unclassified_items.append(path.name)
    else:
        res.dup_items.append((path.name, dst.name, existing))
    return kind


def run(st, db, geo=None, labeler=None, progress=lambda i, n, path, msg: None, cancel=None) -> Result:
    """st: config.Settings. geo/labeler가 None이면 해당 단계는 건너뛴다."""
    job = uuid.uuid4().hex
    root = Path(st.result)
    for sub in (root, root / UNCLASSIFIED, root / DUPLICATE):
        sub.mkdir(parents=True, exist_ok=True)
    files = scan(Path(st.source), root, st.recursive)
    res = Result(job_id=job, found=len(files))
    log.info("작업 시작 job=%s 원본=%s 결과=%s 대상=%d장 geo=%s ai=%s", job, st.source, root, len(files), bool(geo), bool(labeler))
    t0 = time.time()
    counters = {"ok": "ok", "unclassified": "unclassified", "duplicate": "duplicates"}
    for i, path in enumerate(files, 1):
        if cancel and cancel.is_set():
            res.cancelled = True
            break
        progress(i, len(files), path, "분석 중")
        try:
            kind = _process_one(path, st, root, db, job, geo, labeler, res)
            setattr(res, counters[kind], getattr(res, counters[kind]) + 1)
            db.add_stat("processed")
            if kind != "ok":
                db.add_stat("duplicates" if kind == "duplicate" else "unclassified")
            progress(i, len(files), path, kind)
        except ai.AIUnavailable as e:  # 이 사진은 이동 전이라 원본 위치에 남아 있다
            res.cancelled, res.reason = True, str(e)
            log.error("AI 응답 없음으로 작업을 멈춤: %s", e)
            break
        except Exception as e:  # 실패 파일은 원본 위치에 남는다
            res.failed += 1
            res.failed_items.append(path.name)
            db.add_stat("failed")
            db.log(job, "error", f"{path}: {e}")
            log.exception("처리 실패: %s", path)
            progress(i, len(files), path, f"failed: {e}")
    res.total_sec = time.time() - t0
    n = res.ok + res.unclassified + res.duplicates + res.failed
    res.avg_sec = res.total_sec / n if n else 0.0
    log.info("작업 종료 job=%s 대상=%d 총 %.1fs 평균 %.2fs/장 (정상 %d, 분류불가 %d, 중복 %d, 실패 %d)",
             job, len(files), res.total_sec, res.avg_sec, res.ok, res.unclassified, res.duplicates, res.failed)
    db.add_stat("elapsed_sec", int(res.total_sec))
    return res


def format_result(res: Result) -> str:
    """결과 화면에 보여줄 성공·실패·분류불가·중복 목록."""
    out = [f"■ 성공 ({len(res.ok_items)})"] + [f"{a}  →  {b}" for a, b in res.ok_items]
    out += ["", f"■ 실패 ({len(res.failed_items)})"] + list(res.failed_items)
    out += ["", f"■ 분류불가 ({len(res.unclassified_items)})"] + list(res.unclassified_items)
    out += ["", f"■ 중복 ({len(res.dup_items)})"]
    for a, moved, kept in res.dup_items:
        out += [a, f"   →  {moved}  /  {kept}"]
    return "\n".join(out)


def undo(db, job_id: str) -> tuple[int, int]:
    """작업을 되돌린다. (복원 수, 건너뜀 수). 원래 자리에 다른 파일이 있으면 건너뛴다."""
    done = skipped = 0
    for hid, src, dst in db.job_history(job_id):
        src, dst = Path(src), Path(dst)
        if dst.exists() and not src.exists():
            move_verified(dst, src)
            db.mark_undone(hid)
            done += 1
        else:
            skipped += 1
    return done, skipped
