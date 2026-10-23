"""arch2.py - 양궁 게임 새 방식 (fastcam: 창 없는 scrcpy, 초당 40장 이상 관찰 + 즉시 터치)
화면 판별·화살 관측은 arch.py 것을 그대로 쓰고, '관찰 → 발사 시각 계산' 부분만 새로 짰습니다.
  py arch2.py look              지금 화면 판별 (시작 버튼 / 과녁 위치)
  py arch2.py play go           양궁 화면(게임 시작 버튼이 보이는 상태)에서 한 판
  py arch2.py replay 영상.mp4   녹화 영상으로 예측 시험 (게임은 건드리지 않음)
기록: shots\\arch2_log.txt (설명) / shots\\arch2_trace_시각.csv (과녁 위치 전부, 분석용)
"""
import sys, os, time
import numpy as np
import cv2
import arch
from arch import (START, RES_OK, SHOOT, CENTER_X, HIT_Y, TIP_V, start_visible, result_visible,
                  find_target, arrow_strip, arrow_tip, title_score, _tpl)

SHOTS = r"C:\macro\shots"
LOGF = os.path.join(SHOTS, "arch2_log.txt")
LEAD0 = 0.697   # patch213: 10-20~23 실측 0.686~0.705 (업데이트 뒤 화살이 조금 빨라짐), 지난 판 값이 있으면 그것부터 / 예전 0.72                 # patch143: 0.70 -> 0.72 (실측 0.709~0.730, 1라운드 6점이던 원인). 누른 뒤 화살이 과녁 높이에 닿기까지(관찰 지연 포함) 첫 추정. 라운드마다 스스로 보정
V0 = 200.0                   # 1라운드 과녁 속도 첫 추정 (영상: 140~300 px/s)
MIN_SPAN = 0.12              # 속도는 최소 이 시간 동안 본 뒤에 계산 (patch152: 0.15 -> 0.12, 화면 시각이 정확해져서 짧게 봐도 됨)
AIM_PX = 4.0                 # patch152: 실측으로 평균 3~6px 늦게 맞음 -> 가운데보다 이만큼 앞을 노림
GONE_SEC = 0.35              # 과녁이 이만큼 안 보이면 라운드 끝
# patch165: 빠른 라운드(6·7)는 관찰 0.12~0.2초뿐이라 속도를 7~9% 틀리게 잼 (10-18 7라운드 317 -> 실제 346, 28px 늦음)
#   -> 라운드별 지난 판 속도(중앙값)를 미리 알고, 관찰이 짧을수록 그 값을 더 믿음
SPEEDS_F = os.path.join(SHOTS, "arch2_speeds.json")
LEAD_F = os.path.join(SHOTS, "arch2_lead.txt")      # patch213
# patch166: 영상 4개 + 기록 5판(10-13~10-18, 서로 다른 6판)에서 다시 잰 라운드별 속도 (라운드 안에서는 일정, 오차 ±1px/s)
PRIOR0 = {1: [214.5, 160.0, 204.7, 191.9, 227.3, 166.9],
          2: [138.8, 199.8, 116.5, 148.6, 113.3, 183.8],
          3: [190.5, 202.7, 250.3, 266.8, 257.3, 250.9],
          4: [292.9, 286.7, 235.3, 173.0, 187.5, 167.4],
          5: [298.5, 289.9, 285.7, 268.9, 245.1, 272.6],
          6: [233.1, 330.1, 290.6, 220.1, 297.3, 317.3],
          7: [298.3, 328.3, 313.4, 336.3, 334.7, 346.4]}
POS_SD = 2.0                 # 과녁 위치·시각 오차(px 환산). patch195: 5.0 -> 2.0 (기록 6판 재계산: 짧게 봐도 관찰 속도가 더 정확, 10-19 7라운드 지난 판 속도에 끌려 29px 빗나감)
PRIOR_SD_MIN = 40.0          # patch195: 지난 판 속도의 퍼짐을 최소 이만큼으로 봄 (판마다 속도가 크게 달라짐, 8 -> 40)


def _speeds():
    import json
    try:
        with open(SPEEDS_F, encoding="utf-8") as f:
            d = {int(k): v for k, v in json.load(f).items()}
    except Exception:
        d = {}
    for k, v in PRIOR0.items():
        d.setdefault(k, list(v))
    return d


def _save_speeds(d):
    import json
    try:
        with open(SPEEDS_F, "w", encoding="utf-8") as f:
            json.dump({str(k): v[-10:] for k, v in d.items()}, f)
    except OSError:
        pass


def _prior(d, rnd):
    """(평균, 표준편차) - 지난 판들의 이 라운드 속도"""
    v = d.get(rnd)
    if not v or len(v) < 3:
        return None
    return float(np.mean(v)), max(PRIOR_SD_MIN, float(np.std(v)))
_sleep = getattr(sys.modules.get("speed"), "_real_sleep", time.sleep)


def log(*a):
    s = time.strftime("[%H:%M:%S] arch2: ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    try:
        os.makedirs(SHOTS, exist_ok=True)
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- 환경: 실제 (fastcam)
class FastEnv:
    def __init__(self):
        from fastcam import FastCam
        self.cam = FastCam().start()
        self.n = 0

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
            _sleep(d - 0.004 if d > 0.008 else 0.0005)

    def grab(self, timeout=0.5):
        """새 화면이 오면 (받은 시각, 화면). 화면이 안 바뀌면 timeout 뒤 마지막 화면"""
        g = self.cam.wait_new(self.n, timeout)
        if g is None:
            img, t, n = self.cam.latest()
            return (self.now(), img) if img is not None else None
        img, t, self.n = g
        return t, img

    def tap(self, pt):
        return self.cam.tap(pt[0], pt[1], hold=0.03)

    def close(self):
        self.cam.stop()


# ---------------------------------------------------------------- 환경: 녹화 영상 (시험용)
class VideoEnv:
    """녹화 영상을 실제 시간처럼 재생. 누르기는 기록만 함"""
    def __init__(self, path, lag=0.06):
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.t = 0.0
        self.k = 0
        self.lag = lag             # 화면이 우리에게 도착하기까지 지연(가정)
        self.taps = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)

    def wait_until(self, t):
        self.t = max(self.t, t)

    def grab(self, timeout=0.5):
        while True:
            ok, img = self.cap.read()
            if not ok:
                return None
            ft = self.k / self.fps + self.lag
            self.k += 1
            if ft >= self.t:
                self.t = ft
                return ft, img

    def tap(self, pt):
        self.taps.append((self.t, pt))
        return self.t

    def close(self):
        self.cap.release()


# ---------------------------------------------------------------- 속도 맞추기
def robust_fit(samples):
    """(t, x) 들에 직선 맞춤. 화면이 늦게 갱신된 점(과녁이 실제보다 뒤에 보임)은 빼고 맞춤.
    반환: (속도 px/s, 기준 시각 t0, t0 에서의 x)"""
    t = np.array([s[0] for s in samples])
    x = np.array([s[1] for s in samples], dtype=float)
    keep = np.r_[True, np.diff(x) != 0]          # 위치가 그대로인 화면(갱신 안 됨)은 버림
    t, x = t[keep], x[keep]
    if len(t) < 3:
        return None
    t0 = t[0]
    p = np.polyfit(t - t0, x, 1)
    for _ in range(3):
        r = x - np.polyval(p, t - t0)
        m = r < max(2.0, r.std())
        if m.sum() < 3:
            break
        p = np.polyfit(t[m] - t0, x[m], 1)
    v = -float(p[0])
    if not (40.0 < v < 800.0):
        return None
    return v, t0, float(p[1])


# ---------------------------------------------------------------- 한 판
def play(env, tpl, lead=LEAD0, max_sec=150, say=log, trace=None, calibrate=True):
    t_begin = env.now()
    v_prev = V0
    hist = _speeds()                                 # patch165
    seen = shots = calibrated = 0
    phase = "wait"
    samples, tips, bg = [], [], None
    t_tap = None
    fired = False
    last_seen = 0.0
    last_start_tap = env.now()
    popup = False
    rounds = []
    while env.now() - t_begin < max_sec:
        g = env.grab()
        if g is None:
            break
        tf, img = g
        if result_visible(img):
            popup = True
            break
        x = find_target(img, tpl)
        if trace is not None:
            trace.append((tf, -1 if x is None else x, seen, phase))
        if phase == "wait":
            if x is None:
                if seen == 0 and start_visible(img) and env.now() - last_start_tap > 3.0:
                    env.tap(START)
                    last_start_tap = env.now()
                continue
            if x < 450:                              # 이미 많이 지나간 과녁(라운드 끝 직후 잔상)은 무시
                continue
            seen += 1
            samples, tips = [(tf, x)], []
            bg = arrow_strip(img)
            fired, t_tap = False, None
            last_seen = tf
            phase = "track"
            say("라운드 %d 시작: 과녁 x=%d" % (seen, x))
            continue
        # track / post
        if x is None:
            if tf - last_seen >= GONE_SEC:
                info = {"round": seen, "fired": fired}
                fit = robust_fit(samples)
                if fit:
                    v_prev = fit[0]
                    info["v"] = round(fit[0])
                    if samples[-1][0] - samples[0][0] >= 0.3:          # patch165: 충분히 본 라운드만 기록
                        hist.setdefault(seen, []).append(round(fit[0]))
                    say("  라운드 %d 과녁 속도 %.0f px/s" % (seen, fit[0]))
                if fired and t_tap is not None and calibrate:
                    if tips:
                        vals = sorted(t2 + (ty - HIT_Y) / TIP_V - t_tap for t2, ty in tips)
                        obs = vals[len(vals) // 2]
                        w = 0.7 if calibrated == 0 else 0.5
                        new = min(1.2, max(0.4, w * obs + (1 - w) * lead))
                        say("  화살 관측: 누른 뒤 %.3f초에 도달 -> LEAD %.3f -> %.3f" % (obs, lead, new))
                        info["lead_obs"] = round(obs, 3)
                        lead = new
                        calibrated += 1
                    else:
                        say("  화살을 못 봄 (LEAD 그대로 %.3f)" % lead)
                rounds.append(info)
                phase = "wait"
            continue
        last_seen = tf
        samples.append((tf, x))
        if phase == "post":
            if t_tap is not None and t_tap + 0.05 <= tf <= t_tap + 1.2:
                ty = arrow_tip(img, bg)
                if ty is not None and 600 <= ty <= 1030:
                    tips.append((tf, ty))
            continue
        # 발사 시각 계산
        span = samples[-1][0] - samples[0][0]
        fit = robust_fit(samples) if span >= MIN_SPAN else None
        if fit:
            v, t0, x0 = fit
            pr = _prior(hist, seen)
            if pr:                                   # patch165/166: 관찰이 짧으면 지난 판 속도를 섞음 (오차 크기로 비중 결정)
                n = max(3, len(samples))
                sd_fit = POS_SD * 3.46 / (max(span, 0.03) * n ** 0.5)
                w = pr[1] ** 2 / (pr[1] ** 2 + sd_fit ** 2)
                vb = w * v + (1 - w) * pr[0]
                tl = samples[-1][0]
                xl = x0 - v * (tl - t0)              # 맞춘 직선에서 지금 위치
                v = vb
                t_cross = tl + (xl - CENTER_X) / v
            else:
                t_cross = t0 + (x0 - CENTER_X) / v
        else:                                        # 아직 덜 봤으면 직전 라운드 속도로 임시 계산
            tl, xl = samples[-1]
            v = v_prev
            t_cross = tl + (xl - CENTER_X) / v
        t_shot = t_cross - lead - AIM_PX / v
        now = env.now()
        if t_shot - now > 0.03:                      # 아직 여유 있음 -> 다음 화면 보고 다시 계산
            continue
        if fit is None and span < 0.08:
            say("  관찰 시간이 너무 짧음(%.2f초) - 추정 속도 %.0f 로 발사" % (span, v))
        if t_shot < now - 0.08:
            say("  발사 시각을 %.2f초 놓침 -> 그래도 즉시 발사" % (now - t_shot))
        env.wait_until(t_shot)
        t_tap = env.tap(SHOOT)
        fired = True
        shots += 1
        phase = "post"
        say("  발사: 과녁 x=%d, 속도 %.0f px/s (관찰 %.2f초, %d장), 가운데 도착까지 %.3f초, LEAD %.3f" % (
            samples[-1][1], v, span, len(samples), t_cross - t_tap, lead))
    if calibrate:
        _save_speeds(hist)                           # patch165
    return dict(result="done" if popup else "timeout", shots=shots, lead=lead, rounds=rounds, seen=seen)


def _save_trace(trace, tag):
    try:
        p = os.path.join(SHOTS, "arch2_trace_%s.csv" % tag)
        with open(p, "w", encoding="utf-8") as f:
            f.write("t,x,round,phase\n")
            for t, x, r, ph in trace:
                f.write("%.4f,%d,%d,%s\n" % (t, x, r, ph))
    except OSError:
        pass


# ---------------------------------------------------------------- 실행
def run(env=None, say=log):
    """양궁 화면에서 한 판. 'done' / 'already'(시작 버튼 없음) / 'timeout' / 'nocam'(fastcam 실패)"""
    own = env is None
    if own:
        try:
            env = FastEnv()
        except Exception as e:
            say("fastcam 시작 실패: %r" % (e,))
            return "nocam"
    trace = []
    try:
        tpl = _tpl("arch_target.png")
        if tpl is None:
            say("tpl\\arch_target.png 가 없습니다")
            return "notpl"
        g = env.grab()
        if g is None or not start_visible(g[1]):
            say("게임 시작 버튼이 안 보임 (오늘 이미 했거나 다른 화면)")
            return "already"
        env.tap(START)
        say("게임 시작 버튼 클릭")
        lead0 = LEAD0
        try:                                             # patch213: 지난 판 마지막 LEAD 부터 (1라운드가 첫 추정값 차이로 6점 나던 것)
            v = float(open(LEAD_F, encoding="utf-8").read().strip())
            if 0.6 < v < 0.8:
                lead0 = v
        except Exception:
            pass
        res = play(env, tpl, lead=lead0, say=say, trace=trace)
        try:
            if res.get("result") == "done" and 0.6 < res["lead"] < 0.8:
                with open(LEAD_F, "w", encoding="utf-8") as f:
                    f.write("%.3f" % res["lead"])
        except Exception:
            pass
        say("결과: %s / 쏜 횟수 %d / 최종 LEAD %.3f / 라운드 %s" % (res["result"], res["shots"], res["lead"], res["rounds"]))
        if res["result"] == "done":
            env.sleep(0.8)
            env.tap(RES_OK)
            env.sleep(1.0)
        return res["result"]
    finally:
        _save_trace(trace, time.strftime("%m%d_%H%M%S"))
        if own:
            env.close()


def replay(path):
    """녹화 영상으로 예측 시험: 발사한 순간의 '예측 가운데 도착 시각'과 영상에서 실제로 가운데를 지난 시각을 비교"""
    tpl = _tpl("arch_target.png")
    env = VideoEnv(path)
    trace = []
    msgs = []
    res = play(env, tpl, say=lambda *a: msgs.append(" ".join(str(x) for x in a)), trace=trace,
               calibrate=False)     # 영상 속 화살은 우리가 쏜 게 아니므로 보정하지 않음
    env.close()
    for m in msgs:
        log("[영상] " + m)
    # 실제 가운데 통과 시각 (영상 전체를 보고 계산)
    by_round = {}
    for t, x, r, ph in trace:
        if x >= 0 and r > 0:
            by_round.setdefault(r, []).append((t, x))
    for r in sorted(by_round):
        fit = robust_fit(by_round[r])
        if not fit:
            continue
        v, t0, x0 = fit
        tc = t0 + (x0 - CENTER_X) / v
        tap = [t for t, p in env.taps if p == SHOOT and t0 - 0.1 <= t <= tc + 0.5]
        if tap:
            hit_t = tap[0] + res["lead"]
            log("[영상] 라운드 %d: 속도 %.0f, 실제 가운데 통과 %.3f초, (누른 시각 + LEAD) %.3f초 -> 차이 %+.0f ms (= %+.0f px)" % (
                r, v, tc, hit_t, (hit_t - tc) * 1000, (hit_t - tc) * v))
    log("[영상] 끝. 과녁 폭은 약 120px 이라 차이가 ±50px 안이면 맞는 것으로 봄")


def look():
    env = FastEnv()
    try:
        g = env.grab()
        img = g[1]
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, "arch2_look.png"), img)
        tpl = _tpl("arch_target.png")
        x = find_target(img, tpl) if tpl is not None else None
        log("양궁 제목 %.2f / 시작 버튼 %s / 결과 팝업 %s / 과녁 x=%s (shots\\arch2_look.png)" % (
            title_score(img), start_visible(img), result_visible(img), x))
    finally:
        env.close()


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["look"]:
        look()
    elif a[:2] == ["play", "go"]:
        log("결과:", run())
    elif a[:1] == ["replay"] and len(a) >= 2:
        replay(a[1])
    else:
        print(__doc__)
