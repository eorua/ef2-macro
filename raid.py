"""raid.py - 길드레이드 보스 전투 / 연습 (patch168, 사용자가 필요할 때 직접 실행)
  py raid.py go             실제 [전투] 한 판
  py raid.py go practice    [연습] 한 판
  py raid.py go practice 3  [연습] 세 판 연속
  py raid.py look           지금 화면의 스킬 버튼 상태만 출력

어느 화면에서 시작해도 됨: 보스 상세(연습/전투 버튼) -> 그대로, 보스 목록 -> 맨 위 보스 [전투],
그 밖 -> 길드 -> 퀘스트 탭 -> 길드레이드 줄(글자로 찾음) -> 보스 목록
전투 중 (사용자 지정): 조이스틱 안 건드림 / 1번 스킬 안 누름 / 2·3·4번은 셋 다 준비되면 같이 / 5번은 될 때마다
끝: '시간 종료' 창의 총 데미지를 로그에 남기고 [확인]
"""
import os, re, sys, time
import cv2, numpy as np
import daily

SKILL_TAP = [(77, 1222), (213, 1222), (349, 1222), (483, 1222), (619, 1222)]   # 아래 영웅 스킬 칸 (그림 쪽)
SKILL_NUM = [112, 248, 384, 518, 654]        # 칸 오른쪽 쿨타임 숫자 원 가운데 x
SKILL_Y = 1222
BOSS_FIGHT = (625, 479)                       # 보스 목록 맨 위 [전투]
DETAIL_PRACTICE = (622, 557)                  # 보스 상세 [연습]
DETAIL_FIGHT = (469, 1234)                    # 보스 상세 [전투]
END_OK_ROI = (250, 800, 470, 875)             # '시간 종료' 창 초록 [확인]
END_OK = (360, 837)
LOGF = os.path.join(daily.SHOTS, "raid_log.txt")
# patch173: 발리스타 (2번 폭풍의 하피 / 5번 고대 용기사) - '약점 노출!' 이 뜨면 초록 게이지 발리스타를 눌러 붉은 원에 대고 뗌
# patch174: 화면이 1번 유닛을 따라 움직여 발리스타 위치가 바뀜 -> 발리스타 아래 게이지 막대(초록=발사 가능)를 찾아서 씀
BALLISTA_DY = -60                             # 게이지 막대 가운데 -> 발리스타 몸통
WEAK_TPL = os.path.join(r"C:\macro\tpl", "raid_weak.png")         # '약점 노출!' 빨간 글자 모양
WEAK_DY = 185                                 # 글자 가운데 -> 붉은 원 가운데 (글자가 처음 뜬 순간 기준, 실측 +188)
GO = False


def log(*a):
    s = time.strftime("[%H:%M:%S] raid: ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    try:
        with open(LOGF, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except OSError:
        pass


def cap():
    return daily.cap()


def tap(pt, wait=0.8):
    if GO:
        daily.tap(pt, wait)
    else:
        log("[시험] 누를 곳", pt)


def tap_many(pts):
    if not GO:
        log("[시험] 같이 누를 곳", pts)
        return
    cmd = "; ".join("input tap %d %d &" % p for p in pts) + " wait"
    daily.adb("shell", cmd)


def words(img):
    try:
        import ocrx
        return ocrx.words(img) or []
    except Exception:
        return []


def find(ws, key, box=None):
    for t, x, y, w, h in ws:
        if key in t and (box is None or (box[0] <= x <= box[2] and box[1] <= y <= box[3])):
            return (x, y)
    return None


# ---------------------------------------------------------------- 스킬 버튼 상태
def skill_state(img, i):
    """'cd'(쿨타임: 어두운 원 + 흰 숫자) / 'ready'(숫자 없음) / '?'(가려짐 등)"""
    cx = SKILL_NUM[i]
    c = cv2.cvtColor(img[SKILL_Y - 15:SKILL_Y + 15, cx - 15:cx + 15], cv2.COLOR_BGR2HSV)
    v, s = c[..., 2], c[..., 1]
    dark = float((v < 70).mean())
    white = float(((v > 200) & (s < 60)).mean())
    if dark >= 0.5 and white >= 0.03:
        return "cd"
    if 0.05 <= dark < 0.45:                  # 쿨타임 원(어두움)이 없음 -> 준비 (5번은 준비돼도 흰 표시가 조금 있음)
        return "ready"
    return "?"


_wt = []


def _rmask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((((h <= 10) | (h >= 170)) & (s > 120) & (v > 150)) * 255).astype(np.uint8)


def weak_text(img):
    """'약점 노출!' 글자 가운데 (x, y). 없으면 None (영상 89초 동안 잘못 잡힌 것 0번)"""
    if not _wt:
        t = cv2.imread(WEAK_TPL, cv2.IMREAD_GRAYSCALE)
        _wt.append(t)
    t = _wt[0]
    if t is None:
        return None
    r = cv2.matchTemplate(_rmask(img[100:1000]), t, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    if mx < 0.55:
        return None
    return loc[0] + t.shape[1] // 2, loc[1] + 100 + t.shape[0] // 2


def weak_disk(img, wt):
    """붉은 원(반투명 주황빨강 원판) 가운데. '약점 노출!' 글자 아래쪽(좌우 150, 아래 60~300px) 에서 찾음, 없으면 None
    (하피: 글자 아래 약 190 / 타이탄: 글자 왼쪽·오른쪽 아래 70~80, 아래 120~190)"""
    hsv = cv2.cvtColor(img[100:1000], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1], hsv[..., 2]
    m = (((h <= 12) | (h >= 170)) & (s > 70) & (v > 130)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    best = None
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if 70 <= w <= 170 and 70 <= hh <= 170 and abs(w - hh) < 0.3 * max(w, hh) and a / (np.pi * w * hh / 4) >= 0.5:
            c = (int(cen[i][0]), int(cen[i][1]) + 100)
            if abs(c[0] - wt[0]) <= 150 and 60 <= c[1] - wt[1] <= 300:
                d = abs(c[0] - wt[0]) + abs(c[1] - wt[1] - 170)
                if best is None or d < best[0]:
                    best = (d, c)
    return best[1] if best else None


def weak_ring(img, wt):
    """약점 원의 흰 테두리(반지름 약 46px)를 원 찾기로. 글자 아래쪽에서. 없으면 None
    (영상 5번의 약점 모두 첫 후보가 정답 - 용암·병사에 가려진 경우 포함)"""
    x0, x1 = max(0, wt[0] - 170), min(720, wt[0] + 170)
    y0, y1 = wt[1] + 40, min(1000, wt[1] + 320)
    if x1 - x0 < 100 or y1 - y0 < 100:
        return None
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    w = (((hsv[..., 1] < 70) & (hsv[..., 2] > 200)) * 255).astype(np.uint8)
    cs = cv2.HoughCircles(cv2.GaussianBlur(w, (5, 5), 0), cv2.HOUGH_GRADIENT, 1.2, 60,
                          param1=80, param2=18, minRadius=40, maxRadius=75)
    if cs is None:
        return None
    for a, b, r in cs[0][:3]:
        if 38 <= r <= 56:
            return int(a + x0), int(b + y0)
    return None


def ready_ballistas(img):
    """화면에 다 보이는 초록 게이지 발리스타들의 몸통 위치 [(x, y)] (게이지 막대 폭 약 129px, 반쯤 가려진 것은 뺌)"""
    hsv = cv2.cvtColor(img[100:1000], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = ((h >= 45) & (h <= 80) & (s >= 120) & (v >= 120)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if 100 <= w <= 170 and 5 <= hh <= 14 and a >= 0.7 * w * hh:
            out.append((int(x + w / 2), int(y + hh / 2) + 100 + BALLISTA_DY))
    return out


def end_popup(img):
    return daily.ratio(img, END_OK_ROI, "green") >= 0.35


# ---------------------------------------------------------------- 화면 이동
def to_detail():
    """보스 상세 화면(연습/전투 버튼)까지. 성공하면 True"""
    for step in range(4):
        img = cap()
        if img is None:
            return False
        ws = words(img)
        if find(ws, "연습") and find(ws, "고속"):
            return True
        if find(ws, "남은 시간", (0, 300, 400, 450)):
            # patch172: 잡힌 보스는 '격파 완료'로 바뀌고 다음 보스 줄에만 [전투]가 생김 -> 위치 대신 글자로 찾음
            p = find(ws, "전투", (480, 400, 720, 1200))
            if p is None:
                log("보스 목록에 [전투] 버튼이 없음 (모두 격파됐거나 아직 열리지 않음)")
                return False
            log("보스 목록 -> [전투] 버튼 (y=%d)" % p[1])
            tap(p, 1.5)
            continue
        if step == 0:
            import guild
            if not guild.open_guild():
                return False
            tap(guild.TAB_Q, 1.0)
            ys = guild._raid_rows()
            log("길드레이드 줄 y =", ys[0])
            tap((guild.ROW_RAID[0], ys[0]), 1.8)
            continue
    log("보스 상세 화면을 못 찾음")
    cv2.imwrite(os.path.join(daily.SHOTS, "raid_nav.png"), cap())
    return False


# ---------------------------------------------------------------- 전투 한 판
def battle(max_sec=200):
    t0 = time.time()
    started = False
    last5 = last234 = 0.0
    AIM_LEAD = 0.45                               # 원을 본 뒤 손을 떼기까지 걸리는 시간(캡처 + 끌기 0.25초)
    n5 = n234 = nb = 0
    last_b = noted = 0.0
    prev_t = None
    while time.time() - t0 < max_sec:
        img = cap()
        if img is None:
            time.sleep(0.5)
            continue
        if end_popup(img):
            ws = words(img)
            dmg = None
            p = find(ws, "총")
            if p:
                for t, x, y, w, h in ws:
                    if abs(y - p[1]) < 20 and x > 450 and re.search(r"\d", t):
                        dmg = t
            log("전투 끝: 총 데미지 %s / 2·3·4번 %d번, 5번 %d번, 발리스타 %d번 (%.0f초)" % (dmg, n234, n5, nb, time.time() - t0))
            cv2.imwrite(os.path.join(daily.SHOTS, "raid_result.png"), img)
            tap(END_OK, 1.5)
            return True
        st = [skill_state(img, i) for i in range(5)]
        if not started:
            if sum(s == "cd" for s in st) >= 3:
                started = True
                log("전투 시작 (스킬 쿨타임 보임)")
            else:
                time.sleep(0.4)
                continue
        now = time.time()
        wt = weak_text(img)                           # patch173/174: 발리스타 (글자가 떠 있는 약 1초 동안 매 화면 다시 봄)
        if wt and now - last_b > 3.0:
            tgt = weak_ring(img, wt) or weak_disk(img, wt)
            rb = ready_ballistas(img)
            # patch175: 하피가 날아갈 때도 약점 원은 보스를 따라 움직임 -> 맞히면 바로 떨어짐(사용자). 두 화면에서 움직인 만큼 앞을 노림
            aim = None
            if tgt is not None and prev_t is not None and 0 < now - prev_t[0] < 1.0:
                dx, dy = tgt[0] - prev_t[1][0], tgt[1] - prev_t[1][1]
                dt = now - prev_t[0]
                if abs(dx) + abs(dy) < 150:              # 다른 원으로 튄 게 아니면
                    aim = (int(min(700, max(20, tgt[0] + dx / dt * AIM_LEAD))),
                           int(min(990, max(120, tgt[1] + dy / dt * AIM_LEAD))))
            prev_t = (now, tgt) if tgt else None
            if aim and rb:
                tgt = aim
                src = max(rb, key=lambda p: p[1])        # patch176: 아래쪽 발리스타가 쿨타임이 짧음(사용자) -> 둘 다 초록이면 아래쪽부터
                if GO:
                    daily.adb("shell", "input", "swipe", str(src[0]), str(src[1]), str(tgt[0]), str(tgt[1]), "250")
                last_b = now
                nb += 1
                log("약점 노출 -> 발리스타 발사 %s -> %s" % (src, tgt))
                cv2.imwrite(os.path.join(daily.SHOTS, "raid_ballista_%d.png" % min(nb, 3)), img)
            elif (not tgt or not rb) and now - noted > 3.0:
                noted = now
                log("약점 노출: 붉은 원 %s / 초록 발리스타 %s -> 이번 화면은 못 쏨" % (tgt, rb))
                cv2.imwrite(os.path.join(daily.SHOTS, "raid_noballista.png"), img)
        if st[1] == st[2] == st[3] == "ready" and now - last234 > 1.5:
            tap_many([SKILL_TAP[1], SKILL_TAP[2], SKILL_TAP[3]])
            last234 = now
            n234 += 1
        if st[4] == "ready" and now - last5 > 1.5:
            tap_many([SKILL_TAP[4]])
            last5 = now
            n5 += 1
        time.sleep(0.35)
    log("시간 안에 끝 창이 안 뜸")
    cv2.imwrite(os.path.join(daily.SHOTS, "raid_timeout.png"), cap())
    return False


def run(practice=True, n=1):
    if not to_detail():
        return False
    ok = 0
    for k in range(n):
        if k > 0 and not to_detail():
            break
        img = cap()
        ws = words(img)
        if practice:
            p = find(ws, "연습")
            log("[연습] %d/%d" % (k + 1, n))
            tap(p or DETAIL_PRACTICE, 2.0)
        else:
            p = find(ws, "전투", (300, 1150, 640, 1280))
            log("[전투]")
            tap(p or DETAIL_FIGHT, 2.0)
        if battle():
            ok += 1
        time.sleep(1.5)
    log("끝: %d판" % ok)
    return ok > 0


if __name__ == "__main__":
    a = sys.argv[1:]
    GO = "go" in a
    if "look" in a:
        img = cap()
        print("스킬:", [skill_state(img, i) for i in range(5)], "/ 끝 창:", end_popup(img))
    else:
        nums = [int(x) for x in a if x.isdigit()]
        run(practice="practice" in a, n=nums[0] if nums else 1)
