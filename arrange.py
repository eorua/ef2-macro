"""arrange.py - 성 클릭 '영웅 배치' 창에서 아이콘을 끌어 배치 정리
  불의정령 2마리: 성 9시 / 3시, 전장의북: 성 가운데, 나머지(드루이드 등)는 전부 12시에 겹쳐 놓고 '저장' (patch153)

  py arrange.py look     지금 화면(영웅 배치 창이 열린 상태)에서 아이콘을 어떻게 찾는지 출력 (아무것도 안 누름)
  py arrange.py open     성을 눌러 '영웅 배치' 창만 열어 봄 (go 필요)
  py arrange.py go       열기 -> 드래그 -> 확인 -> 저장 까지 실제 실행 (창이 이미 열려 있으면 그대로 진행)
  py arrange.py go draganddrop   드래그 방식을 input draganddrop 으로 (기본은 input swipe)
검증이 실패하면 '취소'를 눌러 원래 배치를 그대로 둡니다.
"""
import os, sys, time, subprocess
import cv2, numpy as np

ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
TPL = r"C:\macro\tpl"
SHOTS = r"C:\macro\shots"
GO = "go" in sys.argv[1:]
MODE = "draganddrop" if "draganddrop" in sys.argv[1:] else "swipe"

CASTLE = (350, 340)                       # 성 (여기를 누르면 영웅 배치 창)
BTN_SAVE = (267, 727)
BTN_CANCEL = (452, 727)
SAVE_ROI = (190, 705, 345, 750)
CANCEL_ROI = (375, 705, 530, 750)
ICON_ROI = (120, 190, 600, 560)           # 아이콘이 놓이는 영역 (x1, y1, x2, y2)
T12 = (350, 212)                          # 12시 (얼굴 중심 기준)
T_SPIRIT = [(221, 343), (485, 346)]       # patch292: 정확히 9시 / 3시 끝쪽 (성 y=340 수평선)
#               # 왼쪽 / 오른쪽 - patch110 (불의 정령 2마리)
T_DRUM = (352, 342)                       # 전장의 북: 성 한가운데
THR = {"spirit": 0.72, "druid": 0.72, "drum": 0.72}
NEAR = 26                                 # 이 거리 안이면 '그 자리에 있다'
MAX_MOVES = 30
GRAB = [(-12, 33), (0, 0), (18, 2), (-12, 18), (0, -10), (-22, 30)]   # 집는 위치(얼굴 중심 기준): 막대 끝 -> 얼굴 -> 화살표 끝 ...
_gv = [0]
# 놓을 지점 = 목표 얼굴 중심 + OFFS[목표]  (아이콘 기준점은 깃발 아래 막대 끝이라 위치마다 실측으로 맞춤)
OFFS = {(352, 342): [0, 35], (350, 212): [9, 28], (226, 314): [-12, 33], (483, 317): [7, 40], (359, 474): [7, 41],
        (276, 316): [-6, 35], (430, 315): [4, 38], (356, 406): [5, 39],
        (249, 353): [-9, 34], (459, 348): [6, 39]}     # patch110: 새 자리(추정, 보정 로직이 맞춤)     # patch107: 새 자리(추정, 보정 로직이 맞춤)
GUARD = None                              # main.py 가 환생 팝업 안전장치를 넣어 줌
OFFS.setdefault((272, 396), [-9, 34]); OFFS.setdefault((437, 396), [6, 39])     # patch130
OFFS.setdefault((221, 343), [-12, 33]); OFFS.setdefault((485, 346), [7, 40])
OFFS.setdefault((253, 368), [-9, 34]); OFFS.setdefault((459, 372), [6, 39])     # patch169: 가까운 자리 보정값에서 시작     # patch157: 가까운 자리 실측값에서 시작 (보정 로직이 맞춤)


def log(*a):
    print(time.strftime("[%H:%M:%S] arrange:"), *a, flush=True)


def capture():
    try:
        png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True, timeout=20).stdout
        return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR) if png else None
    except Exception:
        return None


def tap(pt, label=""):
    if GO and GUARD:
        GUARD()
    log(("클릭 " if GO else "[시험] 클릭할 곳 ") + "%s %s" % (label, pt))
    if GO:
        subprocess.run(ADB + ["shell", "input", "tap", str(int(pt[0])), str(int(pt[1]))])


def drag(p, q, ms=700):
    if GO and GUARD:
        GUARD()
    log(("드래그 " if GO else "[시험] 드래그 ") + "%s -> %s (%s)" % (tuple(map(int, p)), tuple(map(int, q)), MODE))
    if GO:
        cmd = ["shell", "input", MODE, str(int(p[0])), str(int(p[1])), str(int(q[0])), str(int(q[1])), str(ms)]
        subprocess.run(ADB + cmd)


_T = {}


def _tpl(key):
    if key not in _T:
        p = os.path.join(TPL, "arr_%s.png" % key)
        _T[key] = cv2.imread(p) if os.path.exists(p) else None
    return _T[key]


def ratio(img, roi, kind):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if kind == "green":
        m = (h >= 35) & (h <= 85) & (s >= 120) & (v >= 90)
    else:
        m = ((h <= 8) | (h >= 172)) & (s >= 150) & (v >= 90)
    return float(m.mean())


def dialog_open(img):
    """'영웅 배치' 창: 초록 저장 + 빨간 취소 버튼이 나란히 보임"""
    return img is not None and ratio(img, SAVE_ROI, "green") >= 0.4 and ratio(img, CANCEL_ROI, "red") >= 0.4


def find_icons(img, key, thr=None, sep=28):
    """key(spirit/druid/drum) 얼굴 그림을 찾아 [(점수, x, y)] (점수 높은 순)"""
    t = _tpl(key)
    if t is None:
        return []
    thr = THR[key] if thr is None else thr
    x1, y1, x2, y2 = ICON_ROI
    r = cv2.matchTemplate(img[y1:y2, x1:x2], t, cv2.TM_CCOEFF_NORMED).copy()
    out = []
    for _ in range(12):
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx < thr:
            break
        out.append((round(float(mx), 2), loc[0] + x1 + t.shape[1] // 2, loc[1] + y1 + t.shape[0] // 2))
        cv2.rectangle(r, (loc[0] - sep, loc[1] - sep), (loc[0] + sep, loc[1] + sep), -1, -1)
    return out


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


# 깃발(아이콘)의 노란 화살표 모양 (34x18). 아이콘 종류와 상관없이 모든 깃발이 같다.
_CHEV_ROWS = ['...#####..........', '...######.........', '....#####.........', '....#####.........', '.....#####........', '.....#####........', '.....######.......', '......#####.......', '......#####.......', '.......#####......', '#......#####......', '........#####.....', '....#...#####.....', '#..##.#.######....', '..#......#####....', '.........######...', '..........#####...', '..........######..', '..........######..', '..........#####...', '.........######...', '.#.......#####....', '.#......######....', '##......######....', '#.......#####.....', '.......######.....', '.......#####......', '......######......', '......#####.......', '.....######.......', '.....######.......', '.....#####........', '....######........', '....#####.........']
_CHEV = np.array([[255 if ch == "#" else 0 for ch in r] for r in _CHEV_ROWS], np.uint8)
CHEV_DX = 35          # 화살표 중심은 얼굴 중심에서 오른쪽으로 35


def _ymask(img):
    h = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (((h[..., 0] >= 18) & (h[..., 0] <= 34) & (h[..., 1] >= 140) & (h[..., 2] >= 140)) * 255).astype(np.uint8)


def face_kind(img, x, y):
    """얼굴 색으로 종류 구분: 'sp'(붉은 머리 불의정령) / 'dm'(회색+파랑 전장의 북) / 'ot'(그 밖: 드루이드 등)"""
    c = img[max(0, y - 12):y + 12, max(0, x - 18):x + 14]
    if c.size == 0:
        return "ot"
    h = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    H, S, V = h[..., 0].astype(int), h[..., 1], h[..., 2]
    red = (((H <= 12) | (H >= 170)) & (S > 120) & (V > 120)).mean()
    blue = ((H >= 85) & (H <= 115) & (S > 60) & (V > 60)).mean()
    grey = ((S < 50) & (V > 110)).mean()
    if red >= 0.12:
        return "sp"
    if 0.05 <= blue <= 0.2 and grey >= 0.3:
        return "dm"
    return "ot"


def scan3(img, thr=0.58):
    """(불의정령, 드루이드 등, 전장의 북) 각 [(점수, x, y)]  (x, y = 얼굴 중심). 깃발 화살표로 찾고 얼굴 색으로 종류를 나눔"""
    x1, y1, x2, y2 = ICON_ROI
    m = _ymask(img[y1:y2, x1:x2])
    r = cv2.matchTemplate(m, _CHEV, cv2.TM_CCOEFF_NORMED).copy()
    sp, ot, dm = [], [], []
    for _ in range(16):
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx < thr:
            break
        fx = loc[0] + x1 + _CHEV.shape[1] // 2 - CHEV_DX
        fy = loc[1] + y1 + _CHEV.shape[0] // 2
        item = (round(float(mx), 2), fx, fy)
        {"sp": sp, "ot": ot, "dm": dm}[face_kind(img, fx, fy)].append(item)
        cv2.rectangle(r, (loc[0] - 14, loc[1] - 14), (loc[0] + 14, loc[1] + 14), -1, -1)
    return sp, ot, dm


def scan(img):
    sp, ot, dm = scan3(img)
    return sp, ot + dm


def _rect_gap(p, c):
    """점 p 가 아이콘(얼굴 중심 c) 깃발 사각형에서 얼마나 떨어져 있나 (안이면 음수)"""
    dx = max(c[0] - 24 - p[0], p[0] - (c[0] + 41))
    dy = max(c[1] - 21 - p[1], p[1] - (c[1] + 21))
    return max(dx, dy)


def grab_points(src, others):
    """src 깃발 안에서, 다른 아이콘 깃발과 가장 멀리 떨어진 집을 곳 순서 (좋은 순)"""
    cs = []
    for dx in (-14, -4, 6, 16, 26):
        for dy in (-14, -6, 0, 6, 14):
            p = (src[0] + dx, src[1] + dy)
            gap = min([_rect_gap(p, o) for o in others] or [99])
            cs.append((min(gap, 12), -abs(dx - 6) - abs(dy), p))
    cs.sort(reverse=True)
    return [p for _, _, p in cs]


def status(img):
    """(불의정령이 자리 잡은 목표 수, 12시 밖에 남은 나머지 아이콘 목록, 자리 밖 불의정령 목록)"""
    sp, ot, dm = scan3(img)
    placed = 0
    free_t = []
    for t in T_SPIRIT:
        if any(dist((x, y), t) <= NEAR for _, x, y in sp):
            placed += 1
        else:
            free_t.append(t)
    stray_sp = [(x, y) for _, x, y in sp if all(dist((x, y), t) > NEAR for t in T_SPIRIT)]
    occ = [t for t in T_SPIRIT if any(dist((x, y), t) <= NEAR for _, x, y in sp)]     # patch112: 정령이 이미 앉은 자리만 제외
    stray_ot = [(x, y) for _, x, y in ot if dist((x, y), T12) > NEAR and all(dist((x, y), t) > NEAR for t in occ)]
    stray_dm = [(x, y) for _, x, y in dm if dist((x, y), T_DRUM) > NEAR]
    if not free_t and stray_sp:                  # patch130: 좌우 자리가 다 찼으면 남는 정령(새 불정)은 12시로
        stray_ot = stray_ot + [p for p in stray_sp if dist(p, T12) > NEAR]
        stray_sp = []
    return placed, stray_ot, stray_sp, free_t, stray_dm


def open_dialog():
    img = capture()
    if dialog_open(img):
        return True
    tap(CASTLE, "성")
    for _ in range(8):
        time.sleep(0.5)
        if dialog_open(capture()):
            return True
    return False


def snap(name):
    try:
        img = capture()
        if img is not None:
            os.makedirs(SHOTS, exist_ok=True)
            cv2.imwrite(os.path.join(SHOTS, name), img)
            log("화면 저장: shots\\%s" % name)
    except Exception:
        pass


def run():
    """성공 True / 실패 False (실패하면 취소를 눌러 원래 배치 유지)"""
    if not open_dialog():
        log("영웅 배치 창이 안 열림 (성 위치를 확인하세요) -> 중단")
        snap("arrange_noopen.png")
        return False
    fails = 0
    last = None
    stuck = {}                                   # patch112: 옮겼는데 변화 없던 아이콘 위치
    bad_pts = []                                 # patch124: 집었더니 제자리 정령이 딸려 나온 위치
    prev_placed = None
    last_src = None
    prev = None
    best = 0
    for mv in range(MAX_MOVES):
        time.sleep(0.4)
        img = capture()
        if not dialog_open(img):
            log("영웅 배치 창이 사라짐 -> 중단")
            return False
        placed, stray_ot, stray_sp, free_t, stray_dm = status(img)
        sig = (placed, len(stray_ot), len(stray_sp), len(stray_dm))
        if prev_placed is not None and last_src is not None and placed < prev_placed:
            bad_pts.append(last_src)
            log("%s 를 옮겼더니 제자리 정령이 빠짐 -> 이 위치는 다시 집지 않음" % (last_src,))
        prev_placed = placed
        if mv == 0:
            _sp, _dr, _dm = scan3(img)
            log("찾은 아이콘: 정령 %s / 드루이드 %s / 북 %s" % ([p[1:] for p in _sp], [p[1:] for p in _dr], [p[1:] for p in _dm]))
        log("자리 잡은 불의정령 %d/%d / 12시 밖 드루이드 %d / 자리 밖 북 %d / 자리 밖 불의정령 %d" % (placed, len(T_SPIRIT), len(stray_ot), len(stray_dm), len(stray_sp)))
        if placed == len(T_SPIRIT) and not stray_ot and not stray_dm:
            log("배치 완료 -> 저장")
            tap(BTN_SAVE, "저장")
            time.sleep(1.5)
            if dialog_open(capture()):
                tap(BTN_SAVE, "저장(재시도)")
                time.sleep(1.5)
            ok = not dialog_open(capture())
            log("저장 " + ("성공" if ok else "실패 -> 취소"))
            if not ok:
                tap(BTN_CANCEL, "취소")
            return ok
        if sig == last:
            fails += 1
            if last_src is not None:
                k_ = (last_src[0] // 20, last_src[1] // 20)
                stuck[k_] = stuck.get(k_, 0) + 1
            if fails >= 6:
                log("드래그해도 변화가 없음 (%s 방식)" % MODE)
                snap("arrange_stuck.png")
                return _give_up(placed)
        else:
            fails = 0
        last = sig
        if prev is not None and prev[0] in ("ot", "dm") and (len(stray_ot) if prev[0] == "ot" else len(stray_dm)) >= prev[1]:
            _gv[0] += 1
            log("나머지가 안 옮겨짐 -> 집는 위치 바꿈 (%d)" % _gv[0])
        if not GO:
            log("(시험 모드: 여기까지만 판별)")
            return True
        tgt = None
        kind = None
        best = max(best, placed)
        # patch112: 후보 전부에 점수를 매겨 가장 집기 쉽고 목표가 비어 있는 것부터
        sp_a, dr_a, dm_a = scan3(img)
        allpts = [(x, y, "sp") for _, x, y in sp_a] + [(x, y, "ot") for _, x, y in dr_a] + [(x, y, "dm") for _, x, y in dm_a]
        cands = []
        for s in stray_sp:
            if free_t:
                cands.append(("sp", s, min(free_t, key=lambda q: dist(s, q))))
        for s in stray_ot:
            cands.append(("ot", s, T12))
        for s in stray_dm:
            cands.append(("dm", s, T_DRUM))
        cands = [c for c in cands if all(dist(c[1], b) > 25 for b in bad_pts)]     # patch124

        def _cscore(c):
            k, s, t = c
            oth = [(x, y) for x, y, _ in allpts if dist((x, y), s) > 3]
            gp = grab_points(s, oth)[0]
            iso = min([_rect_gap(gp, o) for o in oth] or [20])
            blocked = any(kk != k and dist((x, y), t) <= 34 and dist((x, y), s) > 3 for x, y, kk in allpts)
            sc = min(iso, 20) - (40 if blocked else 0) - 60 * stuck.get((s[0] // 20, s[1] // 20), 0)
            # patch117: 겹쳐 쌓였으면 맨 앞(더 아래쪽에 그려진) 아이콘부터
            cov = any(yy > s[1] + 3 and _rect_gap(gp, (xx, yy)) < 0 for xx, yy, _ in allpts if dist((xx, yy), s) > 3)
            over = any(abs(xx - s[0]) < 65 and abs(yy - s[1]) < 42 for xx, yy, _ in allpts if dist((xx, yy), s) > 3)
            if cov:
                sc -= 80
            elif over:
                sc += 15
            if k == "dm":
                sc -= 5
            if k == "sp" and stray_sp and placed < best:
                sc += 10                                 # 밀려난 정령은 조금 먼저
            return sc

        if cands:
            kind, src, tgt = max(cands, key=_cscore)
            log("옮길 아이콘: %s %s -> %s (점수 %.0f)" % ({"sp": "불의정령", "ot": "드루이드 등", "dm": "북"}[kind], src, tgt, _cscore((kind, src, tgt))))
        last_src = src if cands else None
        prev = (kind, len(stray_ot) if kind == "ot" else len(stray_dm))
        if tgt is not None:
            off = OFFS[tgt]
            sp_all, dr_all, dm_all = scan3(img)
            pool_all = {"sp": sp_all, "ot": dr_all, "dm": dm_all}[kind]
            rad = 70 if kind == "sp" else 35
            lone = kind == "sp" or not any(dist((x, y), tgt) <= rad for _, x, y in pool_all)
            drop = (tgt[0] + off[0], tgt[1] + off[1])
            others = [(x, y) for _, x, y in sp_all + dr_all + dm_all if dist((x, y), src) > 3]
            gps = grab_points(src, others)
            drag(gps[_gv[0] % len(gps)], drop)
            if lone:
                for _try in range(3):
                    time.sleep(0.7)
                    sp2, dr2, dm2 = scan3(capture())
                    near = [(x, y) for _, x, y in {"sp": sp2, "ot": dr2, "dm": dm2}[kind] if dist((x, y), tgt) <= rad]
                    if not near:
                        break
                    f = min(near, key=lambda p: dist(p, tgt))
                    if dist(f, tgt) <= 10 or _try == 2:
                        break
                    drop = (drop[0] + int(tgt[0] - f[0]), drop[1] + int(tgt[1] - f[1]))
                    OFFS[tgt] = [drop[0] - tgt[0], drop[1] - tgt[1]]
                    log("놓인 위치 오차 %s -> 한 번 더 보정" % ((int(tgt[0] - f[0]), int(tgt[1] - f[1])),))
                    oth2 = [(x, y) for _, x, y in sp2 + dr2 + dm2 if dist((x, y), f) > 3]
                    drag(grab_points(f, oth2)[0], drop)
        else:
            snap("arrange_unknown.png")
            if placed >= 1:                                          # patch122/124: 정령이 1마리 이상 제자리면 저장
                log("정령 %d/%d (나머지는 가려져 안 보임), 드루이드·북은 제자리 -> 지금까지 옮긴 것 저장" % (placed, len(T_SPIRIT)))
                tap(BTN_SAVE, "저장")
                time.sleep(1.5)
                if dialog_open(capture()):
                    tap(BTN_SAVE, "저장(재시도)")
                    time.sleep(1.5)
                ok = not dialog_open(capture())
                log("저장 " + ("성공" if ok else "실패 -> 취소"))
                if not ok:
                    tap(BTN_CANCEL, "취소")
                return ok
            log("더 옮길 아이콘을 못 찾음 (가려져 있거나 못 읽음) -> 취소")
            tap(BTN_CANCEL, "취소")
            return False
    log("이동 횟수 한도")
    return _give_up(placed)


def _give_up(placed):
    """patch124: 정령이 1마리 이상 제자리면 지금까지 옮긴 것 저장, 아니면 취소"""
    if placed >= 1:
        log("정령 %d/%d 제자리 -> 지금까지 옮긴 것 저장" % (placed, len(T_SPIRIT)))
        tap(BTN_SAVE, "저장")
        time.sleep(1.5)
        if dialog_open(capture()):
            tap(BTN_SAVE, "저장(재시도)")
            time.sleep(1.5)
        ok = not dialog_open(capture())
        log("저장 " + ("성공" if ok else "실패 -> 취소"))
        if not ok:
            tap(BTN_CANCEL, "취소")
        return ok
    log("-> 취소")
    tap(BTN_CANCEL, "취소")
    return False


if __name__ == "__main__":
    cmd = [a for a in sys.argv[1:] if a not in ("go", "draganddrop", "swipe")]
    cmd = cmd[0] if cmd else ("run" if GO else "look")
    if cmd == "look":
        img = capture()
        if img is None:
            print("캡처 실패")
        else:
            sp, ot, dm = scan3(img)
            print("영웅 배치 창:", dialog_open(img))
            print("불의정령:", sp)
            print("드루이드 등:", ot)
            print("전장의 북:", dm)
            print("상태(자리 잡은 불의정령, 12시 밖 드루이드, 자리 밖 불의정령, 빈 목표, 자리 밖 북):", status(img))
    elif cmd == "open":
        print("열림:", open_dialog())
    else:
        print("결과:", run())
