"""panel.py - 환생2 매크로 조작 패널 (tkinter, 추가 설치 없음)
실행:  py panel.py      (콘솔 창 없이 쓰려면  pyw panel.py)

구성
  머리글   : 제목 + 현재 상태 표시등
  제어줄   : 시작 / 중지 / 일시정지  (단축키 F5 / F6 / F7)
  탭       : 바로 실행 / 옵션 / 도구
  로그     : 메인과 단발 작업의 출력 (글자 크기 조절 가능)
  하단 줄  : 마우스를 올린 버튼의 설명
"""
import os, sys, subprocess, threading, time, json
import tkinter as tk
from tkinter import ttk, messagebox

BASE = r"C:\macro"
LOG = os.path.join(BASE, "macro.log")
PAUSE = os.path.join(BASE, "PAUSE")
STATE = os.path.join(BASE, "state.json")
PIDFILE = os.path.join(BASE, "main.pid")
SETTINGS = os.path.join(BASE, "settings.json")
SHOTS = os.path.join(BASE, "shots")
DEFAULTS = {"fairy": False, "log_font": 10}     # fairy: 정령의 고원 자동 구매/소탕 (다이아 사용이라 기본 꺼짐)
MAX_LINES = 400                                  # 로그창에 남기는 최대 줄 수
FONT = "맑은 고딕"

# ---- 색 (어두운 배경 + 한 가지 강조색, 상태는 초록/주황/빨강/파랑으로 고정)
C_BG, C_SURF, C_CARD, C_LINE = "#14161b", "#1b1e25", "#232733", "#323847"
C_TEXT, C_MUTED, C_DIM = "#e9ebf1", "#98a1b6", "#5d6578"
C_ACC, C_GOOD, C_WARN, C_BAD, C_RUN = "#4f8cff", "#4cc38a", "#f5a524", "#ef5b5b", "#6ea8ff"


def load_settings():
    d = dict(DEFAULTS)
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            d.update(json.load(f))
    except Exception:
        pass
    return d


def save_settings(d):
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


PY = sys.executable
if PY.lower().endswith("pythonw.exe"):
    PY = PY[:-len("pythonw.exe")] + "python.exe"
NOWIN = 0x08000000      # CREATE_NO_WINDOW
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def pid_alive(pid):
    """프로세스가 살아 있는지 (명령 실행 없이 윈도우 API 로 즉시 확인)"""
    if not pid:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = wintypes.DWORD()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259           # STILL_ACTIVE
    except Exception:
        return False


def classify(ln):
    if any(k in ln for k in ("실패", "오류", "중단", "정체")):
        return "warn"
    if any(k in ln for k in ("성공", "완료", "수령", "done")):
        return "good"
    return None


class App:
    WATCH = ("main.py", "daily.py", "fossil.py", "lvdigits.py", "activate.py")

    # 바로 실행 목록: (제목, 설명, 명령, 마우스 올렸을 때 안내)
    DAILY = [
        ("일일 퀘스트", "던전 · 랭킹전 · 퀘스트", ["daily.py", "go"],
         "일일 던전, 랭킹전, 퀘스트 보상을 한 번 처리합니다."),
        ("프리셋 활성화", "영웅/유물 프리셋 적용", ["activate.py", "go"],
         "프리셋 활성화를 한 번 실행합니다."),
        ("무한랭킹전", "티켓이 없어질 때까지", ["daily.py", "go", "infinite"],
         "내 레벨 이하 상대만 싸웁니다. 다이아는 쓰지 않고, 끝나면 4.5시간 뒤로 자동 실행이 미뤄집니다."),
        ("상점 광고", "코인 · 보석 · 배속", ["daily.py", "go", "ads"],
         "상점의 무료 광고(코인/보석/배속)를 한 번 받습니다. 광고제거 패키지가 있어야 합니다."),
    ]

    def __init__(self, root):
        self.root = root
        self.me = os.path.abspath(__file__)
        self.me_mt = self.mtime(self.me)
        self.proc = None
        self.pid = self.read_pid()
        self.busy = None              # 단발 작업 중이면 그 이름
        self.cur = None               # 단발 작업의 프로세스
        self.alive = False            # 백그라운드 스레드가 갱신하는 값 (화면은 이 값만 읽음)
        self.shown = None
        self.log_pos = None
        self.set = load_settings()

        root.title("환생2 매크로 패널")
        root.geometry("640x860")
        root.minsize(560, 680)
        root.configure(bg=C_BG)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.style()
        self.build()
        for key, fn in (("<F5>", self.start), ("<F6>", self.stop), ("<F7>", self.toggle_pause)):
            root.bind(key, lambda e, f=fn: f())

        threading.Thread(target=self.monitor, daemon=True).start()   # 프로세스 확인은 별도 스레드에서
        self.refresh()
        self.poll_log()
        self.root.after(2000, self.watch)

    # ============================================================ 모양
    def style(self):
        st = ttk.Style()
        st.theme_use("clam")
        base = dict(borderwidth=0, focusthickness=2, focuscolor=C_ACC, relief="flat")

        def btn(name, bg, hover, fg=C_TEXT, font=(FONT, 10), pad=(12, 9)):
            st.configure(name, background=bg, foreground=fg, font=font, padding=pad,
                         bordercolor=bg, lightcolor=bg, darkcolor=bg, justify="center", anchor="center", **base)
            st.map(name, background=[("disabled", C_SURF), ("pressed", hover), ("active", hover)],
                   foreground=[("disabled", C_DIM)], bordercolor=[("focus", C_ACC)])

        btn("Start.TButton", "#1f6b4a", "#27855d", font=(FONT, 12, "bold"), pad=(10, 13))
        btn("Stop.TButton", "#7a2b2b", "#973737", font=(FONT, 12, "bold"), pad=(10, 13))
        btn("Pause.TButton", "#7a5a17", "#977021", font=(FONT, 12, "bold"), pad=(10, 13))
        btn("Card.TButton", C_CARD, "#2d3342", font=(FONT, 10, "bold"), pad=(10, 12))
        btn("Tool.TButton", C_CARD, "#2d3342", pad=(10, 8))
        btn("Danger.TButton", "#3a2327", "#58292e", pad=(10, 8))
        btn("Ghost.TButton", C_SURF, C_CARD, fg=C_MUTED, font=(FONT, 9), pad=(8, 3))

        st.configure("TFrame", background=C_BG)
        st.configure("Surf.TFrame", background=C_SURF)
        st.configure("Card.TFrame", background=C_SURF)
        st.configure("TLabel", background=C_BG, foreground=C_TEXT, font=(FONT, 10))
        st.configure("Sect.TLabel", background=C_BG, foreground=C_MUTED, font=(FONT, 9, "bold"))
        st.configure("Sub.TLabel", background=C_SURF, foreground=C_MUTED, font=(FONT, 9))
        st.configure("TCheckbutton", background=C_SURF, foreground=C_TEXT, font=(FONT, 10), focuscolor=C_SURF)
        st.map("TCheckbutton", background=[("active", C_SURF), ("pressed", C_SURF)],
               foreground=[("active", C_TEXT), ("pressed", C_TEXT), ("disabled", C_DIM)],
               indicatorcolor=[("selected", C_ACC), ("!selected", C_BG)])
        st.configure("TSpinbox", fieldbackground=C_BG, background=C_CARD, foreground=C_TEXT,
                     arrowcolor=C_TEXT, bordercolor=C_LINE, lightcolor=C_LINE, darkcolor=C_LINE, padding=4)
        st.configure("TNotebook", background=C_BG, borderwidth=0, tabmargins=(0, 0, 0, 0), bordercolor=C_BG, lightcolor=C_BG, darkcolor=C_BG)
        st.configure("TNotebook.Tab", background=C_SURF, foreground=C_MUTED, padding=(18, 9),
                     font=(FONT, 10, "bold"), borderwidth=0, bordercolor=C_BG, lightcolor=C_BG, darkcolor=C_BG)
        st.map("TNotebook.Tab", background=[("selected", C_SURF), ("active", "#2a2f3c")], expand=[("selected", (0, 0, 0, 0))],
               lightcolor=[("selected", C_SURF)], bordercolor=[("selected", C_SURF)],
               foreground=[("selected", C_TEXT), ("active", C_TEXT)])
        st.configure("Vertical.TScrollbar", background=C_CARD, troughcolor=C_SURF, bordercolor=C_SURF,
                     arrowcolor=C_MUTED, lightcolor=C_CARD, darkcolor=C_CARD, gripcount=0)
        st.map("Vertical.TScrollbar", background=[("active", "#3a4152"), ("pressed", "#4a5266")])

    def mk(self, parent, text, cmd, style="Tool.TButton", tip="", **kw):
        b = ttk.Button(parent, text=text, command=cmd, style=style, **kw)
        b.bind("<Enter>", lambda e: self.hint(tip), add="+")
        b.bind("<Leave>", lambda e: self.hint(""), add="+")
        b.bind("<FocusIn>", lambda e: self.hint(tip), add="+")
        return b

    def hint(self, text):
        self.hintbar.config(text=text or "버튼 위에 마우스를 올리면 설명이 여기에 나옵니다.   단축키: F5 시작 · F6 중지 · F7 일시정지/재개")

    # ============================================================ 화면 구성
    def build(self):
        root = self.root

        # ---- 머리글: 제목 + 상태
        head = ttk.Frame(root, style="Surf.TFrame")
        head.pack(fill="x")
        left = ttk.Frame(head, style="Surf.TFrame")
        left.pack(side="left", padx=18, pady=14)
        tk.Label(left, text="환생2 매크로", font=(FONT, 16, "bold"), bg=C_SURF, fg=C_TEXT).pack(anchor="w")
        tk.Label(left, text="오늘도 환생2 · BlueStacks", font=(FONT, 9), bg=C_SURF, fg=C_MUTED).pack(anchor="w")
        pill = ttk.Frame(head, style="Surf.TFrame")
        pill.pack(side="right", padx=18)
        self.dot = tk.Canvas(pill, width=16, height=16, bg=C_SURF, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.dot_id = self.dot.create_oval(2, 2, 14, 14, fill=C_BAD, outline="")
        self.status = tk.Label(pill, text="", font=(FONT, 13, "bold"), bg=C_SURF, fg=C_TEXT)
        self.status.pack(side="left")

        # ---- 제어줄
        ctl = ttk.Frame(root)
        ctl.pack(fill="x", padx=16, pady=(14, 0))
        self.btn_start = self.mk(ctl, "▶  시작   F5", self.start, "Start.TButton", "메인 매크로를 시작합니다.")
        self.btn_stop = self.mk(ctl, "■  중지   F6", self.stop, "Stop.TButton", "메인 매크로를 끝냅니다.")
        self.btn_pause = self.mk(ctl, "⏸  일시정지   F7", self.toggle_pause, "Pause.TButton",
                                 "메인을 잠깐 멈춥니다. 다시 누르면 이어서 진행합니다.")
        for i, b in enumerate((self.btn_start, self.btn_stop, self.btn_pause)):
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0 if i == 2 else 5))
            ctl.columnconfigure(i, weight=1, uniform="ctl")

        # ---- 코드 변경 안내 (평소엔 숨김)
        self.notice = tk.Label(root, text="", font=(FONT, 9), fg=C_WARN, bg="#2b2412", anchor="w", padx=12, pady=6)

        # ---- 탭
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="x", padx=16, pady=(14, 0))
        self.tab_run = ttk.Frame(self.nb, style="Card.TFrame")
        self.tab_opt = ttk.Frame(self.nb, style="Card.TFrame")
        self.tab_tool = ttk.Frame(self.nb, style="Card.TFrame")
        self.nb.add(self.tab_run, text="바로 실행")
        self.nb.add(self.tab_opt, text="옵션")
        self.nb.add(self.tab_tool, text="도구")
        self.build_run(self.tab_run)
        self.build_opt(self.tab_opt)
        self.build_tool(self.tab_tool)

        # ---- 로그
        lh = ttk.Frame(root)
        lh.pack(fill="x", padx=16, pady=(14, 4))
        ttk.Label(lh, text="로그", style="Sect.TLabel").pack(side="left")
        self.mk(lh, "지우기", self.clear_view, "Ghost.TButton", "화면의 로그만 지웁니다. 파일(macro.log)은 그대로입니다.").pack(side="right")
        self.mk(lh, "A+", lambda: self.font_step(1), "Ghost.TButton", "로그 글자를 키웁니다.").pack(side="right", padx=4)
        self.mk(lh, "A−", lambda: self.font_step(-1), "Ghost.TButton", "로그 글자를 줄입니다.").pack(side="right")

        lf = ttk.Frame(root)
        lf.pack(fill="both", expand=True, padx=16)
        self.text = tk.Text(lf, bg="#0f1115", fg="#cfd3dc", font=("Consolas", self.set["log_font"]), wrap="none",
                            relief="flat", height=10, undo=False, padx=10, pady=8, insertbackground="#cfd3dc",
                            selectbackground="#34518a", borderwidth=0, highlightthickness=0)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_config("warn", foreground=C_WARN)
        self.text.tag_config("good", foreground=C_GOOD)
        self.text.tag_config("cmd", foreground=C_RUN)

        # ---- 하단 안내줄
        self.hintbar = tk.Label(root, text="", font=(FONT, 9), bg=C_SURF, fg=C_MUTED, anchor="w", padx=16, pady=8)
        self.hintbar.pack(fill="x", pady=(10, 0))
        self.hint("")

    def section(self, parent, text, first=False):
        ttk.Label(parent, text=text, style="Sub.TLabel", font=(FONT, 9, "bold")).pack(
            anchor="w", padx=14, pady=(10 if first else 16, 6))

    # ---- 탭 1: 바로 실행
    def build_run(self, tab):
        top = ttk.Frame(tab, style="Card.TFrame")
        top.pack(fill="x", padx=14, pady=(12, 0))
        self.run_msg = ttk.Label(top, text="메인이 돌고 있으면 자동으로 잠깐 멈췄다가 끝나면 재개합니다.", style="Sub.TLabel")
        self.run_msg.pack(side="left")
        self.btn_cancel = self.mk(top, "작업 중단", self.cancel_job, "Danger.TButton", "지금 실행 중인 단발 작업을 강제로 끝냅니다.")
        self.btn_cancel.pack(side="right")
        self.btn_cancel.state(["disabled"])

        self.section(tab, "일일 작업", first=True)
        grid = ttk.Frame(tab, style="Card.TFrame")
        grid.pack(fill="x", padx=14)
        self.cards = []
        for i, (title, sub, args, tip) in enumerate(self.DAILY):
            b = self.mk(grid, "%s\n%s" % (title, sub), lambda a=args, l=title: self.oneshot(l, a),
                        "Card.TButton", tip)
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0 if i % 2 == 0 else 5, 5 if i % 2 == 0 else 0), pady=4)
            self.cards.append(b)
        for c in range(2):
            grid.columnconfigure(c, weight=1, uniform="g")

        self.section(tab, "미니게임")
        fos = ttk.Frame(tab, style="Card.TFrame")
        fos.pack(fill="x", padx=14, pady=(0, 14))
        self.btn_fossil = self.mk(fos, "화석 발굴\n지금 화면에서 자동 진입 · 망치 소진", self.run_fossil, "Card.TButton",
                                  "발굴 화면이면 바로, 기본 화면이면 이벤트 > 화석 발굴로 들어가서 시작합니다. 끝나면 창을 닫습니다.")
        self.btn_fossil.pack(fill="x", pady=(0, 6))
        self.cards.append(self.btn_fossil)
        opt = ttk.Frame(fos, style="Card.TFrame")
        opt.pack(fill="x")
        ttk.Label(opt, text="남길 망치", style="Sub.TLabel").pack(side="left")
        self.keep_var = tk.StringVar(value="0")
        ttk.Spinbox(opt, from_=0, to=999, width=5, textvariable=self.keep_var).pack(side="left", padx=(6, 18))
        ttk.Label(opt, text="판 수 제한 (0 = 무제한)", style="Sub.TLabel").pack(side="left")
        self.boards_var = tk.StringVar(value="0")
        ttk.Spinbox(opt, from_=0, to=99, width=4, textvariable=self.boards_var).pack(side="left", padx=6)

    # ---- 탭 2: 옵션
    def build_opt(self, tab):
        self.section(tab, "자동화 옵션  (켜고 끄면 메인이 돌고 있어도 바로 반영)", first=True)
        self.opt_vars = {}
        row = ttk.Frame(tab, style="Card.TFrame")
        row.pack(fill="x", padx=14, pady=(0, 14))
        for key, label, sub in (
                ("fairy", "정령의 고원: 티켓 구매 + 소탕", "다이아를 사용합니다. 기본은 꺼짐."),
                ("fall_continue", "성 함락 시 이어하기 우선", "켜면 하트를 써서 이어하기, 하트가 없으면 환생. 끄면 바로 환생."),
                ("barracks_swap", "병영 편성으로 최대레벨 단계 진행", "6200 웨이브에서 병영을 재편성해 일괄 레벨업합니다. 켜면 기존 렙뻥 프리셋 방식 대신 사용. 기본은 꺼짐."),):
            v = tk.BooleanVar(value=bool(self.set.get(key, False)))
            self.opt_vars[key] = v
            ttk.Checkbutton(row, text=label, variable=v, command=self.save_opts).pack(anchor="w", pady=(4, 0))
            ttk.Label(row, text="      " + sub, style="Sub.TLabel").pack(anchor="w", pady=(0, 6))

    # ---- 탭 3: 도구
    def build_tool(self, tab):
        self.section(tab, "프로그램", first=True)
        g1 = ttk.Frame(tab, style="Card.TFrame")
        g1.pack(fill="x", padx=14)
        self.mk(g1, "↻  메인 재시작", self.restart_main, "Tool.TButton",
                "메인을 껐다가 다시 켭니다. main.py / daily.py 를 고친 뒤에 누르세요.").grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=4)
        self.mk(g1, "↻  패널 재시작", self.restart_panel, "Tool.TButton",
                "이 패널만 새로 띄웁니다. 메인은 계속 돌아갑니다.").grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=4)
        for c in range(2):
            g1.columnconfigure(c, weight=1, uniform="t")

        self.section(tab, "폴더 · 파일")
        g2 = ttk.Frame(tab, style="Card.TFrame")
        g2.pack(fill="x", padx=14)
        items = [("매크로 폴더", lambda: self.open_path(BASE), "C:\\macro 폴더를 엽니다."),
                 ("스크린샷 폴더", lambda: self.open_path(SHOTS), "실패했을 때 저장된 화면(shots)을 엽니다."),
                 ("로그 파일", lambda: self.open_path(LOG), "macro.log 를 메모장으로 엽니다.")]
        for i, (t, fn, tip) in enumerate(items):
            self.mk(g2, t, fn, "Tool.TButton", tip).grid(row=0, column=i, sticky="ew",
                                                          padx=(0 if i == 0 else 5, 0 if i == 2 else 5), pady=4)
            g2.columnconfigure(i, weight=1, uniform="f")

        self.section(tab, "초기화")
        g3 = ttk.Frame(tab, style="Card.TFrame")
        g3.pack(fill="x", padx=14, pady=(0, 14))
        self.mk(g3, "상태 초기화 (state.json 삭제)", self.reset_state, "Danger.TButton",
                "오늘 일일 작업 기록 등을 지웁니다. 메인을 재시작해야 반영됩니다.").pack(fill="x", pady=4)

    # ============================================================ 코드 변경 감시
    def mtime(self, p):
        try:
            return os.path.getmtime(p)
        except Exception:
            return 0

    def watch(self):
        try:
            if self.mtime(self.me) != self.me_mt:      # 패널 파일이 바뀌면 스스로 다시 실행 (메인은 그대로 둠)
                subprocess.Popen([sys.executable, self.me], cwd=BASE, env=ENV, creationflags=NOWIN)
                self.root.destroy()
                return
            stale = []
            if self.alive:
                t0 = self.mtime(PIDFILE)
                for f in self.WATCH:
                    if t0 and self.mtime(os.path.join(BASE, f)) > t0 + 1:
                        stale.append(f)
            if stale:
                self.notice.config(text="⚠ 코드가 바뀜: %s   →  [도구] 탭의 '메인 재시작'을 누르면 반영됩니다" % ", ".join(stale))
                if not self.notice.winfo_ismapped():
                    self.notice.pack(fill="x", padx=16, pady=(12, 0), before=self.nb)
            elif self.notice.winfo_ismapped():
                self.notice.pack_forget()
        except Exception:
            pass
        self.root.after(2000, self.watch)

    def restart_main(self):
        if self.alive:
            self.stop()
        self.root.after(2500, self.start)

    def restart_panel(self):
        subprocess.Popen([sys.executable, self.me], cwd=BASE, env=ENV, creationflags=NOWIN)
        self.root.destroy()

    # ============================================================ 상태 표시
    def read_pid(self):
        try:
            return int(open(PIDFILE).read().strip())
        except Exception:
            return None

    def monitor(self):
        while True:
            try:
                alive = (self.proc is not None and self.proc.poll() is None) or pid_alive(self.pid)
                self.alive = alive
            except Exception:
                pass
            time.sleep(1.0)

    def refresh(self):
        run, paused, busy = self.alive, os.path.exists(PAUSE), self.busy
        cur = (run, paused, busy)
        if cur != self.shown:             # 바뀔 때만 화면 갱신
            self.shown = cur
            if busy:
                txt, col = "작업 중: %s" % busy, C_RUN
            elif run and paused:
                txt, col = "일시정지 중", C_WARN
            elif run:
                txt, col = "실행 중", C_GOOD
            else:
                txt, col = "중지됨", C_BAD
            self.status.config(text=txt)
            self.dot.itemconfig(self.dot_id, fill=col)
            self.btn_start.state(["disabled"] if run else ["!disabled"])
            self.btn_stop.state(["!disabled"] if run else ["disabled"])
            self.btn_pause.config(text="▶  재개   F7" if paused else "⏸  일시정지   F7")
            self.btn_pause.state(["!disabled"] if run else ["disabled"])
            for b in self.cards:
                b.state(["disabled"] if busy else ["!disabled"])
            self.btn_cancel.state(["!disabled"] if busy else ["disabled"])
        self.root.after(400, self.refresh)

    # ============================================================ 메인 시작/중지
    def start(self):
        if self.alive:
            return
        args = [PY, "main.py", "go"]
        self.proc = subprocess.Popen(args, cwd=BASE, env=ENV, creationflags=NOWIN,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.pid = self.proc.pid
        self.alive = True
        try:
            open(PIDFILE, "w").write(str(self.pid))
        except Exception:
            pass
        self.note("메인 시작: " + " ".join(args[1:]), "cmd")

    def stop(self):
        if not self.alive:
            return
        pid = self.pid
        self.alive = False
        self.proc = None
        self.pid = None

        def _kill():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                           creationflags=NOWIN)
            try:
                os.remove(PIDFILE)
            except Exception:
                pass
            self.note("메인 중지", "warn")
        threading.Thread(target=_kill, daemon=True).start()

    def toggle_pause(self):
        if not self.alive:
            return
        try:
            if os.path.exists(PAUSE):
                os.remove(PAUSE)
                self.note("재개", "good")
            else:
                open(PAUSE, "w").close()
                self.note("일시정지 (PAUSE 파일 생성)", "warn")
        except Exception as e:
            self.note("일시정지 전환 실패: %r" % e, "warn")

    # ============================================================ 단발 실행
    def run_fossil(self):
        args = ["fossil.py", "go"]
        try:
            keep = int(self.keep_var.get() or 0)
            boards = int(self.boards_var.get() or 0)
        except ValueError:
            messagebox.showwarning("숫자 확인", "남길 망치와 판 수는 숫자로 입력해 주세요.")
            return
        if keep > 0:
            args.append("keep=%d" % keep)
        if boards > 0:
            args.append("boards=%d" % boards)
        self.oneshot("화석 발굴", args)

    def oneshot(self, label, args):
        if self.busy:
            messagebox.showinfo("실행 중", "다른 작업이 끝날 때까지 기다려 주세요.")
            return
        self.busy = label
        threading.Thread(target=self._oneshot, args=(label, args), daemon=True).start()

    def cancel_job(self):
        p = self.cur
        if p is not None and p.poll() is None:
            self.note("작업 중단 요청", "warn")
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)

    def _oneshot(self, label, args):
        was_paused = os.path.exists(PAUSE)
        made = False
        try:
            if self.alive and not was_paused:
                open(PAUSE, "w").close()
                made = True
                time.sleep(2)               # 메인이 멈출 시간
            self.note("▶ %s 실행" % label, "cmd")
            p = subprocess.Popen([PY] + args, cwd=BASE, env=ENV, creationflags=NOWIN,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.cur = p
            for raw in iter(p.stdout.readline, b""):
                self.note(raw.decode("utf-8", "replace").rstrip())
            p.wait()
            self.note("■ %s 종료 (코드 %s)" % (label, p.returncode), "good" if p.returncode == 0 else "warn")
        except Exception as e:
            self.note("실행 실패: %r" % e, "warn")
        finally:
            self.cur = None
            if made:
                try:
                    os.remove(PAUSE)
                except Exception:
                    pass
            self.busy = None

    # ============================================================ 설정 · 도구
    def save_opts(self):
        try:
            d = load_settings()
            for k, v in self.opt_vars.items():
                d[k] = bool(v.get())
            save_settings(d)
            self.note("옵션 저장: " + ", ".join("%s=%s" % (k, "켬" if d[k] else "끔") for k in self.opt_vars), "cmd")
        except Exception as e:
            self.note("옵션 저장 실패: %r" % e, "warn")

    def font_step(self, d):
        n = max(8, min(18, int(self.set.get("log_font", 10)) + d))
        self.set["log_font"] = n
        self.text.configure(font=("Consolas", n))
        try:
            s = load_settings()
            s["log_font"] = n
            save_settings(s)
        except Exception:
            pass

    def open_path(self, p):
        try:
            if not os.path.exists(p):
                self.note("없음: %s" % p, "warn")
                return
            os.startfile(p)
        except Exception as e:
            self.note("열기 실패: %r" % e, "warn")

    def reset_state(self):
        if not messagebox.askyesno("상태 초기화", "state.json 을 삭제합니다.\n오늘 일일 작업 기록, 고레벨 실패 횟수 등이 초기화됩니다.\n계속할까요?"):
            return
        try:
            if os.path.exists(STATE):
                os.remove(STATE)
            self.note("state.json 삭제 (메인을 재시작해야 반영됨)", "warn")
        except Exception as e:
            self.note("삭제 실패: %r" % e, "warn")

    # ============================================================ 로그 (새로 생긴 줄만 덧붙임)
    def add_lines(self, items):
        """items: [(문장, 태그)]  한 번에 넣고, 보고 있던 위치가 맨 아래일 때만 따라감"""
        if not items:
            return
        at_bottom = self.text.yview()[1] >= 0.98
        for ln, tag in items:
            self.text.insert("end", ln + "\n", tag or ())
        extra = int(self.text.index("end-1c").split(".")[0]) - MAX_LINES
        if extra > 0:
            self.text.delete("1.0", "%d.0" % (extra + 1))
        if at_bottom:
            self.text.see("end")

    def note(self, msg, tag=None):
        self.root.after(0, lambda: self.add_lines([(msg, tag)]))

    def clear_view(self):
        self.text.delete("1.0", "end")

    def poll_log(self):
        try:
            size = os.path.getsize(LOG)
            if self.log_pos is None:                      # 처음: 마지막 40줄만
                with open(LOG, "rb") as f:
                    f.seek(max(0, size - 6000))
                    data = f.read()
                lines = data.decode("utf-8", "replace").splitlines()[-40:]
                self.log_pos = size
                self.add_lines([(ln, classify(ln)) for ln in lines])
            elif size < self.log_pos:                     # 로그가 비워짐
                self.log_pos = 0
            elif size > self.log_pos:
                with open(LOG, "rb") as f:
                    f.seek(self.log_pos)
                    data = f.read(size - self.log_pos)
                self.log_pos = size
                lines = data.decode("utf-8", "replace").splitlines()
                self.add_lines([(ln, classify(ln)) for ln in lines if ln.strip()])
        except Exception:
            pass
        self.root.after(700, self.poll_log)

    def on_close(self):
        if self.alive:
            r = messagebox.askyesnocancel("종료", "매크로가 돌고 있습니다.\n예 = 매크로도 같이 중지, 아니오 = 매크로는 계속 두고 패널만 닫기")
            if r is None:
                return
            if r:
                self.stop()
                time.sleep(0.3)
        self.root.destroy()


if __name__ == "__main__":
    r = tk.Tk()
    App(r)
    r.mainloop()
