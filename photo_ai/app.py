"""Tkinter GUI: 폴더 선택 → AI 분석(백그라운드) → 미리보기 → 이름 변경 적용."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import analyzer, namer


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo AI Renamer")
        self.geometry("820x520")
        self.folder: Path | None = None
        self.q: queue.Queue = queue.Queue()
        self.model = tk.StringVar(value=analyzer.DEFAULT_MODEL)
        self.use_date = tk.BooleanVar(value=True)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="폴더 선택", command=self.choose_folder).pack(side="left")
        ttk.Label(top, text="모델:").pack(side="left", padx=(12, 2))
        ttk.Entry(top, textvariable=self.model, width=18).pack(side="left")
        ttk.Checkbutton(top, text="촬영일 포함", variable=self.use_date).pack(side="left", padx=12)
        self.btn_analyze = ttk.Button(top, text="분석", command=self.analyze, state="disabled")
        self.btn_analyze.pack(side="left")
        self.btn_apply = ttk.Button(top, text="이름 변경 적용", command=self.apply, state="disabled")
        self.btn_apply.pack(side="left", padx=6)

        self.tree = ttk.Treeview(self, columns=("old", "new"), show="headings")
        self.tree.heading("old", text="현재 이름")
        self.tree.heading("new", text="새 이름 (더블클릭하여 수정)")
        self.tree.pack(fill="both", expand=True, padx=8)
        self.tree.bind("<Double-1>", self.edit_cell)

        self.status = ttk.Label(self, text="폴더를 선택하세요.", padding=8)
        self.status.pack(fill="x")
        self.after(100, self.poll)

    def choose_folder(self):
        d = filedialog.askdirectory()
        if not d:
            return
        self.folder = Path(d)
        self.tree.delete(*self.tree.get_children())
        for p in namer.list_images(self.folder):
            self.tree.insert("", "end", iid=p.name, values=(p.name, ""))
        n = len(self.tree.get_children())
        self.status.config(text=f"이미지 {n}장")
        self.btn_analyze.config(state="normal" if n else "disabled")
        self.btn_apply.config(state="disabled")

    def analyze(self):
        self.btn_analyze.config(state="disabled")
        names = list(self.tree.get_children())
        threading.Thread(target=self._worker, args=(names, self.model.get(), self.use_date.get()), daemon=True).start()

    def _worker(self, names, model, use_date):
        for i, name in enumerate(names, 1):
            path = self.folder / name
            try:
                desc = analyzer.describe(path, model)
                new = namer.build_name(desc, namer.get_taken_date(path) if use_date else None, path.suffix)
                self.q.put(("row", name, new, i, len(names)))
            except Exception as e:  # Ollama 미실행/모델 없음 등
                self.q.put(("error", str(e)))
                return
        self.q.put(("done",))

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "row":
                    _, name, new, i, total = msg
                    self.tree.set(name, "new", new)
                    self.status.config(text=f"분석 중 {i}/{total}")
                elif msg[0] == "done":
                    self.status.config(text="분석 완료. 확인 후 적용하세요.")
                    self.btn_analyze.config(state="normal")
                    self.btn_apply.config(state="normal")
                else:
                    self.status.config(text="오류")
                    self.btn_analyze.config(state="normal")
                    messagebox.showerror("오류", f"{msg[1]}\n\nOllama 실행 및 모델 설치(ollama pull)를 확인하세요.")
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def edit_cell(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify_column(event.x) != "#2":
            return
        x, y, w, h = self.tree.bbox(iid, "new")
        e = ttk.Entry(self.tree)
        e.place(x=x, y=y, width=w, height=h)
        e.insert(0, self.tree.set(iid, "new"))
        e.focus()

        def commit(_=None):
            self.tree.set(iid, "new", e.get())
            e.destroy()
        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)

    def apply(self):
        taken: set[Path] = set()
        done = 0
        for old in self.tree.get_children():
            new = self.tree.set(old, "new")
            if not new or new == old:
                continue
            target = namer.unique_path(self.folder / new, taken)
            taken.add(target)
            (self.folder / old).rename(target)
            done += 1
        messagebox.showinfo("완료", f"{done}개 파일 이름을 변경했습니다.")
        self.choose_after_apply()

    def choose_after_apply(self):
        self.tree.delete(*self.tree.get_children())
        for p in namer.list_images(self.folder):
            self.tree.insert("", "end", iid=p.name, values=(p.name, ""))
        self.btn_apply.config(state="disabled")
        self.status.config(text="적용 완료.")


def main():
    App().mainloop()
