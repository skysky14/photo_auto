"""CustomTkinter GUI. 처리는 백그라운드 스레드, 진행 상황은 queue로 전달해 메인 스레드가 갱신한다."""
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import ai, config, db as dbm, geo, organizer

STAT_ROWS = [
    ("처리 사진 수", "processed"), ("카카오 API 호출", "kakao_calls"), ("GPS 캐시 적중", "gps_cache_hits"),
    ("Ollama 분석", "ollama_calls"), ("AI 성공", "ai_success"), ("AI 실패", "ai_fail"),
    ("분류불가", "unclassified"), ("중복파일", "duplicates"), ("실패", "failed"),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PhotoAI Organizer")
        self.geometry("720x720")
        self.db = dbm.DB(config.DB_PATH)
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        st = config.load()
        self.v = {
            "source": ctk.StringVar(value=st.source), "result": ctk.StringVar(value=st.result),
            "ollama_url": ctk.StringVar(value=st.ollama_url), "ollama_model": ctk.StringVar(value=st.ollama_model),
            "kakao_key": ctk.StringVar(value=st.kakao_key),
            "ai_enabled": ctk.BooleanVar(value=st.ai_enabled), "check_same": ctk.BooleanVar(value=st.check_same),
            "recursive": ctk.BooleanVar(value=st.recursive),
        }
        self._build()
        self.refresh_stats()
        self.after(100, self.poll)

    # ---- UI ----
    def _build(self):
        f = ctk.CTkFrame(self)
        f.pack(fill="x", padx=12, pady=(12, 6))
        f.columnconfigure(1, weight=1)
        for r, (label, key, browse) in enumerate([("원본 사진 폴더", "source", True), ("결과 저장 폴더", "result", True),
                                                  ("Ollama URL", "ollama_url", False), ("Ollama 모델", "ollama_model", False),
                                                  ("카카오 API 키", "kakao_key", False)]):
            ctk.CTkLabel(f, text=label).grid(row=r, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkEntry(f, textvariable=self.v[key], show="*" if key == "kakao_key" else "").grid(row=r, column=1, padx=4, sticky="ew")
            if browse:
                ctk.CTkButton(f, text="찾기", width=60, command=lambda k=key: self.browse(k)).grid(row=r, column=2, padx=8)
        opts = ctk.CTkFrame(self)
        opts.pack(fill="x", padx=12, pady=6)
        ctk.CTkCheckBox(opts, text="AI 사용", variable=self.v["ai_enabled"]).pack(side="left", padx=10, pady=8)
        ctk.CTkCheckBox(opts, text="동일 파일 검사", variable=self.v["check_same"]).pack(side="left", padx=10)
        ctk.CTkCheckBox(opts, text="하위 폴더 포함", variable=self.v["recursive"]).pack(side="left", padx=10)

        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=12, pady=6)
        for c, h in enumerate(("통계", "오늘", "누적")):
            ctk.CTkLabel(box, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=c, padx=14, pady=4, sticky="w")
        self.stat_labels = {}
        ctk.CTkLabel(box, text="발견된 사진 수").grid(row=1, column=0, padx=14, sticky="w")
        self.found = ctk.CTkLabel(box, text="-")
        self.found.grid(row=1, column=1, sticky="w", padx=14)
        for r, (label, key) in enumerate(STAT_ROWS, 2):
            ctk.CTkLabel(box, text=label).grid(row=r, column=0, padx=14, sticky="w")
            t, a = ctk.CTkLabel(box, text="0"), ctk.CTkLabel(box, text="0")
            t.grid(row=r, column=1, padx=14, sticky="w")
            a.grid(row=r, column=2, padx=14, sticky="w")
            self.stat_labels[key] = (t, a)
        self.rate = ctk.CTkLabel(box, text="GPS 캐시 적중률: -")
        self.rate.grid(row=len(STAT_ROWS) + 2, column=0, columnspan=3, padx=14, pady=4, sticky="w")

        self.bar = ctk.CTkProgressBar(self)
        self.bar.set(0)
        self.bar.pack(fill="x", padx=12, pady=(10, 2))
        self.status = ctk.CTkLabel(self, text="폴더를 선택하고 [분석 시작]을 누르세요.", anchor="w")
        self.status.pack(fill="x", padx=14)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=10)
        self.btn_start = ctk.CTkButton(btns, text="분석 시작", command=self.start)
        self.btn_start.pack(side="left", padx=6)
        self.btn_cancel = ctk.CTkButton(btns, text="취소", state="disabled", command=self.cancel.set)
        self.btn_cancel.pack(side="left", padx=6)
        ctk.CTkButton(btns, text="마지막 작업 되돌리기", fg_color="gray40", command=self.undo).pack(side="left", padx=6)

    def browse(self, key):
        d = filedialog.askdirectory()
        if d:
            self.v[key].set(d)
            if key == "source" and not self.v["result"].get():
                self.v["result"].set(str(Path(d) / organizer.DONE))

    def settings(self) -> config.Settings:
        return config.Settings(**{k: v.get() for k, v in self.v.items()})

    # ---- 실행 ----
    def start(self):
        st = self.settings()
        if not Path(st.source).is_dir() or not st.result:
            messagebox.showwarning("확인", "원본 폴더와 결과 저장 폴더를 지정하세요.")
            return
        prepare = False
        if st.ai_enabled and (state := ai.diagnose(st.ollama_url, st.ollama_model)):
            why = ai.MESSAGES[state].format(url=st.ollama_url, model=st.ollama_model)
            if state == "unreachable":
                if not messagebox.askyesno("AI 사용 불가", f"{why}\n\nAI 없이 계속할까요?"):
                    return
                st.ai_enabled = False
            else:
                need = {"no_install": "Ollama 설치 파일(약 1GB)과 모델(수 GB)을 내려받아 설치합니다.",
                        "no_server": "Ollama를 실행합니다. 모델이 없으면 함께 내려받습니다.",
                        "no_model": "모델(수 GB)을 내려받습니다."}[state]
                ans = messagebox.askyesnocancel("AI 준비", f"{why}\n\n{need}\n\n지금 준비할까요?\n(아니요: AI 없이 계속, 취소: 중단)")
                if ans is None:
                    return
                prepare, st.ai_enabled = ans, ans
        if not st.kakao_key:
            self.status.configure(text="카카오 API 키가 없어 장소명은 생략합니다.")
        config.save(self.settings())
        self.cancel.clear()
        self.running = True
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        threading.Thread(target=self._worker, args=(st, prepare), daemon=True).start()

    def _worker(self, st, prepare=False):
        try:
            if prepare:
                ai.prepare(st.ollama_url, st.ollama_model, lambda t, f: self.q.put(("prep", t, f)))
            g = geo.Geo(st.kakao_key, self.db) if st.kakao_key else None
            lab = ai.make_labeler(st.ollama_url, st.ollama_model) if st.ai_enabled else None
            res = organizer.run(st, self.db, g, lab, lambda *a: self.q.put(("p", *a)), self.cancel)
            self.q.put(("done", res))
        except Exception as e:
            self.q.put(("err", str(e)))

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "p":
                    _, i, n, path, msg = m
                    self.found.configure(text=str(n))
                    self.bar.set(i / n if n else 1)
                    self.status.configure(text=f"{i}/{n}  {Path(path).name}  [{msg}]")
                elif m[0] == "prep":
                    self.status.configure(text=m[1])
                    if m[2] is not None:
                        self.bar.set(m[2])
                elif m[0] == "done":
                    r = m[1]
                    self.finish(f"{'취소됨' if r.cancelled else '완료'}: 정상 {r.ok}, 분류불가 {r.unclassified}, 중복 {r.duplicates}, 실패 {r.failed}")
                    self.found.configure(text=str(r.found))
                else:
                    self.finish("오류")
                    messagebox.showerror("오류", m[1])
        except queue.Empty:
            pass
        if self.running:
            self.refresh_stats()
        self.after(150, self.poll)

    def finish(self, text):
        self.running = False
        self.status.configure(text=text)
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.refresh_stats()

    def refresh_stats(self):
        today, total = self.db.stats()
        for key, (t, a) in self.stat_labels.items():
            t.configure(text=str(today[key]))
            a.configure(text=str(total[key]))
        calls = total["kakao_calls"] + total["gps_cache_hits"]
        self.rate.configure(text=f"GPS 캐시 적중률: {total['gps_cache_hits'] / calls:.0%}" if calls else "GPS 캐시 적중률: -")

    def undo(self):
        job = self.db.last_job()
        if self.running or not job:
            messagebox.showinfo("되돌리기", "되돌릴 작업이 없습니다." if not job else "작업 중에는 되돌릴 수 없습니다.")
            return
        if messagebox.askyesno("되돌리기", "마지막 작업으로 이동한 파일을 원래 위치로 되돌릴까요?"):
            done, skipped = organizer.undo(self.db, job)
            messagebox.showinfo("되돌리기", f"복원 {done}개, 건너뜀 {skipped}개")


def main():
    ctk.set_appearance_mode("system")
    App().mainloop()
