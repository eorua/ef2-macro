"""barracks.py (v48) - 병영 편성 자동화 (최대레벨 유닛으로 레벨업 -> 렙뻥 유닛으로 재편성)

시험 모드(기본): 화면만 읽고 아무것도 누르지 않음. 실제 실행은 맨 끝에 go.
  py barracks.py read                 현재 화면 상태 읽기 (병영/영웅 목록 어디서든)
  py barracks.py release go           영웅 목록에서 3번째 줄부터 전부 해제 (위 2명만 남김)
  py barracks.py deploy golem 8 go    병영에서 골렘을 최대 8명 배치 (슬롯이 차면 멈춤)
  py barracks.py phase1 go            2명만 남기고 -> 죽음의 손(부족하면 골렘)으로 채움
  py barracks.py phase2 go            3번째 줄부터 해제 -> 드루이드 6, 불의정령 1, 전장의북 1 로 채움
  py barracks.py races 인간 go        병영 종족 필터를 그 종족만 켜기 (여러 개면 띄어쓰기)
  py barracks.py scan 이름 go         병영 목록을 맨 위->맨 아래로 훑으며 각 화면의 점수 출력 + scan_N.png 저장 (진단용)
  py barracks.py mk 이름 줄번호       현재 병영 화면에서 그 줄의 얼굴을 템플릿으로 저장 (예: mk spirit 3)
"""
import sys, os, time, cv2, numpy as np
import preset

# main.py 의 speed.py 가 time.sleep 을 줄여 놓아도, 여기서는 시험한 그대로의 대기시간을 씀
_sleep = getattr(sys.modules.get("speed"), "_real_sleep", time.sleep)

BASE = r"C:\macro"
TPL = os.path.join(BASE, "tpl")
GO = "go" in sys.argv[1:]

# ---- 좌표 (720x1280) ----
TAB_HERO = (185, 1240)
BTN_BARRACKS = (520, 788)           # 영웅 탭의 '병영' 버튼
BK_X = (675, 790)                   # 병영 화면의 빨간 X
RACES = {"인간": (312, 792), "엘프": (370, 792), "언데드": (430, 792), "오크": (490, 792)}
DEPLOY_X = 632                      # 병영 줄의 '배치' 버튼 x
HERO_ROW_X = 330                    # 영웅 목록 줄을 누를 x (이름 부근, +1 버튼은 피함)
HERO_ROW_Y0, HERO_ROW_DY = 962, 87  # 영웅 목록 1번째 줄 중심, 줄 간격
DETAIL_X = (683, 213)               # 병사 상세창의 빨간 X
BTN_RELEASE = (408, 1220)           # 상세창의 '해제'
TAB_DETAIL = (120, 415)                # 상세창의 '상세' 탭 (스킬 345 / 초월 571)
LABEL_ROI = (50, 794, 102, 815)     # '10/10' 슬롯 표시
KEEP = 2                            # 위에서 남길 영웅 수 (불의정령 2마리) - patch110

# 유닛: 이름, 종족
UNITS = {"golem": ("골렘", "인간"), "hand": ("죽음의 손", "언데드"), "drum": ("전장의북", "오크"),
         "druid": ("드루이드", "엘프"), "spirit": ("불의 정령", "인간")}


def log(*a):
    print(*a, flush=True)


def tap(pt, label=""):
    preset.tap(pt, label)           # main.py 가 환생 팝업 안전장치를 씌운 preset.tap 을 그대로 사용


def capture():
    return preset.capture()


def snap(wait=0.5):
    _sleep(wait)
    return capture()


def swipe(x, y1, y2, ms=600):
    log(("스와이프 " if GO else "[시험] 스와이프 ") + f"{x},{y1} -> {y2}")
    if GO:
        import subprocess
        subprocess.run(preset.ADB + ["shell", "input", "swipe", str(x), str(y1), str(x), str(y2), str(ms)],
                       creationflags=getattr(preset, "NOWIN", 0x08000000))


def shot_fail(name="barracks_fail", img=None):
    """patch267: 이상/실패 시점의 화면을 shots 폴더에 즉시 저장"""
    try:
        im = img if img is not None else capture()
        if im is not None:
            p = os.path.join(BASE, "shots", f"{name}_{time.strftime('%m%d_%H%M%S')}.png")
            cv2.imwrite(p, im)
            log(f"이상 화면 저장: shots\\{os.path.basename(p)}")
            return p
    except Exception:
        pass
    return None


def tap_multi(pts, label="", gap=0.12):
    """여러 곳을 adb 한 번으로 연달아 누름 (adb 호출 1번 = 프로세스 1번이라 훨씬 빠름)"""
    log(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{label} {pts}")
    if GO and pts:
        import subprocess
        cmd = "; ".join(f"input tap {x} {y} & sleep {gap}" for x, y in pts) + "; wait"
        subprocess.run(preset.ADB + ["shell", cmd], creationflags=getattr(preset, "NOWIN", 0x08000000))


def same_view(a, b):
    """목록 영역이 거의 같으면 True (스크롤이 끝에 닿았는지 판단)"""
    if a is None or b is None:
        return False
    d = cv2.absdiff(a[815:1170, 8:600], b[815:1170, 8:600])
    return float(d.mean()) < 3.0


# ---------------------------------------------------------------- 화면 읽기
def red(img, pt, r=14):
    return preset.red_ratio(img, pt, r)


def barracks_open(img):
    return red(img, BK_X) > 0.1


def detail_open(img):
    return red(img, DETAIL_X) > 0.1


def race_on(img, pt):
    x, y = pt
    v = cv2.cvtColor(img[y - 18:y + 19, x - 18:x + 19], cv2.COLOR_BGR2HSV)[..., 2]
    return int((v > 150).sum()) > 80


def races_state(img):
    return {k: race_on(img, p) for k, p in RACES.items()}


def label_mask(img, dx=0, dy=0):
    x1, y1, x2, y2 = LABEL_ROI
    x1, x2 = x1 + dx, x2 + dx
    y1, y2 = y1 + dy, y2 + dy
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 150, 120), (8, 255, 255)) | cv2.inRange(hsv, (172, 150, 120), (180, 255, 255))
    return m


_FULL = None


def _full_tpl():
    global _FULL
    if _FULL is None:
        p = os.path.join(TPL, "bk_full.png")
        _FULL = cv2.imread(p, cv2.IMREAD_GRAYSCALE) if os.path.exists(p) else False
    return _FULL


def is_full(img):
    """슬롯 표시가 '10/10' 이면 True (글자 모양 비교)"""
    t = _full_tpl()
    if t is False or t is None:
        return False
    b = t > 0
    # patch212: 10-21 업데이트로 '10/10' 글자가 오른쪽으로 4px 이동
    # patch254: 뮤뮤에서는 글자가 x+3, y+1 에 그려져 짝수 dx 만 보던 예전 방식이 '10/10' 을 못 알아봄
    #           -> 1px 단위로 x -6~+12, y -2~+2 전부 확인
    for dy in (0, 1, -1, 2, -2):
        for dx in range(-6, 13):
            m = label_mask(img, dx, dy)
            if m.shape != t.shape:
                continue
            a = m > 0
            union = (a | b).sum()
            if union > 0 and (a & b).sum() / union > 0.75:
                return True
    return False


def row_centers(img):
    """병영 목록에서 '배치' 버튼 줄들의 중심 y (스크롤 위치와 무관). 화면 아래 탭에 가린 줄은 제외"""
    col = img[:, 585, :].astype(int)
    b, g, r = col[:, 0], col[:, 1], col[:, 2]
    mask = ((r - b) > 40) & (r > 90) & (r < 200)
    out, on, s = [], False, 0
    for y in range(815, 1205):
        if mask[y] and not on:
            on, s = True, y
        if (not mask[y]) and on:
            on = False
            if y - s >= 40:
                out.append((s + y) // 2)
    return [c for c in out if c < 1170]


def hero_row_y(i):
    return HERO_ROW_Y0 + HERO_ROW_DY * (i - 1)


def hero_row_filled(img, i):
    """영웅 목록 i번째 줄에 영웅이 있는지 (이름 글씨의 흰 픽셀 수)"""
    yc = hero_row_y(i)
    v = cv2.cvtColor(img[yc - 16:yc - 3, 165:300], cv2.COLOR_BGR2HSV)[..., 2]
    return int((v > 200).sum()) > 60


_TPLS = {}


def load_tpls(key):
    if key not in _TPLS:
        lst = []
        for n in ("1", "2"):
            p = os.path.join(TPL, f"bk_{key}{n}.png")
            if os.path.exists(p):
                lst.append(cv2.imread(p))
        _TPLS[key] = lst
    return _TPLS[key]


def unit_score(img, key, yc):
    best = 0.0
    band = img[max(0, yc - 38):yc + 18, 8:244]
    for t in load_tpls(key):
        if band.shape[0] < t.shape[0] or band.shape[1] < t.shape[1]:
            continue
        best = max(best, float(cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED).max()))
    return best


def find_unit(img, key, thr=0.72):
    """보이는 줄 중 유닛 key 의 줄 중심 y (없으면 None)"""
    best = (0.0, None)
    for yc in row_centers(img):
        s = unit_score(img, key, yc)
        if s > best[0]:
            best = (s, yc)
    return best[1] if best[0] >= thr else None


# ---------------------------------------------------------------- 동작
def open_hero_tab():
    img = capture()
    if img is not None and detail_open(img):
        log("상세창이 열려 있음 -> 닫기 불가(해제 위험), 중단"); return False
    if img is not None and barracks_open(img):
        tap(BK_X, "병영 닫기")
        _sleep(0.45)
    tap(TAB_HERO, "영웅 탭")
    _sleep(0.35)
    return True


def open_barracks():
    img = capture()
    if img is None:
        return False
    if barracks_open(img):
        return True
    tap(BTN_BARRACKS, "병영")
    img = preset.wait_for(barracks_open, 4.0, first=0.25, step=0.25)
    ok = img is not None and barracks_open(img)
    if not ok:
        log("병영이 안 열림")
    return ok


def close_barracks():
    img = capture()
    if img is not None and barracks_open(img):
        tap(BK_X, "병영 닫기")
        img = preset.wait_for(lambda im: not barracks_open(im), 4.0, first=0.25, step=0.25)
        return img is not None and not barracks_open(img)
    return True


def _toggle_to(want_on, off):
    """want_on 종족은 켜고 off 종족은 끔. 어긋난 것만 한 번에 눌러 바꾸고 확인 (최대 3번)"""
    for _ in range(3):
        img = capture()
        if img is None:
            return None
        todo = [n for n in ORDER if (n in want_on and not race_on(img, RACES[n])) or (n in off and race_on(img, RACES[n]))]
        if not todo:
            return img
        tap_multi([RACES[n] for n in todo], "종족 " + ",".join(todo))
        _sleep(0.3)
    img = capture()
    return img


ORDER = ["인간", "엘프", "언데드", "오크"]      # 병영 목록 정렬 순서 (켜진 종족 중 앞쪽이 위)


def set_races(want):
    """want 에 든 종족만 켜기"""
    img = _toggle_to(set(want), set(RACES) - set(want))
    st = races_state(img) if img is not None else {}
    ok = bool(st) and all(st.get(k) == (k in want) for k in RACES)
    log("종족 상태:", st, "OK" if ok else "불일치")
    return ok


def set_races_for(race):
    """race 가 목록 맨 위에 오도록 최소한만 전환: race 는 켜고, 그보다 앞 순서 종족만 끔 (뒤 순서는 그대로)"""
    off = set(ORDER[:ORDER.index(race)])
    img = _toggle_to({race}, off)
    st = races_state(img) if img is not None else {}
    ok = bool(st) and st.get(race) and not any(st.get(n) for n in off)
    log("종족 상태:", st, "OK" if ok else "불일치")
    return bool(ok)


SW_MS = 600        # 스크롤 드래그 시간(ms)
TOP_A, TOP_B = 850, 1100    # 맨 위로 올릴 때 드래그 구간 (크게, 빠르게)
STEP_A, STEP_B = 1010, 900  # 아래로 찾으며 내릴 때 드래그 구간 (110px: 게임이 실제로는 몇 배로 움직여도 화면(355px)을 건너뛰지 않게 작게)


def _best(img, key):
    return max([unit_score(img, key, yc) for yc in row_centers(img)] or [0.0])


def _scroll_once(direction):
    if direction == "up":
        swipe(360, TOP_A, TOP_B, SW_MS)
    else:
        swipe_hold(360, 1100, 870)                     # patch124: 관성 없이 230px
        return snap(0.3)
    return snap(0.55)


def to_top(steps=10):
    """목록을 맨 위까지 올림 (같은 화면이 두 번 나오면 끝)"""
    prev = capture()
    for _ in range(steps):
        img = _scroll_once("up")
        if img is None:
            return
        if same_view(prev, img):
            return
        prev = img


def _scroll_search(key, steps):
    """아래로 조금씩 내리며 찾기. (찾은 y 또는 None, 끝에 닿았는지)"""
    prev = capture()
    for n in range(steps):
        img = _scroll_once("down")
        if img is None:
            return None, True
        if is_full(img):                          # patch254: 슬롯이 이미 10/10 -> 더 찾을 필요 없음
            log("  슬롯 10/10 -> 스크롤 중단")
            return None, True
        y = find_unit(img, key)
        log("  아래 %d: 최고점 %.2f%s" % (n + 1, _best(img, key), " -> 찾음" if y else ""))
        if y is not None:
            return y, False
        if same_view(prev, img):
            img2 = snap(0.5)                      # 정말 끝인지 한 번 더 확인
            if same_view(img, img2):
                return None, True
        prev = img
    return None, False


def locate(key, tries=30):
    try:                                                 # patch124: 찾기가 끝나면 fastcam 정리
        return _locate_impl(key, tries)
    finally:
        fc_stop()


def _locate_impl(key, tries=30):
    """유닛 줄 찾기: 지금 화면 -> 맨 위까지 올리며 -> 맨 위부터 아래로 내리며. 줄 중심 y 반환"""
    img = snap(0.2)
    if img is None:
        return None
    if is_full(img):                                     # patch254
        log("  슬롯 10/10 -> 찾기 생략")
        return None
    y = find_unit(img, key)
    log("  지금 화면: 최고점 %.2f" % _best(img, key))
    if y is None:
        to_top()
        img = snap(0.2)
        y = find_unit(img, key) if img is not None else None
        if y is None:
            y, _ = _scroll_search(key, tries)
        if y is None:                                      # patch109: 맨 위로 다시 올려 한 번 더
            log("  끝까지 못 찾음 -> 맨 위로 다시 올려 한 번 더 찾기")
            to_top(16)
            img = snap(0.4)
            y = find_unit(img, key) if img is not None else None
            if y is None:
                y, _ = _scroll_search(key, tries)
    if y is None:
        return None
    # 스크롤 관성이 멈춘 뒤 위치를 다시 확인
    for _ in range(3):
        img = snap(0.3)
        if img is None:
            return None
        y2 = find_unit(img, key)
        if y2 is not None and abs(y2 - y) <= 2:
            return y2
        if y2 is not None:
            y = y2
    return y


# ---------------------------------------------------------------- patch124: fastcam 으로 빠르게 (안 되면 예전 adb 방식)
class _FC:
    cam = None


def fc_start():
    if _FC.cam is None:
        try:
            from fastcam import FastCam
            _FC.cam = FastCam(max_fps=30, scid="0e2f0a02", port=27198).start()    # 스킬용(0e2f0a01)과 따로
        except Exception as e:
            log("fastcam 시작 실패 -> 예전 방식: %r" % (e,))
            _FC.cam = None
    return _FC.cam


def fc_stop():
    if _FC.cam is not None:
        try:
            _FC.cam.stop()
        except Exception:
            pass
        _FC.cam = None


def fc_wait(cond, timeout=2.5, after=0.0):
    """after(perf_counter) 이후 화면 중 cond 를 만족하는 첫 화면 (없으면 None)"""
    cam = _FC.cam
    end = time.perf_counter() + timeout
    img, t, n = cam.latest()
    if img is not None and t >= after and cond(img):
        return img
    while time.perf_counter() < end:
        g = cam.wait_new(n, 0.3)
        if g is None:
            img, t, n2 = cam.latest()                 # 화면이 안 바뀌는 중이면 마지막 화면으로 판단
            if img is not None and time.perf_counter() - after > 0.4 and cond(img):
                return img
            continue
        img, t, n = g
        if t >= after and cond(img):
            return img
    return None


def swipe_hold(x, y1, y2, ms=350, hold=0.25):
    """손가락을 끝에서 잠깐 멈췄다 떼는 드래그 -> 관성 없이 딱 그만큼만 움직임"""
    cam = fc_start()
    if cam is None:
        swipe(x, y1, y2, SW_MS)
        return
    log(("스와이프(멈춤) " if GO else "[시험] 스와이프(멈춤) ") + f"{x},{y1} -> {y2}")
    if not GO:
        return
    steps = 8
    cam.touch(0, x, y1)
    for i in range(1, steps + 1):
        time.sleep(ms / 1000.0 / steps)
        cam.touch(2, x, int(y1 + (y2 - y1) * i / steps))
    time.sleep(hold)
    cam.touch(1, x, y2)


def release_top_fast(keep=KEEP, total=10):
    """release_top 과 같은 동작을 fastcam 으로 (확인 절차 동일). fastcam 이 없으면 'nofast'"""
    cam = fc_start()
    if cam is None or not GO:
        return "nofast"
    if not open_hero_tab():
        return False
    img = _list_to_top()
    if img is None or barracks_open(img) or detail_open(img):
        return None
    rows = _name_rows(img)
    if len(rows) <= keep:
        return None
    y = rows[keep]
    done = 0
    for _ in range(total - keep + 1):
        time.sleep(0.15)
        img = fc_wait(lambda im: not detail_open(im), 1.5)
        if img is None:
            shot_fail("barracks_detail_not_closed")
            log("상세창이 닫히지 않음 -> 중단"); return False
        if not all(_name_filled(img, rows[j]) for j in range(keep)):
            log("맨 위 %d줄이 안 보임 -> 예전 방식으로" % keep)
            return None if done == 0 else False
        if not _name_filled(img, y):
            log(f"{keep + 1}번째 줄이 비었음 -> 해제 완료 ({done}명 해제, 빠른 방식)")
            return True
        t0 = cam.tap(HERO_ROW_X, y + 10)
        img = fc_wait(detail_open, 2.5, after=t0 + 0.03)
        if img is None:
            shot_fail("barracks_detail_not_open")
            log("상세창이 안 열림 -> 중단"); return False
        if red(img, BTN_RELEASE) <= 0.5:
            img = fc_wait(lambda im: red(im, BTN_RELEASE) > 0.5, 0.6, after=t0 + 0.03)   # 창이 펼쳐지는 중일 수 있음
        if img is None or red(img, BTN_RELEASE) <= 0.5:
            log("해제 버튼이 안 보임(다른 탭?) -> '상세' 탭으로 이동")
            t1 = cam.tap(*TAB_DETAIL)
            img = fc_wait(lambda im: red(im, BTN_RELEASE) > 0.5, 2.0, after=t1 + 0.03)
            if img is None:
                shot_fail("barracks_release_btn_not_found")
                log("해제 버튼을 못 찾음 -> 중단"); return False
        t2 = cam.tap(*BTN_RELEASE)
        img = fc_wait(lambda im: not detail_open(im), 2.5, after=t2 + 0.03)
        if img is None:
            shot_fail("barracks_still_open_after_release")
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
        done += 1
    log(f"해제 완료 ({done}명 해제, 빠른 방식)")
    return True


CHUNK = 4          # 한 번에 연타할 배치 수 (줄이 사라지는 것을 중간중간 확인)


def deploy(key, n):
    """병영에서 key 유닛을 최대 n명 배치 (슬롯이 가득 차면 멈춤). 누른 횟수 반환"""
    name, race = UNITS[key]
    if not load_tpls(key):
        log(f"{name} 템플릿 없음 (tpl\\bk_{key}1.png). py barracks.py mk {key} 줄번호 로 만드세요"); return 0
    if not open_barracks():
        return 0
    if not set_races_for(race):
        return 0
    img = capture()
    if img is not None and is_full(img):                 # patch254: 이미 가득이면 스크롤 없이 끝
        log(f"슬롯이 이미 10/10 -> {name} 배치 생략"); return 0
    y = locate(key)
    if y is None:
        log(f"{name} 줄을 못 찾음"); return 0
    log(f"{name} 줄 y={y} -> 최대 {n}명 배치")
    done = 0
    while done < n:
        img = capture()
        if img is None:
            break
        if is_full(img):
            log("슬롯이 가득 참 -> 중지"); break
        if unit_score(img, key, y) < 0.6:       # 다 써서 줄이 사라졌거나 밀렸음
            y2 = find_unit(img, key)
            if y2 is None and done == 0:                  # patch122: 하나도 안 눌렀는데 안 보이면 다시 찾기
                log(f"{name} 줄이 밀려서 안 보임 -> 다시 찾기")
                y2 = locate(key)
            if y2 is None:
                log(f"{name} 줄이 사라짐(다 배치함?) -> 중지"); break
            y = y2
        k = min(CHUNK, n - done)
        tap_multi([(DEPLOY_X, y)] * k, f"{name} 배치 {done + 1}~{done + k}", gap=0.2)
        done += k
        _sleep(0.2)
    return done


def ensure_release_btn(img):
    """상세창 아래에 빨간 '해제' 버튼이 없으면(예: '초월' 탭) '상세' 탭으로 돌려서 다시 확인. 이미지 반환"""
    for k in range(2):
        if red(img, BTN_RELEASE) > 0.5:
            return img
        log("해제 버튼이 안 보임(다른 탭?) -> '상세' 탭으로 이동")
        tap(TAB_DETAIL, "상세 탭")
        im2 = preset.wait_for(lambda im: red(im, BTN_RELEASE) > 0.5, 2.0, first=0.3, step=0.2)
        if im2 is not None and red(im2, BTN_RELEASE) > 0.5:
            return im2
        img = snap(0.2)
        if img is None:
            return None
    return img


def release_rest(start=KEEP + 1, cap=10):
    """영웅 목록에서 start 번째 줄이 빌 때까지 그 줄의 영웅을 해제"""
    if not open_hero_tab():
        return False
    img = snap(0.15)
    for k in range(cap):
        if img is None:
            return False
        if not hero_row_filled(img, start):
            img = snap(0.3)                  # 화면 전환 중일 수 있어 한 번 더 확인
            if img is None or not hero_row_filled(img, start):
                log(f"{start}번째 줄이 비었음 -> 해제 완료 ({k}명 해제)")
                return True
        tap((HERO_ROW_X, hero_row_y(start)), f"{start}번째 영웅")
        img = preset.wait_for(detail_open, 3.0, first=0.2, step=0.15)
        if img is None or not detail_open(img):
            img = snap(0.3)
            if img is not None and not hero_row_filled(img, start):
                log(f"{start}번째 줄이 비었음 -> 해제 완료 ({k}명 해제)")
                return True
            shot_fail("barracks_detail_not_open", img)
            log("상세창이 안 열림 -> 중단"); return False
        img = ensure_release_btn(img)
        if img is None or red(img, BTN_RELEASE) <= 0.5:
            shot_fail("barracks_release_btn_not_found", img)
            log("해제 버튼을 못 찾음 -> 중단"); return False
        tap(BTN_RELEASE, "해제")
        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.25, step=0.15)
        if img is None or detail_open(img):
            shot_fail("barracks_still_open_after_release", img)
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
    log("해제를 너무 많이 반복해 중단")
    return False


LIST_ROI = (60, 925, 580, 1195)      # 영웅 목록이 보이는 영역


def _list_moved(a, b, thr=6.0):
    ga = cv2.cvtColor(a[LIST_ROI[1]:LIST_ROI[3], LIST_ROI[0]:LIST_ROI[2]], cv2.COLOR_BGR2GRAY).astype(np.int16)
    gb = cv2.cvtColor(b[LIST_ROI[1]:LIST_ROI[3], LIST_ROI[0]:LIST_ROI[2]], cv2.COLOR_BGR2GRAY).astype(np.int16)
    return float(np.abs(ga - gb).mean()) > thr


def scroll_bottom(max_swipes=4):
    """영웅 목록을 더 안 움직일 때까지 위로 밀어 맨 아래로 보냄"""
    prev = snap(0.1)
    for _ in range(max_swipes):
        swipe(360, 1150, 940, 250)
        cur = snap(0.35)
        if prev is None or cur is None:
            return False
        if not _list_moved(prev, cur):
            return True
        prev = cur
    return True


def _settle(tries=6):
    """목록이 멈출 때까지(연속 두 장이 같을 때까지) 기다린 뒤 그 화면을 돌려줌"""
    prev = snap(0.2)
    for _ in range(tries):
        cur = snap(0.25)
        if prev is None or cur is None:
            return cur
        if not _list_moved(prev, cur, 3.0):
            return cur
        prev = cur
    return prev


def _more_than_visible():
    """patch98: 목록을 맨 위로 올린 뒤 아래로 밀어 봄.
    움직이면 보이는 3줄보다 많음(True), 안 움직이면 3명 이하(False), 캡처 실패 None.
    (예전 방식은 해제 직후 목록 위치가 어중간해서 3명인데도 '움직임'으로 보고 불의정령까지 해제했음)"""
    prev = _settle()
    if prev is None:
        return None
    for _ in range(4):                                   # 맨 위로
        swipe(360, 1000, 1150, 250)
        cur = _settle()
        if cur is None:
            return None
        if not _list_moved(prev, cur, 3.0):
            break
        prev = cur
    swipe(360, 1150, 940, 250)                           # 아래로 밀어 봄
    after = _settle()
    if after is None:
        return None
    return _list_moved(prev, after)


def _bar_open(img):
    """patch111: 영웅 탭의 프리셋 줄(오른쪽 초록 '저장')이 펼쳐져 있으면 True"""
    hsv = cv2.cvtColor(img[885:918, 580:700], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 35) & (h <= 85) & (s >= 120) & (v >= 100)).mean()) >= 0.5


def _name_rows(img):
    """patch111: 맨 위에서부터 영웅 이름 줄의 y 목록 (레이아웃에 따라)"""
    return [960, 1050, 1140] if _bar_open(img) else [852, 942, 1032, 1122]


def _name_filled(img, y):
    v = cv2.cvtColor(img[y - 8:y + 8, 165:300], cv2.COLOR_BGR2HSV)[..., 2]
    return int((v > 200).sum()) > 150


def _list_to_top():
    prev = _settle()
    if prev is None:
        return None
    for _ in range(4):
        swipe(360, 1000, 1150, 250)
        cur = _settle()
        if cur is None:
            return None
        if not _list_moved(prev, cur, 3.0):
            return cur
        prev = cur
    return prev


def release_top(keep=KEEP, total=10):
    """patch111: 목록 맨 위에서 keep+1 번째 줄을 연달아 해제. 성공 True / 실패 False / 판단 불가 None"""
    if not open_hero_tab():
        return False
    img = _list_to_top()
    if img is None or barracks_open(img) or detail_open(img):
        return None
    rows = _name_rows(img)
    if len(rows) <= keep:
        return None
    y = rows[keep]
    done = 0
    for _ in range(total - keep + 1):
        img = _settle()
        if img is None:
            return False
        if not all(_name_filled(img, rows[j]) for j in range(keep)):
            log("맨 위 %d줄이 안 보임 -> 예전 방식으로" % keep)
            return None if done == 0 else False
        if not _name_filled(img, y):
            log(f"{keep + 1}번째 줄이 비었음 -> 해제 완료 ({done}명 해제)")
            return True
        tap((HERO_ROW_X, y + 10), "%d번째 영웅" % (keep + 1))
        img = preset.wait_for(detail_open, 3.0, first=0.12, step=0.1)
        if img is None or not detail_open(img):
            shot_fail("barracks_detail_not_open", img)
            log("상세창이 안 열림 -> 중단"); return False
        img = ensure_release_btn(img)                     # patch120: 상세 탭 확인
        if img is None or red(img, BTN_RELEASE) <= 0.5:
            shot_fail("barracks_release_btn_not_found", img)
            log("해제 버튼을 못 찾음 -> 중단"); return False
        tap(BTN_RELEASE, "해제")
        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.12, step=0.1)
        if img is None or detail_open(img):
            shot_fail("barracks_still_open_after_release", img)
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
        done += 1
    log(f"해제 완료 ({done}명 해제)")
    return True


def release_tail(keep=KEEP, total=10):
    try:                                                 # patch124: 빠른 방식 먼저
        r = release_top_fast(keep, total)
    finally:
        fc_stop()
    if r == "nofast":
        r = release_top(keep, total)                     # patch111: 위에서 연달아 해제가 기본
    if r is not None:
        return r
    log("위에서 해제 판단 불가 -> 맨 아래부터 해제(예전 방식)")
    return _release_tail_old(keep, total)


def _release_tail_old(keep=KEEP, total=10):
    """맨 아래로 스크롤하면 마지막 영웅이 3번째 줄 자리에 옴 -> 그 줄을 해제 (목록이 아래로 채워짐). keep 명이 남으면 멈춤"""
    if not open_hero_tab():
        return False
    img = snap(0.15)
    if img is None:
        return False
    fixed = total - keep if is_full(img) else None       # 10/10 이면 정확히 7번
    if not scroll_bottom():
        return False
    done = 0
    for k in range(total - keep):
        if fixed is None:
            more = _more_than_visible()                  # patch98: 맨 위에서 아래로 밀어 봄
            if more is None:
                return False
            row = 3
            if not more:                                 # patch110: 3줄 이하 -> 보이는 줄 수로 판단
                img = _settle()
                filled = [i for i in (1, 2, 3) if img is not None and hero_row_filled(img, i)]
                if len(filled) <= keep:
                    log(f"남은 영웅이 {keep}명 이하 -> 해제 완료 ({done}명 해제)")
                    return True
                row = filled[-1]
            elif not scroll_bottom():
                return False
        else:
            row = 3
        img = snap(0.3) if (fixed is not None and done > 0) else _settle()
        if img is None:
            return False
        if row != 3:
            pass
        elif not hero_row_filled(img, 3):
            log("3번째 줄이 비었음 -> 맨 아래로 다시 밀고 재확인")
            if not scroll_bottom():
                return False
            img = _settle()
            if img is None or not hero_row_filled(img, 3):
                log("3번째 줄이 여전히 비었음 -> 해제 중단"); return done > 0
        tap((HERO_ROW_X, hero_row_y(row)), "맨 아래 영웅")
        img = preset.wait_for(detail_open, 3.0, first=0.12, step=0.1)
        if img is None or not detail_open(img):
            shot_fail("barracks_detail_not_open", img)
            log("상세창이 안 열림 -> 중단"); return False
        img = ensure_release_btn(img)                     # patch120: 상세 탭 확인
        if img is None or red(img, BTN_RELEASE) <= 0.5:
            shot_fail("barracks_release_btn_not_found", img)
            log("해제 버튼을 못 찾음 -> 중단"); return False
        tap(BTN_RELEASE, "해제")
        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.12, step=0.1)
        if img is None or detail_open(img):
            shot_fail("barracks_still_open_after_release", img)
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
        done += 1
    log(f"해제 완료 ({done}명 해제)")
    return True


def topup(key, tries=3):
    """슬롯이 10/10 이 아니면 key 유닛을 한 명씩 더 배치 (연타 중 누락된 탭 보충)"""
    for _ in range(tries):
        img = snap(0.3)
        if img is None or is_full(img):
            return True
        log("슬롯이 덜 찼음 -> %s 1명 보충" % UNITS[key][0])
        if deploy(key, 1) == 0:
            return False
    img = snap(0.3)
    return img is not None and is_full(img)


def phase1(after_release=None):
    """불정 2명만 남기고 죽음의 손(부족하면 골렘)으로 채움 (patch190)"""
    if not release_tail():
        return False
    if after_release is not None:                      # patch130: 불정 2마리만 남았을 때 먼저 자리 잡기
        try:
            after_release()
        except Exception as e:
            if type(e).__name__ == "Abort":
                raise
            log("먼저 자리 잡기 오류: %r" % (e,))
    need = 10 - KEEP
    # patch190 (10-19 사용자): 죽음의 손이 20마리를 넘겨 펫(미라) 각성 효과 '병영에 있어도 최대 레벨업 +5' 가 적용됨
    #   -> 골렘 대신 죽음의 손 8마리. 부족하면 골렘으로 채움
    got = deploy("hand", need)
    topup("hand", 2)
    img = capture()
    if img is not None and not is_full(img) and got < need:
        got += deploy("golem", need - got)
    close_barracks()
    img = snap(0.3)
    ok = img is not None and not barracks_open(img)
    if got == 0:                                          # patch102: 한 명도 못 넣었으면 실패
        shot_fail("barracks_phase1_no_units", img)
        log("phase1: 골렘/죽음의 손을 한 명도 배치하지 못함 -> 실패")
        return False
    log("phase1 끝 (배치 시도 %d명)" % got, "OK" if ok else "병영이 안 닫힘")
    return ok


def phase2():
    """불의정령 2마리만 남기고 해제한 뒤 드루이드 6, 전장의북 2 로 채움 (빈 슬롯은 드루이드로 보충)"""
    if not release_tail():
        return False
    deploy("druid", 6)
    deploy("drum", 2)                                  # patch153: 다시 전장의북 2마리 (새 불정 2마리는 편성에서 뺌)
    full = topup("druid", 3)
    close_barracks()
    img = snap(0.3)
    closed = img is not None and not barracks_open(img)
    if not full and img is not None and is_full(img):    # patch98: 닫은 뒤 한 번 더 확인
        full = True
    if not full and img is not None:
        try:
            p = os.path.join(BASE, "shots", time.strftime("bk_notfull_%m%d_%H%M%S.png"))
            cv2.imwrite(p, img)
            log("슬롯이 10/10 아님 -> 화면 저장", p)
        except Exception:
            pass
    log("phase2 끝", "병영 닫힘" if closed else "병영이 안 닫힘",
        "| 슬롯 가득" if full else "| 슬롯이 덜 참 -> 실패로 처리")
    return closed and full


def read_state():
    img = capture()
    if img is None:
        log("캡처 실패"); return
    log("병영:", "열림" if barracks_open(img) else "닫힘", "| 상세창:", "열림" if detail_open(img) else "닫힘")
    log("슬롯 10/10:", "예" if is_full(img) else "아니오(또는 템플릿 없음)")
    if barracks_open(img):
        log("종족:", races_state(img))
        rows = row_centers(img)
        log("보이는 줄 중심 y:", rows)
        for k, (nm, rc) in UNITS.items():
            s = [(yc, round(unit_score(img, k, yc), 2)) for yc in rows]
            hit = find_unit(img, k)
            log(f"  {nm}({k}) 점수 {s} -> {'줄 y=%d' % hit if hit else '없음'}")
    else:
        log("영웅 목록 줄:", [i for i in range(1, 5) if hero_row_filled(img, i)], "번째 줄에 영웅 있음")


def make_template(key, row):
    img = capture()
    if img is None or not barracks_open(img):
        log("병영 화면을 연 상태에서 실행하세요"); return
    rows = row_centers(img)
    if not 1 <= row <= len(rows):
        log("보이는 줄:", len(rows)); return
    yc = rows[row - 1]
    os.makedirs(TPL, exist_ok=True)
    for n, x0 in (("1", 26), ("2", 131)):
        t = img[yc - 30:yc + 10, x0:x0 + 68]
        cv2.imwrite(os.path.join(TPL, f"bk_{key}{n}.png"), t)
    log(f"템플릿 저장: bk_{key}1.png, bk_{key}2.png (줄 {row}, y={yc})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "go"]
    cmd = args[0] if args else "read"
    if cmd == "read":
        read_state()
    elif cmd == "mk" and len(args) >= 3:
        make_template(args[1], int(args[2]))
    elif cmd == "races" and len(args) >= 2:
        set_races(args[1:])
    elif cmd == "scan" and len(args) >= 2 and args[1] in UNITS:
        scan(args[1])
    elif cmd == "release":
        release_tail()
    elif cmd == "deploy" and len(args) >= 3 and args[1] in UNITS:
        log("배치 %d명" % deploy(args[1], int(args[2])))
    elif cmd == "phase1":
        phase1()
    elif cmd == "phase2":
        phase2()
    else:
        print(__doc__)
    if not GO and cmd not in ("read", "mk"):
        print("(시험 모드: 아무것도 누르지 않았습니다. 실제 실행은 맨 끝에 go 를 붙이세요)")
