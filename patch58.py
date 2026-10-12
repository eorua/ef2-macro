# patch58.py - 패널에 '최근 환생 층수' 표시 (C:\macro 에서 py patch58.py)
#  main.py : 환생할 때마다 직전 최고 웨이브를 state.json 의 rebirths 에 최근 10개까지 기록
#  panel.py: 제어줄 아래에 최근 환생 층수(최신이 크게, 나머지는 옆에) 표시
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")

# ---------------- main.py ----------------
M_HELPER_ANCHOR = "def cap():\n"
M_HELPER = '''def record_rebirth(st, why=""):
    """환생 직전의 최고 웨이브(peak_wave)를 최근 환생 목록에 기록 (패널에서 표시)"""
    try:
        w = int(st.get("peak_wave") or 0)
        if w > 0:
            lst = list(st.get("rebirths") or [])
            lst.append({"wave": w, "t": int(time.time()), "why": why})
            st["rebirths"] = lst[-10:]
            log("환생 기록: %d층 (%s)" % (w, why))
        st["peak_wave"] = 0
    except Exception as e:
        log("환생 기록 오류: %r" % (e,))


'''
M_PEAK_OLD = "                hist[:] = hist[-3:]\n"
M_PEAK_NEW = ("                hist[:] = hist[-3:]\n"
              "                if len(hist) == 3 and min(hist) > int(st.get(\"peak_wave\") or 0):\n"
              "                    st[\"peak_wave\"] = min(hist)      # 최근 3번 읽은 값 중 최솟값 = 오인식에 안 흔들리는 최고층\n")
M_UPD_OLD = "st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)"
M_UPD_NEW = "record_rebirth(st, \"환생\"); " + M_UPD_OLD
M_DROP_OLD = "st.update(high_done=False, need_low=True, high_fails=0, mid_done=False, mid_fails=0)"
M_DROP_NEW = "record_rebirth(st, \"감지\"); " + M_DROP_OLD

# ---------------- panel.py ----------------
P_UI_ANCHOR = "        # ---- 코드 변경 안내 (평소엔 숨김)\n"
P_UI = '''        # ---- 최근 환생 층수
        rb = ttk.Frame(root, style="Card.TFrame")
        rb.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(rb, text="최근 환생", font=(FONT, 9), bg=C_CARD, fg=C_MUTED).pack(side="left", padx=(14, 10), pady=10)
        self.rb_last = tk.Label(rb, text="-", font=(FONT, 15, "bold"), bg=C_CARD, fg=C_TEXT)
        self.rb_last.pack(side="left")
        self.rb_time = tk.Label(rb, text="", font=(FONT, 9), bg=C_CARD, fg=C_DIM)
        self.rb_time.pack(side="left", padx=(6, 12))
        self.rb_rest = tk.Label(rb, text="", font=(FONT, 10), bg=C_CARD, fg=C_MUTED, anchor="w")
        self.rb_rest.pack(side="left", fill="x", expand=True, padx=(0, 14))
        self.rb_mt = None

'''
P_REFRESH_OLD = "        self.root.after(400, self.refresh)\n"
P_REFRESH_NEW = "        self.show_rebirths()\n        self.root.after(400, self.refresh)\n"
P_METHOD_ANCHOR = "    # ============================================================ 메인 시작/중지\n"
P_METHOD = '''    def show_rebirths(self):
        """state.json 의 rebirths(최근 환생 층수)를 표시. 파일이 바뀔 때만 다시 읽음"""
        try:
            mt = os.path.getmtime(STATE) if os.path.exists(STATE) else 0
            if mt == self.rb_mt:
                return
            self.rb_mt = mt
            lst = []
            if mt:
                with open(STATE, encoding="utf-8") as f:
                    lst = json.load(f).get("rebirths") or []
            if not lst:
                self.rb_last.config(text="-")
                self.rb_time.config(text="")
                self.rb_rest.config(text="기록 없음 (다음 환생부터 기록)")
                return
            rev = list(reversed(lst))
            self.rb_last.config(text="%d층" % rev[0]["wave"])
            self.rb_time.config(text=time.strftime("%m-%d %H:%M", time.localtime(rev[0]["t"])))
            self.rb_rest.config(text="  ".join(str(x["wave"]) for x in rev[1:10]))
        except Exception:
            pass

'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    for p in (MAIN, PANEL):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다. C:\\macro 에서 실행하세요."); return 1
    ms = open(MAIN, encoding="utf-8").read()
    ps = open(PANEL, encoding="utf-8").read()
    done_m = "def record_rebirth(" in ms
    done_p = "def show_rebirths(" in ps
    if not done_m:
        c = (ms.count(M_HELPER_ANCHOR), ms.count(M_PEAK_OLD), ms.count(M_UPD_OLD), ms.count(M_DROP_OLD))
        if c != (1, 1, 3, 1):
            print("main.py 앵커 불일치 %s (기대 (1, 1, 3, 1)) -> main.py 를 올려 주세요" % (c,)); return 1
    if not done_p:
        c = (ps.count(P_UI_ANCHOR), ps.count(P_REFRESH_OLD), ps.count(P_METHOD_ANCHOR))
        if c != (1, 1, 1):
            print("panel.py 앵커 불일치 %s -> panel.py 를 올려 주세요" % (c,)); return 1
    if not done_m:
        ns = (ms.replace(M_HELPER_ANCHOR, M_HELPER + M_HELPER_ANCHOR, 1)
                .replace(M_PEAK_OLD, M_PEAK_NEW, 1)
                .replace(M_UPD_OLD, M_UPD_NEW)
                .replace(M_DROP_OLD, M_DROP_NEW, 1))
        print("main.py 백업:", backup(MAIN))
        open(MAIN, "w", encoding="utf-8").write(ns)
        print("main.py 패치 완료")
    else:
        print("main.py 는 이미 최신")
    if not done_p:
        ns = (ps.replace(P_UI_ANCHOR, P_UI + P_UI_ANCHOR, 1)
                .replace(P_REFRESH_OLD, P_REFRESH_NEW, 1)
                .replace(P_METHOD_ANCHOR, P_METHOD + P_METHOD_ANCHOR, 1))
        print("panel.py 백업:", backup(PANEL))
        open(PANEL, "w", encoding="utf-8").write(ns)
        print("panel.py 패치 완료 (패널이 자동으로 다시 뜹니다)")
    else:
        print("panel.py 는 이미 최신")
    print("메인 매크로는 껐다 켜야 기록이 시작됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
