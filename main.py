import sys, os, time, json, subprocess, datetime

import cv2
import speed          # 대기시간 단축 (speed.py 의 FACTOR 로 조절)
import rebirth, wave, preset, recruit, bsrestart, activate, daily
import notice

BASE = r"C:\macro"
GO = "go" in sys.argv[1:]
STATE_FILE = os.path.join(BASE, "state.json")
LOG_FILE = os.path.join(BASE, "macro.log")
PAUSE_FILE = os.path.join(BASE, "PAUSE")      # 이 파일을 만들면 일시정지 (지우면 재개)
HIGH_WAVE = 6200                               # 이 웨이브 이상이면 최대레벨 단계 시작
LOOP_SEC = 1.5
MID_WAVE = 5000                                # 이 웨이브 이상이면 (고레벨 전에) 중간 영웅 업그레이드 1회
RECRUIT_OK_SEC = 3700                          # 영입 성공 후 다음 시도까지
RECRUIT_RETRY_SEC = 600                        # 쿨타임이라 못 했을 때 재시도 간격
MAX_HIGH_FAILS = 3
ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]
PKG = "com.ekkorr.ef2"
ACTIVITY = "com.ekkorr.ef2/com.ekkorr.ef2.MainActivity"
RESTART_HOURS = 6                              # 이 시간마다 게임을 재시작
FOCUS_CHECK_SEC = 10                           # 게임이 떠 있는지 확인하는 간격
FOCUS_FAIL_LIMIT = 6                           # 이 횟수 연속 게임이 아니면 튕김으로 판단
RECOVER_TIMEOUT = 300                          # 재시작 후 복귀를 기다리는 최대 시간(초)
MAX_RECOVER_FAILS = 3

# ---- 정체 시 직접 환생 ----
STUCK_SEC = 180                   # 같은 웨이브에서 이 시간(초) 이상 안 오르면 환생
STUCK_MIN_WAVE = HIGH_WAVE        # 이 웨이브 이상일 때만 동작
ANGEL = (47, 192)                 # 좌상단 천사(환생) 버튼
ASK_TITLE = (0.30, 0.19, 0.70, 0.27)   # '환생하기' 창 제목 위치(비율)
ASK_GREEN = (0.15, 0.48, 0.44, 0.60)   # 왼쪽 초록 '환생' 버튼 위치(비율) - 오른쪽 빨간(보석 500) 버튼은 제외

# 자동으로 닫을 팝업 목록: (이름, 제목 그림, 제목 영역, 버튼 그림, 버튼 영역)
POPUPS = [
    ("출석 보상", "title_attendance.png", (0.30, 0.03, 0.70, 0.09), "btn_attendance.png", (0.20, 0.56, 0.80, 0.66)),
    ("오프라인 전투", "title_offline.png", (0.25, 0.19, 0.75, 0.26),
     "btn_offline_ok.png", (0.25, 0.52, 0.75, 0.62)),
]


class Abort(Exception):
    pass


def log(msg):
    line = datetime.datetime.now().strftime("%H:%M:%S ") + msg
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state():
    st = {"high_done": False, "need_low": False, "last_recruit": 0, "next_recruit": 0, "high_fails": 0, "last_restart": 0}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            st.update(json.load(f))
    except Exception:
        pass
    return st


def save_state(st):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"state 저장 실패: {e}")


def cap():
    return wave.capture()


def opt_on(name):
    """settings.json (조작 패널의 옵션 탭에서 켜고 끔) 에서 옵션을 읽음. 없으면 꺼짐"""
    try:
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            return bool(json.load(f).get(name, False))
    except Exception:
        return False


_cont_hist = []          # 이어하기를 누른 시각들


def continue_btn(img):
    """성 함락 팝업 오른쪽의 초록 '이어하기' 버튼. 색으로 판별하며 회색(하트 없음)이면 False"""
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(0.71 * W), int(0.52 * H), int(0.89 * W), int(0.56 * H)
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    frac = float(((h > 35) & (h < 90) & (s > 100) & (v > 100)).mean())
    return frac >= 0.5, (int(0.80 * W), int(0.54 * H)), frac


def fall_popup(img):
    ts, _ = rebirth.match(img, "title_fall.png", rebirth.FALL_TITLE)
    gs, (gx, gy) = rebirth.match(img, "btn_green.png", rebirth.FALL_GREEN)
    ok = ts >= 0.85 and gs >= 0.90 and gx < 0.29 * img.shape[1]
    return ok, (gx, gy)


def result_popup(img):
    ts, _ = rebirth.match(img, "title_result.png", rebirth.RES_TITLE)
    bs, (bx, by) = rebirth.match(img, "btn_confirm.png", rebirth.RES_CONFIRM)
    return (ts >= 0.85 and bs >= 0.90), (bx, by)


def blocked_by_rebirth_popup():
    img = cap()
    if img is None:
        return False
    return fall_popup(img)[0] or result_popup(img)[0]


# ---- 안전장치: 모든 클릭 직전에 환생 팝업이 떠 있는지 확인 (빨간 환생 버튼 오클릭 방지) ----
_orig_preset_tap = preset.tap
_orig_recruit_tap = recruit.tap


def _guard():
    if blocked_by_rebirth_popup():
        raise Abort("환생 팝업이 떠서 동작 중단")


def safe_preset_tap(pt, label=""):
    _guard()
    _orig_preset_tap(pt, label)


def safe_recruit_tap(name):
    _guard()
    _orig_recruit_tap(name)


preset.tap = safe_preset_tap
recruit.tap = safe_recruit_tap


def _cap_safe():
    for _ in range(5):
        img = cap()
        if img is not None:
            return img
        time.sleep(1)
    raise Abort("캡처 실패")


rebirth.capture = _cap_safe


def adb_reconnect():
    log("ADB 재연결 시도")
    subprocess.run([r"C:\platform-tools\adb.exe", "connect", "127.0.0.1:5585"], capture_output=True)


def popup_open(img):
    return preset.preset_open(img) or preset.bulk_open(img)


def run_cycle_mid():
    """중간 영웅 업그레이드: 최대레벨 프리셋으로 일괄 레벨업 후 기본/시간으로 복귀"""
    ok = preset.set_presets("최대레벨", "영웅강화골드")
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = preset.set_presets("기본", "시간")
    return bulk_ok and final_ok


def _barracks_fallback(why):
    """병영 편성이 중간에 실패하면 영웅 기본 프리셋으로 되돌림 (편성이 어중간하게 남지 않게)"""
    log("병영 편성 실패: %s -> 영웅 기본 프리셋으로 복구" % why)
    try:
        preset.set_presets("기본", "기본")
    except Abort:
        raise
    except Exception as e:
        log("복구 중 오류: %r" % (e,))
    return False


def _retry_step(name, fn, *a, **k):
    """한 단계를 실행하고, 실패하면 열려 있는 창을 닫은 뒤 한 번 더 시도"""
    import closer
    if fn(*a, **k):
        return True
    n = closer.close_all()
    log("%s 실패 -> 열린 창 %d개 닫고 한 번 더 시도" % (name, n))
    return bool(fn(*a, **k))


def run_cycle_barracks():
    """병영 편성 방식 고레벨 단계 (패널 옵션 barracks_swap)"""
    import barracks, closer
    closer.close_all()                      # 시작 전에 남아 있는 창이 있으면 정리
    if not _retry_step("골렘 편성(1단계)", barracks.phase1):
        return _barracks_fallback("골렘 편성(1단계)")
    if not _retry_step("유물 프리셋 변경", preset.set_presets, None, "영웅강화골드"):
        return _barracks_fallback("유물 프리셋 변경")
    if not _retry_step("일괄 레벨업", preset.bulk_levelup, max_rounds=1):
        return _barracks_fallback("일괄 레벨업")
    if not _retry_step("최종 편성(2단계)", barracks.phase2):
        return _barracks_fallback("최종 편성(2단계)")
    for _ in range(3):
        if preset.set_presets(None, "기본"):
            return True
        closer.close_all()
        time.sleep(2)
    log("최종 유물 프리셋(기본) 설정 실패 -> 다음 기회에 재시도")
    return False


def run_cycle_high():
    if opt_on("barracks_swap"):
        return run_cycle_barracks()
    ok = preset.set_presets("최대레벨", "영웅강화골드")
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = preset.set_presets("렙뻥", "기본")
    return bulk_ok and final_ok


def adb_out(args):
    try:
        r = subprocess.run(ADB + args, capture_output=True, text=True, timeout=30)
        return r.stdout
    except Exception as e:
        log(f"ADB 오류: {e!r}")
        return ""


def game_in_focus():
    """True=게임이 앞에 있음 / False=확실히 다른 화면 / None=확인 실패(렉·타임아웃·전환 중, 판단 보류)"""
    out = adb_out(["shell", "dumpsys window | grep mCurrentFocus"])
    if "mCurrentFocus" not in out:
        return None
    if PKG in out:
        return True
    if "mCurrentFocus=null" in out:
        return None
    return False


def wave_visible(img):
    """화면에 웨이브 숫자가 읽히면 게임 화면으로 본다 (포커스 확인이 틀렸을 때의 보조 확인)"""
    try:
        return wave.read_wave(img) is not None
    except Exception:
        return False


def launch_game():
    log("게임 실행")
    adb_out(["shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1"])


def adb_alive(tries=1):
    """ADB 로 접속되고 안드로이드 부팅이 끝났는지. 실패하면 이유를 로그에 남김"""
    for i in range(tries):
        try:
            c = subprocess.run([r"C:\platform-tools\adb.exe", "connect", "127.0.0.1:5585"],
                               capture_output=True, text=True, timeout=15)
            r = subprocess.run(ADB + ["shell", "getprop", "sys.boot_completed"],
                               capture_output=True, text=True, timeout=15)
            if r.stdout.strip() == "1":
                return True
            why = (c.stdout + c.stderr + r.stdout + r.stderr).strip().replace("\n", " ")[:120]
        except Exception as e:
            why = repr(e)
        log("ADB 확인 실패 (%d/%d): %s" % (i + 1, tries, why))
        if i < tries - 1:
            time.sleep(4)
    return False


def restart_bluestacks_full():
    """오환2 BlueStacks 자체를 껐다 켜고 게임까지 실행"""
    log("BlueStacks(오환2) 재시작")
    if not bsrestart.restart_bluestacks():
        log("BlueStacks 재시작 실패")
        return False
    time.sleep(10)
    launch_game()
    return True


def _bs_window():
    """오환2 BlueStacks 창이 떠 있으면 True (확인이 안 되면 건드리지 않도록 True)"""
    try:
        pids = bsrestart.find_pids()
    except Exception as e:
        log("오환2 창 확인 오류: %r -> 재시작하지 않고 진행" % (e,))
        return True
    if pids:
        log("ADB 응답은 없지만 오환2 창이 있음 -> 재시작하지 않고 진행")
        return True
    return False


def after_restart_setup(st):
    """재시작 후: 영웅/유물 프리셋 활성화 -> 현재 단계에 맞는 프리셋 선택"""
    img = cap()
    if img is not None and (fall_popup(img)[0] or result_popup(img)[0]):
        log("환생 팝업이 떠 있어 프리셋 설정은 건너뜀")
        return
    ok = activate.activate_presets()
    log("프리셋 활성화: " + ("성공" if ok else "실패"))
    hero, relic = (None, "기본") if (st.get("high_done") and opt_on("barracks_swap")) else \
        (("렙뻥", "기본") if st.get("high_done") else ("기본", "시간"))
    ok2 = preset.set_presets(hero, relic)
    log(f"프리셋 선택({hero}/{relic}): " + ("성공" if ok2 else "실패"))
    if not st.get("high_done"):
        st["need_low"] = False if ok2 else True
    save_state(st)



def restart_game():
    log("게임 강제 종료 후 재실행")
    adb_out(["shell", "am", "force-stop", PKG])
    time.sleep(3)
    launch_game()


def find_popup(img):
    """POPUPS 목록 중 떠 있는 것 하나 -> (이름, 버튼 좌표) 또는 None"""
    nt = notice.detect(img)
    if nt is not None:                   # 공지 팝업: '오늘 하루 보지 않기' 체크 후 X
        if GO:
            notice.check_today()
        return "공지 팝업", nt
    for name, t_tpl, t_roi, b_tpl, b_roi in POPUPS:
        ts, _ = rebirth.match(img, t_tpl, t_roi)
        bs, pos = rebirth.match(img, b_tpl, b_roi)
        if ts >= 0.85 and bs >= 0.90:
            return name, pos
    return None


def recover():
    """게임이 메인 화면으로 돌아올 때까지 팝업을 닫고, 게임이 꺼져 있으면 다시 실행하며 기다림. 성공하면 True"""
    t0 = time.time()
    good = 0
    last_launch = time.time()          # 마지막으로 게임을 실행한 시각
    last_check = 0
    last_x = 0
    relaunch = 0
    while time.time() - t0 < RECOVER_TIMEOUT:
        time.sleep(2)
        if os.path.exists(PAUSE_FILE):
            return False
        img = cap()
        if img is None:
            continue
        if fall_popup(img)[0] or result_popup(img)[0]:
            log("복귀 중 환생 팝업 감지 → 메인 루프에서 처리")
            return True
        found = find_popup(img)
        if found:
            log(f"팝업 닫기: {found[0]}")
            rebirth.tap(*found[1])
            good = 0
            time.sleep(1.5)
            continue
        if wave.read_wave(img) is not None:
            good += 1
            if good >= 3:
                log("메인 화면 복귀 확인")
                return True
            continue
        good = 0
        if time.time() - last_x >= 10:        # 어떤 창이 가리고 있을 수 있음 -> 빨간 X 를 찾아 닫기
            last_x = time.time()
            try:
                import closer
                nx = closer.close_all(2)
                if nx:
                    log("복귀 중 열린 창 %d개 닫음" % nx)
                    time.sleep(1.5)
                    continue
            except Exception as e:
                log("창 닫기 오류: %r" % (e,))
        # 웨이브가 안 보이는데 게임 화면도 아니면(홈 화면 등) 게임을 다시 실행
        if time.time() - last_launch >= 25 and time.time() - last_check >= 10:
            last_check = time.time()
            if not game_in_focus():
                if relaunch >= 5:
                    log("게임을 5번 다시 실행했지만 복귀 실패")
                    return False
                relaunch += 1
                log(f"게임이 실행 중이 아님(홈 화면 등) → 다시 실행 ({relaunch}/5)")
                launch_game()
                last_launch = time.time()
    log("복귀 시간 초과")
    return False


def do_restart(kind, st=None):
    """kind: '정기' 또는 '튕김'. 성공하면 True"""
    if st is None:
        st = load_state()
    for attempt in range(1, MAX_RECOVER_FAILS + 1):
        log(f"{kind} 재시작 시도 {attempt}/{MAX_RECOVER_FAILS}")
        if kind == "정기" or attempt == MAX_RECOVER_FAILS:
            started = restart_bluestacks_full()
        elif attempt == 1:
            launch_game()
            started = True
        else:
            restart_game()
            started = True
        if started and recover():
            after_restart_setup(st)
            return True
    log("재시작 복구 실패 → 5분 후 다시 확인")
    return False


class StuckWatch:
    """웨이브 숫자가 STUCK_SEC 동안 오르지 않으면 정체로 판단"""

    def __init__(self):
        self.best = 0
        self.since = time.time()
        self.last = None
        self.cool = 0
        self.tick = time.time()

    def reset(self):
        self.best = 0
        self.tick = time.time()
        self.since = time.time()
        self.last = None

    def update(self, w):
        now = time.time()
        dt = now - self.tick
        self.tick = now
        if w is None:                            # 숫자가 안 보이는 동안은 정체 시간에 넣지 않음
            self.since += dt
            self.last = None
            return False
        if w == self.last:                       # 같은 값이 연속 2번 읽힐 때만 인정 (오독 방지)
            if w > self.best or (self.best and w < self.best - 500):
                self.best = w
                self.since = now
        self.last = w
        return self.best >= STUCK_MIN_WAVE and now - self.since >= STUCK_SEC and now >= self.cool


def rebirth_now():
    """천사 버튼 -> '환생하기' 창 확인 -> 초록 '환생' 클릭. 클릭까지 했으면 True"""
    if not (rebirth.has("title_ask.png") and rebirth.has("btn_ask_green.png")):
        log("환생하기 창 템플릿(title_ask / btn_ask_green)이 없어 환생 못 함")
        return False
    _guard()
    log("천사(환생) 버튼 클릭")
    rebirth.tap(*ANGEL)
    t0 = time.time()
    while time.time() - t0 < 8:
        time.sleep(0.7)
        img = cap()
        if img is None:
            continue
        ts, _ = rebirth.match(img, "title_ask.png", ASK_TITLE)
        gs, (gx, gy) = rebirth.match(img, "btn_ask_green.png", ASK_GREEN)
        if ts >= 0.85 and gs >= 0.90 and gx < 0.42 * img.shape[1]:
            log("환생하기 창 확인 → 초록 '환생' 클릭")
            rebirth.tap(gx, gy)
            time.sleep(4)
            return True
    log("환생하기 창이 안 떠서 중단")
    return False


def _make_logger(tag):
    """모듈 안의 print 를 macro.log 로 보내서 실패 이유가 로그에 남게 함 (클릭 로그는 제외)"""
    def _p(*a, **k):
        msg = " ".join(str(x) for x in a).strip()
        if not msg or msg.startswith("클릭") or msg.startswith("[시험]"):
            return
        log("  [%s] %s" % (tag, msg))
    return _p


def snap_fail(name):
    """지금 화면을 shots 폴더에 저장 (실패 원인 확인용)"""
    try:
        img = cap()
        if img is None:
            log("화면 저장 실패: 캡처 안 됨")
            return
        os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
        cv2.imwrite(os.path.join(BASE, "shots", name + ".png"), img)
        log("화면 저장: shots\\%s.png" % name)
    except Exception as e:
        log("화면 저장 실패: %r" % (e,))


def bluestacks_running():
    """BlueStacks(HD-Player) 프로세스가 하나라도 떠 있으면 True. 확인이 안 되면 True(건드리지 않음)"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-Process HD-Player -ErrorAction SilentlyContinue | Measure-Object).Count"],
                           capture_output=True, text=True, timeout=30)
        out = r.stdout.strip()
        return not (out.isdigit() and int(out) == 0)
    except Exception:
        return True


def main():
    log("매크로 시작 (" + ("실제 클릭 모드" if GO else "시험 모드: 클릭 안 함") + ") - 중지: Ctrl + C")
    st = load_state()
    if not st.get("last_restart"):
        st["last_restart"] = time.time()
        save_state(st)
    low_fails = 0
    preset.print = _make_logger("프리셋")
    focus_fails = 0
    last_focus_check = 0
    hist = []
    cap_fails = 0
    last_status = 0
    stuck = StuckWatch()
    last_iter = time.time()
    if GO and not adb_alive(tries=3) and not _bs_window():
        log("BlueStacks 가 꺼져 있음 -> 먼저 실행")
        if restart_bluestacks_full() and recover():
            after_restart_setup(st)
            st["last_restart"] = time.time()
            save_state(st)
        else:
            log("BlueStacks 실행/복귀 실패 -> 일반 루프로 진행 (캡처 실패 시 자동 복구 시도)")
    while True:
        time.sleep(LOOP_SEC)
        if time.time() - last_iter > 8:          # 매크로 작업(프리셋/레벨업 등)을 했으면 정체 시간 다시 계산
            stuck.reset()
        last_iter = time.time()
        if os.path.exists(PAUSE_FILE):
            if time.time() - last_status > 30:
                log("일시정지 중 (PAUSE 파일 삭제 시 재개)")
                last_status = time.time()
            continue
        img = cap()
        if img is None:
            cap_fails += 1
            if cap_fails % 3 == 0:
                adb_reconnect()
            if cap_fails >= 30:
                cap_fails = 0
                log("화면 캡처가 계속 실패 → BlueStacks 재시작")
                if GO:
                    if do_restart("정기", st):
                        st["last_restart"] = time.time()
                    hist.clear()
                    save_state(st)
            time.sleep(3)
            continue
        cap_fails = 0
        try:
            # 게임이 튕겨서 홈 화면 등으로 나갔는지 주기적으로 확인
            if time.time() - last_focus_check >= FOCUS_CHECK_SEC:
                last_focus_check = time.time()
                fg = game_in_focus()
                if fg is None:
                    pass                       # 확인 실패(렉)는 세지도 지우지도 않음
                elif fg or wave_visible(img):
                    focus_fails = 0
                else:
                    focus_fails += 1
                    log(f"게임 화면이 아님 ({focus_fails}/{FOCUS_FAIL_LIMIT})")
                    if focus_fails >= FOCUS_FAIL_LIMIT:
                        focus_fails = 0
                        if GO:
                            if do_restart("튕김", st):
                                st["last_restart"] = time.time()
                            else:
                                time.sleep(300)
                            hist.clear()
                            save_state(st)
                        continue
            # 1순위: 성 함락 팝업 → 환생
            ok, (gx, gy) = fall_popup(img)
            if ok and opt_on("fall_continue"):
                now = time.time()
                recent = [t for t in _cont_hist if now - t < 90]
                if recent and now - recent[-1] < 8:
                    time.sleep(2)               # 방금 눌렀음: 화면이 바뀔 때까지 대기 (하트 중복 소모 방지)
                    continue
                cok, (cx, cy), cfrac = continue_btn(img)
                if cok and len(recent) < 3:
                    log("성 함락 감지 → 이어하기 클릭 (버튼 %.2f, 90초 내 %d회째)" % (cfrac, len(recent) + 1))
                    if GO:
                        rebirth.tap(cx, cy)
                        _cont_hist.append(now)
                        time.sleep(3)
                    else:
                        time.sleep(5)
                    continue
                log("이어하기 불가 (버튼 %.2f, 90초 내 %d회) → 환생" % (cfrac, len(recent)))
            if ok:
                log("성 함락 감지 → 환생 클릭")
                if GO:
                    rebirth.tap(gx, gy)
                    time.sleep(2)
                    rebirth.after_click()
                    st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)
                    save_state(st)
                    hist.clear()
                else:
                    time.sleep(5)
                continue
            ok, (bx, by) = result_popup(img)
            if ok:
                log("환생결과 팝업 감지 → 확인 클릭")
                if GO:
                    rebirth.tap(bx, by)
                    st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)
                    save_state(st)
                    hist.clear()
                    time.sleep(2)
                else:
                    time.sleep(5)
                continue
            found = find_popup(img)
            if found:
                log(f"팝업 감지: {found[0]} → 닫기")
                if GO:
                    rebirth.tap(*found[1])
                    time.sleep(1.5)
                else:
                    time.sleep(5)
                continue
            if popup_open(img):
                continue                     # 프리셋/일괄 레벨업 창이 열려 있으면 건드리지 않음

            # 환생 직후: 기본 + 시간
            if st["need_low"]:
                log("환생 후 프리셋 설정: 영웅 기본 / 유물 시간")
                if GO:
                    if preset.set_presets("기본", "시간"):
                        st["need_low"] = False
                        save_state(st)
                        low_fails = 0
                    else:
                        low_fails += 1
                        log(f"프리셋 설정 실패 ({low_fails}회 연속), 다음 루프에서 재시도")
                        if low_fails in (3, 8):
                            snap_fail("preset_fail_%d" % low_fails)
                            daily.close_panels()
                        if low_fails >= 12:
                            log("프리셋 설정이 계속 실패 -> 게임 강제 재시작으로 복구")
                            low_fails = 0
                            restart_game()
                            if recover():
                                after_restart_setup(st)
                            hist.clear()
                            save_state(st)
                        time.sleep(5)
                else:
                    time.sleep(5)
                continue

            # 웨이브 읽기 (최근 3번이 모두 기준 이상이면 고레벨 단계 시작)
            w = wave.read_wave(img)
            if w is not None:
                hist.append(w)
                hist[:] = hist[-3:]
                if st["high_done"] and len(hist) == 3 and max(hist) < HIGH_WAVE * 0.8:
                    log(f"웨이브가 {hist}로 떨어짐 → 환생한 것으로 보고 초기화")
                    st.update(high_done=False, need_low=True, high_fails=0, mid_done=False, mid_fails=0)
                    save_state(st)
                    continue
                if (not st["high_done"] and st["high_fails"] < MAX_HIGH_FAILS
                        and len(hist) == 3 and min(hist) >= HIGH_WAVE):
                    log(f"웨이브 {hist} → 고레벨 단계 시작")
                    if GO:
                        if run_cycle_high():
                            st.update(high_done=True, high_fails=0)
                            log("고레벨 단계 완료")
                        else:
                            chk = cap()
                            if chk is not None and wave.read_wave(chk) is None:
                                log("고레벨 단계 실패: 알 수 없는 팝업/화면으로 추정 → 실패 횟수에 넣지 않음")
                                try:
                                    import closer
                                    log("열린 창 %d개 닫음" % closer.close_all())
                                except Abort:
                                    raise
                                except Exception as e:
                                    log("창 닫기 오류: %r" % (e,))
                                time.sleep(5)
                            else:
                                st["high_fails"] += 1
                                log(f"고레벨 단계 실패 ({st['high_fails']}/{MAX_HIGH_FAILS})")
                                snap_fail("high_fail_%d" % st["high_fails"])
                        save_state(st)
                        hist.clear()
                    else:
                        time.sleep(5)
                    continue

            # 중간 영웅 업그레이드 (5000 이상 ~ 고레벨 단계 전, 환생 한 번당 1회)
            if (not st.get("mid_done") and not st["high_done"] and len(hist) == 3
                    and MID_WAVE <= min(hist) < HIGH_WAVE):
                log(f"웨이브 {hist} → 중간 영웅 업그레이드 시작")
                if GO:
                    if run_cycle_mid():
                        st["mid_done"] = True
                        log("중간 영웅 업그레이드 완료")
                    else:
                        st["mid_fails"] = st.get("mid_fails", 0) + 1
                        log(f"중간 영웅 업그레이드 실패 ({st['mid_fails']}/2)")
                        if st["mid_fails"] >= 2:
                            st["mid_done"] = True
                    save_state(st)
                    hist.clear()
                else:
                    time.sleep(5)
                continue

            # 같은 웨이브에서 너무 오래 정체 → 직접 환생
            wx = wave.read_wave(img, exact=True)
            if stuck.best and time.time() - stuck.since >= 45 and time.time() - getattr(stuck, "logged", 0) >= 30:
                stuck.logged = time.time()
                log("정체 감시: 웨이브 %s (최고 %s) %d초째 변화 없음" % (wx, stuck.best, int(time.time() - stuck.since)))
            if daily.has_x(img) or daily.has_x(img, daily.QUEST_X_ROI):
                stuck.reset()      # 다른 컨텐츠 패널(던전/랭킹전/퀘스트 등)이 열려 있으면 정체로 보지 않음
            elif stuck.update(wx):
                log(f"웨이브 {wx} (최고 {stuck.best}) 에서 {int(time.time() - stuck.since)}초 정체 → 환생 시도")
                if GO:
                    if rebirth_now():
                        st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0)
                        save_state(st)
                        hist.clear()
                        stuck.reset()
                    else:
                        stuck.cool = time.time() + 300
                else:
                    stuck.cool = time.time() + 60
                continue

            # 일일 작업 (던전 소탕 / 일일 랭킹전 / 퀘스트 보상): 웨이브가 낮을 때만
            if (GO and daily.due(st) and not st["need_low"] and len(hist) >= 3
                    and wx is not None and wx < daily.MAX_WAVE - 100):
                log("일일 작업 확인")
                if not daily.run_daily(st):
                    st["daily_next"] = time.time() + 120
                save_state(st)
                hist.clear()
                stuck.reset()
                continue

            # 정기 재시작 (처리할 일이 없을 때만)
            if time.time() - st["last_restart"] >= RESTART_HOURS * 3600 and len(hist) >= 3:
                log(f"{RESTART_HOURS}시간 경과 → 게임 정기 재시작")
                if GO:
                    if do_restart("정기", st):
                        st["last_restart"] = time.time()
                    else:
                        st["last_restart"] = time.time() - RESTART_HOURS * 3600 + 300
                    hist.clear()
                    save_state(st)
                else:
                    st["last_restart"] = time.time()
                continue

            # 영입 (웨이브가 높은데 고레벨 단계가 아직이면 먼저 그쪽)
            pending_high = (not st["high_done"] and st["high_fails"] < MAX_HIGH_FAILS
                            and len(hist) == 3 and min(hist) >= HIGH_WAVE)
            if time.time() >= st["next_recruit"] and not pending_high and len(hist) >= 3:
                log("영입 시도")
                if GO:
                    res = recruit.recruit(force=(time.time() - st.get("last_recruit", 0)) > 4800)
                    now = time.time()
                    if res == "done":
                        st.update(last_recruit=now, next_recruit=now + RECRUIT_OK_SEC)
                    elif res == "cooldown":
                        st["next_recruit"] = now + RECRUIT_RETRY_SEC
                    else:
                        st["next_recruit"] = now + 120
                    log(f"영입 결과: {res}")
                    save_state(st)
                else:
                    st["next_recruit"] = time.time() + 60
        except Abort as e:
            log(f"중단: {e}")
            time.sleep(3)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"오류: {e!r}")
            time.sleep(5)


if __name__ == "__main__":
    try:
        if "restart" in sys.argv[1:]:
            # 시험용: 게임만 한 번 재시작하고 복귀까지 확인한 뒤 종료
            if GO:
                log("재시작 시험: " + ("성공" if do_restart("정기") else "실패"))
            else:
                log("시험 모드: 실제로 재시작하려면 맨 끝에 go 를 붙이세요 (py main.py restart go)")
        elif "rebirth" in sys.argv[1:]:
            # 시험용: 지금 바로 직접 환생을 한 번 실행 (go 를 붙여야 실제 클릭)
            if GO:
                log("환생 시험: " + ("성공" if rebirth_now() else "실패"))
            else:
                log("시험 모드: 실제로 환생하려면 맨 끝에 go 를 붙이세요 (py main.py rebirth go)")
        else:
            main()
    except KeyboardInterrupt:
        log("사용자가 중지함")