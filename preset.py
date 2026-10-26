import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
GO = "go" in sys.argv[1:]

# ---- 좌표 (720x1280, 눈금 캡처로 확인) ----
HUD_PRESET = (487, 655)          # 전투 화면의 프리셋(금색 순환 화살표) 아이콘 (patch218: 10-23 업데이트로 527→487, 옛 자리는 절전 버튼)
HUD_PRESET_ROI = (380, 580, 660, 730)   # patch218: 아이콘 그림(tpl\\hud_preset.png)을 찾는 범위
SLEEP_KNOB = (200, 822)                 # patch218: 절전 화면 '스와이프하면 복귀' 손잡이
TAB_QUEST = (68, 1240)                  # patch292: 하단 '퀘스트' 탭 (기본 대기화면)
TAB_HERO = (185, 1240)           # 하단 '영웅' 탭
BTN_PLUS = (326, 790)            # 영웅 탭의 '+' (일괄 레벨업)
# 통합 프리셋 팝업
PRE_X = (631, 150)
PRE_SAVE = (267, 1094)
PRE_CANCEL = (452, 1094)
HERO_TABS = {"기본": (115, 261), "렙뻥": (197, 261), "최대레벨": (283, 261),
             "골드": (385, 261), "한계": (482, 261)}                  # patch154: 4번째 탭 이름 '골드'
RELIC_TABS = {"기본": (113, 545), "골드 모으기": (216, 545), "영웅강화골드": (348, 545),
              "시간": (453, 545), "오픈골드 감소": (560, 545)}       # patch154: 2번째 '골드 모으기', 5번째 '오픈골드 감소'(10-18 스크린샷)
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


# ---- patch218: 프리셋 아이콘 그림 찾기 + 절전 화면 풀기 ----
_HP_TPL = None


def find_preset_icon(img):
    """전투 화면에서 금색 순환 화살표 아이콘 중심. 못 찾으면 기본 좌표"""
    global _HP_TPL
    try:
        if _HP_TPL is None:
            _HP_TPL = cv2.imread(os.path.join(BASE, "tpl", "hud_preset.png"))
        if img is not None and _HP_TPL is not None:
            x1, y1, x2, y2 = HUD_PRESET_ROI
            r = cv2.matchTemplate(img[y1:y2, x1:x2], _HP_TPL, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(r)
            if mx >= 0.7:
                th, tw = _HP_TPL.shape[:2]
                return (x1 + loc[0] + tw // 2, y1 + loc[1] + th // 2)
    except Exception as e:
        print("프리셋 아이콘 찾기 오류:", e)
    return HUD_PRESET


def is_sleep(img):
    """절전 화면(어두운 배경 + 파란 스와이프 손잡이)이면 True"""
    try:
        v = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2]
        if float(v.mean()) > 55:
            return False
        x, y = SLEEP_KNOB
        p = img[y - 10:y + 11, x - 14:x + 15].reshape(-1, 3).astype(int)
        blue = ((p[:, 0] > 110) & (p[:, 0] > p[:, 2] + 50)).mean()
        return blue > 0.3
    except Exception:
        return False


def exit_sleep(img=None):
    """절전 화면이면 손잡이를 오른쪽으로 밀어 복귀. 풀었으면 True"""
    if img is None:
        img = capture()
    if img is None or not is_sleep(img):
        return False
    print("절전 화면 감지 → 스와이프로 복귀")
    if GO:
        x, y = SLEEP_KNOB
        subprocess.run(ADB + ["shell", "input", "swipe", str(x), str(y), "620", str(y), "500"])
    time.sleep(1.5)
    return True


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


def set_presets(hero, relic, pet=None):
    """통합 프리셋 팝업에서 영웅/유물 프리셋(+대표 펫)을 고르고 저장. 성공하면 True
    patch116: relic=None 이면 유물은 그대로, pet 이 있으면 대표 펫도 교체 (펫 실패는 무시하고 진행)"""
    img = capture()
    if img is None:
        print("캡처 실패"); return False
    if bulk_open(img):
        print("일괄 레벨업 창이 열려 있어 중단"); return False
    if exit_sleep(img):                                            # patch218
        img = capture()
        if img is None:
            print("캡처 실패"); return False
    if not preset_open(img):
        tap(find_preset_icon(img), "프리셋 아이콘")
        img = wait_for(preset_open, 5.0, first=0.4, step=0.25)     # patch106
        if img is None or not preset_open(img):
            # patch213: 다른 창(펫 상세 등)이 남아 있으면 오른쪽 빨간 X 를 위에서부터 닫고 한 번 더
            closed = 0
            try:
                import ocrx
                for _ in range(4):
                    cur = capture()
                    xs = ocrx.red_x_buttons(cur) if cur is not None else []
                    if not xs or preset_open(cur):
                        break
                    tap(xs[0], "남은 창 X")
                    closed += 1
                    time.sleep(0.8)
            except Exception as e:
                print("남은 창 닫기 오류:", e)
            if closed:
                print("통합 프리셋 팝업이 안 열려 남은 창 %d개 닫고 다시 시도" % closed)
                tap(find_preset_icon(capture()), "프리셋 아이콘")
                img = wait_for(preset_open, 5.0, first=0.4, step=0.25)
            if img is None or not preset_open(img):
                print("통합 프리셋 팝업이 안 열려 중단"); return False
    cur_h, cur_r = selected(img, HERO_TABS), selected(img, RELIC_TABS)
    want_r = relic if relic is not None else cur_r
    pet_ok = True
    if pet is not None:
        try:
            import pet as _petm
            pet_ok = _petm.rep_pet(img) == pet
        except Exception as e:
            print("펫 판별 오류: %r" % (e,))
    print(f"현재 영웅={cur_h}, 유물={cur_r} / 목표 영웅={hero}, 유물={relic}" + (f", 펫={pet}" if pet else ""))
    if (hero is None or cur_h == hero) and cur_r == want_r and pet_ok:
        print("이미 목표 상태 → 취소로 닫기")
        tap(PRE_CANCEL, "취소")
        wait_for(lambda im: not preset_open(im), 2.0, first=0.2, step=0.25)     # patch106: 닫히면 바로
        return True
    if hero is not None and cur_h != hero:
        tap(HERO_TABS[hero], f"영웅 {hero}")
    if cur_r != want_r:
        tap(RELIC_TABS[want_r], f"유물 {want_r}")
    img = wait_for(lambda im: (hero is None or selected(im, HERO_TABS) == hero) and selected(im, RELIC_TABS) == want_r, 4.0, first=0.25, step=0.25)     # patch106
    if img is None or (hero is not None and selected(img, HERO_TABS) != hero) or selected(img, RELIC_TABS) != want_r:
        print("탭 선택 확인 실패 → 취소로 닫고 중단")
        cur = capture()
        if cur is not None and preset_open(cur):      # 팝업이 아직 열려 있을 때만 취소 (닫혀 있으면 뒤의 영웅 목록이 눌림)
            tap(PRE_CANCEL, "취소")
        else:
            print("  (팝업이 이미 닫혀 있어 취소는 누르지 않음)")
        return False
    if not pet_ok:                                   # patch116: 대표 펫 교체
        try:
            import pet as _petm
            pet_ok = _petm.select(pet)
        except Exception as e:
            print("펫 교체 오류: %r" % (e,))
        if not pet_ok:
            print(f"대표 펫 {pet} 교체 실패 -> 펫은 그대로")
            if (hero is None or cur_h == hero) and cur_r == want_r:
                tap(PRE_CANCEL, "취소")
                wait_for(lambda im: not preset_open(im), 2.0, first=0.2, step=0.25)
                return False
    tap(PRE_SAVE, "저장")
    img = wait_for(lambda im: not preset_open(im), 5.0, first=0.4, step=0.3)     # patch106
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


def _btn_x(i):
    return BULK_BTNS[i][1][0]


def btn_active(img, i):
    """일괄 레벨업 버튼이 갈색(누를 수 있음)이면 True, 회색(골드 부족)이면 False"""
    x = _btn_x(i)
    hsv = cv2.cvtColor(img[1116:1124, x - 55:x + 55], cv2.COLOR_BGR2HSV)
    return float(np.median(hsv[..., 1])) >= 60


def cost_is_zero(img, i):
    """버튼 아래 비용 글자가 '0' 한 글자뿐이면 True (올릴 레벨이 없음)"""
    x = _btn_x(i)
    hsv = cv2.cvtColor(img[1148:1174, x - 55:x + 60], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 2] > 190) & (hsv[..., 1] < 110)
    n = int((m.sum(axis=0) >= 2).sum())
    return 4 <= n <= 12


def levels_maxed(img):
    """체크된 영웅이 모두 최대 레벨이면 True (+1 버튼 비용이 0)"""
    return cost_is_zero(img, 3)


LAST_MAXED = False      # patch116: 마지막 일괄 레벨업이 '모든 영웅 최대 레벨'로 끝났는지

# ---- patch139: 영웅 탭 AUTO (자동 레벨업) 로 일괄 레벨업 대체 ----
USE_HERO_AUTO = True
HERO_AUTO = (131, 778)              # 영웅 탭 '영웅 !' 옆 • AUTO
HERO_AUTO_ROI = (106, 768, 158, 790)
HERO_AUTO_SEC = 3.0                 # 켜 두는 시간


def _auto_crop(img):
    x1, y1, x2, y2 = HERO_AUTO_ROI
    return img[y1:y2, x1:x2].astype(np.float32)


def hero_auto_on(img):
    """AUTO 가 켜져 있으면(글자/점이 색깔) True. 꺼짐은 회색"""
    x1, y1, x2, y2 = HERO_AUTO_ROI
    h = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    return int(((h[..., 1] > 90) & (h[..., 2] > 140)).sum()) >= 15


def _shot(name, img):
    try:
        os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
        cv2.imwrite(os.path.join(BASE, "shots", name), img)
    except Exception:
        pass


def auto_levelup(sec=None):
    """AUTO 켜기 -> 3초 -> 끄기. 성공 True / AUTO 버튼이 반응 없음 None(예전 방식으로) / 끄기 실패 False"""
    global LAST_MAXED
    LAST_MAXED = False
    tap(TAB_HERO, "영웅 탭")
    time.sleep(0.8)
    img = capture()
    if img is None:
        return None
    if hero_auto_on(img):                            # 혹시 켜져 있으면 먼저 끔
        print("  영웅 AUTO 가 이미 켜져 있음 -> 먼저 끔")
        tap(HERO_AUTO, "영웅 AUTO 끄기")
        time.sleep(0.8)
        img = capture()
        if img is None or hero_auto_on(img):
            _shot("hero_auto_fail.png", img if img is not None else np.zeros((10, 10, 3), np.uint8))
            return False
    ref = _auto_crop(img)
    turned = False
    for k in range(2):
        tap(HERO_AUTO, "영웅 AUTO 켜기")
        t_on = time.time()
        time.sleep(0.6)
        img = capture()
        if img is not None and (hero_auto_on(img) or float(np.abs(_auto_crop(img) - ref).mean()) > 6):
            turned = True
            break
    if not turned:
        print("  영웅 AUTO 를 눌러도 변화 없음 -> 예전 방식(+ 버튼)으로")
        if img is not None:
            _shot("hero_auto_nochange.png", img)
        return None
    if img is not None and not hero_auto_on(img):
        _shot("hero_auto_on_look.png", img)          # 켜짐 모양이 예상(색깔)과 다르면 기록
    sec = HERO_AUTO_SEC if sec is None else sec
    time.sleep(max(0.0, sec - (time.time() - t_on)))
    for k in range(3):
        tap(HERO_AUTO, "영웅 AUTO 끄기")
        time.sleep(0.7)
        img = capture()
        if img is not None and float(np.abs(_auto_crop(img) - ref).mean()) <= 6 and not hero_auto_on(img):
            print("영웅 AUTO 레벨업 완료 (%.0f초)" % sec)
            return True
    print("  영웅 AUTO 가 안 꺼짐! (shots\\hero_auto_fail.png)")
    if img is not None:
        _shot("hero_auto_fail.png", img)
    return False


def bulk_levelup(max_rounds=3, max_press=40):
    try:
        if USE_HERO_AUTO:
            r = auto_levelup()
            if r is not None:
                return r
        return _bulk_levelup_old(max_rounds, max_press)
    finally:
        tap(TAB_QUEST, "퀘스트 탭 복귀")


def _bulk_levelup_old(max_rounds=3, max_press=40):
    global LAST_MAXED
    LAST_MAXED = False
    tap(TAB_HERO, "영웅 탭")
    time.sleep(0.6)                                  # patch106: 1.0 -> 0.6
    tap(BTN_PLUS, "+")
    img = wait_for(bulk_open, 5.0, first=0.4, step=0.25)
    if img is None or not bulk_open(img):
        print("일괄 레벨업 창이 안 열려 중단"); return False
    for _ in range(3):
        if all_checked(img):
            break
        tap(BULK_ALL, "전체 선택(1)")
        time.sleep(0.4)
        tap(BULK_ALL, "전체 선택(2)")
        img = wait_for(all_checked, 1.5, first=0.25, step=0.2)     # patch106: 체크되면 바로
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
    maxed = False
    for rnd in range(1, max_rounds + 1):
        pressed_round = False
        for i, (name, pt) in enumerate(BULK_BTNS):
            presses = 0
            still = 0
            before = None
            zero = 0
            why = "한도"
            for k in range(max(max_press, 300) // BURST):
                now = capture()
                if now is None or not bulk_open(now):
                    print("일괄 레벨업 창 상태 이상 → 중단"); return False
                if levels_maxed(now):
                    zero += 1
                    if zero == 1:
                        print("  비용이 0으로 보이지만 한 번 눌러서 확인 (shots\\bulk_zero.png 저장)")
                        try:
                            os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
                            cv2.imwrite(os.path.join(BASE, "shots", "bulk_zero.png"), now)
                        except Exception:
                            pass
                    if zero >= 2 and before is not None and float(np.abs(level_crop(now) - before).mean()) <= thr:
                        maxed = True
                        why = "모든 영웅 최대 레벨(눌러 봐도 변화 없음)"
                        break
                if not btn_active(now, i):
                    why = "골드 부족(회색)"
                    break
                cur = level_crop(now)
                if before is not None:
                    if float(np.abs(cur - before).mean()) > thr:
                        still = 0
                    else:
                        still += 1
                        if still >= 3:                 # 눌러도 안 오름(렉 등) -> 안전장치
                            why = "변화 없음"
                            break
                before = cur
                tap_burst(pt, name, BURST)
                presses += BURST
                pressed_round = True
                time.sleep(0.25)
            print(f"  라운드 {rnd} {name}: {presses}회 눌러 종료 ({why})")
            if maxed:
                break
        if maxed or not pressed_round:
            break
        _now = capture()                                 # patch135: 네 버튼이 다 회색(골드 부족)이면 다음 라운드 없이 끝
        if _now is not None and not any(btn_active(_now, j) for j in range(len(BULK_BTNS))):
            print("  모든 버튼이 회색(골드 부족) -> 라운드 %d 에서 끝" % rnd)
            break
    LAST_MAXED = maxed
    tap(BULK_X, "X")
    img = wait_for(lambda im: not bulk_open(im), 2.5, first=0.3, step=0.25)     # patch106: 닫히면 바로
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
        set_presets(None if args[1] in ('-', '유지') else args[1], args[2])
    elif cmd == "bulk":
        bulk_levelup()
    elif cmd == "high":
        cycle_high()
    elif cmd == "low":
        cycle_low()
    else:
        print("사용법: py preset.py read | set 영웅 유물 go | bulk go | high go | low go")