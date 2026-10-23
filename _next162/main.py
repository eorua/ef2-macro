import sys, os, time, json, subprocess, datetime

import cv2
import numpy as np
import speed          # 대기시간 단축 (speed.py 의 FACTOR 로 조절)
import rebirth, wave, preset, recruit, bsrestart, activate, daily
import notice

BASE = r"C:\macro"
GO = "go" in sys.argv[1:]
STATE_FILE = os.path.join(BASE, "state.json")
LOG_FILE = os.path.join(BASE, "macro.log")
PAUSE_FILE = os.path.join(BASE, "PAUSE")      # 이 파일을 만들면 일시정지 (지우면 재개)
PAUSED_FILE = os.path.join(BASE, "PAUSED")    # patch104: 메인이 실제로 멈췄음을 패널에 알림
HIGH_WAVE_BASE = 6500  # patch156: 상한 탐색 전 기본값
HIGH_WAVE = 6500                               # 이 웨이브 이상이면 최대레벨 단계 시작 (patch155: 6200 -> 6500)
RELIC_BASIC_WAVE = 7000                        # patch129: 이 웨이브부터 유물 프리셋 기본 (그 전까지는 시간)
LOOP_SEC = 1.5
MID_WAVE = 5000                                # 이 웨이브 이상이면 (고레벨 전에) 중간 영웅 업그레이드 1회
RECRUIT_OK_SEC = 3700                          # 영입 성공 후 다음 시도까지
RECRUIT_RETRY_SEC = 600                        # 쿨타임이라 못 했을 때 재시도 간격
MAX_HIGH_FAILS = 3
import dev                         # patch162: 공통 ADB
from dev import ADB
PKG = "com.ekkorr.ef2"
ACTIVITY = "com.ekkorr.ef2/com.ekkorr.ef2.MainActivity"
RESTART_HOURS = 6                              # 이 시간마다 게임을 재시작
FOCUS_CHECK_SEC = 10                           # 게임이 떠 있는지 확인하는 간격
FOCUS_FAIL_LIMIT = 2                           # patch148: 6 -> 2 (두 번째 확인은 3초 뒤) 게임이 아니면 바로 재시작
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


# ---- patch156: 고레벨 시작 웨이브 1회 상한 탐색 ----
# 1판: 고레벨 단계 없이(중간 업글까지만) 가다가 성 함락 웨이브 W 기록 -> 기준 W-50
# 다음 판부터: 기준 전에 또 함락되면 (그 웨이브-50) 으로 낮춤. 고레벨 단계까지 무사히 가면 그 값으로 확정, 탐색 끝.
PROBE_STEP = 50


def probe_sync(st):
    """현재 고레벨 기준 웨이브를 전역 HIGH_WAVE / STUCK_MIN_WAVE 에 반영"""
    global HIGH_WAVE, STUCK_MIN_WAVE
    p = st.get("probe") or {}
    if p.get("on"):
        HIGH_WAVE = p.get("hw") or 99999        # 첫 판은 고레벨 단계 안 함
    else:
        HIGH_WAVE = int(st.get("high_wave") or HIGH_WAVE_BASE)
    STUCK_MIN_WAVE = HIGH_WAVE


def probe_fall(st):
    """성 함락 팝업을 처음 봤을 때(환생 한 번당 1회) 호출"""
    p = st.get("probe") or {}
    if not p.get("on") or st.get("probe_fell"):
        return
    st["probe_fell"] = True
    if st.get("high_done"):
        return
    w = int(st.get("peak_wave") or 0)
    if w < 5500:
        log("[상한 탐색] 함락 웨이브 %d 를 믿기 어려움 -> 무시" % w)
        return
    new = w - PROBE_STEP
    old = p.get("hw")
    if old is None or new < old:
        p["hw"] = new
        st["probe"] = p
        log("[상한 탐색] %d층에서 성 함락 (고레벨 전) -> 고레벨 기준 %s -> %d" % (w, old or "없음", new))
    save_state(st)


def probe_done(st):
    """고레벨 단계를 무사히 마쳤을 때: 탐색 중이면 기준 확정"""
    p = st.get("probe") or {}
    if p.get("on") and p.get("hw"):
        st["high_wave"] = int(p["hw"])
        p["on"] = False
        st["probe"] = p
        log("[상한 탐색] %d층에서 고레벨 단계 성공 -> 기준 %d 로 확정, 탐색 끝" % (p["hw"], p["hw"]))
        save_state(st)
        probe_sync(st)


def record_rebirth(st, why=""):
    """환생 직전의 최고 웨이브(peak_wave)를 최근 환생 목록에 기록 (패널에서 표시)"""
    st["probe_fell"] = False                   # patch156
    _rp = st.get("rprobe")                      # patch161: 한 판 다 모았으면 끝
    if _rp and _rp.get("shots") and not _rp.get("done"):
        _rp["done"] = True
        log("[보상 수집] 환생 -> 수집 끝 (%d장, shots\\reward)" % _rp["shots"])
    _p = st.get("probe") or {}
    if _p.get("wait"):
        _p.update(wait=False, on=True)
        st["probe"] = _p
        log("[상한 탐색] 시작: 이번 판은 고레벨 단계 없이 성 함락까지 진행")
    st["relic_basic"] = False                  # patch129
    try:
        w = int(st.get("peak_wave") or 0)
        if w > 0:
            lst = list(st.get("rebirths") or [])
            lst.append({"wave": w, "t": int(time.time()), "why": why})
            st["rebirths"] = lst[-10:]
            log("환생 기록: %d층 (%s)" % (w, why))
        st["peak_wave"] = 0
    except Exception as e:
        log("환생 기록 오류: %r" % (e,))


def cap():
    return wave.capture()


def cont_limit():
    """성 함락 시 이어하기 횟수 (환생 한 번당, 0~3). 패널의 fall_continue_n, 없으면 예전 체크박스 값(켬=3)"""
    try:
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            d = json.load(f)
        if "fall_continue_n" in d:
            return max(0, min(3, int(d["fall_continue_n"])))
        return 3 if d.get("fall_continue") else 0
    except Exception:
        return 0


def opt_on(name):
    """settings.json (조작 패널의 옵션 탭에서 켜고 끔) 에서 옵션을 읽음. 없으면 꺼짐"""
    try:
        with open(os.path.join(BASE, "settings.json"), encoding="utf-8") as f:
            return bool(json.load(f).get(name, False))
    except Exception:
        return False


_cont_hist = []          # 이어하기를 누른 시각들
CD_TAP = (350, 295)      # patch118: 카운트다운 줄이기 - 'WAVE' 글자와 숫자 사이
CD_TAPS = 15
_cd_shots = [0]


def _skip_countdown():
    """patch118: 이어하기 뒤 준비 카운트다운(20초)을 연타로 줄임"""
    t0 = time.time()
    while time.time() - t0 < 5:
        img = cap()
        if img is not None and not fall_popup(img)[0]:
            break
        time.sleep(0.3)
    else:
        log("이어하기 뒤 팝업이 안 닫혀 카운트다운 줄이기 생략")
        return
    time.sleep(0.5)
    if _cd_shots[0] < 3:
        _cd_shots[0] += 1
        snap_fail("cont_cd_%d" % _cd_shots[0])
    _guard()
    preset.tap_burst(CD_TAP, "카운트다운 줄이기", CD_TAPS)
    time.sleep(0.6)
    img = cap()
    try:
        import arrange
        if arrange.dialog_open(img):
            log("카운트다운 연타 중 영웅 배치 창이 열림 -> 취소")
            preset.tap(arrange.BTN_CANCEL, "취소")
    except Abort:
        raise
    except Exception as e:
        log("배치 창 확인 오류: %r" % (e,))
    log("카운트다운 줄이기: %d회 연타" % CD_TAPS)


def continue_btn(img):
    """성 함락 팝업 오른쪽의 초록 '이어하기' 버튼. 색으로 판별하며 회색(하트 없음)이면 False"""
    H, W = img.shape[:2]
    # patch131: 버튼 높이가 업데이트마다 바뀔 수 있어 세로로 넓게 보고 초록 띠를 찾음
    x1, y1, x2, y2 = int(0.71 * W), int(0.44 * H), int(0.89 * W), int(0.62 * H)
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    rows = ((h > 35) & (h < 90) & (s > 100) & (v > 100)).mean(axis=1)
    best, cur = None, None
    for i, r in enumerate(list(rows) + [0.0]):
        if r >= 0.5 and cur is None:
            cur = i
        if r < 0.5 and cur is not None:
            if best is None or i - cur > best[1] - best[0]:
                best = (cur, i)
            cur = None
    if best is None or best[1] - best[0] < int(0.015 * H):
        return False, (int(0.80 * W), int(0.54 * H)), float(rows.max()) if len(rows) else 0.0
    frac = float(rows[best[0]:best[1]].mean())
    return frac >= 0.5, (int(0.80 * W), y1 + (best[0] + best[1]) // 2), frac


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
    dev.connect()                                   # patch162


def popup_open(img):
    return preset.preset_open(img) or preset.bulk_open(img)


def run_cycle_mid():
    """중간 영웅 업그레이드: 최대레벨 프리셋으로 일괄 레벨업 후 기본/시간으로 복귀"""
    ok = preset.set_presets(None, "영웅강화골드")
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = preset.set_presets(None, "시간")
    return bulk_ok and final_ok


def _barracks_fallback(why):
    """병영 편성이 중간에 실패하면 영웅 기본 프리셋으로 되돌림 (편성이 어중간하게 남지 않게)"""
    log("병영 편성 실패: %s -> 영웅 기본 프리셋으로 복구" % why)
    try:
        preset.set_presets("기본", "시간")       # patch129: 7000 전까지 유물은 시간
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


def _arrange_after():
    """6200 사이클 직후 영웅 배치 정리 (불의정령 10/2/6시, 나머지 12시). 실패해도 사이클 결과에는 영향 없음"""
    try:
        if not daily.setting("arrange", True):
            return
        import arrange
        arrange.GO = True
        arrange.GUARD = _guard
        arrange.log = lambda *a: log("  [배치] " + " ".join(str(x) for x in a))
        log("영웅 배치 정리 시작")
        ok = arrange.run()
        log("영웅 배치 정리: " + ("성공" if ok else "실패 (원래 배치 유지)"))
        if not ok:
            import closer
            closer.close_all()
    except Abort:
        raise
    except Exception as e:
        log("영웅 배치 정리 오류: %r" % (e,))


def _skill_auto(on):
    """patch130: 고레벨 단계 동안 스킬 AUTO 끄기/켜기"""
    try:
        import skillctl, closer
        closer.close_all()
        ok = skillctl.set_auto(on)
        log("고레벨 단계: 스킬 AUTO %s (%s)" % ("켬" if on else "끔", "확인" if ok else "확인 실패"))
        if not on:
            time.sleep(2.0)                    # 이미 나온 총병이 사라질 때까지
    except Abort:
        raise
    except Exception as e:
        log("스킬 AUTO 전환 오류: %r" % (e,))


def _arrange_early():
    """patch130: 1단계에서 불정 2마리만 남았을 때 먼저 좌우 자리에 놓기"""
    if not daily.setting("arrange", True):
        return
    import arrange
    arrange.GO = True
    arrange.GUARD = _guard
    arrange.log = lambda *a: log("  [배치] " + " ".join(str(x) for x in a))
    log("불의정령 먼저 자리 잡기")
    ok = arrange.run()
    log("불의정령 먼저 자리 잡기: " + ("성공" if ok else "실패 (계속 진행)"))


def run_cycle_barracks():
    """patch130: 스킬 AUTO 를 끈 채로 고레벨 단계 진행, 끝나면(실패해도) 다시 켬"""
    _skill_auto(False)
    try:
        return _run_cycle_barracks_inner()
    finally:
        _skill_auto(True)


def _run_cycle_barracks_inner():
    """병영 편성 방식 고레벨 단계 (패널 옵션 barracks_swap)"""
    import barracks, closer
    _bl = _make_logger("병영")              # patch98: 병영 메시지를 macro.log 에 남김
    barracks.log = lambda *a: None if (a and str(a[0]).startswith("스와이프")) else _bl(*a)
    closer.close_all()                      # 시작 전에 남아 있는 창이 있으면 정리
    if not _retry_step("골렘 편성(1단계)", barracks.phase1, after_release=_arrange_early):     # patch130
        return _barracks_fallback("골렘 편성(1단계)")
    if not _retry_step("유물 프리셋 변경", preset.set_presets, None, "영웅강화골드", pet="백호"):     # patch116
        return _barracks_fallback("유물 프리셋 변경")
    if not _retry_step("일괄 레벨업", preset.bulk_levelup, max_rounds=1):
        return _barracks_fallback("일괄 레벨업")
    if getattr(preset, "LAST_MAXED", False):       # patch116: 백호로 최대치까지 -> 맘보로 바꿔 한 번 더
        log("백호로 모든 영웅 최대 레벨 -> 대표 펫 맘보로 바꿔 다시 강화")
        if preset.set_presets(None, "영웅강화골드", pet="맘보"):
            preset.bulk_levelup(max_rounds=1)
    if not _retry_step("최종 편성(2단계)", barracks.phase2):
        return _barracks_fallback("최종 편성(2단계)")
    # patch153: 전장의북 2마리로 되돌림 -> 새 불의정령 강화(newspirit) 단계 없음
    # patch171: 전장의북 훈장 2000 (사거리·공속 증가) + 전체 레벨업 한 번 (아직 유물 영웅강화골드)
    try:
        import drum
        drum.GO = GO
        drum.log = _make_logger("북")
        drum.upgrade()
    except Abort:
        raise
    except Exception as e:
        log("전장의북 훈장 오류: %r" % (e,))
    try:
        closer.close_all()
        if not preset.bulk_levelup(max_rounds=1):
            log("전북 훈장 뒤 전체 레벨업 실패 (계속 진행)")
    except Abort:
        raise
    except Exception as e:
        log("전체 레벨업 오류: %r" % (e,))
    for _ in range(3):
        if preset.set_presets(None, "시간", pet="사르크"):     # patch116: 이후 사르크 / patch129: 유물은 7000 까지 시간
            _arrange_after()
            return True
        closer.close_all()
        time.sleep(2)
    log("최종 유물 프리셋(시간) 설정 실패 -> 다음 기회에 재시도")
    return False


def run_cycle_high():
    if True:
        return run_cycle_barracks()
    ok = preset.set_presets(None, "영웅강화골드")      # 영웅 프리셋은 그대로 (바꾸면 레벨이 다시 바뀌어 골드 손실)
    if not ok:
        return False
    bulk_ok = preset.bulk_levelup()
    final_ok = False
    for _ in range(3):                                   # 유물이 영웅강화골드로 남지 않게 복귀는 재시도
        if preset.set_presets(None, "기본"):
            final_ok = True
            break
        time.sleep(2)
    return bulk_ok and final_ok


def adb_out(args):
    try:
        r = dev.run(args, text=True, timeout=30)    # patch162
        return r.stdout
    except Exception as e:
        log(f"ADB 오류: {e!r}")
        return ""


def home_screen(img):
    """patch149: BlueStacks 바탕화면(남색 배경 + 위쪽 흰 '게임과 앱 검색' 줄)이면 True = 게임이 강제 종료됨"""
    try:
        import numpy as np
        h, w = img.shape[:2]
        if (w, h) != (720, 1280):
            return False
        bg = img[450:1000, 60:660].reshape(-1, 3).astype(np.float32)
        b, g, r = bg.mean(0)
        if not (20 <= b <= 60 and g <= 20 and r <= 15 and bg.std(0).max() <= 8):
            return False
        bar = img[72:94, 180:520]
        return float((bar.min(axis=2) >= 225).mean()) >= 0.7
    except Exception:
        return False


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
            c = dev.connect()                                                   # patch162
            r = dev.run(["shell", "getprop", "sys.boot_completed"], text=True, timeout=15)
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
    hero, relic = (None, "기본" if st.get("relic_basic") else "시간") if st.get("high_done") else ("기본", "시간")     # patch129
    pet_r = "사르크" if st.get("high_done") else st.get("pet_q", "팅키")
    try:                                                   # patch154: 30퀘 전략 진행 중이면 그 단계 프리셋
        import q30 as _q30
        r30 = None if st.get("high_done") else _q30.restart_presets(st)
        if r30:
            hero, relic, pet_r = r30
    except Exception as e:
        log("30퀘 상태 확인 오류: %r" % (e,))
    ok2 = preset.set_presets(hero, relic, pet=pet_r)     # patch116
    log(f"프리셋 선택({hero}/{relic}): " + ("성공" if ok2 else "실패"))
    if not st.get("high_done"):
        st["need_low"] = False if ok2 else True
    save_state(st)



def restart_game():
    """patch144: 게임만 껐다 켜는 건 끊김 해소에 의미가 없어서 블루스택째 재시작. 블루스택 재시작이 실패하면 예전처럼 게임만"""
    log("재시작: 게임만이 아니라 BlueStacks 째로")
    if restart_bluestacks_full():
        return
    log("BlueStacks 재시작 실패 -> 게임만 강제 종료 후 재실행")
    adb_out(["shell", "am", "force-stop", PKG])
    time.sleep(3)
    launch_game()


def _ocr_popup(img):
    """그림으로 못 찾은 출석 보상 창을 글자(OCR)로 찾음 -> (이름, 누를 좌표) 또는 None"""
    try:
        import ocrx
        return ocrx.find_attendance(img)
    except Exception as e:
        log("글자로 팝업 찾기 오류: %r" % (e,))
        return None


def find_popup(img):
    """POPUPS 목록 중 떠 있는 것 하나 -> (이름, 버튼 좌표) 또는 None"""
    nt = notice.detect(img)
    if nt is not None:                   # 공지 팝업: '오늘 하루 보지 않기' 체크 후 X
        if GO:
            notice.check_today()
        return "공지 팝업", nt
    for name, t_tpl, t_roi, b_tpl, b_roi in POPUPS:
        ts, _ = rebirth.match(img, t_tpl, t_roi)
        if name == "출석 보상":                      # patch137: 받기 버튼은 그림 대신 글자('받기')로 찾음
            if ts >= 0.85:
                try:
                    import ocrx
                    r = ocrx.find_attendance(img, force=True)
                except Exception as e:
                    log("출석 글자 인식 오류: %r" % (e,))
                    r = None
                if r:
                    return r
                return "출석 보상(위치)", (int(img.shape[1] * 0.5), int(img.shape[0] * 0.606))
            continue
        bs, pos = rebirth.match(img, b_tpl, b_roi)
        if ts >= 0.85 and bs >= 0.90:
            return name, pos
    return _ocr_popup(img)


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
        if os.path.exists(PAUSE_FILE):                   # patch104: 일시정지면 더 진행하지 않음
            log("일시정지 중 -> 재시작 단계를 더 진행하지 않음")
            return False
        log(f"{kind} 재시작 시도 {attempt}/{MAX_RECOVER_FAILS}")
        if kind in ("정기", "튕김") or attempt == MAX_RECOVER_FAILS:     # patch150: 튕김(강제 종료)도 블루스택째
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


_wv = {"v": None, "t": 0.0}


def wave_sane(w):
    """연속성 검사: 직전에 믿은 웨이브보다 갑자기 너무 크게 오른 값(예: 5400 -> 6400)은 숫자 오독으로 보고 None.
    낮아지는 값은 환생이나 앞선 오독 정정이라 그대로 받음. 15분 넘게 지나면 기준을 새로 잡음"""
    if w is None:
        return None
    now = time.time()
    v, t = _wv["v"], _wv["t"]
    if v is not None and 0 <= now - t < 900 and w > v + 250 + 6 * (now - t):
        if now - _wv.get("log", 0) > 60:
            _wv["log"] = now
            log("웨이브 %s 는 직전 %s 에서 너무 급하게 올라 오독으로 보고 무시" % (w, v))
        return None
    _wv["v"], _wv["t"] = w, now
    return w


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
        if self.last is not None and abs(w - self.last) <= 60:      # 연속 두 값이 서로 가까울 때만 인정 (오독 방지)
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
        if msg.startswith("[") and "] " in msg[:12]:          # patch104: "[12:34:56] daily: ..." 앞부분 제거
            msg = msg.split("] ", 1)[1]
            head, _, rest = msg.partition(": ")
            if rest and " " not in head:
                msg = rest
        if not msg or msg.startswith("클릭") or msg.startswith("[시험]") or msg.startswith("스와이프"):
            return
        log("  [%s] %s" % (tag, msg))
    return _p


DL_WAIT_MIN = 10                 # patch133: 다른 기기 접속 뒤 다시 접속까지 기다리는 시간(분)
DL_ROI = (0.08, 0.34, 0.92, 0.50)


def dl_popup(img):
    """patch133: '다른 기기에서 접속하였습니다' 창이 떠 있으면 True"""
    try:
        s, _ = rebirth.match(img, "dl_text.png", DL_ROI)
        return s >= 0.80
    except Exception:
        return False


def handle_dl(st):
    """patch133: 다른 기기 접속 처리. 기다리는 중이면 False, 다시 접속했으면 True"""
    now = time.time()
    if not st.get("dl_since"):
        n = st.get("dl_count", 0) if now - st.get("dl_last_resume", 0) < 1800 else 0
        wait = min(DL_WAIT_MIN * (2 ** n), 120)
        st.update(dl_since=now, dl_count=n + 1, dl_resume_at=now + wait * 60)
        log("다른 기기(폰)에서 접속함 -> %d분 동안 기다렸다가 다시 접속 (그동안은 아무것도 누르지 않음)" % wait)
        save_state(st)
        snap_fail("dl_popup")
    if now < st.get("dl_resume_at", 0):
        return False
    log("다른 기기 접속 대기 끝 -> 게임을 껐다 켜서 다시 접속")
    st.update(dl_since=0, dl_last_resume=now)
    save_state(st)
    if GO:
        restart_game()
        if recover():
            after_restart_setup(st)
        st["last_restart"] = time.time()
        save_state(st)
    return True


def snap_reward(img, kind, st):
    """patch160: 환생 보상(훈장) 분석용 - 성 함락/환생결과 창을 shots\\reward 에 jpg 로 저장 (화면 가운데만)"""
    try:
        if img is None:
            return
        d = os.path.join(BASE, "shots", "reward")
        os.makedirs(d, exist_ok=True)
        w = int(st.get("peak_wave") or 0)
        n = time.strftime("%m%d_%H%M%S") + "_%s_w%d.jpg" % (kind, w)
        cv2.imwrite(os.path.join(d, n), img[150:1130], [cv2.IMWRITE_JPEG_QUALITY, 85])
    except Exception as e:
        log("보상 화면 저장 실패: %r" % (e,))


# ---- patch161: 1회성 환생 보상 수집 - 500웨이브마다 '환생하기' 창을 열어 캡처하고 X 로 닫음 (환생 버튼은 절대 안 누름)
RP_START, RP_STEP, RP_END = 4000, 500, 8000


def _ask_x(img):
    """'환생하기' 창 오른쪽 위 X (진한 빨강 사각형 + 흰 X). 화면 오른쪽 40%, 위 30% 안에서만 찾음"""
    H, W = img.shape[:2]
    y2, x1 = int(H * 0.30), int(W * 0.6)
    hsv = cv2.cvtColor(img[:y2, x1:], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = (((h <= 10) | (h >= 170)) & (s > 110) & (v > 60)).astype(np.uint8)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, stt, _ = cv2.connectedComponentsWithStats(red, 8)
    best = None
    for i in range(1, n):
        x, y, w, hh, a = stt[i]
        if not (28 <= w <= 90 and 28 <= hh <= 90) or abs(int(w) - int(hh)) > 12:
            continue
        hv = hsv[y:y + hh, x:x + w]
        k = cv2.dilate(((hv[..., 1] < 110) & (hv[..., 2] > 160)).astype(np.uint8), np.ones((3, 3), np.uint8))
        t = np.linspace(0.3, 0.7, 10)
        d1 = np.mean([k[int(u * (hh - 1)), int(u * (w - 1))] for u in t])
        d2 = np.mean([k[int(u * (hh - 1)), int((1 - u) * (w - 1))] for u in t])
        if d1 < 0.6 or d2 < 0.6:
            continue
        c = (int(x1 + x + w // 2), int(y + hh // 2))
        if best is None or c[1] < best[1]:
            best = c
    return best


def reward_probe(st, hist):
    rp = st.get("rprobe")
    if not rp or rp.get("done") or len(hist) < 3:
        return
    nxt = int(rp.get("next", RP_START))
    if nxt > RP_END:
        rp["done"] = True
        save_state(st)
        return
    if min(hist) < nxt:
        return
    w = min(hist)
    rp["next"] = (w // RP_STEP + 1) * RP_STEP          # 다음 목표 (실패해도 같은 구간은 다시 안 함)
    save_state(st)
    if not rebirth.has("title_ask.png"):
        log("[보상 수집] title_ask 템플릿 없음 -> 중단")
        rp["done"] = True
        return
    log("[보상 수집] 웨이브 %d -> 환생하기 창 열어 캡처" % w)
    rebirth.tap(*ANGEL)
    img = None
    t0 = time.time()
    while time.time() - t0 < 6:
        time.sleep(0.6)
        c = cap()
        if c is not None and rebirth.match(c, "title_ask.png", ASK_TITLE)[0] >= 0.85:
            img = c
            break
    if img is None:
        log("[보상 수집] 환생하기 창이 안 뜸 -> 이번 구간 건너뜀")
        return
    time.sleep(0.4)
    _c2 = cap()
    if _c2 is not None:
        img = _c2
    try:
        d = os.path.join(BASE, "shots", "reward")
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, time.strftime("%m%d_%H%M%S") + "_ask_w%d.png" % w), img)
        rp["shots"] = rp.get("shots", 0) + 1
    except Exception as e:
        log("[보상 수집] 저장 실패: %r" % (e,))
    # 닫기: 창 오른쪽 위 빨간 X 만 누름 (초록/빨강 환생 버튼 영역은 절대 안 누름)
    for _ in range(3):
        c = cap()
        if c is None:
            continue
        if rebirth.match(c, "title_ask.png", ASK_TITLE)[0] < 0.85:
            break
        xp = _ask_x(c)
        if xp:
            rebirth.tap(*xp)
        else:
            dev.keyevent(4)
        time.sleep(0.8)
    c = cap()
    if c is not None and rebirth.match(c, "title_ask.png", ASK_TITLE)[0] >= 0.85:
        log("[보상 수집] 창이 안 닫힘 -> 수집 중단")
        rp["done"] = True
    else:
        log("[보상 수집] 캡처 %d장째 저장, 창 닫음" % rp.get("shots", 0))
    save_state(st)


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


MAINT_POLL_SEC = 1200            # 점검이 끝나는 시각을 모를 때, 이 간격(초)마다 BlueStacks 를 켜서 끝났는지 확인


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


def main():
    log("매크로 시작 (" + ("실제 클릭 모드" if GO else "시험 모드: 클릭 안 함") + ") - 중지: Ctrl + C")
    st = load_state()
    if "rprobe" not in st:                      # patch161: 한 번만 - 500웨이브마다 환생 보상 캡처
        st["rprobe"] = {"next": RP_START, "shots": 0}
        log("[보상 수집] 이번 판부터 %d~%d 사이 %d웨이브마다 환생하기 창 캡처 (1회)" % (RP_START, RP_END, RP_STEP))
    if "probe" not in st:                       # patch156: 한 번만 - 다음 환생부터 상한 탐색
        st["probe"] = {"wait": True, "on": False, "hw": None}
        save_state(st)
        log("[상한 탐색] 다음 환생부터 고레벨 기준 상한 탐색 예약")
    probe_sync(st)
    if GO and st.get("maint"):
        log("점검 대기 중이던 상태를 이어서 처리")
        handle_maintenance(st, {"end": st["maint"].get("wake", 0) - 180})
    if not st.get("last_restart"):
        st["last_restart"] = time.time()
        save_state(st)
    low_fails = 0
    preset.print = _make_logger("프리셋")
    for _m, _tag in (("daily", "일일"), ("guild", "길드"), ("soul", "영혼"), ("wavecall", "웨이브호출"),   # patch104
                     ("recruit", "영입"), ("notice", "공지"), ("maint", "점검"), ("activate", "활성화")):
        try:
            __import__(_m).print = _make_logger(_tag)
        except Exception as _e:
            log("로그 연결 실패 %s: %r" % (_m, _e))
    try:
        if os.path.exists(PAUSED_FILE):
            os.remove(PAUSED_FILE)
    except Exception:
        pass
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
    try:                                          # patch119: 펫/스킬 로그, 재시작 시 스킬 AUTO 복구
        import pet, skillctl
        pet.log = _make_logger("펫")
        skillctl.log = _make_logger("스킬")
        if st.get("skill_manual") and GO:
            skillctl.deactivate(st, "매크로 재시작")
            save_state(st)
    except Exception as e:
        log("펫/스킬 준비 오류: %r" % (e,))
    while True:
        try:
            import skillctl
            skillctl.idle(skillctl.IDLE_ACTIVE if skillctl.active() else LOOP_SEC)
        except Exception as e:
            log("스킬 관리 오류: %r" % (e,))
            time.sleep(LOOP_SEC)
        if time.time() - last_iter > 8:          # 매크로 작업(프리셋/레벨업 등)을 했으면 정체 시간 다시 계산
            stuck.reset()
        last_iter = time.time()
        if os.path.exists(PAUSE_FILE):
            stuck.reset()      # patch99: 일시정지 중에는 정체 시간을 세지 않음
            try:                                   # patch119: 일시정지면 스킬 AUTO 다시 켬
                import skillctl
                if skillctl.active():
                    skillctl.deactivate(st, "일시정지")
                    save_state(st)
            except Exception as e:
                log("스킬 관리 오류: %r" % (e,))
            if not os.path.exists(PAUSED_FILE):          # patch104: 멈췄음을 알림
                try:
                    open(PAUSED_FILE, "w").close()
                except Exception:
                    pass
            if time.time() - last_status > 30:
                log("일시정지 중 (PAUSE 파일 삭제 시 재개)")
                last_status = time.time()
            continue
        if os.path.exists(PAUSED_FILE):
            try:
                os.remove(PAUSED_FILE)
                log("일시정지 해제 -> 재개")
            except Exception:
                pass
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
            # 서버 점검 팝업: BlueStacks 를 끄고 점검이 끝날 때쯤 다시 실행
            if GO:
                _mt = maint_check(img)
                if _mt:
                    handle_maintenance(st, _mt)
                    hist.clear()
                    stuck.reset()
                    continue
            # patch149: 바탕화면이 보이면 = 게임 강제 종료 -> 스킬 연타 멈추고 바로 게임 실행
            if home_screen(img):
                log("바탕화면 감지 -> 게임이 강제 종료됨, 바로 BlueStacks 재시작")
                try:
                    import skillctl
                    if skillctl._cam is not None:
                        try:
                            skillctl._cam.stop()
                        except Exception:
                            pass
                        skillctl._cam = None
                except Exception:
                    pass
                snap_fail("home_screen")
                focus_fails = 0
                if GO:
                    if do_restart("튕김", st):
                        st["last_restart"] = time.time()
                    else:
                        time.sleep(300)
                    hist.clear()
                    save_state(st)
                continue
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
                    if focus_fails == 1:          # patch148: 다른 화면(플레이 스토어 등)에 누르지 않게 스킬 연타부터 멈추고 3초 뒤 다시 확인
                        last_focus_check = time.time() - FOCUS_CHECK_SEC + 3
                        try:                      # AUTO 버튼은 누르지 않고 화면 받기/연타만 끔 (게임 복귀 후 메인 루프가 정리)
                            import skillctl
                            if skillctl._cam is not None:
                                try:
                                    skillctl._cam.stop()
                                except Exception:
                                    pass
                                skillctl._cam = None
                                log("스킬 연타 멈춤 (게임 화면 아님)")
                        except Exception as e:
                            log("스킬 연타 멈춤 오류: %r" % (e,))
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
            # patch133: 다른 기기(폰) 접속으로 끊김 -> 기다렸다가 다시 접속
            if dl_popup(img):
                handle_dl(st)
                hist.clear()
                stuck.reset()
                time.sleep(10)
                continue
            if st.get("dl_since"):
                st["dl_since"] = 0                      # 창이 사라졌으면(직접 확인 누름 등) 대기 끝
                save_state(st)
            # 1순위: 성 함락 팝업 → 환생
            ok, (gx, gy) = fall_popup(img)
            if ok:
                probe_fall(st)                  # patch156
            if ok and cont_limit() > 0:
                now = time.time()
                recent = [t for t in _cont_hist if now - t < 90]
                if recent and now - recent[-1] < 8:
                    time.sleep(2)               # 방금 눌렀음: 화면이 바뀔 때까지 대기 (하트 중복 소모 방지)
                    continue
                cok, (cx, cy), cfrac = continue_btn(img)
                if cok and st.get("cont_used", 0) < cont_limit():
                    log("성 함락 감지 → 이어하기 클릭 (버튼 %.2f, 이번 환생 %d/%d회째)" % (cfrac, st.get("cont_used", 0) + 1, cont_limit()))
                    if GO:
                        rebirth.tap(cx, cy)
                        _cont_hist.append(now)
                        st["cont_used"] = st.get("cont_used", 0) + 1
                        save_state(st)
                        if daily.setting("cont_skip", True):     # patch118
                            try:
                                _skip_countdown()
                            except Abort:
                                raise
                            except Exception as e:
                                log("카운트다운 줄이기 오류: %r" % (e,))
                            time.sleep(1)
                        else:
                            time.sleep(3)
                    else:
                        time.sleep(5)
                    continue
                log("이어하기 불가 (버튼 %.2f, 사용 %d/%d회) → 환생" % (cfrac, st.get("cont_used", 0), cont_limit()))
            if ok:
                log("성 함락 감지 → 환생 클릭")
                snap_reward(img, "fall", st)            # patch160
                if GO:
                    rebirth.tap(gx, gy)
                    time.sleep(2.5)
                    for _try in range(2):
                        _chk = cap()
                        if _chk is None or result_popup(_chk)[0]:
                            if _chk is not None:
                                snap_reward(_chk, "result", st)     # patch160
                            break
                        _ok2, (_gx2, _gy2) = fall_popup(_chk)
                        if not _ok2:
                            break
                        log("환생 클릭이 안 먹힌 것 같음 → 다시 클릭 (%d/2)" % (_try + 1))
                        rebirth.tap(_gx2, _gy2)
                        time.sleep(2.5)
                    rebirth.after_click()
                    _chk = cap()
                    if _chk is not None and fall_popup(_chk)[0] and not result_popup(_chk)[0]:
                        log("성 함락 팝업이 그대로 남아 있음 → 환생 기록 없이 다음 루프에서 재시도")
                        continue
                    record_rebirth(st, "환생"); st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0, cont_used=0)
                    save_state(st)
                    hist.clear()
                else:
                    time.sleep(5)
                continue
            ok, (bx, by) = result_popup(img)
            if ok:
                log("환생결과 팝업 감지 → 확인 클릭")
                snap_reward(img, "result", st)          # patch160
                if GO:
                    rebirth.tap(bx, by)
                    record_rebirth(st, "환생"); st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0, cont_used=0)
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
            if GO:
                try:
                    import inf2
                    if inf2.idle_check(img):
                        hist.clear()
                        stuck.reset()
                        continue
                except Abort:
                    raise
                except Exception as e:
                    log("무한랭킹전 화면 확인 오류: %r" % (e,))
            if popup_open(img):
                continue                     # 프리셋/일괄 레벨업 창이 열려 있으면 건드리지 않음

            # 영혼의 휴식 중: 정체 감시/환생/일일 작업/재시작 등 모든 동작을 멈추고 종료만 기다림
            if st.get("soul"):
                stuck.reset()
                hist.clear()
                if GO:
                    try:
                        import soul
                        soul.tick(st, img)
                    except Abort:
                        raise
                    except Exception as e:
                        log("영혼의 휴식 처리 오류: %r" % (e,))
                    save_state(st)
                time.sleep(3)
                continue

            # 환생 직후: 기본 + 시간
            if st["need_low"]:
                try:                                   # patch154: 30퀘 전략이면 영웅 골드
                    import q30 as _q30
                    _lh, _lr = _q30.low_presets()
                except Exception:
                    _q30, _lh, _lr = None, "기본", "시간"
                log("환생 후 프리셋 설정: 영웅 %s / 유물 %s" % (_lh, _lr))
                try:                                   # patch119: 환생 -> 스킬 AUTO 다시 켬
                    import skillctl
                    if GO and (skillctl.active() or st.get("skill_manual")):
                        skillctl.deactivate(st, "환생")
                except Exception as e:
                    log("스킬 관리 오류: %r" % (e,))
                if GO:
                    if preset.set_presets(_lh, _lr, pet="팅키"):     # patch116: 대표 펫 팅키 / patch154
                        st["need_low"] = False
                        st["pet_q"] = "팅키"
                        if _q30 is not None:
                            _q30.start(st)
                        try:                                   # patch134: 지난 판 기록으로 첫 확인 시점
                            import pet as _pet
                            st["pq_next"] = time.time() + _pet.first_delay(st)
                        except Exception:
                            st["pq_next"] = time.time() + 420     # patch121: 첫 퀘스트 확인은 7분 뒤
                        st["pq_done"] = False
                        save_state(st)
                        low_fails = 0
                    else:
                        low_fails += 1
                        log(f"프리셋 설정 실패 ({low_fails}회 연속), 다음 루프에서 재시도")
                        if low_fails in (1, 3, 8):
                            snap_fail("preset_fail_%d" % low_fails)
                        try:
                            import closer
                            nclosed = closer.close_all()
                            if nclosed:
                                log("프리셋 실패 후 열린 창 %d개 닫음" % nclosed)
                        except Abort:
                            raise
                        except Exception as e:
                            log("창 닫기 오류: %r" % (e,))
                        if low_fails in (3, 8):
                            daily.close_panels()
                        if low_fails >= 12:
                            log("프리셋 설정이 계속 실패 -> 게임 강제 재시작으로 복구")
                            low_fails = 0
                            restart_game()
                            if recover():
                                after_restart_setup(st)
                            st["last_restart"] = time.time()      # patch144: 블루스택째 재시작했으니 정기 재시작 시계도 새로
                            hist.clear()
                            save_state(st)
                        time.sleep(5)
                else:
                    time.sleep(5)
                continue

            # 웨이브 읽기 (최근 3번이 모두 기준 이상이면 고레벨 단계 시작)
            probe_sync(st)                      # patch156
            w = wave.read_wave(img)
            if GO:
                try:
                    import inf2
                    if inf2.nowave_watch(img, w):
                        hist.clear()
                        stuck.reset()
                        continue
                except Abort:
                    raise
                except Exception as e:
                    log("웨이브 미인식 처리 오류: %r" % (e,))
            w = wave_sane(w)
            if w is not None:
                if GO:
                    try:
                        import wavecall
                        if wavecall.tick(st, w): save_state(st)
                    except Exception as _e:
                        log("웨이브 호출 오류: %r" % (_e,))      # patch104: 인자 1개로
                hist.append(w)
                hist[:] = hist[-3:]
                try:                                    # patch182: 7500 이후 화면 녹화 (스킬 직접 굴리기 중일 때만)
                    import skillctl
                    skillctl.note_wave(hist)
                except Exception as _e:
                    log("녹화 확인 오류: %r" % (_e,))
                if GO:
                    try:
                        reward_probe(st, hist)          # patch161
                    except Abort:
                        raise
                    except Exception as _e:
                        log("[보상 수집] 오류: %r" % (_e,))
                if GO and daily.setting("skill_manual", True):     # patch119: 7200 이상 스킬 직접 굴리기
                    try:
                        import skillctl
                        if skillctl.active():
                            stop = skillctl.need_stop()
                            if stop or (len(hist) == 3 and max(hist) < skillctl.START_WAVE - 500):
                                skillctl.deactivate(st, "스킬이 계속 안 눌림" if stop else "웨이브 낮아짐")
                                if stop:
                                    st["skill_off_until"] = time.time() + 1800
                                save_state(st)
                        elif st.get("skill_manual"):
                            skillctl.deactivate(st, "다시 시도")
                            save_state(st)
                        elif (st["high_done"] and len(hist) == 3 and min(hist) >= skillctl.START_WAVE
                              and time.time() >= st.get("skill_off_until", 0)):
                            skillctl.activate(st)
                            save_state(st)
                    except Abort:
                        raise
                    except Exception as e:
                        log("스킬 관리 오류: %r" % (e,))
                if len(hist) == 3 and min(hist) > int(st.get("peak_wave") or 0):
                    st["peak_wave"] = min(hist)      # 최근 3번 읽은 값 중 최솟값 = 오인식에 안 흔들리는 최고층
                if (GO and st["high_done"] and not st.get("relic_basic") and len(hist) == 3
                        and min(hist) >= RELIC_BASIC_WAVE and time.time() >= st.get("relic_basic_retry", 0)):     # patch129
                    log(f"웨이브 {hist} → 유물 프리셋 기본으로 변경")
                    if preset.set_presets(None, "기본"):
                        st["relic_basic"] = True
                        log("유물 프리셋 기본 설정 완료")
                    else:
                        st["relic_basic_retry"] = time.time() + 60
                        log("유물 프리셋 기본 설정 실패 -> 1분 뒤 재시도")
                        try:
                            import closer
                            closer.close_all()
                        except Abort:
                            raise
                        except Exception:
                            pass
                    save_state(st)
                    hist.clear()
                    continue
                if st["high_done"] and len(hist) == 3 and max(hist) < HIGH_WAVE * 0.8:
                    log(f"웨이브가 {hist}로 떨어짐 → 환생한 것으로 보고 초기화")
                    record_rebirth(st, "감지"); st.update(high_done=False, need_low=True, high_fails=0, mid_done=False, mid_fails=0)
                    save_state(st)
                    continue
                if (not st["high_done"] and st["high_fails"] < MAX_HIGH_FAILS
                        and len(hist) == 3 and min(hist) >= HIGH_WAVE):
                    log(f"웨이브 {hist} → 고레벨 단계 시작")
                    if GO:
                        try:                               # patch154: 30퀘 전략이 안 끝났으면 이번 환생은 포기하고 진행
                            import q30
                            q30.abandon(st, "고레벨 단계(%d)가 먼저 옴" % HIGH_WAVE, say=log)
                            save_state(st)
                        except Abort:
                            raise
                        except Exception as e:
                            log("30퀘 정리 오류: %r" % (e,))
                        if run_cycle_high():
                            st.update(high_done=True, high_fails=0)
                            log("고레벨 단계 완료")
                            probe_done(st)              # patch156
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
                    _mid_light = False
                    try:                                   # patch154: 30퀘 골드 모으는 중이면 +1000 두 번만
                        import q30 as _q30
                        _mid_light = _q30.collecting(st)
                    except Exception:
                        pass
                    if _mid_light:
                        log("30퀘 골드 모으는 중 -> 중간 업글은 '+' 창 +1000 두 번만")
                        try:
                            import newspirit
                            newspirit.log = log
                            _mid_ok = newspirit.bulk_gold(2)
                        except Abort:
                            raise
                        except Exception as e:
                            log("+1000 두 번 오류: %r" % (e,))
                            _mid_ok = False
                    else:
                        _mid_ok = run_cycle_mid()
                    if _mid_ok:
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

            # patch154: (시범) 30퀘 열기 전략 - 29퀘 400c 뒤 골드 모으기 -> 200ao -> 오픈골드 감소 + 레오 -> 30퀘 오픈
            if GO and not st["high_done"] and not st["need_low"] and len(hist) == 3:
                try:
                    import q30
                    q30.log = _make_logger("30퀘")
                    if q30.tick(st, say=log):
                        save_state(st)
                        hist.clear()
                        stuck.reset()
                        continue
                except Abort:
                    raise
                except Exception as e:
                    log("30퀘 전략 오류: %r" % (e,))

            # patch116: 대표 펫 팅키/랩티 (환생 후 ~ 고레벨 전, 퀘스트 29번 레벨 기준, 5분마다)
            if GO and not st["high_done"] and not st["need_low"] and len(hist) == 3 and daily.setting("pet_swap", True):
                try:
                    import pet
                    pet.log = _make_logger("펫")
                    if pet.quest_tick(st, say=log):
                        save_state(st)
                        hist.clear()
                        stuck.reset()
                        continue
                except Abort:
                    raise
                except Exception as e:
                    log("펫 교체 오류: %r" % (e,))

            # 같은 웨이브에서 너무 오래 정체 → 직접 환생
            wx = wave_sane(wave.read_wave(img, exact=True))
            if stuck.best and time.time() - stuck.since >= 45 and time.time() - getattr(stuck, "logged", 0) >= 30:
                stuck.logged = time.time()
                log("정체 감시: 웨이브 %s (최고 %s) %d초째 변화 없음" % (wx, stuck.best, int(time.time() - stuck.since)))
            if daily.has_x(img) or daily.has_x(img, daily.QUEST_X_ROI):
                stuck.reset()      # 다른 컨텐츠 패널(던전/랭킹전/퀘스트 등)이 열려 있으면 정체로 보지 않음
            elif stuck.update(wx):
                log(f"웨이브 {wx} (최고 {stuck.best}) 에서 {int(time.time() - stuck.since)}초 정체 → 환생 시도")
                if GO:
                    if rebirth_now():
                        record_rebirth(st, "환생"); st.update(need_low=True, high_done=False, high_fails=0, mid_done=False, mid_fails=0, cont_used=0)
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

            # patch128: 예약된 영혼의 휴식 (soul_at.txt 의 시각, 한 번만)
            _sa = os.path.join(BASE, "soul_at.txt")
            if GO and not st.get("soul") and os.path.exists(_sa) and time.time() >= st.get("soul_at_retry", 0):
                try:
                    _txt = open(_sa, encoding="utf-8").read().strip()
                    _when = datetime.datetime.strptime(_txt[:16], "%Y-%m-%d %H:%M").timestamp()
                except Exception as e:
                    log("soul_at.txt 를 읽지 못함 (%r) -> 파일 삭제" % (e,))
                    _when = None
                    try: os.remove(_sa)
                    except Exception: pass
                if _when is not None and time.time() >= _when:
                    if time.time() > _when + 1800:
                        log("예약된 영혼의 휴식 시각이 30분 넘게 지남 -> 취소")
                        try: os.remove(_sa)
                        except Exception: pass
                    else:
                        import soul
                        log("예약된 영혼의 휴식 시작 (%s)" % _txt)
                        try:
                            res = soul.start(st)
                        except Abort:
                            raise
                        except Exception as e:
                            log("영혼의 휴식 시작 오류: %r" % (e,))
                            res = "fail"
                        log("예약된 영혼의 휴식 결과: %s" % res)
                        if res in ("started", "running", "cooldown", "low"):
                            try: os.remove(_sa)
                            except Exception: pass
                            if res in ("cooldown", "low"):
                                log("예약된 영혼의 휴식을 못 함 (%s) -> 예약 취소" % ("쿨타임" if res == "cooldown" else "다이아 부족"))
                        else:
                            st["soul_at_retry"] = time.time() + 60      # 1분 뒤 다시 (예약 시각 30분 뒤까지)
                        save_state(st)
                        hist.clear()
                        stuck.reset()
                        continue

            # 영혼의 휴식 시작 (패널 옵션 soul): 일일 작업이 끝났고 다이아가 충분할 때만
            if GO and opt_on("soul") and len(hist) >= 3:
                import soul
                if soul.ready_to_start(st, wx):
                    log("영혼의 휴식 시도")
                    try:
                        res = soul.start(st)
                    except Abort:
                        raise
                    except Exception as e:
                        log("영혼의 휴식 시작 오류: %r" % (e,))
                        res = "fail"
                    log("영혼의 휴식 시작 결과: %s" % res)
                    soul.handle_start_result(st, res)
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
                    _base = max(st.get("last_recruit", 0), st.get("last_force", 0))   # patch136
                    _force = (time.time() - _base) > 4800
                    res = recruit.recruit(force=_force)
                    now = time.time()
                    if res == "done":
                        st.update(last_recruit=now, next_recruit=now + RECRUIT_OK_SEC)
                    elif res == "cooldown":
                        st["next_recruit"] = now + RECRUIT_RETRY_SEC
                        if _force:                                  # 강제로 열었는데도 쿨타임 -> 강제 확인은 80분 뒤에 다시
                            st["last_force"] = now
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