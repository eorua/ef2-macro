"""barracks.py (v44) - 병영 편성 자동화 (최대레벨 유닛으로 레벨업 -> 렙뻥 유닛으로 재편성)

시험 모드(기본): 화면만 읽고 아무것도 누르지 않음. 실제 실행은 맨 끝에 go.
  py barracks.py read                 현재 화면 상태 읽기 (병영/영웅 목록 어디서든)
  py barracks.py release go           영웅 목록에서 3번째 줄부터 전부 해제 (위 2명만 남김)
  py barracks.py deploy golem 8 go    병영에서 골렘을 최대 8명 배치 (슬롯이 차면 멈춤)
  py barracks.py phase1 go            2명만 남기고 -> 골렘(부족하면 죽음의 손)으로 채움
  py barracks.py phase2 go            3번째 줄부터 해제 -> 드루이드 6, 불의정령 1, 전장의북 1 로 채움
  py barracks.py races 인간 go        병영 종족 필터를 그 종족만 켜기 (여러 개면 띄어쓰기)
  py barracks.py scan 이름 go         병영 목록을 맨 위->맨 아래로 훑으며 각 화면의 점수 출력 + scan_N.png 저장 (진단용)
  py barracks.py mk 이름 줄번호       현재 병영 화면에서 그 줄의 얼굴을 템플릿으로 저장 (예: mk spirit 3)
"""
import sys, os, time, cv2, numpy as np
import preset

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
LABEL_ROI = (50, 794, 102, 815)     # '10/10' 슬롯 표시
KEEP = 2                            # 위에서 남길 영웅 수

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
    time.sleep(wait)
    return capture()


def swipe(x, y1, y2, ms=600):
    log(("스와이프 " if GO else "[시험] 스와이프 ") + f"{x},{y1} -> {y2}")
    if GO:
        import subprocess
        subprocess.run(preset.ADB + ["shell", "input", "swipe", str(x), str(y1), str(x), str(y2), str(ms)])


def tap_multi(pts, label="", gap=0.12):
    """여러 곳을 adb 한 번으로 연달아 누름 (adb 호출 1번 = 프로세스 1번이라 훨씬 빠름)"""
    log(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{label} {pts}")
    if GO and pts:
        import subprocess
        cmd = "; ".join(f"input tap {x} {y} & sleep {gap}" for x, y in pts) + "; wait"
        subprocess.run(preset.ADB + ["shell", cmd])


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


def label_mask(img):
    x1, y1, x2, y2 = LABEL_ROI
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
    m = label_mask(img)
    if m.shape != t.shape:
        return False
    a, b = m > 0, t > 0
    inter = (a & b).sum()
    union = (a | b).sum()
    return union > 0 and inter / union > 0.75


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
        time.sleep(0.45)
    tap(TAB_HERO, "영웅 탭")
    time.sleep(0.35)
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
        time.sleep(0.3)
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


SW_MS = 800        # 스크롤 드래그 시간(ms). 느릴수록 관성(밀림)이 적어 줄을 건너뛰지 않음
SW_A, SW_B = 850, 1090   # 드래그 구간 (240px = 약 2.8줄, 화면에 보이는 4줄보다 작게)


def _best(img, key):
    return max([unit_score(img, key, yc) for yc in row_centers(img)] or [0.0])


def _scroll_once(direction):
    if direction == "up":
        swipe(360, SW_A, SW_B, SW_MS)
    else:
        swipe(360, SW_B, SW_A, SW_MS)
    return snap(0.6)


def _scroll_search(key, direction, steps):
    """direction 'up' = 맨 위쪽으로, 'down' = 아래쪽으로 조금씩 움직이며 찾기. (찾은 y 또는 None, 끝에 닿았는지)"""
    prev = capture()
    for n in range(steps):
        img = _scroll_once(direction)
        if img is None:
            return None, True
        y = find_unit(img, key)
        log("  %s %d: 최고점 %.2f%s" % (direction, n + 1, _best(img, key), " -> 찾음" if y else ""))
        if y is not None:
            return y, False
        if same_view(prev, img):
            img2 = snap(0.5)                      # 정말 끝인지 한 번 더 확인
            if same_view(img, img2):
                return None, True
            img = img2
        prev = img
    return None, False


def locate(key, tries=12):
    """유닛 줄 찾기: 지금 화면 -> 맨 위까지 올리며 -> 맨 위부터 아래로 내리며. 줄 중심 y 반환"""
    img = snap(0.2)
    if img is None:
        return None
    y = find_unit(img, key)
    log("  지금 화면: 최고점 %.2f" % _best(img, key))
    if y is None:
        y, _ = _scroll_search(key, "up", 6)
        if y is None:
            y, _ = _scroll_search(key, "down", tries)
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
            if y2 is None:
                log(f"{name} 줄이 사라짐(다 배치함?) -> 중지"); break
            y = y2
        k = min(CHUNK, n - done)
        tap_multi([(DEPLOY_X, y)] * k, f"{name} 배치 {done + 1}~{done + k}", gap=0.1)
        done += k
        time.sleep(0.2)
    return done


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
            log("상세창이 안 열림 -> 중단"); return False
        tap(BTN_RELEASE, "해제")
        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.25, step=0.15)
        if img is None or detail_open(img):
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
    log("해제를 너무 많이 반복해 중단")
    return False


def phase1():
    """2명만 남기고 골렘(부족하면 죽음의 손)으로 채움"""
    if not release_rest():
        return False
    need = 10 - KEEP
    got = deploy("golem", need)
    img = capture()
    if img is not None and not is_full(img) and got < need:
        got += deploy("hand", need - got)
    close_barracks()
    img = snap(0.3)
    ok = img is not None and not barracks_open(img)
    log("phase1 끝 (배치 시도 %d명)" % got, "OK" if ok else "병영이 안 닫힘")
    return ok


def phase2():
    """3번째 줄부터 해제하고 드루이드 6, 전장의북 1, 불의정령 1 로 채움"""
    if not release_rest():
        return False
    deploy("druid", 6)
    deploy("drum", 1)
    deploy("spirit", 1)
    close_barracks()
    img = snap(0.3)
    log("phase2 끝", "병영 닫힘" if img is not None and not barracks_open(img) else "병영이 안 닫힘")
    return img is not None and not barracks_open(img)


def scan(key):
    """진단: 그 유닛의 종족만 앞에 오게 하고 맨 위 -> 맨 아래로 훑으며 점수를 찍고 화면을 저장"""
    name, race = UNITS[key]
    if not open_barracks() or not set_races_for(race):
        return
    prev = None
    for n in range(8):                      # 맨 위로
        img = _scroll_once("up")
        if img is None or same_view(prev, img):
            break
        prev = img
    prev = None
    for n in range(14):
        img = snap(0.2)
        if img is None:
            break
        rows = row_centers(img)
        sc = {k: round(max([unit_score(img, k, yc) for yc in rows] or [0]), 2) for k in UNITS}
        log("화면 %d 줄=%s 점수=%s" % (n, rows, sc))
        cv2.imwrite(os.path.join(BASE, "scan_%02d.png" % n), img)
        if same_view(prev, img):
            break
        prev = img
        _scroll_once("down")


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
        release_rest()
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
