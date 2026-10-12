# patch69.py - 서버 점검 팝업을 읽고, BlueStacks 를 끈 뒤 점검이 끝날 때쯤 다시 실행 (C:\macro 에서 py patch69.py)
#   * maint.py 신규: 가운데 초록 '확인' 버튼 하나짜리 팝업이 뜨면 윈도우 내장 OCR 로 글자를 읽어 '점검'/'KST' 확인,
#       '2026-10-12 09:40 ~ 10:40 (KST)' 에서 끝나는 시각을 해석. OCR 이 안 되면 이미지로 대신 판별(이때는 끝나는 시각을 모름)
#   * main.py: 점검 감지 -> BlueStacks(오환2) 종료 -> 끝나는 시각 + 3분에 다시 실행 -> 아직 점검이면 다시 끄고 대기
#       (끝나는 시각을 모르면 20분마다 실행해서 확인). 매크로를 껐다 켜도 대기 시각을 이어감
#   * 패널 옵션 '서버 점검 시 BlueStacks 종료 후 재실행' (기본 켜짐)
#   * 시험:  py maint.py ocrtest  (OCR 되는지)   /   py maint.py look  (지금 화면이 점검 팝업인지)
import os, sys, shutil, base64, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")
MAINT = os.path.join(HERE, "maint.py")
TPLDIR = os.path.join(HERE, "tpl")
MAINT_DATA = """
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
"""
TPL_DATA = """
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
"""

M_OLD0 = 'def main():\n    log("매크로 시작 (" + ("실제 클릭 모드" if GO else "시험 모드: 클릭 안 함") + ") - 중지: Ctrl + C")\n'
M_NEW_FUNCS = '''MAINT_POLL_SEC = 1200            # 점검이 끝나는 시각을 모를 때, 이 간격(초)마다 BlueStacks 를 켜서 끝났는지 확인


def maint_check(img):
    """서버 점검 팝업이면 {'end': 끝나는 시각 또는 None, 'text': ...}, 아니면 None"""
    try:
        import maint
        return maint.detect(img)
    except Exception as e:
        log("점검 확인 오류: %r" % (e,))
        return None


def _kill_bluestacks():
    try:
        pids = bsrestart.find_pids()
    except Exception as e:
        log("BlueStacks 프로세스 확인 오류: %r" % (e,))
        return False
    if len(pids) > 1:
        log("오환2 BlueStacks 가 2개 이상으로 보여 끄지 않음")
        return False
    for p in pids:
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    if pids:
        log("BlueStacks(오환2) 종료")
        time.sleep(8)
    return True


def handle_maintenance(st, info):
    """점검 중이면 BlueStacks 를 끄고 점검이 끝날 때쯤 다시 켬. 아직 점검이면 반복. 끝나면 복귀 설정까지 하고 반환"""
    import maint
    end = (info or {}).get("end")
    while True:
        now = time.time()
        wake = end + 180 if end else now + MAINT_POLL_SEC
        wake = max(wake, now + 5)
        log("서버 점검 -> BlueStacks 를 끄고 %s 에 다시 실행합니다%s" % (
            time.strftime("%m-%d %H:%M", time.localtime(wake)), "" if end else " (끝나는 시각을 못 읽어 확인용으로 주기 실행)"))
        st["maint"] = {"wake": wake}
        save_state(st)
        _kill_bluestacks()
        last_msg = 0
        while time.time() < wake:
            time.sleep(20)
            if time.time() - last_msg > 900:
                last_msg = time.time()
                log("점검 대기 중 (남은 %d분)" % max(0, int((wake - time.time()) / 60)))
        log("BlueStacks 다시 실행")
        if not restart_bluestacks_full():
            log("BlueStacks 실행 실패 -> 7분 뒤 다시 시도")
            end = time.time() + 240
            continue
        info2 = None
        t0 = time.time()
        while time.time() - t0 < 200:
            time.sleep(6)
            img = cap()
            if img is None:
                continue
            info2 = maint_check(img)
            if info2:
                break
            if wave.read_wave(img) is not None:
                break
        if info2:
            log("아직 점검 중")
            end = info2.get("end")
            continue
        break
    st.pop("maint", None)
    maint._last.update(t=0.0, hit=False)
    log("점검이 끝난 것으로 보임 -> 복귀")
    if recover():
        after_restart_setup(st)
    st["last_restart"] = time.time()
    save_state(st)


'''
M_NEW0 = M_NEW_FUNCS + M_OLD0
M_OLD1 = "    st = load_state()\n    if not st.get(\"last_restart\"):\n"
M_NEW1 = ("    st = load_state()\n"
          "    if GO and st.get(\"maint\"):\n"
          "        log(\"점검 대기 중이던 상태를 이어서 처리\")\n"
          "        handle_maintenance(st, {\"end\": st[\"maint\"].get(\"wake\", 0) - 180})\n"
          "    if not st.get(\"last_restart\"):\n")
M_OLD2 = "        try:\n            # 게임이 튕겨서 홈 화면 등으로 나갔는지 주기적으로 확인\n"
M_NEW2 = ("        try:\n"
          "            # 서버 점검 팝업: BlueStacks 를 끄고 점검이 끝날 때쯤 다시 실행\n"
          "            if GO and daily.setting(\"maint\", True):\n"
          "                _mt = maint_check(img)\n"
          "                if _mt:\n"
          "                    handle_maintenance(st, _mt)\n"
          "                    hist.clear()\n"
          "                    stuck.reset()\n"
          "                    continue\n"
          "            # 게임이 튕겨서 홈 화면 등으로 나갔는지 주기적으로 확인\n")

P_OLD1 = '"soul": False, "soul_x2": True}'
P_NEW1 = '"soul": False, "soul_x2": True, "maint": True}'
P_OLD2 = '끄면 1배로 받습니다. 기본은 켜짐."),):\n'
P_NEW2 = ('끄면 1배로 받습니다. 기본은 켜짐."),\n'
          '                ("maint", "서버 점검 시 BlueStacks 종료 후 재실행", "점검 팝업을 글자로 읽고 BlueStacks 를 끈 뒤, 점검이 끝나는 시각에 다시 실행합니다. 기본은 켜짐."),):\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def unpack(s):
    return zlib.decompress(base64.b64decode("".join(s.split())))


def rd(p):
    s = open(p, encoding="utf-8").read()
    return s.replace("\r\n", "\n"), "\r\n" in s


def wr(p, s, crlf):
    open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)


def main():
    for p in (MAIN, PANEL):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다 (C:\\macro 에서 실행)"); return 1
    ms, mc = rd(MAIN)
    ps, pc = rd(PANEL)
    done_m = "def handle_maintenance(" in ms
    done_p = '"maint"' in ps
    cnt = (ms.count(M_OLD0), ms.count(M_OLD1), ms.count(M_OLD2))
    if not done_m and cnt != (1, 1, 1):
        print("main.py 앵커 불일치", cnt, "-> main.py 를 올려 주세요"); return 1
    if not done_p and (ps.count(P_OLD1) != 1 or ps.count(P_OLD2) != 1):
        print("panel.py 앵커 불일치 (%d, %d) -> patch67 을 먼저 적용했는지 확인하세요" % (ps.count(P_OLD1), ps.count(P_OLD2))); return 1
    os.makedirs(TPLDIR, exist_ok=True)
    raw = unpack(TPL_DATA)
    tp = os.path.join(TPLDIR, "maint_title.png")
    if not os.path.exists(tp) or open(tp, "rb").read() != raw:
        open(tp, "wb").write(raw)
        print("tpl\\maint_title.png 저장")
    raw = unpack(MAINT_DATA)
    if not os.path.exists(MAINT) or open(MAINT, "rb").read() != raw:
        if os.path.exists(MAINT):
            print("백업:", backup(MAINT))
        open(MAINT, "wb").write(raw)
        print("maint.py 갱신")
    else:
        print("maint.py 는 이미 최신")
    if not done_m:
        print("main.py 백업:", backup(MAIN))
        wr(MAIN, ms.replace(M_OLD0, M_NEW0, 1).replace(M_OLD1, M_NEW1, 1).replace(M_OLD2, M_NEW2, 1), mc)
        print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    else:
        print("main.py 는 이미 최신")
    if not done_p:
        print("panel.py 백업:", backup(PANEL))
        wr(PANEL, ps.replace(P_OLD1, P_NEW1, 1).replace(P_OLD2, P_NEW2, 1), pc)
        print("panel.py 패치 완료 (패널이 자동으로 다시 뜹니다)")
    else:
        print("panel.py 는 이미 최신")
    print("먼저 py maint.py ocrtest 로 윈도우 글자 인식(OCR)이 되는지 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
