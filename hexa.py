# -*- coding: utf-8 -*-
"""유물 공방(헥사 머지) 자동 플레이 봇  — 오늘도 환생2

사용법 (PowerShell, C:\\macro 에서)
  py hexa.py look              지금 화면을 읽고 추천 수만 보여줌 (터치 안 함) -> shots\\hexa_look.png
  py hexa.py look 파일.png     저장된 캡처로 같은 확인
  py hexa.py play go           한 판 플레이 (공방 로비 / 게임 화면 어디서든 시작)
  py hexa.py play go 3         세 판 연속 (티켓 3장 사용)
  (patch243) 로비 버튼이 '이어 하기'면 지난 판을 이어서 함 (앱이 꺼져도 판은 저장됨, 티켓 안 씀)
  py hexa.py sim 20            PC에서 가상 대전 20판 (전략 성능 확인용, 게임과 무관)

파일
  hexa_engine.py   규칙 엔진 + 탐색 AI
  hexa_vision.py   화면 읽기
  hexa_cfg.json    자동 보정값 (드래그 높이, 회전 방향, 9·10등급 색)
  shots\\hexa_log.txt, shots\\hexa_learn.jsonl, shots\\hexa_err_*.png
"""
import os, sys, time, json, subprocess, re, datetime
import numpy as np
import cv2

import hexa_engine as E
import hexa_vision as V
for _s in (sys.stdout, sys.stderr):      # patch295: 메인이 utf-8 로 읽으므로 맞춤 + 인코딩 불가 글자도 예외 없이 대체
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
try:
    import hexa_nt as NT      # patch231
except Exception:
    NT = None

BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")
os.makedirs(SHOTS, exist_ok=True)
ADB_EXE = os.path.join(BASE, "adb.exe") if os.path.exists(os.path.join(BASE, "adb.exe")) else (
    r"C:\platform-tools\adb.exe" if os.path.exists(r"C:\platform-tools\adb.exe") else "adb"
)
CFG_PATH = os.path.join(BASE, "hexa_cfg.json")
LOG_PATH = os.path.join(SHOTS, "hexa_log.txt")
LEARN_PATH = os.path.join(SHOTS, "hexa_learn.jsonl")
SPAWN_PATH = os.path.join(SHOTS, "hexa_spawn.jsonl")   # patch246: 매 수 조각 기록(출현 규칙 분석용)
SPAWN = {"gid": None, "last": None}

STOP_REQS = [
    os.path.join(BASE, "stop_hexa.req"),
    os.path.join(BASE, "hexa_stop.req"),
    os.path.join(BASE, "job_cancel.req"),
]
PAUSE_FILE = os.path.join(BASE, "PAUSE")


def should_stop():
    """patch292b: 작업 중단 요청(stop_hexa.req, hexa_stop.req, job_cancel.req, PAUSE) 확인"""
    for req in STOP_REQS:
        if os.path.exists(req):
            try:
                os.remove(req)
            except Exception:
                pass
            return True
    if os.path.exists(PAUSE_FILE):
        return True
    return False

CFG = dict(lift=[0.0, 160.0], rot_dir=1, colors={}, swipe_ms=380, settle=0.9, depth=3)


def load_cfg():
    if os.path.exists(CFG_PATH):
        try:
            CFG.update(json.load(open(CFG_PATH, encoding="utf-8")))
        except Exception:
            pass
    cols = {k: v for k, v in (CFG.get("colors") or {}).items() if int(k) < 9}   # 9·10은 무지개 배경 -> 색 안 씀
    CFG["colors"] = cols
    V.set_colors(cols)


def save_cfg():
    json.dump(CFG, open(CFG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def log(*a):
    s = datetime.datetime.now().strftime("%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    # patch295: 파일에 먼저 기록하고, 콘솔 출력은 인코딩 실패(cp949 파이프에서 '➜' '🎯' 등)가 나도 절대 예외를 내지 않음
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass
    try:
        print(s, flush=True)
    except Exception:
        try:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            print(s.encode(enc, "replace").decode(enc, "replace"), flush=True)
        except Exception:
            pass


def learn(rec):
    rec["t"] = time.time()
    with open(LEARN_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def spawn_new_game(kind):
    """patch246: 새 판(또는 이어 하기) 시작 표시"""
    SPAWN["gid"] = datetime.datetime.now().strftime("%m%d_%H%M%S")
    SPAWN["last"] = None
    EXPECT[:] = [[0] * E.N] if kind in ("start", "again") else []     # patch257: 새 판은 빈 판
    LAST.clear()                 # patch267: 칸별 마지막으로 확인된 등급 기억도 새로
    try:
        with open(SPAWN_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "start", "gid": SPAWN["gid"], "how": kind, "t": time.time()}) + "\n")
    except Exception:
        pass


def spawn_log(r):
    """patch246: 이 수의 대기 조각(모양·칸별 등급)·오른쪽 미리보기·놓기 전 판·해금 수. 같은 수를 다시 계획할 땐 안 씀"""
    try:
        if SPAWN["gid"] is None:
            spawn_new_game("unknown")
        cur = [[list(o), t] for o, t in r["tray"]]
        prev = [[list(o), t] for o, t in r["prev"]] if r.get("prev") else None
        key = json.dumps([r["board"], cur, prev])
        if key == SPAWN["last"]:
            return
        SPAWN["last"] = key
        rec = {"kind": "move", "gid": SPAWN["gid"], "mv": STATS.get("moves", 0), "u": r.get("unlocked"),
               "tray": cur, "prev": prev, "board": list(r["board"]), "t": time.time()}
        with open(SPAWN_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass


# ---------------- ADB ----------------
SERIAL = None


def _run(args, timeout=10):
    return subprocess.run(args, capture_output=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _conf_port():
    for p in [r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf"]:
        try:
            txt = open(p, encoding="utf-8", errors="ignore").read()
            m = re.findall(r'bst\.instance\.[^.]+\.status\.adb_port="(\d+)"', txt)
            if m:
                return m[0]
        except Exception:
            pass
    return None


def find_serial():
    global SERIAL
    try:                                  # 매크로 공통 ADB 주소 (patch202 adbport)
        import adbport
        dev = adbport.sync(say=lambda m: log(m))
        if dev:
            r = _run([ADB_EXE, "-s", dev, "get-state"])
            if b"device" in r.stdout:
                SERIAL = dev
                return SERIAL
    except Exception:
        pass
    out = _run([ADB_EXE, "devices"]).stdout.decode(errors="ignore")
    devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip().endswith("device")]
    if not devs:
        port = _conf_port() or "5585"
        _run([ADB_EXE, "connect", "127.0.0.1:" + port])
        out = _run([ADB_EXE, "devices"]).stdout.decode(errors="ignore")
        devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip().endswith("device")]
    if not devs:
        raise SystemExit("ADB 기기를 못 찾음 (블루스택 켜져 있는지 확인)")
    SERIAL = devs[0]
    return SERIAL


def adb(*args, timeout=10):
    if SERIAL is None:
        find_serial()
    return _run([ADB_EXE, "-s", SERIAL] + list(args), timeout=timeout)


# ---------------- patch245: 빠른 화면(fastcam = 창 없는 scrcpy 영상) ----------------
# ADB 스크린샷(PNG)은 한 장에 0.4~0.7초(추정)라 한 수에 5~7장 찍으면 몇 초가 감 -> 영상으로 받아 둔 최신 화면을 씀.
# 시작할 때 ADB 캡처와 비교해서 판이 똑같이 읽힐 때만 사용, 끊기면 ADB 로 돌아감. hexa_cfg.json "fastcam": false 면 안 씀
FAST_SCID, FAST_PORT = "0e2f0a03", 27203      # 스킬 직접 굴리기(fastcam 기본 0e2f0a01/27199)와 겹치지 않게
_CAM = [None]          # None = 아직 안 켬, False = 못 씀, FastCam = 사용 중
_FV = [False]          # 게임 화면에서 판 비교까지 끝났는지


def _fast_img(c, fresh=0.12):
    """가장 최근 화면(RGB). fresh 초 안에 새 화면이 오면 그것"""
    _, _, n = c.latest()
    got = c.wait_new(n, fresh)
    img = got[0] if got else c.latest()[0]
    if img is None or c.err:
        return None
    if img.shape[1] != 720:
        img = cv2.resize(img, (720, 1280))
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _fast_check(c):
    """ADB 캡처와 빠른 화면이 같은 화면·같은 판으로 읽히는지 (ok, 설명, 판까지 비교했는지)"""
    why = "비교 못함"
    for k in range(4):
        a = _adb_capture()
        f = _fast_img(c, 0.3)
        if f is None:
            why = "빠른 화면 없음 %s" % (c.err,)
            time.sleep(0.3)
            continue
        sa, sf = V.state(a), V.state(f)
        if sa != sf:
            why = "화면 판정 다름 adb %s / fast %s" % (sa, sf)
            time.sleep(0.4)
            continue
        if sa != "game":
            return True, "화면 %s (판 비교는 게임 화면에서)" % sa, False
        ba, bf = V.read_board(a)[0], V.read_board(f)[0]
        idx = [i for i in range(E.N) if 0 <= ba[i] < 9 and 0 <= bf[i] < 9]
        diff = [i for i in idx if ba[i] != bf[i]]
        ta, tf = V.tray(a), V.tray(f)
        same_tray = (norm_piece(ta) if ta else None) == (norm_piece(tf) if tf else None)
        if not diff and same_tray and len(idx) >= E.N - 4:
            d = float(np.abs(a[300:1100].astype(np.int16) - f[300:1100].astype(np.int16)).mean())
            return True, "판 %d칸 일치, 조각 일치, 색 차이 %.1f" % (len(idx), d), True
        why = "판 다른 칸 %s / 조각 %s vs %s" % (diff, ta, tf)
        time.sleep(0.4)
    return False, why, False


def _fast_off(why):
    c = _CAM[0]
    _CAM[0] = False
    log("빠른 화면 끔 -> ADB 캡처 (%s)" % why)
    try:
        if c:
            c.stop()
    except Exception:
        pass


def _cam():
    if _CAM[0] is None:
        _CAM[0] = False
        if CFG.get("fastcam", True):
            try:
                import fastcam
                c = fastcam.FastCam(max_fps=30, scid=FAST_SCID, port=FAST_PORT).start()
                ok, why, full = _fast_check(c)
                if ok:
                    _CAM[0] = c
                    _FV[0] = full
                    import atexit
                    atexit.register(c.stop)
                    log("빠른 화면(fastcam) 사용: %s" % why)
                else:
                    c.stop()
                    log("빠른 화면 안 씀 (%s) -> ADB 캡처" % why)
            except Exception as ex:
                log("빠른 화면 시작 실패 -> ADB 캡처: %r" % (ex,))
    return _CAM[0] or None


def fast_on():
    return bool(_CAM[0])


def fast_verify_game():
    """처음 게임 화면에서 한 번: 판이 ADB 와 똑같이 읽히는지. 아니면 빠른 화면 끔"""
    if not fast_on() or _FV[0]:
        return
    ok, why, full = _fast_check(_CAM[0])
    if ok and full:
        _FV[0] = True
        log("빠른 화면 게임 판 확인: %s" % why)
    elif not ok:
        _fast_off(why)


def capture():
    c = _cam()
    if c is not None:
        if c.err:
            _fast_off("끊김 %s" % c.err)
        else:
            im = _fast_img(c)
            if im is not None:
                return im
    return _adb_capture()


def _adb_capture():
    for _ in range(3):
        png = adb("exec-out", "screencap", "-p").stdout
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            if img.shape[1] != 720:
                img = cv2.resize(img, (720, 1280))
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        time.sleep(0.5)
    raise RuntimeError("캡처 실패")


def tap(x, y):
    c = _CAM[0]
    if c:                     # patch245: 빠른 화면 연결로 바로 터치 (ADB input 은 한 번에 0.3~0.5초)
        try:
            c.tap(int(x), int(y))
            return
        except Exception as ex:
            _fast_off("터치 실패 %r" % (ex,))
    adb("shell", "input", "tap", str(int(x)), str(int(y)))


def swipe(x1, y1, x2, y2, ms=380):
    # patch298: 초반 검증된 안정적인 adb input swipe 방식으로 전면 롤백 (fastcam 소켓 터치 업 유실 방지)
    adb("shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms)))


def save_shot(im, name):
    p = os.path.join(SHOTS, name)
    cv2.imwrite(p, cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
    return p


def check_game_safety(im, context=""):
    """patch294: 모든 입력 경로 공통 안전 가드
    1. 화면 상태가 'game'인지 확인. 'None', 'lobby', 'over', 'popup' 등 비정상 상태면 즉시 차단.
    2. 보드 인식 신뢰도 검증: unk(미인식 칸)이 4칸 이하인지 확인.
    3. 이상 감지 시 스크린샷과 진단 정보를 저장하고 False 반환 (추가 조작 차단).
    """
    if im is None:
        log("[안전 차단] 캡처 화면이 없음 (None) - %s" % context)
        return False, "no_image", None, None
    st = V.state(im)
    if st != "game":
        p = save_shot(im, "hexa_safety_%s_%s.png" % (st or "unknown", datetime.datetime.now().strftime("%H%M%S")))
        log("[안전 차단] 화면 상태가 'game'이 아님 (%s) - %s (저장: %s)" % (st, context, p))
        return False, st, None, p
    b, unk = V.read_board(im)
    if len(unk) > 4:
        p = save_shot(im, "hexa_safety_unk_%d_%s.png" % (len(unk), datetime.datetime.now().strftime("%H%M%S")))
        log("[안전 차단] 보드 인식 신뢰도 부족 (미인식 %d칸 > 4칸: %s) - %s (저장: %s)" % (len(unk), unk, context, p))
        return False, "low_confidence", (b, unk), p
    return True, "game", (b, unk), None


# ---------------- 화면 읽기 묶음 ----------------
def board_for_plan(b):
    """모르는 칸(-1)은 절대 안 합쳐지는 벽으로"""
    return [(-100 - i) if t < 0 else t for i, t in enumerate(b)]


HI = {}      # patch226: 9·10등급 칸 기억 {칸: 등급}. 배경이 무지개색으로 계속 바뀌어 색으로는 못 읽음
HI_PATH = os.path.join(SHOTS, "hexa_hi.json")
_HI_LAST = [None]


def hi_save(board=None):
    """patch243: 9·10등급 기억 + 마지막 판을 파일로 (앱이 꺼진 뒤 '이어 하기' 때 되살림). 바뀌었을 때만 씀"""
    key = (tuple(sorted(HI.items())), tuple(board) if board else None)
    if key == _HI_LAST[0]:
        return
    _HI_LAST[0] = key
    try:
        tmp = HI_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"t": time.time(), "hi": {str(k): v for k, v in HI.items()}, "board": list(board or [])}, f)
        os.replace(tmp, HI_PATH)
    except Exception:
        pass


def hi_load(im):
    """patch243: 이어 하기 직후 - 저장된 판과 지금 판이 같으면 9·10등급 기억을 되살림"""
    try:
        d = json.load(open(HI_PATH, encoding="utf-8"))
    except Exception:
        return
    hi = {int(k): int(v) for k, v in d.get("hi", {}).items()}
    if not hi:
        return
    sb = d.get("board") or []
    b, _ = V.read_board(im)
    same = tot = 0
    if len(sb) == E.N:
        for i in range(E.N):
            if 0 <= sb[i] < 9 and 0 <= b[i] < 9:
                tot += 1
                same += sb[i] == b[i]
    if tot and same / tot >= 0.9:
        HI.clear()
        HI.update(hi)
        log("이어 하기: 9·10등급 기억 %d칸 되살림 %s (판 일치 %d/%d)" % (len(hi), hi, same, tot))
    else:
        log("이어 하기: 저장된 판과 달라 9·10등급 기억은 안 씀 (일치 %d/%d)" % (same, tot))


def read_all(im):
    b, unk = V.read_board(im)
    # 9·10등급: 색으로 읽은 값은 믿지 않고, 우리가 만든 자리(기억)만 인정
    for i in range(E.N):
        if b[i] >= 9 and i not in HI:
            # patch267: ★9 도끼 그림이 확실히 맞으면(hi_art) 우리가 안 만든 자리여도 ★9 로 인정하고 기억에 넣음
            #   (이어 하기·예상 빗나감 뒤 ★9 를 벽으로 두어 ★10 합성 기회를 놓치던 문제)
            if b[i] == 9 and V.hi_art(im, i) == 9:
                HI[i] = 9
            else:
                b[i] = -1
    for i, t in list(HI.items()):
        if b[i] == 0:
            del HI[i]          # 칸이 비었으면(합쳐져 사라짐) 기억 지움
        else:
            b[i] = t
    unk = [i for i in range(E.N) if b[i] < 0]
    hi_save(b)      # patch243
    return dict(board=b, unk=unk, tray=V.tray(im), prev=V.preview(im), unlocked=V.unlocked(im))


def grid_text(b):
    lines = []
    for y in range(10):
        row = []
        for c in range(5):
            if (y - (c & 1)) % 2 == 0:
                r = (y - (c & 1)) // 2
                i = E.CELLS.index((c, r)) if (c, r) in E.CELLS else None
                if i is None:
                    row.append("  ")
                    continue
                t = b[i]
                row.append(" ." if t == 0 else (" ?" if t < 0 else "%2d" % t))
            else:
                row.append("  ")
        lines.append("".join(row))
    return "\n".join(lines)


def norm_piece(p):
    q0 = min(q for (q, r), t in p)
    r0 = min(r for (q, r), t in p)
    return tuple(sorted(((q - q0, r - r0), t) for (q, r), t in p))


def rotated(p, k):
    offs = E.rot([o for o, t in p], k)
    return norm_piece(list(zip(offs, [t for o, t in p])))


def wait_settle(timeout=12.0, need_tray=True, hold=None):
    """판·조각이 두 번 연속 같게 읽힐 때까지.
    patch245: 빠른 화면이면 0.05초마다 읽고, 같은 판이 hold 초(기본 cfg stable_fast 0.6) 동안 그대로면 멈춘 것으로"""
    t0 = time.time()
    fast = fast_on()
    if hold is None:
        hold = CFG.get("stable_fast", 0.6) if fast else 0.0
    last = None
    since = 0.0
    im = None
    hist = []                    # patch257: (시각, 판, 조각키, r, im) - 판이 계속 흔들릴 때 다수결용
    while time.time() - t0 < timeout:
        im = capture()
        st = V.state(im)
        if st != "game":
            return st, im, None
        r = read_all(im)
        pk = (r["tray"] and norm_piece(r["tray"]), r["prev"] and norm_piece(r["prev"]))
        key = (tuple(r["board"]),) + pk
        now = time.time()
        hist.append((now, tuple(r["board"]), pk, r, im))
        if key != last:
            last, since = key, now
        elif (not need_tray or r["tray"]) and now - since >= hold:
            return "game", im, r
        # patch257: 전투 쪽 알림 배너('엘프의 비술 발동! Wave N 스킵' 등)가 판 가운데를 계속 덮어
        #   판이 한 번도 안정되지 않으면 영원히 기다리던 문제 -> 3초 넘게 흔들리면 최근 3초 칸별 다수결로 진행
        if now - t0 >= 3.0 and len(hist) >= 6:
            v = _vote(hist, now - 3.0, need_tray)
            if v is not None:
                return "game", v[1], v[0]
        time.sleep(0.05 if fast else 0.25)
    _diag(hist)
    return "timeout", im, None


_DIAG = [0]


def _diag(hist):
    """patch258: 시간초과 때 왜 안정이 안 됐는지 로그 (조각 흔들림/흔들린 칸 위치) + 처음 2번은 화면 저장"""
    try:
        from collections import Counter
        rec = hist[-80:]
        if not rec:
            return
        pc = Counter(h[2] for h in rec)
        pk, npk = pc.most_common(1)[0]
        sh = []
        for i in range(len(rec[0][1])):
            c = Counter(h[1][i] for h in rec)
            if c.most_common(1)[0][1] < len(rec):
                sh.append("%d@y%d:%s" % (i, E.pix(i)[1], dict(c.most_common(3))))
        log("안정 안 됨 진단: %d장, 조각 같음 %d/%d (조각 있음 %s), 흔들린 칸 %s" % (
            len(rec), npk, len(rec), bool(pk[0]), "; ".join(sh) or "없음"))
        if _DIAG[0] < 2:
            _DIAG[0] += 1
            for k, h in enumerate((rec[0], rec[len(rec) // 2], rec[-1])):
                if h[4] is not None:
                    save_shot(h[4], "hexa_shaky_%d_%d.png" % (_DIAG[0], k))
    except Exception as e:
        log("진단 오류 %r" % (e,))


_VOTE_LOG = [0.0]
EXPECT = []          # patch257: 우리가 둔 수로 예상한 판 후보들 (조각이 새로 나와도 판은 우리 수로만 바뀜). 새 판이면 빈 판


def _vote(hist, since, need_tray):
    """patch257: since 이후 읽은 판들에서 칸마다 가장 많이 나온 값, 조각도 가장 많이 나온 것. (r, im) 또는 None"""
    from collections import Counter
    rec = [h for h in hist if h[0] >= since]
    if len(rec) < 6:
        return None
    pk, n_pk = Counter(h[2] for h in rec).most_common(1)[0]
    if n_pk < len(rec) * 0.6 or (need_tray and not pk[0]):
        return None                          # 조각까지 흔들리면 진짜로 바뀌는 중 -> 기다림
    rec = [h for h in rec if h[2] == pk]
    board = [Counter(h[1][i] for h in rec).most_common(1)[0][0] for i in range(len(rec[0][1]))]
    shaky = [i for i in range(len(board)) if Counter(h[1][i] for h in rec).most_common(1)[0][1] < len(rec)]
    # 예상 판이 있으면: 흔들리지 않은 칸이 예상과 모두 맞는 후보로 흔들린 칸을 채움 (배너가 거의 늘 떠 있어도 정확)
    src = "다수결"
    for cand in EXPECT:
        if len(cand) == len(board) and all(board[i] < 0 or cand[i] < 0 or board[i] == cand[i]
                                             for i in range(len(board)) if i not in shaky):
            for i in shaky:
                if cand[i] >= 0:
                    board[i] = cand[i]
            src = "예상 판"
            break
    # 배너가 덮는 가운데 띠(y 540~710 칸)만 흔들릴 때만 다수결. 다른 칸이 흔들리면 합치기 연출 중일 수 있어 기다림
    if any(not (540 <= E.pix(i)[1] <= 710) for i in shaky):
        return None
    best = max(rec, key=lambda h: sum(1 for i in range(len(board)) if h[1][i] == board[i]))
    r = dict(best[3])
    r["board"] = list(board)
    r["unk"] = [i for i in range(len(board)) if board[i] < 0]
    if time.time() - _VOTE_LOG[0] > 30:
        _VOTE_LOG[0] = time.time()
        log("판이 계속 흔들림(알림 배너?) -> 최근 3초 %d장, 흔들린 칸 %s 은 %s 값으로 진행" % (len(rec), shaky, src))
    return r, best[4]


# ---------------- 한 수 ----------------
STATS = dict(moves=0, fails=0, best=0)
META = {}
NEXT = {}        # patch245: 놓은 뒤 확인한 판(멈춘 판)을 다음 수에 그대로 씀 -> 같은 확인을 두 번 안 함
LAST = {}        # patch267: 칸별 마지막으로 확인된 등급(1~8). 화면에서 못 읽은 칸을 채울 때 씀
TM = dict(n=0, plan=0.0, rot=0.0, drag=0.0, after=0.0, other=0.0, total=0.0, last=None)


def tm_add(**kw):
    """patch245: 한 수 단계별 시간 누적, 10수마다 평균을 로그로"""
    for k, v in kw.items():
        TM[k] = TM.get(k, 0.0) + v


def tm_move_done():
    now = time.time()
    if TM["last"] is not None:
        TM["total"] += now - TM["last"]
        TM["n"] += 1
    else:                         # 첫 수(또는 끊긴 뒤 첫 수)는 기준점만 - 단계 시간도 버림
        for k in ("plan", "rot", "drag", "after", "total"):
            TM[k] = 0.0
        TM["n"] = 0
    TM["last"] = now
    if TM["n"] >= 10:
        n = TM["n"]
        known = TM["plan"] + TM["rot"] + TM["drag"] + TM["after"]
        log("시간(최근 %d수 평균, 화면 %s): 한 수 %.2f초 = 계산 %.2f / 회전 %.2f / 드래그 %.2f / 놓은 뒤 확인 %.2f / 그 외 %.2f" % (
            n, "fast" if fast_on() else "adb", TM["total"] / n, TM["plan"] / n, TM["rot"] / n, TM["drag"] / n,
            TM["after"] / n, max(0.0, TM["total"] - known) / n))
        for k in ("plan", "rot", "drag", "after", "total"):
            TM[k] = 0.0
        TM["n"] = 0


def find_dot_aim_move(b, piece, dot_idx, has_star10=False):
    """확정 합성점(●) 지향 연쇄 조준 (patch287):
    조각의 모든 가능한 회전 및 배치 중, 점(●) 위치를 고려했을 때:
    1순위: 즉시 ★10 합성(8성 5개 합체 등)을 달성하는 수가 있다면 최우선 선택!
    2순위: (★10 미달성 시) 새로 생성되는 ★8이 기존 ★8들과 인접 허브를 이루는 수가 있다면 우선 선택!
    """
    if dot_idx is None or dot_idx >= len(piece):
        return None
    best_hub_move = None
    best_hub_conn = 0
    for k, cells, ts in E.moves(b, piece):
        dot_cell = cells[dot_idx]
        nb, made, _ = E.apply(b, cells, ts, dot_cell=dot_cell)
        if any(nt >= 10 for _t, _n, nt in made):
            return k, cells, ts, "star10"
        if not has_star10:
            for t, n, nt in made:
                if nt == 8:
                    g8 = [n for n in E.NB[dot_cell] if nb[n] == 8]
                    if len(g8) >= 2 and len(g8) > best_hub_conn:
                        best_hub_conn = len(g8)
                        best_hub_move = (k, cells, ts, "hub")
    if best_hub_move is not None and best_hub_conn >= 2:
        return best_hub_move
    return None


def plan(r, only_k0=False):
    b = board_for_plan(r["board"])
    has_star10 = any(x >= 10 for x in b) or any(t >= 10 for t in HI.values()) or STATS.get("star10", 0) >= 1

    # patch287: 확정 합성점(●) 지향 연쇄 조준 (★10 킬각 최우선 저격)
    dot_idx = getattr(r.get("tray"), "dot_idx", None)
    if dot_idx is not None:
        aim_mv = find_dot_aim_move(b, r["tray"], dot_idx, has_star10=has_star10)
        if aim_mv is not None and aim_mv[3] == "star10":
            k, cells, ts, _kind = aim_mv
            log("🎯 [연쇄 조준] 점(●) 위치 회전 최적화 ➜ ★10 확정 합성 각 발견! (회전 %d, 칸 %s)" % (k, cells))
            STATS["plans"] = STATS.get("plans", 0) + 1
            STATS["c_info"] = "[연쇄조준 ★10]"
            return k, cells, ts, 9999.0
    # patch231: 학습된 n-tuple 평가(hexa_nt_w.npz)가 있으면 그것으로 3수 탐색. hexa_cfg.json "brain": "old" 면 예전 방식
    if CFG.get("brain", "nt") == "nt" and NT is not None and NT.available():
        t0 = time.time()
        mv = "py"
        # patch232: C 수 읽기(hexa_search.exe) 우선. 실패하면 Python 탐색으로
        if CFG.get("search", "c") == "c" and hasattr(NT, "c_available") and NT.c_available():
            try:
                mv = NT.best_move_c(b, r["unlocked"], r["tray"], r["prev"], only_k0=only_k0,
                                    D=CFG.get("c_depth", 3) if r["prev"] else 1, B=CFG.get("c_B", 8),
                                    K=CFG.get("c_K", 8), budget_ms=CFG.get("think_sec", 10.0) * 800,
                                    threads=CFG.get("c_threads", 6), seed=STATS["moves"])
                if mv is not None:
                    STATS["c_info"] = mv[4]
                    mv = mv[:4]
            except Exception as ex:
                log("C 수 읽기 실패 -> Python: %s" % ex)
                NT.c_close()
                mv = "py"
        if mv != "py":
            pass
        elif r["prev"]:
            mv = NT.best_move3(b, r["unlocked"], r["tray"], r["prev"], only_k0=only_k0, seed=STATS["moves"],
                               budget=CFG.get("think_sec", 10.0) * 0.8)
        else:
            mv = NT.best_move(b, r["unlocked"], r["tray"], None, only_k0=only_k0)
        STATS["think"] = STATS.get("think", 0.0) + time.time() - t0
        STATS["plans"] = STATS.get("plans", 0) + 1
        return mv
    if CFG.get("depth", 3) >= 3:
        t0 = time.time()
        mv = E.best_move3(b, r["unlocked"], r["tray"], r["prev"], seed=STATS["moves"], only_k0=only_k0,
                          B1=CFG.get("B1", 24), B2=CFG.get("B2", 10), K=CFG.get("K", 24),
                          budget=CFG.get("think_sec", 10.0))
        STATS["think"] = STATS.get("think", 0.0) + time.time() - t0
        STATS["plans"] = STATS.get("plans", 0) + 1
        return mv
    return E.best_move(b, r["unlocked"], r["tray"], r["prev"])


def pick_hammer_target(b, piece, has_star10=False):
    """망치 대상 선택 (patch291: A: zero 전략 - 둘 곳 없을 때 비상 탈출 최적화):
      1순위: 긴급 탈출 (현재 조각을 즉시 둘 수 있게 해주는 1칸 장애물 중 최저 등급 칸)
      2순위: 보드 전체에서 가장 낮은 등급(★1~★3) 중 고립된 칸
    """
    # [1] 긴급 탈출 (둘 곳 없을 때 즉시 배치를 가능하게 만드는 1칸 장애물 칸)
    offs = [c for c, t in piece]
    cands = []
    for k in range(6):
        ro = E.rot(offs, k)
        for cells in E.placements(ro):
            blocked = [c for c in cells if b[c] > 0]
            if len(blocked) == 1:
                cands.append((b[blocked[0]], blocked[0]))
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[0][1]

    # [2] 최저티어 칸 (공간 확보용)
    lows = [(b[i], i) for i in range(E.N) if b[i] > 0]
    if lows:
        lows.sort(key=lambda x: x[0])
        return lows[0][1]
    return None


def use_hammer(target_cell):
    """망치를 터치하고 대상 칸을 터치하여 파괴 (patch283/patch294)"""
    chk_im = capture()
    ok, st, _, p = check_game_safety(chk_im, "망치 탭 직전 상태 검증")
    if not ok:
        log("[안전 차단] 망치 버튼 탭 전 화면 이상 (%s) -> 망치 사용 중단" % st)
        return False
    log("망치 버튼 탭: %s" % (V.HAMMER_BTN,))
    tap(*V.HAMMER_BTN)
    time.sleep(0.5)
    chk_im2 = capture()
    ok2, st2, _, p2 = check_game_safety(chk_im2, "망치 대상 칸 탭 직전 상태 검증")
    if not ok2:
        log("[안전 차단] 망치 대상 칸 탭 전 화면 이상 (%s) -> 대상 터치 중단" % st2)
        return False
    tx, ty = E.pix(target_cell)
    log("망치 대상 칸 %d 탭: (%d, %d)" % (target_cell, tx, ty))
    tap(tx, ty)
    time.sleep(0.8)
    return True


def do_move(im, r):
    if should_stop():
        log("[공방 중단] 작업 중단 요청 감지 -> 수 진행 중단")
        return False
    # patch294: 수 진행 직전 화면 안전 가드 (상태 확인 및 보드 신뢰도 검증)
    ok_safe, st_safe, info_safe, p_safe = check_game_safety(im, "수 시작 전 상태 검증")
    if not ok_safe:
        log("[안전 중단] 수 진행 전 화면 안전 검증 실패 (%s) -> 즉시 중단" % st_safe)
        return False

    b0 = r["board"]
    cur = r["tray"]
    has_star10 = any(x >= 10 for x in b0) or any(t >= 10 for t in HI.values()) or STATS.get("star10", 0) >= 1
    free_cells = sum(1 for x in b0 if x == 0)

    META.clear()
    META.update(spawn=[[list(o), t] for o, t in cur], taps=0)
    spawn_log(r)                 # patch246
    _t = time.time()
    if STATS["moves"] < 2 or (has_star10 and STATS.get("last_mode") != "score"):
        mode_str = "최고 점수 득점 모드(생존/연쇄 극대화)" if has_star10 else "★10 달성 최우선 모드(허브 집중)"
        STATS["last_mode"] = "score" if has_star10 else "star10"
        log("수 %d [%s] 시작 (조각 %s, 빈칸 %d)" % (STATS["moves"] + 1, mode_str, norm_piece(cur), free_cells))

    mv = plan(r)
    if time.time() - _t > 3 or STATS["moves"] < 2:
        log("수 %d 계산 %.1f초 -> %s" % (STATS["moves"] + 1, time.time() - _t, "둘 곳 없음" if mv is None else "칸 %s" % (mv[1],)))
    tm_add(plan=time.time() - _t)
    _t_rot = time.time()
    if mv is None:
        # patch284: 둘 곳이 없을 때 망치가 남아있다면 긴급 파괴 발동!
        if V.hammer_available(im):
            mode_desc = "최고점수 생명연장" if has_star10 else "★10 재도전 긴급탈출"
            log("둘 곳 없음 ➜ 망치 발동 (%s)" % mode_desc)
            target = pick_hammer_target(b0, cur, has_star10=has_star10)
            if target is not None:
                use_hammer(target)
                st, im2, r2 = wait_settle(6, hold=0.3)
                if st == "game" and r2:
                    log("망치 파괴 후 판 재인식 성공 (칸 %d 빈칸화) -> 수 재계산" % target)
                    return do_move(im2, r2)
        log("둘 곳 없음 (게임 끝 대기)")
        time.sleep(2)
        return False
    k, cells, ts, sc = mv
    # 회전
    if k:
        chk_im = capture()
        ok_rot, st_rot, _, _ = check_game_safety(chk_im, "회전 전 상태 검증")
        if not ok_rot:
            log("[안전 중단] 회전 전 화면 상태 이상 (%s) -> 수 중단" % st_rot)
            return False
        n = k if CFG["rot_dir"] == 1 else (6 - k) % 6
        META["taps"] = n
        for _ in range(n):
            tap(*V.ROT_BTN)
            time.sleep(0.35)
        st, im2, r2 = wait_settle(6, hold=0.25)
        if st != "game" or not r2:
            log("[안전 중단] 회전 후 판 안정화 실패 (상태: %s) -> 수 중단" % st)
            return False
        obs = norm_piece(r2["tray"])
        if obs == rotated(cur, k):
            pass
        elif obs == rotated(cur, -k):
            CFG["rot_dir"] *= -1
            save_cfg()
            log("회전 방향 반대로 학습 -> rot_dir", CFG["rot_dir"])
        else:
            hit = [j for j in range(6) if obs == rotated(cur, j)]
            log("회전 %d번 눌렀는데 결과 %s (원래 %s, 실제 %s칸 돈 것)" % (n, obs, norm_piece(cur), hit))
        # patch221: 회전한 뒤에는 다시 계획부터 하지 않음. 계획한 칸·등급 그대로 되면 그것, 아니면 지금 방향에서 최선
        # patch224: 지금 방향에 둘 곳이 없으면 한 칸씩 더 돌려 가며 둘 곳 있는 방향을 찾음(최대 5번) - 무한 반복 방지
        r = r2
        want = sorted(zip(cells, ts))
        for extra in range(6):
            bnow = board_for_plan(r["board"])
            mk0 = E.moves(bnow, r["tray"], only_k0=True)
            same = None
            for k2, c2, t2 in mk0:
                if sorted(zip(c2, t2)) == want:
                    same = (c2, t2)
                    break
            if same:
                cells, ts = same
                break
            mv = plan(r, only_k0=True) if mk0 else None
            if mv is not None:
                k, cells, ts, sc = mv
                log("회전 결과가 예상과 달라 지금 방향에서 다시 고름 (조각 %s)" % (norm_piece(r["tray"]),))
                break
            if extra == 0:
                save_shot(im2, "hexa_rot_%03d.png" % (STATS["moves"] + 1))
            log("지금 방향 둘 곳 없음 -> 한 번 더 회전 (%d) 조각 %s" % (extra + 1, norm_piece(r["tray"])))
            if extra == 5:
                log("[안전 중단] 6회 회전 후에도 둘 곳 없음 -> 수 중단")
                return False
            chk_im_ext = capture()
            ok_ext, st_ext, _, _ = check_game_safety(chk_im_ext, "추가 회전 전 상태 검증")
            if not ok_ext:
                log("[안전 중단] 추가 회전 전 화면 상태 이상 (%s) -> 수 중단" % st_ext)
                return False
            tap(*V.ROT_BTN)
            time.sleep(0.45)
            st, im2, r2 = wait_settle(6, hold=0.25)
            if st != "game" or not r2:
                log("[안전 중단] 추가 회전 후 판 안정화 실패 (상태: %s) -> 수 중단" % st)
                return False
            r = r2
    tm_add(rot=time.time() - _t_rot if k else 0.0)
    # 예상 결과(합쳐질 칸 후보 전부 - patch283: 점 찍힌 칸 우선 확정)
    bp = board_for_plan(r["board"])
    preds = []
    ch, nbr = 0, 1
    dot_idx = getattr(r["tray"], "dot_idx", None)
    dot_cell = cells[dot_idx] if dot_idx is not None and dot_idx < len(cells) else None
    while ch < nbr:
        nb, made, nbr = E.apply(bp, cells, ts, ch, dot_cell=dot_cell)
        preds.append((nb, made))
        ch += 1
    EXPECT[:] = [list(nb) for nb, made in preds]      # patch257

    # patch294: 드래그 직전 공통 안전 검증
    chk_drag = capture()
    ok_drag, st_drag, _, p_drag = check_game_safety(chk_drag, "드래그 직전 상태 검증")
    if not ok_drag:
        log("[안전 중단] 드래그 직전 화면 안전 검증 실패 (%s) -> 입력 차단 및 수 중단" % st_drag)
        return False

    # 드래그 좌표 계산
    xs = [E.pix(c)[0] for c in cells]
    ys = [E.pix(c)[1] for c in cells]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    ex, ey = cx + CFG["lift"][0], cy + CFG["lift"][1]
    META.update(finger=[round(ex), round(ey)], placed=[[c, t] for c, t in zip(cells, ts)],
                tray_now=[[list(o), t] for o, t in r["tray"]])

    # patch294: 정형화된 상세 수 계획 로그 (세션 ID, 타임스탬프, 이동 번호, 계획 좌표, 설정 시간/인자)
    next_move_num = STATS["moves"] + 1
    session_id = SPAWN.get("gid", "unknown")
    swipe_ms_val = CFG.get("swipe_ms", 380)
    log("[세션 %s | 수 %d 준비] %s | 상태: %s | 미인식: %d칸 | 조각: %s | 목표 칸: %s | 드래그: (%d,%d) -> (%d,%d) %dms" % (
        session_id, next_move_num, datetime.datetime.now().strftime("%H:%M:%S"),
        st_drag, len(r.get("unk", [])), norm_piece(r["tray"]), cells,
        V.TRAY_C[0], V.TRAY_C[1], round(ex), round(ey), swipe_ms_val
    ))

    _t = time.time()
    swipe(V.TRAY_C[0], V.TRAY_C[1], ex, ey, swipe_ms_val)
    tm_add(drag=time.time() - _t)
    _t = time.time()
    time.sleep(CFG.get("settle_fast", 0.3) if fast_on() else CFG["settle"])     # patch245: 빠른 화면이면 0.9 -> 0.3
    st, im3, r3 = wait_settle(15)
    tm_add(after=time.time() - _t)

    # 드래그 후 상태 검증 (원칙 1, 3, 4, 6)
    if st != "game" or not r3:
        p = save_shot(im3, "hexa_after_%03d.png" % next_move_num) if im3 is not None else ""
        log("[안전 중단] 수 %d 드래그 후 화면이 게임이 아님 (상태: %s, 저장: %s) -> 추가 입력 없이 안전 중단" % (
            next_move_num, st, p))
        return False

    b1 = r3["board"]
    # 판 변화 검증 (원칙 5: 판이 변하지 않았으면 중복 입력 방지를 위해 즉시 중단)
    if b0 == b1:
        p = save_shot(im3, "hexa_drag_fail_%03d.png" % next_move_num)
        log("[안전 중단] 수 %d 드래그 후 판이 변하지 않음 (드래그 실패/미적용, 저장: %s) -> 중복 입력 방지를 위해 즉시 중단" % (
            next_move_num, p))
        return False

    hit = check_result(r, r3, cells, ts, preds, cx, cy, im3)
    # 요구사항 4: 예상 결과와 실제 결과가 맞지 않으면 이동 성공으로 기록하지 않고 즉시 안전 중단
    if hit is None:
        p = save_shot(im3, "hexa_mismatch_%03d.png" % next_move_num)
        log("[안전 중단] 수 %d 드래그 결과가 예상과 불일치 (빗나감/오배치, 저장: %s) -> 안전 중단" % (
            next_move_num, p))
        return False

    # 판이 정상적으로 변경되고 예상 결과와 일치함이 검증된 경우에만 성공한 수로 기록 (원칙 6)
    STATS["moves"] += 1

    for nb, made in preds:
        for t, n, nt in made:
            STATS["best"] = max(STATS["best"], nt)

    # patch294: 합침 유무와 무관하게 모든 수에 대해 정형화된 성공 결과 로그 출력
    new_tray = norm_piece(r3.get("tray")) if r3.get("tray") else "없음"
    if preds[hit][1]:
        log("[수 %d 성공] 칸 %s 배치 완료 -> 합침 %s (새 조각: %s, 미인식: %d칸)" % (
            STATS["moves"], list(zip(cells, ts)), preds[hit][1], new_tray, len(r3.get("unk", []))
        ))
    else:
        log("[수 %d 성공 (합침 없음)] 칸 %s 배치 완료 (새 조각: %s, 미인식: %d칸)" % (
            STATS["moves"], list(zip(cells, ts)), new_tray, len(r3.get("unk", []))
        ))

    # patch245: 방금 확인한 멈춘 판을 다음 수에 그대로 (9·10등급 기억은 check_result 가 갱신한 것으로 다시 입힘)
    b = list(r3["board"])
    for i, t in HI.items():
        if b[i] != 0:
            b[i] = t
    # patch266: 화면에서 못 읽은 칸(-1)은 맞아떨어진 예상 판 값으로 채움 (읽은 칸이 전부 예상과 같을 때만).
    pb = preds[hit][0] if hit is not None else None
    filled = []
    for i in range(E.N):
        if b[i] >= 0:
            continue
        if pb is not None and 0 < pb[i] < 9:
            b[i] = pb[i]
            filled.append(i)
        elif (pb is None or pb[i] < 0) and i in LAST:
            b[i] = LAST[i]
            filled.append(i)
    if filled:
        STATS["filled"] = STATS.get("filled", 0) + len(filled)
    for i in range(E.N):         # patch267: 칸별 마지막 확인 등급 갱신 (빈칸이면 지움)
        if 0 < b[i] < 9:
            LAST[i] = b[i]
        elif b[i] == 0:
            LAST.pop(i, None)
    nr = dict(r3)
    nr["board"] = b
    nr["unk"] = [i for i in range(E.N) if b[i] < 0]
    NEXT.clear()
    NEXT.update(im=im3, r=nr)
    tm_move_done()
    return True


def check_result(r, r3, cells, ts, preds, cx, cy, im3):
    b0, b1 = r["board"], r3["board"]
    # 모르는 색 학습 (9·10등급 등)
    if r3["unk"]:
        for nb, made in preds:
            for i in r3["unk"]:
                t = nb[i]
                if 0 < t < 9 and str(t) not in CFG["colors"] and t not in V.REF:
                    col = [round(float(v)) for v in V.cell_color(im3, i)]
                    CFG["colors"][str(t)] = col
                    V.REF[t] = tuple(col)
                    save_cfg()
                    log("새 등급 색 학습: %d -> %s" % (t, col))
    hit = None
    for ch, (nb, made) in enumerate(preds):
        if all(nb[i] == b1[i] or b1[i] < 0 or nb[i] < 0 for i in range(E.N)):
            hit = ch
            break
    if hit is None:
        # 예측이 다 틀려도 9·10 기억은 예측(첫 후보)에서 가져오되, 실제로 빈 칸이면 버림
        for i, t in enumerate(preds[0][0]):
            if t >= 9 and b1[i] != 0:
                HI[i] = t
    if hit is not None:
        for i, t in enumerate(preds[hit][0]):
            if t >= 9:
                HI[i] = t
        if len(preds) > 1:
            # 결과 칸 규칙 찾기용: 실제로 합쳐진 칸 위치 + 처음 나온 조각 모양 + 회전 횟수 + 손가락 위치
            learn(dict(kind="target", meta=dict(META), result_cells=[i for i in range(E.N) if b1[i] > 0 and b0[i] != b1[i]],
                       board=b0, cells=list(cells), ts=list(ts), choice=hit,
                       n=len(preds), made=preds[hit][1]))
        if preds[hit][1]:
            # patch271: 실제 판과 맞은 예상에서 ★10 이 만들어졌으면 텔레그램 무음 알림 (made = (원래 등급, 칸 수, 결과 등급))
            if any(nt >= 10 for _t, _n, nt in preds[hit][1]):
                log("★10 합성! (수 %d) ➜ 다음 수부터 최고 점수 득점 모드로 전환!" % STATS["moves"])
                STATS["star10"] = STATS.get("star10", 0) + 1
                try:
                    from telegram_bot import send_telegram
                    send_telegram("🎉 <b>[유물 공방] ★10 달성!</b>\n• 수: %d\n• 시각: %s" % (
                        STATS["moves"], time.strftime("%m-%d %H:%M:%S")))
                except Exception as e:
                    log("텔레그램 ★10 알림 오류: %r" % (e,))
        return hit                 # patch266: 맞은 예상 번호 (못 읽은 칸 채우기용)
    STATS["fails"] += 1
    new = [i for i in range(E.N) if b0[i] == 0 and b1[i] > 0]
    learn(dict(kind="mismatch", board=b0, after=b1, cells=list(cells), ts=list(ts),
               preds=[p[0] for p in preds]))
    save_shot(im3, "hexa_err_%03d.png" % STATS["moves"])
    log("수 %d: 예상과 다름 (놓을 칸 %s, 새로 찬 칸 %s)" % (STATS["moves"], list(cells), new))
    # 합침이 없을 예정이었고 모양 그대로 다른 자리에 놓였으면 -> 드래그 높이 보정
    if not preds[0][1] and len(new) == len(cells):
        tn = sorted(b1[i] for i in new)
        if tn == sorted(ts):
            ax = [E.pix(i)[0] for i in new]
            ay = [E.pix(i)[1] for i in new]
            dx, dy = sum(ax) / len(ax) - cx, sum(ay) / len(ay) - cy
            if abs(dx) < 260 and abs(dy) < 260:
                CFG["lift"][0] -= 0.8 * dx
                CFG["lift"][1] -= 0.8 * dy
                save_cfg()
                log("드래그 보정: 빗나감 (%.0f,%.0f) -> lift %s" % (dx, dy, [round(v) for v in CFG["lift"]]))
    if b0 == b1:
        # patch293c: 10/26 새 UI 정밀 lift(160) 주변에서만 미세 보정, swipe_ms 폭주 방지
        cands = [160, 155, 165, 150, 170]
        CFG["drop_fail"] = CFG.get("drop_fail", 0) + 1
        i = CFG["drop_fail"] % len(cands)
        CFG["lift"] = [0.0, float(cands[i])]
        save_cfg()
        log("판이 그대로 -> 드래그 실패 %d번째, lift %s, swipe %dms" % (CFG["drop_fail"], CFG["lift"], CFG["swipe_ms"]))
    else:
        CFG["drop_fail"] = 0


# ---------------- 게임 흐름 ----------------
BTN_START = (360, 1168)            # patch292: 10/26 UI 변경으로 1093 -> 1168 이동
BTN_RESULT = (360, 1168)           # patch292: 1095 -> 1168
BTN_AGAIN = (470, 882)
BTN_EXIT = (211, 882)
BTN_CLAIM = (597, 647)
BTN_CLOSE = (638, 120)        # 공방 이벤트 창 오른쪽 위 빨간 X


def lobby_button(im):
    """patch243: 로비 아래 버튼 종류. 'start' = '시작 🎫1'(노란 티켓 그림 약 480점) / 'cont' = '이어 하기'(0점) / None"""
    try:
        # patch292: 10/26 새 UI 버튼 위치(1145:1190) 및 구 UI(1070:1116) 모두 확인
        roi = im[1145:1190, 250:470]
        hsv = cv2.cvtColor(np.ascontiguousarray(roi), cv2.COLOR_RGB2HSV)
        n = int(((hsv[..., 1] > 130) & (hsv[..., 2] > 170)).sum())
        if n < 100:
            roi_old = im[1070:1116, 250:470]
            hsv_old = cv2.cvtColor(np.ascontiguousarray(roi_old), cv2.COLOR_RGB2HSV)
            n_old = int(((hsv_old[..., 1] > 130) & (hsv_old[..., 2] > 170)).sum())
            if n_old >= 150:
                n = n_old
    except Exception:
        return None
    return "start" if n >= 150 else ("cont" if n <= 40 else None)


def is_reward_claimable(im):
    """로비 화면에서 주간/일일 등급 달성 보상 받기 버튼(BTN_CLAIM = 597, 647)이 활성 상태인지 확인"""
    if im is None:
        return False
    try:
        roi = im[635:660, 560:635]
        hsv = cv2.cvtColor(np.ascontiguousarray(roi), cv2.COLOR_RGB2HSV)
        # 활성 보상 버튼 (밝은 주황/노랑/갈색): 채도 > 100, 명도 > 140
        act_cnt = int(((hsv[..., 1] > 100) & (hsv[..., 2] > 140)).sum())
        return act_cnt >= 80
    except Exception:
        return False


def is_reward_popup(im):
    """보상 수령 후 나타나는 확인 팝업창인지 판별 (중앙 확인 버튼 등)"""
    if im is None:
        return False
    if V.state(im) in ("game", "lobby", "over", "popup"):
        return False
    try:
        # 중앙 확인 버튼 영역(x=300..420, y=730..770) 확인
        roi = im[730:770, 300:420]
        mean_v = float(roi.mean())
        return 40.0 <= mean_v <= 240.0
    except Exception:
        return False


def claim_and_close():
    """patch227/patch294/patch294d: 공방 정상 완료 후 단계별 처리:
    1. 보상 확인 및 수령 (활성 보상 버튼 존재 시에만 탭)
    2. 로비 창 닫기 (우상단 X 탭 후 로비 닫힘 확인)
    3. 전투 화면 복귀 (icon_score >= 0.7 및 메뉴 닫힘 확인)
    반환: bool (전투 화면 복귀 성공 여부)"""
    im0 = _adb_capture() if fast_on() else capture()
    # 0. 이미 전투 화면이면 어떠한 닫기 터치도 하지 않고 즉시 완료
    sc0, _ = icon_score(im0)
    if sc0 >= 0.7 and menu_forge(im0)[0] < 0.8:
        log("끝. 이미 전투 화면임 -> 추가 조작 없이 즉시 완료")
        return True

    # 1. 보상 수령 (로비 화면이고 수령 가능한 보상이 있는 경우에만 탭)
    st0 = V.state(im0)
    if st0 == "lobby":
        if is_reward_claimable(im0):
            log("로비 보상 수령 버튼 활성 감지 -> 보상 받기 탭 %s" % (BTN_CLAIM,))
            tap(*BTN_CLAIM)
            time.sleep(1.2)
            im_pop = capture()
            if is_reward_popup(im_pop):
                log("보상 획득 팝업 감지 -> 중앙 확인 탭 (360, 750)")
                tap(360, 750)
                time.sleep(1.0)
        else:
            log("로비 보상: 수령 가능한 활성 보상 없음(비활성) -> 보상 받기 건너뜀")

    # 2. 로비 창 닫기 (최대 4회 시도)
    for attempt in range(4):
        im = capture()
        st = V.state(im)
        sc, _ = icon_score(im)
        if sc >= 0.7 and menu_forge(im)[0] < 0.8:
            log("끝. 공방 창 닫힘 -> 전투 화면 복귀 확인 (시도 %d)" % (attempt + 1))
            return True

        if st == "lobby":
            log("로비 우상단 X 탭 %s (시도 %d)" % (BTN_CLOSE, attempt + 1))
            tap(*BTN_CLOSE)
            time.sleep(1.2)
        elif is_reward_popup(im):
            log("남아있는 보상 팝업 닫기 탭 (360, 750)")
            tap(360, 750)
            time.sleep(1.0)
        else:
            time.sleep(0.5)

    # 3. 최종 백업: close_event() 호출로 이벤트 메뉴 닫기 및 최종 전투 화면 검증
    ok_battle = close_event()
    if ok_battle:
        log("전투 화면 복귀 최종 확인 완료")
    else:
        p = save_shot(capture(), "hexa_close_fail_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
        log("[경고] 전투 화면 복귀 실패 (증거 저장: %s)" % p)
    return ok_battle


def play(n_games):
    load_cfg()
    find_serial()
    ok_open, auto_opened = ensure_forge_open()      # patch292: 전투 화면이면 자동으로 공방 로비 진입
    if not ok_open:
        log("공방 화면 준비 실패 -> 플레이 중단")
        return False
    brain = "nt" if (CFG.get("brain", "nt") == "nt" and NT is not None and NT.available()) else "old"
    if brain == "nt" and CFG.get("search", "c") == "c" and hasattr(NT, "c_available") and NT.c_available():
        brain = "nt+C(D%d B%d K%d, %d스레드)" % (CFG.get("c_depth", 3), CFG.get("c_B", 8), CFG.get("c_K", 8), CFG.get("c_threads", 6))
    log("=== 유물 공방 시작: %d판, 기기 %s, lift %s, rot %d, 두뇌 %s" % (n_games, SERIAL, CFG["lift"], CFG["rot_dir"], brain))
    started = 0
    finished = 0
    unknown_since = None
    in_game = False
    game_finished = False        # patch294d: 실제 게임오버(popup/over)가 확인된 정상 완료 플래그
    need_hi = False              # patch243
    stall = None                 # patch257
    NEXT.clear()
    TM.update(n=0, last=None)
    _cam()                       # patch245: 빠른 화면 준비 (안 되면 ADB)
    while True:
        if should_stop():
            log("[공방 중단] 작업 중단 요청 감지 -> 공방 플레이를 중단하고 종료합니다")
            claim_and_close()
            break
        if NEXT:                 # patch245: 놓은 뒤 확인한 판이 있으면 다시 찍지 않음
            im, r_next = NEXT["im"], NEXT["r"]
            NEXT.clear()
            # patch294: NEXT 판이 있어도 현재 화면 상태 및 보드 신뢰도 검증
            ok_next, st, info_next, p_next = check_game_safety(im, "NEXT 화면 상태 검증")
            if not ok_next:
                log("[안전 중단] NEXT 화면 안전 검증 실패 (%s, 저장: %s) -> 플레이 중단" % (st, p_next))
                break
        else:
            r_next = None
            im = capture()
            st = V.state(im)
        if st is None:
            # patch294 (원칙 1): 상태가 None이면 추가 입력을 하지 않고 즉시 증거 저장 후 중단
            p = save_shot(im, "hexa_unknown_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
            log("[안전 중단] 화면 상태 판별 불가(None) 감지 -> 추가 입력 차단 및 즉시 중단 (저장: %s)" % p)
            break
        if st == "lobby":
            # 1. 정상적으로 게임오버를 거쳐 로비로 돌아온 경우
            if game_finished:
                finished += 1
                in_game = False
                game_finished = False
                log("공방 판 정상 완료 (완료: %d/%d)" % (finished, n_games))
                if finished >= n_games:
                    log("목표 판수(%d판) 달성 -> 보상 수령 및 창 닫기 진행" % n_games)
                    claim_and_close()
                    break
                else:
                    log("다음 판 시작 대기 (진행도: %d/%d)" % (finished, n_games))
                    time.sleep(1.0)
                    continue

            # 2. 최초 시작(started == 0)일 때만 정상 시작 허용
            elif started == 0 and not in_game:
                btn = lobby_button(im)
                tap(*BTN_START)
                started += 1
                STATS.update(moves=0, fails=0, best=0, filled=0, star10=0, last_mode=None)
                HI.clear()
                NEXT.clear()
                TM["last"] = None
                spawn_new_game("cont" if btn == "cont" else "start")   # patch246
                if btn == "cont":
                    need_hi = True
                    log("판 시작 - 이어 하기 (지난 판 이어서, 티켓 안 씀) (%d/%d)" % (started, n_games))
                else:
                    hi_save([])
                    log("판 시작 (%d/%d)" % (started, n_games))
                time.sleep(2.5)
                continue

            # 3. 게임 진행 도중(in_game) 예기치 않게 로비로 이탈한 경우 (요구사항 A-2)
            else:
                p = save_shot(im, "hexa_unexpected_lobby_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
                log("[안전 중단] 게임 진행 도중 예기치 않은 로비(lobby) 이탈 감지 (in_game=%s, started=%d, finished=%d) -> 추가 입력 없이 즉시 안전 중단 (저장: %s)" % (
                    in_game, started, finished, p))
                break

        if st == "popup":
            # patch294d: '공방 마감' 오버레이 감지 시 정상 게임오버 처리 -> 나가기 버튼을 눌러 로비로 복귀
            y_btn = V.popup_y(im)
            if y_btn is not None:
                p = save_shot(im, "hexa_gameover_popup_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
                log("[게임오버] 공방 마감 팝업 감지: %d수, 최고 등급 %d -> 나가기 버튼(211, %d) 탭 (저장: %s)" % (
                    STATS["moves"], STATS["best"], y_btn, p))
                tap(211, y_btn)
                time.sleep(1.5)
                game_finished = True
                continue
            else:
                p = save_shot(im, "hexa_popup_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
                log("[안전 중단] 팝업 창(popup) 버튼 판별 불가 -> 임의 조작 없이 안전 중단 (저장: %s)" % p)
                break

        if st == "over":
            # patch294d: 결과 화면(over) 감지 시 정상 게임오버 처리 -> 확인 버튼 탭 후 로비 복귀
            p = save_shot(im, "hexa_gameover_over_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S"))
            log("[게임오버] 결과 화면(over) 감지: %d수, 최고 등급 %d -> 확인 탭 후 로비로 복귀합니다 (저장: %s)" % (
                STATS["moves"], STATS["best"], p))
            tap(360, 882)
            time.sleep(1.5)
            game_finished = True
            continue
        # game
        if started == 0:
            started = 1          # 게임 화면에서 바로 시작한 경우
            spawn_new_game("ingame")   # patch246
            need_hi = True       # patch243: 하던 판일 수 있음
        in_game = True
        fast_verify_game()       # patch245: 처음 게임 화면에서 ADB 와 판 비교 (다르면 빠른 화면 끔)
        if need_hi:
            need_hi = False
            hi_load(im)
        if r_next is not None:
            im2, r = im, r_next
        else:
            st2, im2, r = wait_settle(12)
            if st2 != "game" or not r:
                TM["last"] = None
                p = save_shot(im2, "hexa_stall_%s.png" % datetime.datetime.now().strftime("%m%d_%H%M%S")) if im2 is not None else ""
                log("[안전 중단] 게임 화면 안정화 실패 (상태: %s) -> 추가 입력 없이 안전 중단 (저장: %s)" % (st2, p))
                break
        stall = None
        ok_move = do_move(im2, r)
        if not ok_move:
            log("[안전 중단] do_move 실행 실패(드래그 미적용 또는 안전 가드 차단) -> 공방 플레이 루프 종료")
            break
    if _CAM[0]:
        _fast_off("공방 정상 종료")
    return finished              # patch243: 끝낸 판 수 (0 = 중간에 끊김)


def look(path=None):
    load_cfg()
    if path:
        im = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
    else:
        find_serial()
        im = capture()
    st = V.state(im)
    print("화면 상태:", st)
    r = read_all(im)
    print("해금 등급:", r["unlocked"], " 모르는 칸:", r["unk"])
    print(grid_text(r["board"]))
    print("지금 조각:", r["tray"])
    print("다음 조각:", r["prev"])
    if r["tray"]:
        t0 = time.time()
        mv = plan(r)
        print("계산 %.2f초" % (time.time() - t0))
        if mv:
            k, cells, ts, sc = mv
            print("추천: 회전 %d번, 칸 %s (%s), 평가 %.1f" % (k, [E.CELLS[c] for c in cells], ts, sc))
            out = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
            for c, t in zip(cells, ts):
                x, y = E.pix(c)
                cv2.rectangle(out, (x - 44, y - 44), (x + 44, y + 44), (0, 255, 255), 4)
                cv2.putText(out, str(t), (x - 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
            p = os.path.join(SHOTS, "hexa_look.png")
            cv2.imwrite(p, out)
            print("표시 저장:", p)
        else:
            print("둘 곳 없음")


def sim(n):
    import statistics
    res = [E.play3(s) for s in range(n)]
    best = [x["best"] for x in res]
    print("가상 %d판: 최고등급 평균 %.2f, 9등급 %d%%, 10등급 %d%%, 평균 %d수" % (
        n, statistics.mean(best), 100 * sum(b >= 9 for b in best) / n, 100 * sum(b >= 10 for b in best) / n,
        statistics.mean(x["moves"] for x in res)))



# ---------------- patch238: 메인이 부르는 자동 실행 (전투 화면 -> 티켓 5/5 면 2판) ----------------
EVENT_ICON = (596, 371)          # 전투 화면 오른쪽 아이콘 줄의 유물 공방 아이콘
TAB_FORGE = (150, 212)           # 공방 이벤트 창 '공방' 탭
_ICON_T = None


def icon_score(im):
    """전투 화면에 공방 아이콘이 보이는지 (점수, 중심)"""
    global _ICON_T
    if _ICON_T is None:
        t = cv2.imread(os.path.join(BASE, "tpl", "hexa_event_icon.png"))
        _ICON_T = cv2.cvtColor(t, cv2.COLOR_BGR2RGB) if t is not None else None
    if _ICON_T is None:
        return 0.0, EVENT_ICON
    x0, y0 = EVENT_ICON[0] - 80, EVENT_ICON[1] - 80
    roi = im[y0:y0 + 160, x0:x0 + 160]
    r = cv2.matchTemplate(roi, _ICON_T, cv2.TM_CCOEFF_NORMED)
    _, mv, _, ml = cv2.minMaxLoc(r)
    h, w = _ICON_T.shape[:2]
    return float(mv), (x0 + ml[0] + w // 2, y0 + ml[1] + h // 2)


TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def read_tickets(im):
    """patch264: 로비 왼쪽 티켓 'N/5' 의 N (Tesseract 우선 + ocrx 폴백, 못 읽으면 None)"""
    crop = im[392:448, 135:280]
    bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR) if im.shape[2] == 3 else crop

    # 1) Tesseract 고속 정밀 인식 (0123456789/ 화이트리스트)
    if os.path.exists(TESS):
        try:
            import tempfile
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            _, bin1 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            tmp = os.path.join(tempfile.gettempdir(), "ef2_hexa_ticket.png")
            cv2.imwrite(tmp, bin1)
            r = subprocess.run([TESS, tmp, "-", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789/"],
                               capture_output=True, text=True, timeout=5,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            txt = r.stdout.strip().replace(" ", "")
            m = re.search(r"([0-5])/5", txt)
            if m:
                log("티켓 글자 '%s' (Tesseract)" % txt)
                return int(m.group(1))
        except Exception as e:
            log("Tesseract 티켓 오류: %r" % (e,))

    # 2) 윈도우 내장 OCR 폴백
    try:
        import ocrx
        big = cv2.resize(bgr, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        big = cv2.copyMakeBorder(big, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
        ws = ocrx.words(big)
        if ws:
            txt = "".join(w[0] for w in ws).replace(" ", "").upper()
            m = re.search(r"([0-5])/5", txt)
            if m:
                log("티켓 글자 '%s' (ocrx)" % txt)
                return int(m.group(1))
            m2 = re.search(r"([0-5])/[S$]", txt)
            if m2:
                log("티켓 글자 '%s' (ocrx 대체 매칭)" % txt)
                return int(m2.group(1))
    except Exception:
        pass

    return None


_MENU_T = None
MENU_X_OFF = (174, -89)          # 이벤트 메뉴 X = '유물 공방' 버튼 중심 + (174,-89)  (버튼 (360,507), X (534,418))


def menu_forge(im):
    """이벤트 메뉴의 '유물 공방' 버튼 (점수, 중심)"""
    global _MENU_T
    if _MENU_T is None:
        t = cv2.imread(os.path.join(BASE, "tpl", "hexa_menu_forge.png"))
        _MENU_T = cv2.cvtColor(t, cv2.COLOR_BGR2RGB) if t is not None else None
    if _MENU_T is None:
        return 0.0, (360, 507)
    r = cv2.matchTemplate(im, _MENU_T, cv2.TM_CCOEFF_NORMED)
    _, mv, _, ml = cv2.minMaxLoc(r)
    h, w = _MENU_T.shape[:2]
    return float(mv), (ml[0] + w // 2, ml[1] + h // 2)


def close_event():
    """공방 창 / 이벤트 메뉴를 닫고 전투 화면으로 (patch241). 전투 화면이면 True"""
    for _ in range(4):
        im = _adb_capture()          # patch245: 아이콘·메뉴 판정은 정확한 ADB 캡처로
        if icon_score(im)[0] >= 0.7 and menu_forge(im)[0] < 0.8:
            return True
        ms, mp = menu_forge(im)
        if ms >= 0.8:
            tap(mp[0] + MENU_X_OFF[0], mp[1] + MENU_X_OFF[1])     # 이벤트 메뉴 X
        elif V.state(im) in ("lobby", None, "over"):
            tap(*BTN_CLOSE)                                       # 공방 창 X
        time.sleep(1.5)
    return icon_score(_adb_capture())[0] >= 0.7


def ensure_forge_open():
    """patch292: 공방 화면(로비/게임)인지 확인하고, 전투 화면이면 자동으로 이벤트 아이콘을 눌러 공방 로비로 진입
    패널에서 공방 단발 실행 시 사용자가 직접 로비를 열어두지 않아도 자동 진입하도록 개선.
    반환: (성공여부, 새로열었는지여부)"""
    im = _adb_capture()
    st = V.state(im)
    if st in ("lobby", "game"):
        return True, False

    sc, pt = icon_score(im)
    if sc < 0.65:
        close_event()
        time.sleep(1.0)
        im = _adb_capture()
        sc, pt = icon_score(im)
        st = V.state(im)
        if st in ("lobby", "game"):
            return True, False

    if sc < 0.6:
        log("공방 진입 건너뜀: 전투 화면이 아님 (이벤트 아이콘 점수 %.2f)" % sc)
        return False, False

    log("전투 화면 감지 -> 이벤트 아이콘 누름 %s (점수 %.2f)" % (pt, sc))
    tap(*pt)
    time.sleep(2.0)
    ok = False
    icon_taps = 1
    for i in range(8):
        im = _adb_capture()
        st = V.state(im)
        if st == "lobby":
            ok = True
            break
        ms, mp = menu_forge(im)
        sc_i = icon_score(im)[0]
        log("공방 진입 확인 %d: 화면 %s, 메뉴 '유물 공방' %.2f, 이벤트 아이콘 %.2f" % (i, st, ms, sc_i))
        if ms >= 0.75:
            tap(*mp)
            time.sleep(2.5)
            continue
        if sc_i >= 0.65 and icon_taps < 2:
            icon_taps += 1
            tap(*pt)
            time.sleep(2.0)
            continue
        if st in (None, "over"):
            tap(*TAB_FORGE)
        time.sleep(1.5)
    if not ok:
        save_shot(im, "hexa_auto_open.png")
        log("공방 로비 진입 실패 -> 닫기 (shots\\hexa_auto_open.png)")
        close_event()
        return False, False
    log("공방 로비 진입 성공")
    return True, True


def auto(need=5, games=2):
    """전투 화면일 때만: 공방 아이콘 -> 이벤트 메뉴 '유물 공방' -> '공방' 탭 확인 -> 티켓 need 장 이상이면 games 판, 아니면 닫기"""
    load_cfg()
    find_serial()
    im = _adb_capture()              # patch245
    sc, pt = icon_score(im)
    if sc < 0.7:
        log("AUTO 건너뜀: 전투 화면이 아님 (공방 아이콘 점수 %.2f)" % sc)
        return "skip"
    log("AUTO 이벤트 아이콘 누름 %s (점수 %.2f)" % (pt, sc))
    tap(*pt)
    time.sleep(2.0)
    ok = False
    icon_taps = 1
    for i in range(8):
        im = _adb_capture()          # patch245
        st = V.state(im)
        if st == "lobby":
            ok = True
            break
        ms, mp = menu_forge(im)
        sc_i = icon_score(im)[0]
        log("AUTO 확인 %d: 화면 %s, 메뉴 '유물 공방' %.2f, 이벤트 아이콘 %.2f" % (i, st, ms, sc_i))
        if ms >= 0.8:
            tap(*mp)                 # 이벤트 메뉴 -> '유물 공방'
            time.sleep(2.5)
            continue
        if sc_i >= 0.7:
            if icon_taps < 2:        # 메뉴가 안 떴으면 한 번만 더
                icon_taps += 1
                tap(*pt)
                time.sleep(2.0)
                continue
            break
        if st in (None, "over"):
            save_shot(im, "hexa_auto_%d.png" % i)
            tap(*TAB_FORGE)          # 공방 창은 열렸는데 랭킹/보상 탭이면 공방 탭으로
        time.sleep(1.5)
    if not ok:
        save_shot(im, "hexa_auto_open.png")
        log("AUTO 공방 창을 못 엶 -> 닫고 건너뜀 (shots\\hexa_auto_open.png)")
        close_event()
        return "fail"
    if lobby_button(im) == "cont":
        # patch243: 지난 판이 남아 있음(앱이 꺼졌던 판). 티켓을 안 쓰므로 장수와 상관없이 마저 함
        log("AUTO 이어 하기 판 있음 -> 티켓과 상관없이 이어서 1판")
        fin = play(1)
        _after_play(fin)
        return "resumed" if fin else "interrupted"
    # patch264: 로비 진입 직후 애니메이션 렌더링 지연 대비 최대 3회 재확인
    n = None
    for attempt in range(3):
        n = read_tickets(im)
        if n is not None:
            break
        if attempt < 2:
            time.sleep(0.7)
            im = _adb_capture()
    log("AUTO 티켓 %s/5" % ("?" if n is None else n))
    if n is None:
        save_shot(im, "hexa_ticket_none.png")
    if n is None or n < need:
        back = close_event()
        log("AUTO 티켓 %s장 < %d -> 창 닫음%s" % ("?" if n is None else n, need, "" if back else " (전투 화면 확인 못함)"))
        return "closed"
    log("AUTO 티켓 %d장 >= %d -> %d판" % (n, need, games))
    fin = play(games)
    _after_play(fin)
    return "played" if fin else "interrupted"


def _after_play(fin):
    """patch243: 판이 끝났으면 창 닫기. 중간에 끊겼으면(앱 꺼짐 등) 공방 화면일 때만 닫음 - 홈 화면을 누르지 않게"""
    if fin:
        close_event()
        return
    try:
        im = _adb_capture()
        if V.state(im) in ("lobby", "over", "popup") or menu_forge(im)[0] >= 0.8:
            close_event()
        else:
            log("AUTO 판이 중간에 끊김 -> 창 닫기 생략 (메인이 복구 뒤 이어 하기)")
    except Exception as ex:
        log("AUTO 판이 중간에 끊김 (화면 확인 실패 %r)" % (ex,))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "look":
        look(a[1] if len(a) > 1 else None)
    elif a[0] == "play":
        if "go" not in a:
            print("테스트: 실제 플레이는 'py hexa.py play go' (티켓 1장 사용)")
            look()
        else:
            nums = [int(x) for x in a if x.isdigit()]
            play(nums[0] if nums else 1)
    elif a[0] == "close":            # 로비에서 보상 받기 + 창 닫기만
        load_cfg()
        find_serial()
        claim_and_close()
    elif a[0] == "auto":             # patch238: 메인이 환생 뒤 부름
        need = int(a[1]) if len(a) > 1 else 5
        games = int(a[2]) if len(a) > 2 else 2
        try:
            print("AUTO 결과", auto(need, games), flush=True)
        except Exception as ex:
            log("AUTO 오류 %r" % (ex,))
            sys.exit(1)
    elif a[0] == "sim":
        sim(int(a[1]) if len(a) > 1 else 10)
