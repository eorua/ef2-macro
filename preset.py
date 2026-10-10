import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]
GO = "go" in sys.argv[1:]

# ---- 좌표 (720x1280, 눈금 캡처로 확인) ----
HUD_PRESET = (527, 660)          # 전투 화면의 프리셋(금색 순환 화살표) 아이콘
TAB_HERO = (185, 1240)           # 하단 '영웅' 탭
BTN_PLUS = (326, 790)            # 영웅 탭의 '+' (일괄 레벨업)
# 통합 프리셋 팝업
PRE_X = (631, 150)
PRE_SAVE = (267, 1094)
PRE_CANCEL = (452, 1094)
HERO_TABS = {"기본": (115, 261), "렙뻥": (197, 261), "최대레벨": (283, 261),
             "드루최대렙": (385, 261), "한계": (482, 261)}
RELIC_TABS = {"기본": (113, 545), "성체력뻥튀기": (218, 545), "영웅강화골드": (348, 545),
              "시간": (453, 545), "엘프": (535, 545)}
# 일괄 레벨업 팝업
BULK_X = (631, 525)
BULK_ALL = (90, 583)
BULK_BTNS = [("+1000", (145, 1135)), ("+100", (287, 1135)), ("+10", (430, 1135)), ("+1", (574, 1135))]
CHECK_X = 103
CHECK_YS = [627 + 47 * i for i in range(10)]
LEVEL_ROI = (520, 600, 650, 1080)   # x1, y1, x2, y2 : 영웅 레벨(Lv.NNNN) 열


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    if not png:
        return None
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def tap(pt, label=""):
    print(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{label} {pt}")
    if GO:
        subprocess.run(ADB + ["shell", "input", "tap", str(pt[0]), str(pt[1])])


def red_ratio(img, c, r=14):
    x, y = c
    hsv = cv2.cvtColor(img[y - r:y + r + 1, x - r:x + r + 1], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 150, 120), (8, 255, 255)) | cv2.inRange(hsv, (172, 150, 120), (180, 255, 255))
    return float(m.mean()) / 255.0


def preset_open(img):
    return red_ratio(img, PRE_X) > 0.1


def bulk_open(img):
    return red_ratio(img, BULK_X) > 0.1


def orange_count(img, c, hw=30, hh=12):
    x, y = c
    hsv = cv2.cvtColor(img[y - hh:y + hh + 1, x - hw:x + hw + 1], cv2.COLOR_BGR2HSV)
    return int(cv2.inRange(hsv, (10, 150, 200), (25, 255, 255)).sum() / 255)


def selected(img, tabs):
    """주황 글씨가 가장 많은 탭 이름 (없으면 None)"""
    best = max(tabs, key=lambda k: orange_count(img, tabs[k]))
    return best if orange_count(img, tabs[best]) >= 40 else None


def checked(img, y, r=9):
    hsv = cv2.cvtColor(img[y - r:y + r + 1, CHECK_X - r:CHECK_X + r + 1], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 120, 150), (14, 255, 255)) | cv2.inRange(hsv, (172, 120, 150), (180, 255, 255))
    return float(m.mean()) / 255.0 > 0.15


def all_checked(img):
    return all(checked(img, y) for y in CHECK_YS)


def level_crop(img):
    x1, y1, x2, y2 = LEVEL_ROI
    return cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY).astype(np.int16)


def snap(wait=0.5):
    time.sleep(wait)
    return capture()


def wait_for(cond, timeout=4.0, first=0.5, step=0.4):
    """first 초 쉰 뒤, 조건이 맞을 때까지 timeout 초 동안 화면을 다시 확인 (렉이 있어도 기다려 줌). 마지막 화면을 돌려줌"""
    time.sleep(first)
    t0 = time.monotonic()
    img = capture()
    while time.monotonic() - t0 < timeout:
        try:
            if img is not None and cond(img):
                return img
        except Exception:
            pass
        time.sleep(step)
        nxt = capture()
        if nxt is not None:
            img = nxt
    return img


def read_state():
    img = capture()
    if img is None:
        print("캡처 실패 (ADB 연결 확인)")
        return None
    print("통합 프리셋 팝업:", "열림" if preset_open(img) else "닫힘",
          "| 일괄 레벨업 팝업:", "열림" if bulk_open(img) else "닫힘")
    if preset_open(img):
        print("  영웅 프리셋 선택:", selected(img, HERO_TABS), "| 유물 프리셋 선택:", selected(img, RELIC_TABS))
    if bulk_open(img):
        print("  전체 선택 상태:", "모두 체크됨" if all_checked(img) else "체크 안 된 항목 있음")
    return img


def set_presets(hero, relic):
    """통합 프리셋 팝업에서 영웅/유물 프리셋을 고르고 저장. 성공하면 True"""
    img = capture()
    if img is None:
        print("캡처 실패"); return False
    if bulk_open(img):
        print("일괄 레벨업 창이 열려 있어 중단"); return False
    if not preset_open(img):
        tap(HUD_PRESET, "프리셋 아이콘")
        img = wait_for(preset_open, 5.0, first=0.8)
        if img is None or not preset_open(img):
            print("통합 프리셋 팝업이 안 열려 중단"); return False
    cur_h, cur_r = selected(img, HERO_TABS), selected(img, RELIC_TABS)
    print(f"현재 영웅={cur_h}, 유물={cur_r} / 목표 영웅={hero}, 유물={relic}")
    if cur_h == hero and cur_r == relic:
        print("이미 목표 상태 → 취소로 닫기")
        tap(PRE_CANCEL, "취소")
        time.sleep(1.0)
        return True
    if cur_h != hero:
        tap(HERO_TABS[hero], f"영웅 {hero}")
    if cur_r != relic:
        tap(RELIC_TABS[relic], f"유물 {relic}")
    img = wait_for(lambda im: selected(im, HERO_TABS) == hero and selected(im, RELIC_TABS) == relic, 4.0, first=0.5)
    if img is None or selected(img, HERO_TABS) != hero or selected(img, RELIC_TABS) != relic:
        print("탭 선택 확인 실패 → 취소로 닫고 중단")
        tap(PRE_CANCEL, "취소")
        return False
    tap(PRE_SAVE, "저장")
    img = wait_for(lambda im: not preset_open(im), 5.0, first=1.0)
    if img is not None and preset_open(img):
        print("저장 후에도 팝업이 열려 있음 → 취소")
        tap(PRE_CANCEL, "취소")
        return False
    print("프리셋 저장 완료")
    return True


BURST = 10        # 한 번에 연속으로 누르는 횟수 (확인 사이클당)
BURST_GAP = 0.1   # 연타 시작 간격(초). 렉이 심하면 0.2 로


def tap_burst(pt, label, n):
    print(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{label} {pt} x{n}")
    if GO:
        x, y = pt
        one = f"input tap {x} {y} & sleep {BURST_GAP}"
        cmd = "; ".join([one] * n) + "; wait"
        subprocess.run(ADB + ["shell", cmd])


def bulk_levelup(max_rounds=3, max_press=40):
    tap(TAB_HERO, "영웅 탭")
    time.sleep(1.0)
    tap(BTN_PLUS, "+")
    img = wait_for(bulk_open, 5.0, first=0.8)
    if img is None or not bulk_open(img):
        print("일괄 레벨업 창이 안 열려 중단"); return False
    for _ in range(3):
        if all_checked(img):
            break
        tap(BULK_ALL, "전체 선택(1)")
        time.sleep(0.4)
        tap(BULK_ALL, "전체 선택(2)")
        img = snap(0.6)
        if img is None:
            return False
    if not all_checked(img):
        print("전체 선택 실패 → 닫고 중단")
        tap(BULK_X, "X")
        return False
    a = level_crop(snap(0.3)); b = level_crop(snap(0.3))
    noise = float(np.abs(a - b).mean())
    thr = max(0.25, noise * 3 + 0.1)
    print(f"변화 판단 기준: {thr:.2f}")
    for rnd in range(1, max_rounds + 1):
        changed_round = False
        for name, pt in BULK_BTNS:
            before = level_crop(capture())
            presses = 0
            for k in range(max_press // BURST):
                tap_burst(pt, name, BURST)
                presses += BURST
                time.sleep(0.25)
                now = capture()
                if now is None or not bulk_open(now):
                    print("일괄 레벨업 창 상태 이상 → 중단"); return False
                cur = level_crop(now)
                diff = float(np.abs(cur - before).mean())
                before = cur
                if diff > thr:
                    changed_round = True
                else:
                    break
            print(f"  라운드 {rnd} {name}: {presses}회 눌러 종료")
        if not changed_round:
            break
    tap(BULK_X, "X")
    img = snap(1.0)
    if img is not None and bulk_open(img):
        print("X를 눌렀는데도 창이 열려 있음"); return False
    print("일괄 레벨업 완료")
    return True


def cycle_high():
    return (set_presets("최대레벨", "영웅강화골드") and bulk_levelup()
            and set_presets("렙뻥", "기본"))


def cycle_low():
    return set_presets("기본", "시간")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "go"]
    cmd = args[0] if args else "read"
    if cmd == "read" or not GO:
        read_state()
        if cmd != "read":
            print("(시험 모드: 아무것도 누르지 않았습니다. 실제 실행은 맨 끝에 go 를 붙이세요)")
    elif cmd == "set" and len(args) >= 3:
        set_presets(args[1], args[2])
    elif cmd == "bulk":
        bulk_levelup()
    elif cmd == "high":
        cycle_high()
    elif cmd == "low":
        cycle_low()
    else:
        print("사용법: py preset.py read | set 영웅 유물 go | bulk go | high go | low go")