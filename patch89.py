# patch89.py - 옵션 정리
#   * 서버 점검 재실행 / 길드 출석+우체국 / 길드레이드 상점 뽑기: 체크박스 삭제, 항상 켜짐
#   * 성 함락 시 이어하기: 체크박스 대신 횟수(0~3, 환생 한 번당) 선택
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")
DAILY = os.path.join(HERE, "daily.py")


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def rw(path, fn):
    s = open(path, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    new, msg = fn(s)
    if new is None:
        print(os.path.basename(path), msg)
        return msg.endswith("최신")
    try:
        compile(new, os.path.basename(path), "exec")
    except SyntaxError as e:
        print(os.path.basename(path), "문법 오류 %r -> 중단" % (e,))
        return False
    print(os.path.basename(path), "백업:", backup(path))
    open(path, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n") if crlf else new)
    print(os.path.basename(path), msg)
    return True


def rep(s, old, new, cnt=1):
    n = s.count(old)
    if n != cnt:
        raise ValueError("앵커 개수 이상 (%d, 기대 %d): %s" % (n, cnt, old.strip()[:50]))
    return s.replace(old, new)


# ------------------------------------------------------------------ main.py
M_DEF = 'def opt_on(name):\n'
M_DEF_NEW = '''def cont_limit():
    """성 함락 시 이어하기 횟수 (환생 한 번당, 0~3). 패널의 fall_continue_n, 없으면 예전 체크박스 값(켬=3)"""
    try:
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            d = json.load(f)
        if "fall_continue_n" in d:
            return max(0, min(3, int(d["fall_continue_n"])))
        return 3 if d.get("fall_continue") else 0
    except Exception:
        return 0


def opt_on(name):
'''
M_A = '            if ok and opt_on("fall_continue"):\n'
M_A_NEW = '            if ok and cont_limit() > 0:\n'
M_B = '''                if cok and len(recent) < 3:
                    log("성 함락 감지 → 이어하기 클릭 (버튼 %.2f, 90초 내 %d회째)" % (cfrac, len(recent) + 1))
                    if GO:
                        rebirth.tap(cx, cy)
                        _cont_hist.append(now)
'''
M_B_NEW = '''                if cok and st.get("cont_used", 0) < cont_limit():
                    log("성 함락 감지 → 이어하기 클릭 (버튼 %.2f, 이번 환생 %d/%d회째)" % (cfrac, st.get("cont_used", 0) + 1, cont_limit()))
                    if GO:
                        rebirth.tap(cx, cy)
                        _cont_hist.append(now)
                        st["cont_used"] = st.get("cont_used", 0) + 1
                        save_state(st)
'''
M_C = '                log("이어하기 불가 (버튼 %.2f, 90초 내 %d회) → 환생" % (cfrac, len(recent)))\n'
M_C_NEW = '                log("이어하기 불가 (버튼 %.2f, 사용 %d/%d회) → 환생" % (cfrac, st.get("cont_used", 0), cont_limit()))\n'
M_D = "st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)"
M_D_NEW = "st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0, cont_used=0)"
M_E = '            if GO and daily.setting("maint", True):\n'
M_E_NEW = '            if GO:\n'


def fix_main(s):
    if "def cont_limit" in s:
        return None, "main.py 는 이미 최신"
    s = rep(s, M_DEF, M_DEF_NEW)
    s = rep(s, M_A, M_A_NEW)
    s = rep(s, M_B, M_B_NEW)
    s = rep(s, M_C, M_C_NEW)
    s = rep(s, M_D, M_D_NEW, 3)
    s = rep(s, M_E, M_E_NEW)
    return s, "패치 완료 (메인 재시작 필요)"


# ------------------------------------------------------------------ daily.py
D_A = '        if not d.get(key) and setting(opt, opt != "archery"):     # 양궁은 기본 꺼짐\n'
D_A_NEW = '        if not d.get(key) and (opt in ("guild_post", "raid_shop") or setting(opt, False)):     # 출석/레이드 상점은 항상 켜짐, 양궁은 기본 꺼짐\n'


def fix_daily(s):
    if D_A_NEW in s:
        return None, "daily.py 는 이미 최신"
    return rep(s, D_A, D_A_NEW), "패치 완료 (메인 재시작 필요)"


# ------------------------------------------------------------------ panel.py
P_SEL = '''        crow = ttk.Frame(tab, style="Card.TFrame")
        crow.pack(fill="x", padx=14, pady=(0, 14))
        ttk.Label(crow, text="성 함락 시 이어하기 횟수 (환생 한 번당)", style="Sub.TLabel").pack(side="left")
        try:
            n0 = int(self.set.get("fall_continue_n", 3 if self.set.get("fall_continue") else 0))
        except Exception:
            n0 = 0
        self.cont_var = tk.StringVar(value=str(max(0, min(3, n0))))
        cb = ttk.Combobox(crow, values=("0", "1", "2", "3"), width=3, state="readonly", textvariable=self.cont_var)
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self.save_cont())
        ttk.Label(crow, text="0 = 바로 환생 / 하트가 없으면 횟수와 상관없이 환생", style="Sub.TLabel").pack(side="left")

'''
P_METHOD = '''    def save_cont(self):
        try:
            n = int(self.cont_var.get())
            d = load_settings()
            d["fall_continue_n"] = n
            d["fall_continue"] = n > 0
            save_settings(d)
            self.note("성 함락 이어하기 횟수: %d" % n, "cmd")
        except Exception as e:
            self.note("이어하기 횟수 저장 실패: %r" % e, "warn")

    def save_opts(self):
'''


def fix_panel(s):
    if "def save_cont" in s:
        return None, "panel.py 는 이미 최신"
    lines = s.split("\n")
    out = []
    changed = 0
    for l in lines:
        t = l.lstrip()
        if t.startswith('("fall_continue", ') or t.startswith('("guild_post", ') or t.startswith('("raid_shop", '):
            changed += 1
            continue
        if t.startswith('("maint", ') and t.rstrip().endswith("),):"):
            out.append(l[:len(l) - len(t)] + "):")
            changed += 1
            continue
        out.append(l)
    if changed != 4:
        raise ValueError("패널 항목 개수 이상 (%d, 기대 4)" % changed)
    s = "\n".join(out)
    anchor = '            ttk.Label(row, text="      " + sub, style="Sub.TLabel").pack(anchor="w", pady=(0, 6))\n\n'
    s = rep(s, anchor, anchor + P_SEL)
    s = rep(s, "    def save_opts(self):\n", P_METHOD)
    return s, "패치 완료 (패널은 스스로 다시 뜸)"


def main():
    ok = True
    for p, f in ((MAIN, fix_main), (DAILY, fix_daily), (PANEL, fix_panel)):
        if not os.path.exists(p):
            print(os.path.basename(p), "없음")
            ok = False
            continue
        try:
            ok = rw(p, f) and ok
        except ValueError as e:
            print(os.path.basename(p), "->", e)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
