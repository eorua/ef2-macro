"""soul.py - 신전 '영혼의 휴식' 자동화 (최대 4시간 자리비움 보상. 끝날 때 다이아로 훈장 2배 선택)

  py soul.py look        지금 화면이 어떤 상태인지만 출력 (누르지 않음)
  py soul.py dia         HUD 다이아 개수 읽기 시험
  py soul.py start go    (성 > 신전 > 영혼의 휴식 시작) 실제로 한 번 실행
  py soul.py end go      휴식 중 화면에서 종료창을 열어 2배로 받기까지 한 번 실행 (4시간 안 기다림, 시험용)

main.py 연결: 패널 옵션 'soul' 이 켜져 있고, 일일 작업이 없고, 다이아가 5000 이상일 때 start(st), 휴식 중에는 tick(st, img)
"""
import os, sys, time
import cv2, numpy as np
import preset

BASE = r"C:\macro"
TPLDIR = os.path.join(BASE, "tpl")
SHOTS = os.path.join(BASE, "shots")

SOUL_HOURS = 4.0                    # 한 번에 쉴 수 있는 최대 시간
COOLDOWN_SEC = 8 * 3600 + 300       # 휴식이 끝난 뒤 다시 시작할 수 있을 때까지 (게임 표시 약 8시간)
MIN_DIA_START = 5000                # 이 다이아 이상일 때만 시작
MIN_DIA_X2 = 2000                   # 종료할 때 이 이상이면 다이아 1000 으로 훈장 2배

TAB_CASTLE = (302, 1245)            # 하단 '성' 탭
BTN_TEMPLE = (640, 790)             # 성 - 자원 화면의 '신전' 버튼 (추정 좌표 -> 위아래로 몇 곳 시도)
TEMPLE_TRY = [(640, 790), (640, 772), (640, 808), (610, 790)]
PANEL_X = (677, 790)                # 패널(성 - 신전) 빨간 X
LIST_SWIPE = (360, 1120, 360, 820)  # 신전 목록 아래로 스크롤
ROW_BTN_X = 600                     # 영혼의 휴식 줄 버튼의 x
CONFIRM_OK = (265, 465)             # '영혼의 휴식을 시작하시겠습니까?' 확인
BTN_REST_END = (375, 545)           # 휴식 중 화면의 '휴식 종료'
END_OK = (232, 622)                 # 종료창 확인 (훈장 1배)
END_X2 = (448, 622)                 # 종료창 다이아 1000 / 훈장 x 2

ROI_PANEL_HDR = (0, 750, 200, 820)
ROI_ROW = (100, 820, 420, 1215)
ROI_CONFIRM_Q = (200, 370, 520, 415)
ROI_RUN_BTN = (240, 500, 520, 590)
ROI_END_Q = (190, 465, 530, 515)
ROI_DIA = (327, 722, 400, 748)

_cache = {}


def log(*a):
    print(time.strftime("[%H:%M:%S] soul:"), *a, flush=True)


def grab():
    img = preset.capture()
    if img is None:
        raise RuntimeError("화면 캡처 실패")
    return img


def tap(pt, label="", wait=0.9):
    preset.tap(pt, label)
    time.sleep(wait)


def swipe(x1, y1, x2, y2, ms=600):
    import subprocess
    print(("스와이프 " if preset.GO else "[시험] 스와이프 ") + f"{(x1, y1)} -> {(x2, y2)}")
    if preset.GO:
        subprocess.run(preset.ADB + ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(ms)])
    time.sleep(0.8)


def shot(name, img=None):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        if img is None:
            img = preset.capture()
        if img is not None:
            cv2.imwrite(os.path.join(SHOTS, name + ".png"), img)
    except Exception:
        pass


def _tpl(name):
    if name not in _cache:
        _cache[name] = cv2.imread(os.path.join(TPLDIR, name))
    return _cache[name]


def match(img, name, roi):
    """roi 안에서 템플릿 위치 찾기 -> (점수, (중심x, 중심y)). 템플릿이 없으면 (0, None)"""
    t = _tpl(name)
    if t is None:
        return 0.0, None
    x1, y1, x2, y2 = roi
    sub = img[y1:y2, x1:x2]
    th, tw = t.shape[:2]
    if sub.shape[0] < th or sub.shape[1] < tw:
        return 0.0, None
    res = cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED)
    _, s, _, loc = cv2.minMaxLoc(res)
    return float(s), (x1 + loc[0] + tw // 2, y1 + loc[1] + th // 2)


# ---------------------------------------------------------------- 화면 판별
def panel_open(img):
    return match(img, "soul_panel_hdr.png", ROI_PANEL_HDR)[0] >= 0.85


def row_y(img):
    s, p = match(img, "soul_row_title.png", ROI_ROW)
    return p[1] if s >= 0.85 else None


def button_state(img, y):
    """영혼의 휴식 줄 버튼: 'ready'(초록 시작) / 'cool'(갈색 시간 단축) / 'run'(회색 휴식 중) / None"""
    roi = img[y - 24:y + 24, 520:690]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    green = float(((h >= 35) & (h <= 85) & (s >= 120)).mean())
    brown = float(((h >= 8) & (h <= 22) & (s >= 80) & (v >= 100)).mean())
    grey = float(((s < 40) & (v >= 50)).mean())
    if green >= 0.4:
        return "ready"
    if brown >= 0.25:
        return "cool"
    if grey >= 0.5:
        return "run"
    return None


def confirm_open(img):
    return match(img, "soul_confirm_q.png", ROI_CONFIRM_Q)[0] >= 0.85


def running_view(img):
    return match(img, "soul_run_btn.png", ROI_RUN_BTN)[0] >= 0.85


def end_dialog(img):
    return match(img, "soul_end_q.png", ROI_END_Q)[0] >= 0.85


def screen_state(img):
    if end_dialog(img):
        return "end_dialog"
    if confirm_open(img):
        return "confirm"
    if running_view(img):
        return "running"
    if panel_open(img):
        y = row_y(img)
        if y is not None:
            return "panel_row:" + str(button_state(img, y))
        return "panel"
    return "other"


# ---------------------------------------------------------------- 다이아 읽기
def _glyphs(img):
    x1, y1, x2, y2 = ROI_DIA
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 0] >= 90) & (hsv[..., 0] <= 112) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 120)).astype(np.uint8)
    cols = np.nonzero(m.any(0))[0]
    if len(cols) == 0:
        return []
    runs, s, p = [], cols[0], cols[0]
    for c in cols[1:]:
        if c != p + 1:
            runs.append((s, p)); s = c
        p = c
    runs.append((s, p))
    out = []
    for a, b in runs:
        g = m[:, a:b + 1]
        rows = np.nonzero(g.any(1))[0]
        g = g[rows.min():rows.max() + 1]
        out.append(g)
    return out


def _norm(g):
    return cv2.resize(g.astype(np.float32), (10, 14), interpolation=cv2.INTER_AREA)


_DIG = {}


def _digit_tpls():
    if not _DIG:
        for d in "0123456789":
            path = os.path.join(TPLDIR, "dig_%s.png" % d)
            if not os.path.exists(path):
                continue
            t = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if t is not None:
                _DIG[d] = t.astype(np.float32) / 255.0
    return _DIG


def _classify(g):
    a = _norm(g)
    best, bs = None, 0.0
    for d, t in _digit_tpls().items():
        den = float(np.linalg.norm(a) * np.linalg.norm(t))
        sc = float((a * t).sum()) / den if den > 0 else 0.0
        if sc > bs:
            best, bs = d, sc
    return (best, bs) if bs >= 0.9 else (None, bs)


def read_diamonds(img):
    """HUD 다이아 개수 -> (값 또는 None, 정확한지). 아직 템플릿이 없는 숫자가 섞이면 자릿수로 하한만 알려줌
    5자리 이상이면 10000 이상, 못 읽는 4자리 이하는 None"""
    gl = _glyphs(img)
    if not gl:
        return None, False
    ds = [_classify(g)[0] for g in gl]
    n = len(gl)
    if all(d is not None for d in ds):
        return int("".join(ds)), True
    if n >= 5:
        return 10 ** (n - 1), False          # 하한 (예: 5자리 -> 10000 이상)
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, "dia_unknown_%d.png" % int(time.time())), img[ROI_DIA[1]:ROI_DIA[3], ROI_DIA[0]:ROI_DIA[2]])
    except Exception:
        pass
    return None, False


# ---------------------------------------------------------------- 시작
def _close_everything():
    import daily
    try:
        import closer
        closer.close_all(3)
    except Exception:
        pass
    daily.close_panels()


def _open_temple():
    """성 탭 -> 신전 패널 열기. 패널이 열렸으면 True"""
    img = grab()
    if panel_open(img):
        return True
    tap(TAB_CASTLE, "성 탭", 1.0)
    for pt in TEMPLE_TRY:
        tap(pt, "신전 버튼", 1.2)
        img = grab()
        if panel_open(img):
            return True
    shot("soul_fail_temple")
    return False


def _find_row():
    """신전 목록을 아래로 스크롤하며 '영혼의 휴식' 줄 찾기 -> (이미지, y)"""
    for k in range(7):
        img = grab()
        y = row_y(img)
        if y is not None and y > 1080:      # 맨 아래까지 내려온 위치(약 1153)
            return img, y
        if y is not None and k >= 5:
            return img, y
        swipe(*LIST_SWIPE)
    img = grab()
    return img, row_y(img)


def start(st, force=False):
    """영혼의 휴식 시작. 반환: 'started' / 'cooldown' / 'running' / 'low' / 'fail'
    patch206: force=True(사용자 예약) 면 다이아 5000 조건을 건너뛰고, 끝날 때 무조건 다이아 1000 으로 2배"""
    img = grab()
    dia, exact = read_diamonds(img)
    log("다이아 %s%s" % (dia, "" if exact else " (자릿수 기준 추정)"))
    if not force and (dia is None or dia < MIN_DIA_START):
        log("다이아가 %d 미만이거나 읽지 못함 -> 시작 안 함" % MIN_DIA_START)
        return "low"
    if not _open_temple():
        log("신전 패널을 못 열었음")
        _close_everything()
        return "fail"
    img, y = _find_row()
    if y is None:
        log("영혼의 휴식 줄을 못 찾음")
        shot("soul_fail_row", img)
        _close_everything()
        return "fail"
    stt = button_state(img, y)
    log("영혼의 휴식 버튼 상태:", stt)
    if stt == "cool":
        _close_everything()
        return "cooldown"
    if stt == "run":
        log("이미 휴식 중으로 보임 -> 진행 중으로 이어서 처리")
        st["soul"] = {"start": time.time(), "last_seen": time.time(), "dia": dia}
        return "running"
    if stt != "ready":
        log("버튼 상태를 알 수 없음")
        shot("soul_fail_btn", img)
        _close_everything()
        return "fail"
    tap((ROW_BTN_X, y), "시작", 1.0)
    for _ in range(6):
        img = grab()
        if confirm_open(img):
            break
        time.sleep(0.4)
    else:
        log("시작 확인창이 안 뜸")
        shot("soul_fail_confirm", img)
        _close_everything()
        return "fail"
    tap(CONFIRM_OK, "시작 확인", 1.2)
    for _ in range(8):
        img = grab()
        if running_view(img):
            st["soul"] = {"start": time.time(), "last_seen": time.time(), "dia": dia}
            log("영혼의 휴식 시작 (최대 %.1f시간)" % SOUL_HOURS)
            return "started"
        time.sleep(0.5)
    log("휴식 중 화면을 확인하지 못함")
    shot("soul_fail_run", img)
    st["soul"] = {"start": time.time(), "last_seen": 0, "dia": dia}      # 시작됐을 수 있으니 추적은 시작
    return "started"


# ---------------------------------------------------------------- 진행 / 종료
def _finish(st, got_x2):
    d = st.pop("soul", {}) or {}
    now = time.time()
    dur = max(0.0, now - d.get("start", now))
    st["soul_next"] = now + COOLDOWN_SEC
    if st.get("last_restart"):
        st["last_restart"] = min(now, st["last_restart"] + dur)       # 쉰 시간은 정기 재시작 시간에 넣지 않음
    log("영혼의 휴식 종료 처리 완료 (%.0f분, 훈장 %s)" % (dur / 60, "x2" if got_x2 else "x1"))
    try:
        _close_everything()
    except Exception as e:
        log("정리 중 오류:", repr(e))


def _resolve_end(st, img):
    import daily
    d = st.get("soul", {})
    dia, exact = read_diamonds(img)
    if dia is None:
        dia = d.get("dia", 0)
    want_x2 = daily.setting("soul_x2", True) and dia >= MIN_DIA_X2
    if d.get("force_x2"):                                # patch206: 사용자 예약 - 무조건 2배
        want_x2 = True
    log("종료창: 다이아 %s -> %s" % (dia, "훈장 x2 (다이아 1000)" if want_x2 else "그냥 받기"))
    tap(END_X2 if want_x2 else END_OK, "종료 선택", 1.5)
    for i in range(4):
        img = grab()
        if not end_dialog(img):
            return True, want_x2
        if want_x2 and i >= 2:                           # patch206: 2배가 계속 안 되면(다이아 부족 등) 그냥 받기
            log("2배 선택이 안 됨 -> 그냥 받기")
            want_x2 = False
        tap(END_X2 if want_x2 else END_OK, "종료 선택(재시도)", 1.5)
    return False, want_x2


END_GRACE = 60                      # patch224: 4시간 + 이만큼 지나면 종료 처리
END_GIVEUP = 3600                   # patch224: 종료 시각 뒤 이만큼 휴식 화면을 못 찾으면 추적 종료 (patch223 기준 유지)


def end_time(d):
    """시작 시각 + 4시간(+여유) = 종료 처리 시각"""
    return d.get("start", time.time()) + SOUL_HOURS * 3600 + END_GRACE


def idle_sleep(st):
    """patch224: main 루프 대기 시간 - 종료 시각 전에는 15초, 지나면 3초"""
    d = st.get("soul")
    if d and time.time() < end_time(d) - 20:
        return 15
    return 3


def _clear_cover():
    """가린 창(우편함·이벤트 등)을 빨간 X 로 닫음 -> 닫은 개수"""
    n = 0
    try:
        import ocrx
        for _ in range(4):
            cur = grab()
            if cur is None or running_view(cur) or end_dialog(cur):
                break
            xs = ocrx.red_x_buttons(cur)
            if not xs:
                break
            tap(xs[0], "가린 창 X", 0.8)
            n += 1
    except Exception as e:
        log("가린 창 닫기 오류: %r" % (e,))
    return n


def tick(st, img):
    """휴식 중일 때 main 루프에서 매번 호출. 반환 True 면 휴식 중(다른 동작 금지)
    patch224: 휴식은 4시간 고정 -> 종료 시각 전에는 화면 확인/가린 창 닫기를 전혀 하지 않고 기다리기만 함.
    종료 시각(state.json 에 저장된 시작 시각 + 4시간)이 되면 그때만 휴식 화면을 찾아 종료 + 2배 받기."""
    d = st.get("soul")
    if not d:
        return False
    now = time.time()
    end = end_time(d)
    if now < end:
        if now - d.get("note", 0) > 1800:
            d["note"] = now
            log("휴식 중 - 종료 예정 %s (%.0f분 남음)" % (time.strftime("%H:%M", time.localtime(end)), (end - now) / 60))
        return True
    if end_dialog(img):
        d["last_seen"] = now
        ok, x2 = _resolve_end(st, img)
        if ok:
            _finish(st, x2)
        else:
            log("종료창을 닫지 못함 -> 다음 루프에서 재시도")
        return True
    if running_view(img):
        d["last_seen"] = now
        if now - d.get("end_tap", 0) > 5:
            d["end_tap"] = now
            log("%.1f시간 경과 -> 휴식 종료 버튼" % ((now - d.get("start", now)) / 3600))
            tap(BTN_REST_END, "휴식 종료", 1.2)
        return True
    # 종료 시각이 지났는데 휴식 화면이 안 보임 -> 이때만 가린 창을 닫고 다시 확인
    if now - end > END_GIVEUP:
        log("종료 시각 뒤 %d분 동안 휴식 화면을 못 찾음 -> 추적 종료 (상태 확인 필요)" % (END_GIVEUP // 60))
        shot("soul_lost")
        st.pop("soul", None)
        st["soul_next"] = now + 1800
        return False
    if now - d.get("close_try", 0) > 60:
        d["close_try"] = now
        n = _clear_cover()
        if n:
            log("휴식 화면을 가린 창 %d개 닫음 -> 다시 확인" % n)
            cur = grab()
            if cur is not None and (running_view(cur) or end_dialog(cur)):
                return tick(st, cur)
        else:
            log("종료 시각인데 휴식 화면이 안 보임 (닫을 창도 없음) -> 1분 뒤 다시")
            shot("soul_miss_%d" % int(now), img)
    return True


def ready_to_start(st, wave_exact):
    """일일 작업이 남아 있으면 먼저 하게 하고, 쿨타임/조건이 맞을 때만 True"""
    import daily
    if st.get("soul") or time.time() < st.get("soul_next", 0):
        return False
    if st.get("need_low"):
        return False
    if wave_exact is None:
        return False
    if wave_exact < daily.MAX_WAVE - 100 and daily.due(st):
        return False                        # 밀린 일일 작업(전투 이벤트 등)부터
    return True


def handle_start_result(st, res):
    now = time.time()
    if res == "started" or res == "running":
        st["soul_fail"] = 0
        return
    if res == "cooldown":
        st["soul_next"] = now + 1800
    elif res == "low":
        st["soul_next"] = now + 1800
    else:
        st["soul_fail"] = st.get("soul_fail", 0) + 1
        st["soul_next"] = now + (600 if st["soul_fail"] < 3 else 7200)
        if st["soul_fail"] >= 3:
            st["soul_fail"] = 0
    log("다음 시도: %d분 뒤" % int((st["soul_next"] - now) / 60))


if __name__ == "__main__":
    args = sys.argv[1:]
    img = preset.capture()
    if img is None:
        print("캡처 실패"); sys.exit(1)
    if "dia" in args:
        print("다이아:", read_diamonds(img)); sys.exit(0)
    print("화면 상태:", screen_state(img))
    dia = read_diamonds(img)
    print("다이아:", dia)
    y = row_y(img)
    if y is not None:
        print("영혼의 휴식 줄 y=%d 버튼=%s" % (y, button_state(img, y)))
    if "go" in args:
        st = {"last_restart": time.time()}
        if "start" in args:
            res = start(st)
            print("결과:", res)
        elif "end" in args:
            if screen_state(img) == "running":
                tap(BTN_REST_END, "휴식 종료", 1.5)
            st["soul"] = {"start": time.time() - 60, "dia": (dia[0] or 0)}
            img = grab()
            print("종료창:", end_dialog(img))
            if end_dialog(img):
                ok, x2 = _resolve_end(st, img)
                print("처리:", ok, "x2" if x2 else "x1")
    else:
        print("(시험 모드. 실제 실행은 맨 끝에 go)")
