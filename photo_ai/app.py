"""CustomTkinter GUI. 처리는 백그라운드 스레드, 진행 상황은 queue로 전달해 메인 스레드가 갱신한다."""
import logging
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import ai, config, db as dbm, geo, hw, log as logsetup, organizer

log = logging.getLogger("photoai.app")

STAT_ROWS = [
    ("처리 사진 수", "processed"), ("장소 조회 성공", "geo_hits"), ("장소 없음", "geo_miss"),
    ("AI 분석", "ollama_calls"), ("AI 성공", "ai_success"), ("AI 실패", "ai_fail"),
    ("분류불가", "unclassified"), ("중복파일", "duplicates"), ("실패", "failed"),
]


def fmt_sec(s: float) -> str:
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h}시간 {m}분 {sec}초" if h else f"{m}분 {sec}초" if m else f"{s:.1f}초"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PhotoAI Organizer")
        self.geometry("820x720")
        config.migrate_old_db()
        self.db = dbm.DB(config.DB_PATH)
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.quit_when_done = False
        self.last_result = None  # 마지막 분석 결과. 새 분석을 시작하면 지운다.
        self.installed: set[str] | None = None  # None: Ollama에 연결 불가(설치 여부 모름)
        self.ram, self.vram = hw.ram_gb(), hw.nvidia_vram_gb()
        self.recommended = ai.recommend(self.ram, self.vram)
        st = config.load()
        self.v = {
            "source": ctk.StringVar(value=st.source), "result": ctk.StringVar(value=st.result),
            "ollama_url": ctk.StringVar(value=st.ollama_url), "ollama_model": ctk.StringVar(value=st.ollama_model),
            "ai_enabled": ctk.BooleanVar(value=st.ai_enabled), "check_same": ctk.BooleanVar(value=st.check_same),
            "recursive": ctk.BooleanVar(value=st.recursive),
        }
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_quit)  # X 버튼도 [종료]와 같게(분석 중이면 현재 사진까지 끝내고 닫음)
        self.refresh_stats()
        self.after(100, self.poll)

    # ---- UI ----
    def _build(self):
        f = ctk.CTkFrame(self)
        f.pack(fill="x", padx=12, pady=(12, 6))
        f.columnconfigure(1, weight=1)
        for r, (label, key, browse) in enumerate([("원본 사진 폴더", "source", True), ("결과 저장 폴더", "result", True),
                                                  ("AI 주소", "ollama_url", False)]):
            ctk.CTkLabel(f, text=label).grid(row=r, column=0, padx=8, pady=4, sticky="w")
            ctk.CTkEntry(f, textvariable=self.v[key], state="disabled" if key == "ollama_url" else "normal").grid(row=r, column=1, padx=4, sticky="ew")
            if browse:
                ctk.CTkButton(f, text="찾기", width=60, command=lambda k=key: self.browse(k)).grid(row=r, column=2, padx=8)
        ctk.CTkLabel(f, text="AI 모델").grid(row=3, column=0, padx=8, pady=4, sticky="w")
        self.model_menu = ctk.CTkComboBox(f, values=[], command=self.on_model)  # 목록에서 고르거나 직접 입력 후 Enter
        self.model_menu.grid(row=3, column=1, padx=4, sticky="ew")
        self.model_menu._entry.bind("<Return>", lambda e: self.on_model(self.model_menu.get()))
        ctk.CTkButton(f, text="?", width=60, fg_color="gray40", command=self.show_model_help).grid(row=3, column=2, padx=8)
        self.refresh_models()
        if self.v["ai_enabled"].get():
            threading.Thread(target=self._boot_server, args=(self.v["ollama_url"].get(),), daemon=True).start()
        else:
            self.refresh_models_async()
        opts = ctk.CTkFrame(self)
        opts.pack(fill="x", padx=12, pady=6)
        ctk.CTkCheckBox(opts, text="AI 사용", variable=self.v["ai_enabled"]).pack(side="left", padx=10, pady=8)
        ctk.CTkCheckBox(opts, text="동일 파일 검사", variable=self.v["check_same"]).pack(side="left", padx=10)
        ctk.CTkCheckBox(opts, text="하위 폴더 포함", variable=self.v["recursive"]).pack(side="left", padx=10)
        self.btn_result = ctk.CTkButton(opts, text="결과", width=70, state="disabled", command=self.show_result)
        self.btn_result.pack(side="left", padx=10)

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

        self.timing = ctk.CTkLabel(self, text="총 소요시간: -   평균: -", anchor="w")
        self.timing.pack(fill="x", padx=14)
        self.bar = ctk.CTkProgressBar(self)
        self.bar.set(0)
        self.bar.pack(fill="x", padx=12, pady=(10, 2))
        self.status = ctk.CTkLabel(self, text="폴더를 선택하고 [분석 시작]을 누르세요.", anchor="w")
        self.status.pack(fill="x", padx=14)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=10)
        self.btn_start = ctk.CTkButton(btns, text="분석 시작", command=self.start)
        self.btn_start.pack(side="left", padx=6)
        self.btn_cancel = ctk.CTkButton(btns, text="취소", state="disabled", command=self.on_cancel)
        self.btn_cancel.pack(side="left", padx=6)
        ctk.CTkButton(btns, text="마지막 작업 되돌리기", fg_color="gray40", command=self.undo).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="종료", fg_color="#a33", hover_color="#822", width=70, command=self.on_quit).pack(side="left", padx=6)

    # ---- AI 모델 선택 ----
    def show_model_help(self):
        """[?] 클릭 시 모델별 성능·속도 안내창. 이미 열려 있으면 앞으로 가져온다."""
        win = getattr(self, "help_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus()
            return
        win = self.help_win = ctk.CTkToplevel(self)
        win.title("AI 모델 안내")
        win.geometry("760x470")
        win.attributes("-topmost", True)
        head = ("모델", "크기", "이미지 분석", "한국어", "속도", "특징")
        grid = ctk.CTkFrame(win)
        grid.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        for c, h in enumerate(head):
            ctk.CTkLabel(grid, text=h, font=ctk.CTkFont(weight="bold")).grid(row=0, column=c, padx=8, pady=4, sticky="w")
        for r, (name, _, gb) in enumerate(ai.MODELS, 1):
            vals = (name, f"{gb:.1f}GB", *ai.MODEL_INFO[name])
            for c, v in enumerate(vals):
                ctk.CTkLabel(grid, text=v, anchor="w").grid(row=r, column=c, padx=8, pady=2, sticky="w")
        pc = f"내 PC: 메모리 {self.ram:.1f}GB" if self.ram else "내 PC: 메모리 확인 불가"
        pc += f", NVIDIA GPU {self.vram:.0f}GB" if self.vram else ", 가속 가능한 GPU 없음(내장 GPU는 CPU로 간주)"
        ctk.CTkLabel(win, text=f"{pc}  →  ★추천은 이 사양 기준의 대략적인 추정입니다.", anchor="w").pack(fill="x", padx=14)
        ctk.CTkLabel(win, justify="left", anchor="w", wraplength=720,
                     text="※ 직접 측정한 값이 아니라 일반적으로 알려진 평가입니다. 설명어는 한 단어라서 큰 모델이라고 결과가 크게 좋아지지는 않고, "
                          "속도는 PC(특히 GPU 유무)에 따라 크게 다릅니다. 같은 사진으로 바꿔 가며 [총 소요시간/평균]을 비교해 보세요."
                     ).pack(fill="x", padx=14, pady=(0, 12))

    def _model_label(self, name):
        tag = "   (기본)" if name == ai.DEFAULT_MODEL else "   ★추천" if name in self.recommended else ""
        mark = "" if self.installed is None else ("   [설치됨]" if ai.is_installed(self.installed, name) else "   [미설치]")
        return name + tag + mark

    def refresh_models(self):
        cur = self.v["ollama_model"].get()
        first = [ai.DEFAULT_MODEL] + self.recommended  # 기본 → 추천 → 나머지 → 직접 입력한 모델
        names = first + [n for n in ai.MODEL_NAMES if n not in first] + ([cur] if cur and cur not in ai.MODEL_NAMES else [])
        self.model_menu.configure(values=[self._model_label(n) for n in names])
        self.model_menu.set(self._model_label(cur))

    def _boot_server(self, url):
        """창이 열릴 때 Ollama가 꺼져 있으면 실행한 뒤 설치된 모델을 확인한다."""
        try:
            if ai.find_ollama():
                ai.ensure_server(url, lambda t, f: None)
        except Exception:
            log.exception("Ollama 자동 실행 실패")
        self.q.put(("models", ai.installed_models(url)))

    def _start_server_then_retry(self, url):
        try:
            ai.ensure_server(url, lambda t, f: self.q.put(("prep", t, f)))
            self.q.put(("retry",))
        except Exception as e:
            log.exception("Ollama 자동 실행 실패")
            self.q.put(("err", str(e)))

    def refresh_models_async(self):
        url = self.v["ollama_url"].get()
        threading.Thread(target=lambda: self.q.put(("models", ai.installed_models(url))), daemon=True).start()

    def on_model(self, choice):
        if self.running:  # 작업 중에는 모델을 바꾸지 않는다
            self.refresh_models()
            return
        parts = choice.split()
        tags = {"(기본)", "★추천", "[설치됨]", "[미설치]"}  # 목록 라벨의 꼬리표만 허용, 그 밖의 공백 입력은 잘못된 이름
        name = parts[0] if parts and set(parts[1:]) <= tags else ""
        if not ai.valid_model_name(name):
            messagebox.showwarning("모델 이름", "모델 이름은 Ollama 모델 이름(예: gemma3:4b)으로 입력하세요.\n영문 소문자·숫자와 . _ - 만, 선택적으로 :태그")
            self.refresh_models()
            return
        self.v["ollama_model"].set(name)
        self.refresh_models()
        url = self.v["ollama_url"].get()
        if self.running or self.installed is None or ai.is_installed(self.installed, name):
            return
        gb = ai.model_size_gb(name)
        size = f"약 {gb:.1f}GB" if gb else "크기를 알 수 없는(수 GB 이상일 수 있는)"
        if not messagebox.askyesno("모델 설치", f"'{name}' 모델이 설치되어 있지 않습니다.\n{size} 모델을 내려받아 설치할까요?"):
            self.status.configure(text=f"'{name}'은 미설치 상태입니다. [분석 시작] 때 다시 물어봅니다.")
            return
        self.running = True
        self.btn_start.configure(state="disabled")
        self.model_menu.configure(state="disabled")
        threading.Thread(target=self._pull_worker, args=(url, name), daemon=True).start()

    def _pull_worker(self, url, name):
        try:
            ai.pull_model(url, name, lambda t, f: self.q.put(("prep", t, f)))
            self.q.put(("pulled", name))
        except Exception as e:
            log.exception("모델 설치 실패: %s", name)
            self.q.put(("err", str(e)))

    def reset_results(self):
        self.last_result = None
        self.btn_result.configure(state="disabled")
        win = getattr(self, "result_win", None)
        if win is not None and win.winfo_exists():
            win.destroy()

    def show_result(self):
        r = self.last_result
        if r is None:
            return
        win = getattr(self, "result_win", None)
        if win is not None and win.winfo_exists():
            win.lift()
            return
        win = self.result_win = ctk.CTkToplevel(self)
        win.title("분석 결과")
        win.geometry("760x560")
        win.attributes("-topmost", True)
        ctk.CTkButton(win, text="닫기", width=100, command=win.destroy).pack(side="bottom", pady=(0, 12))
        box = ctk.CTkTextbox(win, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 8))
        box.insert("1.0", organizer.format_result(r))
        box.configure(state="disabled")  # 보기 전용(복사는 가능)

    def on_quit(self):
        """종료. 분석 중이면 파일 이동이 반쯤 끊기지 않게 현재 사진까지 끝낸 뒤 닫는다."""
        if not self.running:
            self.destroy()
            return
        messagebox.showinfo("종료", "작업이 진행 중입니다.\n내려받기·처리 중인 작업을 끝낸 뒤 종료합니다.")
        self.quit_when_done = True
        self.on_cancel()

    def on_cancel(self):
        self.cancel.set()
        self.btn_cancel.configure(state="disabled")
        self.status.configure(text="취소하는 중... 지금 처리 중인 사진까지 끝낸 뒤 멈춥니다.")

    def report_callback_exception(self, exc, val, tb):
        """창을 닫아도 보이지 않는 exe에서 버튼 처리 중 난 오류를 로그에 남긴다."""
        log.error("화면 처리 중 오류", exc_info=(exc, val, tb))

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
        log.info("[분석 시작] 클릭")
        st = self.settings()
        if not Path(st.source).is_dir() or not st.result:
            messagebox.showwarning("확인", "원본 폴더와 결과 저장 폴더를 지정하세요.")
            return
        prepare = False
        if st.ai_enabled and (state := ai.diagnose(st.ollama_url, st.ollama_model)):
            why = ai.MESSAGES[state].format(url=st.ollama_url, model=st.ollama_model)
            if state == "no_server":  # 설치돼 있고 꺼져 있을 뿐이면 묻지 않고 실행한다
                self.status.configure(text="Ollama를 시작하는 중...")
                self.running = True
                self.btn_start.configure(state="disabled")
                self.model_menu.configure(state="disabled")
                threading.Thread(target=self._start_server_then_retry, args=(st.ollama_url,), daemon=True).start()
                return
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
        fetch = self.db.regions_stale()  # 없거나 받은 지 30일이 넘으면 받는다
        config.save(self.settings())
        self.reset_results()
        self.cancel.clear()
        self.running = True
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.model_menu.configure(state="disabled")  # 작업 중에는 모델을 바꾸지 못하게
        threading.Thread(target=self._worker, args=(st, prepare, fetch), daemon=True).start()

    def _worker(self, st, prepare=False, fetch=False):
        try:
            if prepare:
                ai.prepare(st.ollama_url, st.ollama_model, lambda t, f: self.q.put(("prep", t, f)))
            if fetch:
                try:
                    geo.download_regions(self.db, lambda t, f: self.q.put(("prep", t, f)))
                except Exception as e:
                    log.exception("행정구역 데이터 받기 실패")
                    if self.db.region_count() == 0:  # 처음 받는 데이터는 필수라 여기서 멈춘다
                        raise RuntimeError(f"행정구역 데이터를 받지 못해 분석을 시작할 수 없습니다.\n인터넷 연결을 확인하고 다시 시도하세요.\n({e})") from e
                    self.q.put(("prep", "행정구역 데이터를 새로 받지 못해 기존 데이터로 진행합니다.", None))
            if st.ai_enabled:
                self.q.put(("prep", "AI 모델을 불러오는 중... (오래 쉬었다면 몇 분 걸릴 수 있습니다)", None))
                try:
                    ai.warm_up(st.ollama_url, st.ollama_model)
                except Exception:
                    log.exception("AI 모델 미리 불러오기 실패 (분석은 계속 시도)")
            g = geo.Geo(self.db) if self.db.region_count() else None
            lab = ai.make_labeler(st.ollama_url, st.ollama_model) if st.ai_enabled else None
            res = organizer.run(st, self.db, g, lab, lambda *a: self.q.put(("p", *a)), self.cancel,
                               on_result=lambda r: self.q.put(("live", r)))
            self.q.put(("done", res))
        except Exception as e:
            log.exception("작업 스레드 오류")
            self.q.put(("err", str(e)))

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "p":
                    _, i, n, path, msg = m
                    self.found.configure(text=str(n))
                    if msg == "분석 중":  # 지금 처리하려는 파일
                        self.bar.set((i - 1) / n if n else 0)
                        self.status.configure(text=f"분석 중 {i}/{n}:  {Path(path).name}")
                    else:
                        self.bar.set(i / n if n else 1)
                        self.status.configure(text=f"{i}/{n}  {Path(path).name}  [{msg}]")
                elif m[0] == "retry":  # Ollama를 켠 뒤 분석 시작을 다시 이어간다
                    self.running = False
                    self.btn_start.configure(state="normal")
                    self.model_menu.configure(state="normal")
                    if self.quit_when_done:
                        self.destroy()
                        return
                    self.start()
                elif m[0] == "live":  # 분석 중에도 [결과]로 지금까지 옮긴 파일을 볼 수 있게
                    self.last_result = m[1]
                    self.btn_result.configure(state="normal")
                elif m[0] == "models":
                    self.installed = m[1]
                    self.refresh_models()
                elif m[0] == "pulled":
                    self.finish(f"모델 '{m[1]}' 설치 완료")
                    if self.quit_when_done:
                        self.destroy()
                        return
                elif m[0] == "prep":
                    self.status.configure(text=m[1])
                    if m[2] is not None:
                        self.bar.set(m[2])
                elif m[0] == "done":
                    r = m[1]
                    self.last_result = r
                    self.btn_result.configure(state="normal")
                    self.finish(f"{'취소됨' if r.cancelled else '완료'}: 정상 {r.ok}, 분류불가 {r.unclassified}, 중복 {r.duplicates}, 실패 {r.failed}")
                    self.timing.configure(text=f"총 소요시간: {fmt_sec(r.total_sec)}   평균: {r.avg_sec:.2f}초/장")
                    if self.quit_when_done:
                        pass  # 종료 중이라 알림 없이 아래에서 닫는다
                    elif r.reason:
                        messagebox.showwarning("작업 중단", f"{r.reason}\nOllama 상태를 확인한 뒤 다시 시작하세요.\n처리된 사진은 이동되었고 나머지는 원래 위치에 그대로 있습니다.")
                    elif r.cancelled:
                        messagebox.showinfo("취소 완료", f"작업을 취소했습니다.\n처리된 {r.ok + r.unclassified + r.duplicates}장은 이동되었고, 나머지는 원래 위치에 그대로 있습니다.\n(되돌리려면 [마지막 작업 되돌리기])")
                    self.found.configure(text=str(r.found))
                    if self.quit_when_done:
                        self.destroy()
                        return
                else:
                    self.finish("오류")
                    if self.quit_when_done:
                        self.destroy()
                        return
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
        self.model_menu.configure(state="normal")
        self.refresh_models_async()
        self.refresh_stats()

    def refresh_stats(self):
        today, total = self.db.stats()
        for key, (t, a) in self.stat_labels.items():
            t.configure(text=str(today[key]))
            a.configure(text=str(total[key]))

    def undo(self):
        job = self.db.last_job()
        if self.running or not job:
            messagebox.showinfo("되돌리기", "되돌릴 작업이 없습니다." if not job else "작업 중에는 되돌릴 수 없습니다.")
            return
        if messagebox.askyesno("되돌리기", "마지막 작업으로 이동한 파일을 원래 위치로 되돌릴까요?"):
            done, skipped = organizer.undo(self.db, job)
            messagebox.showinfo("되돌리기", f"복원 {done}개, 건너뜀 {skipped}개")


def main():
    logsetup.setup()
    log.info("PhotoAI 시작")
    ctk.set_appearance_mode("system")
    App().mainloop()
