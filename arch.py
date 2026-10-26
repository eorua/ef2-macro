"""arch.py - 길드 놀이터 '양궁 게임' 자동 플레이
과녁이 오른쪽에서 왼쪽으로 일정한 속도로 지나가고, 화면을 누르면 화살이 약 0.6초 뒤 과녁 높이에 닿습니다.
과녁 위치를 연속 캡처로 읽어 속도를 구하고, 과녁이 화면 가운데(x=360)에 올 시각에 화살이 닿도록 미리 누릅니다.
화살이 날아가는 모습을 보고 누른 뒤 지연 시간(LEAD)을 스스로 보정합니다.
실행:  py arch.py look      지금 화면 판별만 / py arch.py speed  캡처 속도 측정
       py arch.py play go   양궁 화면(게임 시작 버튼이 보이는 상태)에서 한 판 실행
"""
import sys, os, time, subprocess
import cv2, numpy as np

ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
NOWIN = 0x08000000                # CREATE_NO_WINDOW (검은 창 깜빡임 방지)
TPL = r"C:\macro\tpl"
SHOTS = r"C:\macro\shots"
W, H = 720, 1280
START = (360, 868)
START_ROI = (296, 844, 424, 894)
RES_OK = (360, 602)
RES_ROI = (300, 585, 420, 620)
ARCH_X = (683, 181)                   # patch260(양궁): 양궁 창 우상단 빨간 X (놀이터로 즉시 탈출)
TAB_B = (620, 1247)                   # 길드 건물 탭
BLD_PLAY = (360, 653)                 # 길드 건물 탭 3번째 줄: 놀이터
HIT_ROI = (150, 775, 570, 820)        # patch260(양궁): 발사 후 중앙 점수 팝업 ('☆ PERFECT! 7점!' vs '6점!')
DONE_ROI = (300, 850, 420, 890)       # patch260(양궁): '오늘 도전 끝' 텍스트 영역
SHOOT = (360, 900)                    # 화면 아무데나 누르면 발사
TGT_ROI = (0, 430, 720, 600)          # 과녁이 지나가는 띠
TGT_MIN = 0.80
CENTER_X = 360
ARROW_ROI = (340, 590, 380, 1040)     # 화살이 날아오르는 세로 띠 (과녁 아래쪽)
TIP_V = 915.0                         # 화살 끝 속도 (px/s)
HIT_Y = 510.0                         # 과녁 중심 높이
LEAD0 = 0.75                          # 누른 뒤 화살이 과녁 높이에 닿기까지 (초). 첫 판에서 스스로 보정
ROUNDS = 7
V_FIRST = 100.0                       # 1라운드 과녁 속도 추정 (px/s)
V_STEP = 38.0                         # 라운드마다 빨라지는 폭 추정
_sleep = getattr(sys.modules.get("speed"), "_real_sleep", time.sleep)


def log(*a):
    print(time.strftime("[%H:%M:%S] arch:"), *a, flush=True)


def _tpl(name):
    return cv2.imread(os.path.join(TPL, name))


# ---------------------------------------------------------------- 화면 판별
def green(img, roi):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 35) & (h <= 85) & (s >= 120) & (v >= 100)).mean())


def start_visible(img):
    return green(img, START_ROI) >= 0.5


def result_visible(img):
    return green(img, RES_ROI) >= 0.5 and not start_visible(img)


def done_today(img):
    """patch260(양궁): '오늘 도전 끝' 텍스트 표시 여부 (초록 글씨 + 검은 테두리, 시작 버튼/결과창 아님)"""
    if start_visible(img) or result_visible(img):
        return False
    x1, y1, x2, y2 = DONE_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    grn = float(((h >= 35) & (h <= 85) & (s >= 110) & (v >= 70)).mean())
    blk = float((v < 48).mean())
    return 0.08 <= grn <= 0.38 and blk >= 0.08


def hit_judge(img):
    """patch260(양궁): 발사 후 중앙 팝업 텍스트로 정중앙 만점('☆ PERFECT! 7점!') 여부 판정.
    반환: 'perfect' (정중앙 명중, 폭 198~401px) / 'miss' (하위 점수 6점 이하, 폭 43~59px) / None (팝업 전)"""
    x1, y1, x2, y2 = HIT_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    blk = hsv[..., 2] < 48
    n_blk = int(blk.sum())
    if n_blk < 180:
        return None
    xs = np.where(blk)[1]
    w = int(xs.max() - xs.min())
    if w >= 165 and n_blk >= 1000:
        return "perfect"
    if 25 <= w <= 135 and n_blk >= 220:
        return "miss"
    return None


def title_score(img):
    t = _tpl("arch_title.png")
    if t is None:
        return 0.0
    r = cv2.matchTemplate(img[250:330, 0:400], t, cv2.TM_CCOEFF_NORMED)
    return float(r.max())


def find_target(img, tpl):
    x1, y1, x2, y2 = TGT_ROI
    r = cv2.matchTemplate(img[y1:y2, x1:x2], tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    if mx < TGT_MIN:
        return None
    return loc[0] + x1 + tpl.shape[1] // 2


def arrow_strip(img):
    x1, y1, x2, y2 = ARROW_ROI
    return img[y1:y2, x1:x2].copy()


def arrow_tip(img, bg):
    """날아가는 화살 끝의 y (없으면 None). bg 는 화살이 없을 때의 같은 띠"""
    x1, y1, x2, y2 = ARROW_ROI
    d = cv2.absdiff(img[y1:y2, x1:x2], bg).max(axis=2) > 70
    col = d.sum(axis=1) >= 3
    rows = np.where(col)[0]
    if len(rows) < 12:
        return None
    top = int(rows.min())
    seg = col[top:top + 40]
    if len(seg) < 30 or seg.mean() < 0.8:        # 위에서부터 이어진 긴 막대만 화살로 인정
        return None
    return top + y1


# ---------------------------------------------------------------- 실제 환경
class RealEnv:
    def __init__(self):
        self.sh = None

    def now(self):
        return time.perf_counter()

    def sleep(self, s):
        if s > 0:
            _sleep(s)

    def wait_until(self, t):
        while True:
            d = t - time.perf_counter()
            if d <= 0:
                return
            _sleep(d - 0.01 if d > 0.02 else 0.001)

    def grab(self):
        t0 = time.perf_counter()
        out = subprocess.run(ADB + ["exec-out", "screencap"], capture_output=True, creationflags=NOWIN).stdout
        t1 = time.perf_counter()
        n = W * H * 4
        if len(out) < n:
            return None
        a = np.frombuffer(out[-n:], np.uint8).reshape(H, W, 4)
        img = np.ascontiguousarray(a[:, :, 2::-1])        # RGBA -> BGR
        return 0.5 * (t0 + t1), img, t1 - t0

    def tap(self, pt):
        if self.sh is None or self.sh.poll() is not None:
            self.sh = subprocess.Popen(ADB + ["shell"], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       creationflags=NOWIN)
            self.sh.stdin.write(b"echo ok\n")
            self.sh.stdin.flush()
            _sleep(0.3)
        t = time.perf_counter()
        self.sh.stdin.write(("input tap %d %d\n" % (pt[0], pt[1])).encode())
        self.sh.stdin.flush()
        return t

    def slow_tap(self, pt):
        subprocess.run(ADB + ["shell", "input", "tap", str(pt[0]), str(pt[1])], creationflags=NOWIN)

    def close(self):
        try:
            if self.sh is not None:
                self.sh.stdin.close()
                self.sh.terminate()
        except Exception:
            pass


# ---------------------------------------------------------------- 속도 추정
def est_speed(samples, prior):
    n = len(samples)
    if n >= 2:
        t = np.array([s[0] for s in samples])
        x = np.array([s[1] for s in samples], dtype=float)
        span = t[-1] - t[0]
        if span > 0.05:
            v = -float(np.polyfit(t - t[0], x, 1)[0])
            if v > 0:
                w = 1.0 if span >= 0.15 else 0.4
                return min(600.0, max(40.0, w * v + (1 - w) * prior))
    return prior


def fit_speed(samples):
    if len(samples) < 3:
        return None
    t = np.array([s[0] for s in samples])
    x = np.array([s[1] for s in samples], dtype=float)
    if t[-1] - t[0] < 0.4:
        return None
    v = -float(np.polyfit(t - t[0], x, 1)[0])
    return v if 20 < v < 700 else None


# ---------------------------------------------------------------- 한 판 진행
def play(env, tpl, lead=LEAD0, max_sec=150, say=log):
    """게임 시작 버튼을 누른 직후부터 결과 팝업까지. 결과: dict(result, shots, lead, speeds)"""
    t_begin = env.now()
    prior = V_FIRST
    v_hist = []
    seen = 0
    shots = 0
    phase = "wait"
    samples, bg, tips = [], None, []
    t_tap = None
    fired = False
    absent = 0
    cap_dur = 0.2
    calibrated = 0
    last_start_tap = env.now()
    popup = False
    while env.now() - t_begin < max_sec:
        g = env.grab()
        if g is None:
            env.sleep(0.2)
            continue
        tf, img, dur = g
        cap_dur = 0.8 * cap_dur + 0.2 * dur
        if result_visible(img):
            popup = True
            break
        x = find_target(img, tpl)
        if phase == "wait":
            if x is None:
                if seen == 0 and start_visible(img) and env.now() - last_start_tap > 3.0:
                    env.tap(START)
                    last_start_tap = env.now()
                continue
            seen += 1
            samples = [(tf, x)]
            bg = arrow_strip(img)
            tips = []
            fired = False
            absent = 0
            phase = "track"
            say("라운드 %d 시작: 과녁 x=%d (추정 속도 %.0f px/s)" % (seen, x, prior))
        else:
            if x is None:
                absent += 1
                if absent >= (4 if phase == "post" else 8):
                    # 라운드 끝
                    if fired:
                        if tips:
                            vals = sorted(tf2 + (ty - HIT_Y) / TIP_V - t_tap for tf2, ty in tips)
                            obs = vals[len(vals) // 2]
                            w = 0.7 if calibrated == 0 else 0.5
                            new = min(1.3, max(0.45, w * obs + (1 - w) * lead))
                            say("  화살 관측: 누른 뒤 %.3f초에 도달 -> LEAD %.3f -> %.3f" % (obs, lead, new))
                            lead = new
                            calibrated += 1
                        else:
                            say("  화살을 못 봄 (LEAD 그대로 %.3f)" % lead)
                    v = fit_speed(samples)
                    if v:
                        v_hist.append(v)
                        step = V_STEP
                        if len(v_hist) >= 2:
                            step = min(60.0, max(20.0, v_hist[-1] - v_hist[-2]))
                        prior = v + step
                        say("  라운드 %d 과녁 속도 %.0f px/s -> 다음 추정 %.0f" % (seen, v, prior))
                    phase = "wait"
                continue
            absent = 0
            samples.append((tf, x))
        if phase == "post":
            if t_tap is not None and t_tap + 0.05 <= tf <= t_tap + 1.1:
                ty = arrow_tip(img, bg)
                if ty is not None and 600 <= ty <= 1030:
                    tips.append((tf, ty))
            continue
        if phase == "track" and not fired:
            if len(samples) < 2:
                continue
            v = est_speed(samples, prior)
            tl, xl = samples[-1]
            t_cross = tl + (xl - CENTER_X) / v
            t_shot = t_cross - lead
            now = env.now()
            if t_shot - now <= cap_dur + 0.04:
                if xl < 200:
                    say("  과녁이 이미 지나감 -> 이번 라운드는 쏘지 않음")
                    fired = True
                    t_tap = None
                    phase = "post"
                    continue
                env.wait_until(t_shot)
                t_tap = env.tap(SHOOT)
                fired = True
                shots += 1
                phase = "post"
                say("  발사: 과녁 x=%d, 속도 %.0f, 예상 도달까지 %.2f초" % (xl, v, t_cross - t_tap))
    result = "done" if popup else "timeout"
    return dict(result=result, shots=shots, lead=lead, speeds=v_hist, seen=seen)


# ---------------------------------------------------------------- 실행
def run(env=None, say=log):
    """양궁 화면에서 한 판. 반환: 'done'(끝까지 함) / 'already'(시작 버튼 없음=오늘 이미 함) / 'timeout'"""
    own = env is None
    if own:
        env = RealEnv()
    try:
        tpl = _tpl("arch_target.png")
        if tpl is None:
            say("tpl\\arch_target.png 가 없습니다")
            return "notpl"
        g = env.grab()
        if g is None:
            return "nocap"
        if not start_visible(g[1]):
            say("게임 시작 버튼이 안 보임 (오늘 이미 했거나 다른 화면)")
            return "already"
        env.tap(START)
        say("게임 시작 버튼 클릭")
        res = play(env, tpl, say=say)
        say("결과: %s / 쏜 횟수 %d / 최종 LEAD %.3f / 속도 %s" % (
            res["result"], res["shots"], res["lead"], ", ".join("%.0f" % v for v in res["speeds"])))
        if res["result"] == "done":
            env.sleep(0.8)
            env.slow_tap(RES_OK) if hasattr(env, "slow_tap") else env.tap(RES_OK)
            env.sleep(1.0)
        return res["result"]
    finally:
        if own:
            env.close()


def look():
    env = RealEnv()
    g = env.grab()
    if g is None:
        log("캡처 실패")
        return
    tf, img, dur = g
    os.makedirs(SHOTS, exist_ok=True)
    cv2.imwrite(os.path.join(SHOTS, "arch_look.png"), img)
    tpl = _tpl("arch_target.png")
    x = find_target(img, tpl) if tpl is not None else None
    log("캡처 %.3f초 / 양궁 제목 %.2f / 시작 버튼 %s / 결과 팝업 %s / 과녁 x=%s" % (
        dur, title_score(img), start_visible(img), result_visible(img), x))
    log("(shots\\arch_look.png 가 실제 화면과 색이 같게 저장됐는지 확인하세요)")


def speed_test(n=8):
    env = RealEnv()
    ds = []
    for _ in range(n):
        g = env.grab()
        if g:
            ds.append(g[2])
    if ds:
        log("캡처 시간: 평균 %.3f초 / 최소 %.3f / 최대 %.3f (%d회)" % (sum(ds) / len(ds), min(ds), max(ds), len(ds)))


if __name__ == "__main__":
    cmd = [a for a in sys.argv[1:] if a != "go"]
    cmd = cmd[0] if cmd else "look"
    if cmd == "speed":
        speed_test()
    elif cmd == "play" and "go" in sys.argv[1:]:
        log("결과:", run())
    elif cmd == "play":
        log("시험 모드: 실제로 하려면 맨 끝에 go 를 붙이세요 (py arch.py play go)")
        look()
    else:
        look()
