"""skillctl.py - 고층(웨이브 7200 이상)에서 액티브 스킬(총병 소환) 3개를 겹치지 않게 직접 굴림
  - 스킬 AUTO 를 끄고, 한 스킬의 총병이 끝날 때쯤(약 1초) 준비된 다음 스킬을 누름
  - 메인 루프가 쉬는 시간(idle)에만 동작 -> 메인의 다른 작업과 동시에 누르는 일이 없음
  - 환생하면/매크로가 다시 시작되면 AUTO 를 다시 켬
  - 실측: 총병 지속 약 1.0~1.1초, 재사용 4.0 / 4.1 / 5.6초 (빠른 배속 기준)
  py skillctl.py look     지금 화면: 스킬 원 보임 여부 / 준비 상태 / AUTO 상태
  py skillctl.py auto on|off   스킬 AUTO 켜기/끄기 시험
"""
import os, sys, time, subprocess
import numpy as np
import cv2

from dev import ADB          # patch162
CIRCLES = [(250, 129), (315, 129), (381, 129)]     # 스킬 원 중심
AUTO_BTN = (448, 173)                              # 스킬 원 아래 'AUTO'
AUTO_ROI = (420, 160, 480, 186)
START_WAVE = 7200
DUR = 1.05            # 총병 지속(초, 실측)
GAP = 1.45            # 스킬 사이 최소 간격(초): 누른 뒤 등장 0.1~0.2초 + 지속 1.1초 + 여유 -> 총병이 겹치지 않음
                      #   세 스킬을 다 써도 평균 간격이 약 1.5초라 이 간격으로도 쿨타임 손해는 거의 없음
STALL = 20.0          # 준비된 스킬이 보이는데 이 시간 동안 한 번도 못 쓰면 AUTO 로 되돌림 (쿨타임/창이 덮은 시간은 안 셈)
IDLE_ACTIVE = 3.0     # 직접 굴리는 동안 메인 루프 한 바퀴 쉬는 시간

_cam = None
_last_fire = -9.0
_fails = 0
_n = 0
_ban = [0.0, 0.0, 0.0]   # 눌렀는데 안 쓰인 스킬은 이 시각까지 건너뜀
_stats = {"fire": 0, "skip": 0}
_t_on = 0.0
_vis = 0.0            # 마지막 사용 뒤, 스킬 원이 보였던 시간 합
_prev_t = None
_dbg = {"t": 0.0, "frames": 0, "ring": 0, "ready": [0, 0, 0], "saved": 0}
SHOTS = r"C:\macro\shots"

# ---------------------------------------------------------------- patch170: 성 근처 적 기록 (하늘의 검 기준 정하기용, 지금은 기록만)
# 0.2초 간격 두 화면의 차이 중 '어두운 것이 움직인 픽셀'(적) 비율을 성 안쪽 원 / 바깥 띠로 나눠 1초마다 기록
# 기절한 적은 멈춰 있어 빠지고, 새로 파고드는 적만 잡힘. 밝은 불 이펙트·글자는 밝기로 걸러냄
PROX_C = (355, 375)          # 성 가운데 (화면 좌표)
R_IN, R_OUT = 130, 200       # 안쪽 원 / 바깥 띠 반지름
PROX_EVERY = 0.2
# ---------------------------------------------------------------- patch183: 하늘의 검(스킬 1·2·3 모두)을 '밤'에만 사용
# 10-18 영상: 낮/밤이 약 10초 주기(밤 약 6초), 함락 2번 모두 밤 시작 1~3초 안. 함락 순간엔 스킬 3개가 다 쿨타임이었음
# -> 낮에는 아껴 두고, 밤이 시작되면(화면 밝기가 최근 최댓값의 72% 아래로) 1개, 밤 2.5초째에 준비된 게 2개 이상이면 1개 더
# 밤을 못 잡는 화면이어도 준비된 검을 HOLD_MAX 초 넘게 쥐고 있으면 예전처럼 사용 (안전장치 STALL 보다 짧게)
NIGHT_RATIO = 0.72
NIGHT_WIN = 12.0
NIGHT_2ND = 2.5
HOLD_MAX = 15.0
import collections as _co
_nt = {"hist": _co.deque(), "night": False, "cnt": 0, "t0": 0.0, "ev": [], "tp": 0.0, "n": 0, "nf": 0}


def _night_update(img, t):
    """밝기로 밤 시작/끝 판단. 밤이 새로 시작되면 사용 기회 2개(시작, 2.5초째)를 만듦"""
    if t - _nt["tp"] < 0.1:
        return
    _nt["tp"] = t
    v = float(np.median(img[60:600:8, 20:540:8].max(axis=2)))
    h = _nt["hist"]
    h.append((t, v))
    while h and t - h[0][0] > NIGHT_WIN:
        h.popleft()
    day = max(x[1] for x in h)
    dark = day >= 100 and v < NIGHT_RATIO * day
    if not _nt["night"]:
        if dark:
            _nt["cnt"] += 1
            if _nt["cnt"] >= 2:                          # 두 번 연속 어두우면 밤
                _nt.update(night=True, t0=t, ev=[1, 2], cnt=0)
                _nt["n"] += 1
                _px.setdefault("fired", []).append("N")  # sword_trace 에 밤 시작 표시
        else:
            _nt["cnt"] = 0
    elif v >= 0.8 * day:                                # 다시 밝아짐 -> 밤 끝 (남은 기회는 버림)
        _nt.update(night=False, ev=[], cnt=0)


def _night_want(t, nready):
    """지금 검을 써야 하면 사용할 기회 번호, 아니면 0"""
    if not _nt["night"]:
        return 0
    ev = _nt["ev"]
    if 1 in ev:
        return 1
    if 2 in ev and t - _nt["t0"] >= NIGHT_2ND and nready >= 2:
        return 2
    return 0


SWORD_SHOTS = 0              # patch182: 15초마다 저장하던 화면 (WAVE 숫자·화살 때문에 의미 없음) -> 끔

# ---------------------------------------------------------------- patch182: 7500 이후 화면 녹화 (하늘의 검 기준 정하기용, 1회성)
# 스킬 직접 굴리기로 이미 받고 있는 실시간 화면(fastcam)을 PC 에서 mp4 로 저장 -> 블루스택 쪽 추가 부담 없음
# 웨이브 3번 연속 7500 이상이면 시작, 환생(AUTO 복구)·화면 받기 끊김·25분이면 끝. 하루 REC_MAX_DAY 판까지
REC_WAVE = 7500
REC_FPS = 15
REC_SIZE = (360, 640)
REC_MAX_DAY = 4
REC_MAX_SEC = 25 * 60
REC_DIR = os.path.join(r"C:\macro\shots", "rec")
_rec = {"thr": None, "run": False}


def _rec_today():
    try:
        d = time.strftime("%m%d_")
        return sum(1 for f in os.listdir(REC_DIR) if f.startswith(d) and f.endswith(".mp4"))
    except OSError:
        return 0


def note_wave(hist):
    """메인 루프에서 웨이브를 읽을 때마다 호출. 조건이 되면 녹화 시작"""
    try:
        if _rec["run"] or _cam is None or len(hist) < 3 or min(hist) < REC_WAVE:
            return
        if _rec_today() >= REC_MAX_DAY:
            return
        import threading
        os.makedirs(REC_DIR, exist_ok=True)
        path = os.path.join(REC_DIR, "%s_%d.mp4" % (time.strftime("%m%d_%H%M%S"), min(hist)))
        _rec["run"] = True
        _rec["thr"] = threading.Thread(target=_rec_loop, args=(path,), daemon=True)
        _rec["thr"].start()
    except Exception as e:
        _rec["run"] = False
        log("녹화 시작 오류: %r" % (e,))


def _rec_loop(path):
    vw = None
    n_fr = 0
    t0 = time.perf_counter()
    try:
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), REC_FPS, REC_SIZE)
        if not vw.isOpened():
            log("녹화 파일을 못 엶: %s" % path)
            return
        log("화면 녹화 시작 -> %s" % path)
        last = None
        while _rec["run"] and time.perf_counter() - t0 < REC_MAX_SEC:
            cam = _cam
            if cam is None:
                break
            img = cam.latest()[0]
            if img is not None:
                last = img
            if last is not None:                     # 새 화면이 없어도 같은 화면을 넣어 영상 시간 = 실제 시간
                fr = cv2.resize(last, REC_SIZE, interpolation=cv2.INTER_AREA)
                cv2.putText(fr, time.strftime("%H:%M:%S"), (6, 632), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
                cv2.putText(fr, time.strftime("%H:%M:%S"), (6, 632), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                vw.write(fr)
                n_fr += 1
            nxt = t0 + n_fr / REC_FPS
            d = nxt - time.perf_counter()
            if d > 0:
                time.sleep(d)
            elif d < -2.0:                           # 많이 밀렸으면 (PC 가 바쁨) 따라잡지 않고 기준만 옮김
                t0 = time.perf_counter() - n_fr / REC_FPS
    except Exception as e:
        log("녹화 오류: %r" % (e,))
    finally:
        if vw is not None:
            vw.release()
        _rec["run"] = False
        log("화면 녹화 끝 (%.0f초, %d장) %s" % (time.perf_counter() - t0, n_fr, os.path.basename(path)))


def rec_stop():
    if _rec["run"]:
        _rec["run"] = False
        th = _rec.get("thr")
        if th is not None:
            th.join(timeout=5)
_px = {"prev": None, "tp": 0.0, "sec": None, "mx": [0.0, 0.0], "f": None, "saved": 0, "last_save": 0.0, "mask": None}


def _prox_masks():
    if _px["mask"] is None:
        x0, y0 = PROX_C[0] - R_OUT, PROX_C[1] - R_OUT
        n = R_OUT * 2 // 2
        yy, xx = np.mgrid[0:n, 0:n]
        r = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) * 2
        excl = np.zeros((n, n), bool)
        try:
            import arrange
            pts = list(arrange.T_SPIRIT) + [arrange.T_DRUM, arrange.T12]
        except Exception:
            pts = []
        for (x, y) in pts:                           # 영웅 깃발 아이콘 자리는 뺌
            a, b = (x - 45 - x0) // 2, (y - 35 - y0) // 2
            excl[max(0, b):max(0, b + 40), max(0, a):max(0, a + 48)] = True
        _px["mask"] = ((r < R_IN) & ~excl, (r >= R_IN) & (r < R_OUT) & ~excl, (x0, y0, n))
    return _px["mask"]


def prox_update(img, t, fired=-1):
    """화면마다 호출. 1초에 한 줄씩 shots\\sword_trace_날짜.csv 에 (시각, 안쪽, 바깥, 사용한 스킬)"""
    try:
        m_in, m_ring, (x0, y0, n) = _prox_masks()
        if fired >= 0:
            _px.setdefault("fired", []).append(fired + 1)
        if t - _px["tp"] < PROX_EVERY:
            return
        _px["tp"] = t
        g = cv2.cvtColor(img[y0:y0 + 2 * n, x0:x0 + 2 * n], cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (n, n), interpolation=cv2.INTER_AREA).astype(np.int16)
        prev, _px["prev"] = _px["prev"], g
        if prev is None or prev.shape != g.shape:
            return
        mv = (np.abs(g - prev) > 25) & (np.minimum(g, prev) < 110)
        a, b = float(mv[m_in].mean()), float(mv[m_ring].mean())
        sec = int(t)
        if _px["sec"] is not None and sec != _px["sec"]:
            _prox_write(_px["sec"], img)
        if _px["sec"] != sec:
            _px["sec"] = sec
            _px["mx"] = [0.0, 0.0]
        _px["mx"] = [max(_px["mx"][0], a), max(_px["mx"][1], b)]
    except Exception as e:
        log("성 근처 기록 오류: %r" % (e,))


def _prox_write(sec, img):
    a, b = _px["mx"]
    fired = _px.pop("fired", [])
    try:
        os.makedirs(SHOTS, exist_ok=True)
        p = os.path.join(SHOTS, "sword_trace_%s.csv" % time.strftime("%m%d"))
        new = not os.path.exists(p)
        with open(p, "a", encoding="utf-8") as f:
            if new:
                f.write("clock,inner,ring,fired\n")
            f.write("%s,%.4f,%.4f,%s\n" % (time.strftime("%H:%M:%S"), a, b, "+".join(map(str, fired))))
    except OSError:
        pass
    now = time.time()                                 # 안쪽 값이 클 때 화면 저장 (15초에 1장, 하루 40장까지)
    if a >= 0.03 and now - _px["last_save"] > 15 and _px["saved"] < SWORD_SHOTS:     # patch182: 쓸모없어 끔(0)
        _px["last_save"] = now
        _px["saved"] += 1
        _save(img, os.path.join("sword", time.strftime("%m%d_%H%M%S") + "_in%03d.png" % int(a * 1000)))


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- 화면 판별
def _ring_bands(img):
    """원마다 반지름 3px 띠별 금색 비율의 최댓값. 준비된 원은 살짝 작아지거나 움직여서 띠를 넓게 봄
    (13:03 초록 맵에서 원 2의 테두리가 반지름 20~23 에 있어 기존 23~28 범위로는 0.05 -> '창이 덮음'으로 오판)"""
    hsv = cv2.cvtColor(img[90:170, 210:420], cv2.COLOR_BGR2HSV)
    yy, xx = np.mgrid[-30:31, -30:31]
    r = np.sqrt(xx ** 2 + yy ** 2)
    out = []
    for x, y in CIRCLES:
        p = hsv[y - 30 - 90:y + 31 - 90, x - 30 - 210:x + 31 - 210]
        m = (p[..., 0] >= 15) & (p[..., 0] <= 35) & (p[..., 1] >= 90) & (p[..., 2] >= 140)
        out.append(max(float(m[(r >= a) & (r < a + 3)].mean()) for a in range(17, 29)))
    return out


def ring_ok(img):
    """스킬 원 3개의 금색 테두리가 다 보이면 True (창이 덮었거나 어두워지면 False)"""
    return min(_ring_bands(img)) >= 0.30


def ready(img, k):
    """준비됨 = 원 안이 색 있는 총병 그림. 세 조건 모두:
    채도 중앙값 > 65, 붉은/갈색 픽셀 >= 8%, 흰 숫자 픽셀 < 6%
    (23:42 숲·밤 맵에서 쿨타임 원이 채도 72 로 읽혀 '준비'로 오판 -> 숫자/색 조건 추가)"""
    x, y = CIRCLES[k]
    hsv = cv2.cvtColor(img[y - 16:y + 16, x - 16:x + 16], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if float(np.median(s)) <= 65:
        return False
    red = float((((h <= 20) | (h >= 165)) & (s >= 110) & (v >= 90)).mean())
    white = float(((s < 40) & (v > 200)).mean())
    return red >= 0.08 and white < 0.06


def auto_on(img):
    x1, y1, x2, y2 = AUTO_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 0] >= 8) & (hsv[..., 0] <= 25) & (hsv[..., 1] >= 150) & (hsv[..., 2] >= 180)
    return float(m.mean()) >= 0.03          # 켜짐: 주황 글씨 0.05~0.08


def _adb_cap():
    import dev                      # patch162
    return dev.capture(timeout=15)


def _adb_tap(pt):
    import dev                      # patch162
    dev.tap(pt[0], pt[1])


def set_auto(want):
    """스킬 AUTO 를 want(True/False) 로. 확인까지 되면 True. 실패하면 화면을 shots\\skill_auto_fail.png 로"""
    img = None
    for _ in range(3):
        img = _adb_cap()
        if img is None or not ring_ok(img):
            time.sleep(1.0)
            continue
        if auto_on(img) == want:
            return True
        _adb_tap(AUTO_BTN)
        time.sleep(0.8)
    img = _adb_cap()
    ok = img is not None and ring_ok(img) and auto_on(img) == want
    if not ok and img is not None:
        _save(img, "skill_auto_fail.png")
    return ok


# ---------------------------------------------------------------- 켜기 / 끄기
def active():
    return _cam is not None


def activate(st):
    global _cam, _fails, _last_fire
    if _cam is not None:
        return True
    try:
        from fastcam import FastCam
        cam = FastCam(max_fps=30).start()
    except Exception as e:
        log("fastcam 시작 실패 -> 스킬 직접 굴리기 안 함: %r" % (e,))
        st["skill_off_until"] = time.time() + 1800
        return False
    if not set_auto(False):
        cam.stop()
        log("스킬 AUTO 끄기 실패 -> 이번엔 안 함")
        st["skill_off_until"] = time.time() + 300
        return False
    global _t_on
    _cam, _fails, _last_fire = cam, 0, -9.0
    global _vis, _prev_t, _n
    _t_on = time.perf_counter()
    _vis, _prev_t = 0.0, None
    _ban[:] = [0.0, 0.0, 0.0]
    _n = 0                                           # 새 fastcam 은 화면 번호가 0부터 -> 안 맞추면 영원히 '새 화면 없음'(10-14 밤 0회 원인)
    _dbg.update(t=0.0, frames=0, ring=0, ready=[0, 0, 0])
    _stats.update(fire=0, skip=0)
    st["skill_manual"] = True
    _start_worker()                                  # patch189
    log("스킬 직접 굴리기 시작 (AUTO 끔)")
    return True


def deactivate(st, why=""):
    """AUTO 를 다시 켜고 fastcam 종료. AUTO 켜기를 확인하면 True"""
    global _cam
    rec_stop()                                       # patch182
    _stop_worker()                                   # patch189
    if _cam is not None:
        try:
            _cam.stop()
        except Exception:
            pass
        _cam = None
    ok = set_auto(True)
    if ok:
        st["skill_manual"] = False
        log("스킬 AUTO 다시 켬%s (이번 구간 직접 사용 %d회)" % (" - " + why if why else "", _stats["fire"]))
    else:
        log("스킬 AUTO 켜기 확인 실패 - 다음 루프에서 다시 시도")
    return ok


# ---------------------------------------------------------------- 메인 루프의 쉬는 시간
def idle(sec):
    """patch189: 스킬 관리는 별도 스레드(_worker)가 화면마다 계속 함 -> 메인 루프는 그냥 쉼
    (예전엔 메인이 쉬는 동안만 봐서, 웨이브 읽기 등을 하는 사이 밤 시작을 놓치거나 검이 1~6초 늦게 나갔음 - 10-18 18:55 함락)"""
    if _cam is not None and _wk.get("thr") is not None and not _wk["thr"].is_alive() and _wk["run"]:
        log("스킬 스레드가 멈춰 있음 -> 다시 시작")
        _start_worker()
    time.sleep(sec)


_wk = {"run": False, "thr": None}


def _start_worker():
    import threading
    _wk["run"] = True
    _wk["thr"] = threading.Thread(target=_worker, args=(_cam,), daemon=True)
    _wk["thr"].start()


def _stop_worker():
    _wk["run"] = False
    th = _wk.get("thr")
    if th is not None and th.is_alive():
        th.join(timeout=3)
    _wk["thr"] = None


def _worker(cam):
    """직접 굴리는 동안 화면마다: 밤 판단, 준비 상태, 밤 시작이면 바로 검 사용, 눌렀는데 안 쓰였는지 확인
    스킬 원이 안 보이면(창이 떴거나 다른 화면) 절대 누르지 않음"""
    global _last_fire, _fails, _n, _vis, _prev_t
    pending = None                                   # (스킬, 누른 시각) - 실제로 쓰였는지 확인용
    while _wk["run"] and _cam is cam:
        try:
            g = cam.wait_new(_n, 0.3)
            if g is None:
                if cam.err:
                    log("fastcam 끊김: %s" % cam.err)
                    break
                continue
            img, t, _n = g
            _dbg["frames"] += 1
            prox_update(img, t)                          # patch170
            if t - _dbg["t"] > 60:                       # 1분마다 판별값 기록 + 화면 저장 (5장까지 돌려 씀)
                _dbg["t"] = t
                log("스킬 상태: 1분간 화면 %d장 / 원 보임 %d장 / 준비 %s / 금테 %s / 원 안 채도 %s / 사용 %d회 (밤 %d번, 밤에 사용 %d회)" % (
                    _dbg["frames"], _dbg["ring"], _dbg["ready"], _ring_vals(img), [_sat(img, k) for k in range(3)], _stats["fire"],
                    _nt["n"], _nt["nf"]))
                _save(img, "skill_dbg_%d.png" % (_dbg["saved"] % 5))
                _dbg["saved"] += 1
                _dbg.update(frames=0, ring=0, ready=[0, 0, 0])
            dt = 0.0 if _prev_t is None else min(0.5, max(0.0, t - _prev_t))
            _prev_t = t
            if not ring_ok(img):                         # 창이 떠 있거나 다른 화면 -> 손대지 않음 (안전장치 시간도 안 셈)
                continue
            _dbg["ring"] += 1
            _night_update(img, t)                        # patch183
            rd = [ready(img, k) for k in range(3)]
            if any(rd[j] and t >= _ban[j] for j in range(3)):
                _vis += dt                               # 준비된 스킬이 있는데 못 쓴 시간만 셈
            for k in range(3):
                _dbg["ready"][k] += int(rd[k])
            if pending is not None:
                k, tp = pending
                if not rd[k]:
                    pending = None
                    _fails = 0
                elif t - tp > 0.6:
                    pending = None
                    _fails += 1
                    log("스킬 %d 을 눌렀는데 안 쓰임 (%d회 연속, 원 안 채도 %d) -> 손 떼기 + 이 스킬 5초 쉼" % (k + 1, _fails, _sat(img, k)))
                    _save(img, "skill_miss_%d.png" % min(_fails, 5))
                    try:
                        cam.touch(1, *CIRCLES[k])
                    except Exception:
                        pass
                    _ban[k] = t + 5.0
                continue
            now = time.perf_counter()
            if now < _last_fire + GAP or not any(rd):
                continue
            ok = [rd[j] and t >= _ban[j] for j in range(3)]
            if not any(ok):
                continue
            ev = _night_want(t, sum(ok))                 # patch183: 낮에는 아낌
            if ev == 0 and _vis <= HOLD_MAX:
                continue
            if ev:
                _nt["ev"].remove(ev)
                _nt["nf"] += 1
            k = ok.index(True)
            _last_fire = cam.tap(*CIRCLES[k], hold=0.03)
            prox_update(img, t, fired=k)                 # patch170: 사용 기록
            _vis = 0.0
            pending = (k, _last_fire)
            _stats["fire"] += 1
        except Exception as e:
            log("스킬 스레드 오류: %r" % (e,))
            time.sleep(0.5)


def need_stop():
    """눌러도 계속 안 쓰이거나, 오래 한 번도 못 눌렀으면 True -> 메인이 AUTO 로 되돌림"""
    if _fails >= 6:                                  # 스킬을 돌아가며 건너뛰므로 6번 연속 안 쓰일 때만 포기
        return True
    if _cam is not None and _vis > STALL:
        return True
    return False


def _save(img, name):
    try:
        os.makedirs(os.path.dirname(os.path.join(SHOTS, name)), exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name), img)
    except Exception:
        pass


def _ring_vals(img):
    return [round(v, 2) for v in _ring_bands(img)]


def _sat(img, k):
    x, y = CIRCLES[k]
    hsv = cv2.cvtColor(img[y - 16:y + 16, x - 16:x + 16], cv2.COLOR_BGR2HSV)
    return int(np.median(hsv[..., 1]))


# ---------------------------------------------------------------- 시험
if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["look"]:
        img = _adb_cap()
        print("스킬 원 보임:", ring_ok(img), "/ 준비:", [ready(img, k) for k in range(3)], "/ AUTO 켜짐:", auto_on(img))
    elif a[:1] == ["auto"] and len(a) >= 2:
        print("결과:", set_auto(a[1] == "on"))
    else:
        print(__doc__)
