import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
GO = "go" in sys.argv[1:]

# 클릭 좌표 (720x1280 기준)
P = {
    "영입":     (650, 790),
    "새로고침": (465, 790),
    "훈장구매": (585, 790),
    "닫기X":    (674, 790),
    "확인(금지)": (266, 632),
    "취소":     (452, 632),
    "성탭":     (302, 1240),
    "영웅탭":   (185, 1240),
}
# 점 위치 (중심 x, y) - 영웅 탭의 '영입' 주황 점 / 고용 화면의 '새로고침' 빨간 점
DOT_HERO = (608, 768)
DOT_REFRESH = (420, 768)
DOT_R = 14          # 검사 상자 반지름(px)
DOT_THR = 0.06      # 이 비율 이상이면 점이 있다고 판단


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    if not png:
        return None
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def tap(name):
    x, y = P[name]
    if GO:
        subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)])
    print(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{name} ({x},{y})")


def dot_ratio(img, center, kind):
    x, y = center
    box = img[max(y - DOT_R, 0):y + DOT_R + 1, max(x - DOT_R, 0):x + DOT_R + 1]
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    if kind == "orange":
        m = cv2.inRange(hsv, (8, 200, 230), (25, 255, 255))
    elif kind == "any":   # 점이 깜빡이며 빨강 <-> 주황으로 바뀌므로 둘 다 인정
        m = cv2.inRange(hsv, (0, 200, 200), (25, 255, 255)) | cv2.inRange(hsv, (172, 200, 200), (180, 255, 255))
    else:  # red
        m = cv2.inRange(hsv, (0, 200, 200), (8, 255, 255)) | cv2.inRange(hsv, (172, 200, 200), (180, 255, 255))
    return float(m.mean()) / 255.0


def mark():
    img = capture()
    if img is None:
        print("캡처 실패 (ADB 연결 확인)")
        return
    ro = dot_ratio(img, DOT_HERO, "orange")
    rr = dot_ratio(img, DOT_REFRESH, "any")
    print("영입 주황점 비율:", round(ro, 3), "| 새로고침 빨간점 비율:", round(rr, 3), "| 기준:", DOT_THR)
    for name, (x, y) in P.items():
        c = (0, 0, 255) if "금지" in name else (0, 255, 0)
        cv2.circle(img, (x, y), 22, c, 3)
        cv2.putText(img, name, (max(x - 60, 0), y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    for (x, y), c in ((DOT_HERO, (0, 165, 255)), (DOT_REFRESH, (255, 0, 255))):
        cv2.rectangle(img, (x - DOT_R, y - DOT_R), (x + DOT_R, y + DOT_R), c, 2)
    path = os.path.join(BASE, "shots", "mark.png")
    cv2.imwrite(path, img)
    print("저장:", path)


GEM_ROW_Y0, GEM_ROW_DY = 868, 107      # patch204: 고용 목록 줄의 가격 버튼 가운데 y (첫 줄, 줄 간격)
GEM_FILE = os.path.join(BASE, "recruit_left.json")


def _gem_ratio(img, y):
    """가격 버튼 왼쪽의 파란 보석 아이콘 비율 (훈장 가격은 노란 메달이라 0)"""
    roi = cv2.cvtColor(img[y - 14:y + 14, 583:620], cv2.COLOR_BGR2HSV)
    return float(((roi[..., 0] >= 95) & (roi[..., 0] <= 125) & (roi[..., 1] > 100) & (roi[..., 2] > 140)).mean())


def gem_left():
    """patch204: 훈장구매 뒤 남은 '보석으로 사야 하는' 영웅 이름/가격을 읽어 recruit_left.json 에 저장 (패널에 크게 표시)"""
    import json, re
    img = capture()
    if img is None:
        return None
    cv2.imwrite(os.path.join(BASE, "shots", "recruit_after_buy.png"), img)
    info = {"name": "", "price": None, "t": time.time()}
    for i in range(4):
        y = GEM_ROW_Y0 + GEM_ROW_DY * i
        if y + 14 > img.shape[0] or _gem_ratio(img, y) < 0.08:
            continue
        name, price = "", None
        try:
            import ocrx
            c = cv2.resize(img[y - 42:y - 4, 150:430], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            ws = ocrx.words(c) or []
            name = "".join(w[0] for w in sorted(ws, key=lambda w: w[1]) if not re.search(r"\d", w[0])).strip()
        except Exception as e:
            print("보석 영웅 글자 읽기 오류:", e)
        info.update(name=name or "?", price=price)
        break
    try:
        with open(GEM_FILE, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)
    except OSError:
        pass
    print("보석으로 살 영웅: %s" % (info["name"] or "없음"))      # 보석 가격은 항상 2000 고정이라 안 읽음
    return info


# ---------------------------------------------------------------- patch222: 고용 화면 쿨타임 숫자(빨간 MM:SS) 읽기
# 글꼴이 깔끔해서 (1) 빨간 글자를 조각으로 나눠 (2) 모아 둔 숫자 그림(tpl\rtimer\)으로 읽고
# (3) 윈도우 OCR 로도 읽어 서로 맞춰 봄. OCR 로 확실히 읽은 숫자는 그림으로 저장해 다음부터 그림 인식에 씀.
TIMER_ROI = (300, 760, 430, 800)          # x1, y1, x2, y2 (10-23 캡처: 글자 336~384, 774~787)
TIMER_DIR = os.path.join(BASE, "tpl", "rtimer")
TIMER_SAVE = os.path.join(BASE, "shots", "rtimer")
_TPL = None
last_wait = None                          # 마지막으로 읽은 남은 시간(초). main 이 다음 확인 시각을 정할 때 씀
last_note = ""


def _red_mask(img):
    x1, y1, x2, y2 = TIMER_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((((h <= 10) | (h >= 170)) & (s > 110) & (v > 120)).astype(np.uint8)) * 255


def _pieces(mask):
    """빨간 글자 -> 숫자 조각 [(x, 그림)] 과 쌍점(:) x 위치 목록"""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    comps = [(int(st[i][0]), int(st[i][1]), int(st[i][2]), int(st[i][3]), int(st[i][4]), i) for i in range(1, n) if st[i][4] >= 3]
    if not comps:
        return [], []
    hmax = max(c[3] for c in comps)
    digs, dots = [], []
    for x, y, w, h, a, i in sorted(comps):
        if h >= 0.6 * hmax and h >= 8:
            m = (lab[y:y + h, x:x + w] == i).astype(np.uint8) * 255
            digs.append((x, m))
        elif w <= 5 and h <= 5:
            dots.append(x)
    colons = []
    for x in dots:                        # 위아래 점 두 개 = 쌍점 하나
        if not colons or abs(x - colons[-1]) > 3:
            colons.append(x)
    return digs, colons


def _norm(m):
    return cv2.resize(m, (10, 16), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _load_tpl():
    global _TPL
    if _TPL is None:
        _TPL = {}
        try:
            for f in os.listdir(TIMER_DIR):
                if f.endswith(".png") and f[0].isdigit():
                    g = cv2.imread(os.path.join(TIMER_DIR, f), cv2.IMREAD_GRAYSCALE)
                    if g is not None:
                        _TPL.setdefault(f[0], []).append(_norm(g))
        except OSError:
            pass
    return _TPL


def _by_tpl(digs):
    """모아 둔 그림으로 숫자 읽기 -> 문자열 또는 None(모르는 숫자가 있거나 애매하면)"""
    T = _load_tpl()
    if len(T) < 2:
        return None
    out = []
    for _, m in digs:
        a = _norm(m)
        sc = sorted(((1.0 - float(np.abs(a - t).mean()), d) for d, ts in T.items() for t in ts), reverse=True)
        best = sc[0]
        second = next((x for x in sc if x[1] != best[1]), (0.0, ""))
        if best[0] < 0.85 or best[0] - second[0] < 0.04:
            return None
        out.append(best[1])
    return "".join(out)


def _by_ocr(mask):
    try:
        import ocrx, re
        big = cv2.resize(255 - mask, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
        ws = ocrx.words(cv2.cvtColor(big, cv2.COLOR_GRAY2BGR)) or []
        txt = "".join(w[0] for w in sorted(ws, key=lambda w: w[1]))
        txt = txt.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1").replace("S", "5").replace("B", "8")
        return re.sub(r"\D", "", txt)
    except Exception as e:
        print("쿨타임 OCR 오류:", e)
        return None


def _learn(digs, text):
    """OCR·자리수가 맞게 읽힌 숫자 그림을 저장 (숫자마다 최대 6장)"""
    global _TPL
    try:
        os.makedirs(TIMER_DIR, exist_ok=True)
        have = {}
        for f in os.listdir(TIMER_DIR):
            have[f[0]] = have.get(f[0], 0) + 1
        for (_, m), d in zip(digs, text):
            if have.get(d, 0) < 6:
                cv2.imwrite(os.path.join(TIMER_DIR, "%s_%d.png" % (d, int(time.time() * 1000) % 10 ** 9)), m)
                have[d] = have.get(d, 0) + 1
        _TPL = None
    except OSError:
        pass


def _to_sec(text, colons, digs):
    """숫자 문자열 -> 초. 쌍점 위치로 자리를 나눔 (쌍점을 못 찾으면 뒤 두 자리가 초)"""
    if not text or len(text) != len(digs):
        return None
    xs = [x for x, _ in digs]
    groups, cur = [], text[0]
    for i in range(1, len(text)):
        if any(xs[i - 1] < c < xs[i] for c in colons):
            groups.append(cur); cur = ""
        cur += text[i]
    groups.append(cur)
    if len(groups) == 1:
        g = groups[0]
        if len(g) < 3:
            return None
        groups = [g[:-2], g[-2:]]
    if any(len(g) != 2 for g in groups[1:]) or len(groups[0]) > 2:
        return None
    vals = [int(g) for g in groups]
    if any(v >= 60 for v in vals[1:]):
        return None
    if len(vals) == 2:
        return vals[0] * 60 + vals[1] if vals[0] <= 120 else None
    if len(vals) == 3 and vals[0] <= 3:
        return vals[0] * 3600 + vals[1] * 60 + vals[2]
    return None


def read_timer(img):
    """화면 한 장 -> (초 또는 None, 설명)"""
    if img is None:
        return None, "화면 없음"
    mask = _red_mask(img)
    digs, colons = _pieces(mask)
    if len(digs) < 3:
        return None, "숫자 조각 %d개" % len(digs)
    t_txt = _by_tpl(digs)
    o_txt = _by_ocr(mask)
    if o_txt and len(o_txt) == len(digs):
        if t_txt is None or t_txt == o_txt:
            _learn(digs, o_txt)
        txt = o_txt if (t_txt is None or t_txt == o_txt) else None
        if txt is None:
            return None, "그림 %s / OCR %s 불일치" % (t_txt, o_txt)
    else:
        txt = t_txt
    sec = _to_sec(txt, colons, digs)
    return sec, "그림 %s / OCR %s" % (t_txt, o_txt)


def timer_wait(first_img):
    """두 번 읽어 맞춰 본 남은 시간(초). 못 믿으면 분 단위만이라도, 그것도 안 되면 None"""
    s1, n1 = read_timer(first_img)
    t1 = time.time()
    time.sleep(1.6)
    img2 = capture()
    s2, n2 = read_timer(img2)
    dt = time.time() - t1
    try:
        os.makedirs(TIMER_SAVE, exist_ok=True)
        x1, y1, x2, y2 = TIMER_ROI
        if img2 is not None:
            cv2.imwrite(os.path.join(TIMER_SAVE, "%s_%s.png" % (time.strftime("%m%d_%H%M%S"), s2)), img2[y1:y2, x1:x2])
    except Exception:
        pass
    print("쿨타임 읽기: 1차 %s초 (%s) / 2차 %s초 (%s)" % (s1, n1, s2, n2))
    if s1 is not None and s2 is not None:
        if abs((s1 - s2) - dt) <= 2.5:
            return s2, "두 번 읽은 값이 맞음"
        if abs(s1 - s2) <= 90:                         # 초가 흔들리면 분만 믿고 일찍 봄 (늦게 보는 것보다 나음)
            return (min(s1, s2) // 60) * 60, "초가 안 맞아 분만 사용"
        return None, "두 번 읽은 값이 크게 다름"
    one = s2 if s2 is not None else s1
    if one is not None:
        return max(0, one - 60), "한 번만 읽힘 -> 1분 일찍"
    return None, "못 읽음"


def hire_open(img):
    """patch222: 고용 화면 = 닫기 X(674,790)가 빨강"""
    x, y = P["닫기X"]
    hsv = cv2.cvtColor(img[y - 14:y + 15, x - 14:x + 15], cv2.COLOR_BGR2HSV)
    m = (((hsv[..., 0] <= 10) | (hsv[..., 0] >= 170)) & (hsv[..., 1] > 120) & (hsv[..., 2] > 120))
    return float(m.mean()) > 0.3


def recruit(force=False):
    """결과: 'done'(새로고침+훈장구매 완료) / 'cooldown'(쿨타임 중) / 'fail'(캡처 실패 등)
    patch222: 쿨타임이면 고용 화면의 남은 시간을 읽어 recruit.last_wait(초)에 남김 (못 읽으면 None)"""
    global last_wait, last_note
    last_wait, last_note = None, ""
    # patch219: 성 탭을 거치지 않아도 영웅 탭을 한 번 누르면 점이 갱신됨(사용자 확인) → 영웅 탭만 누름
    tap("영웅탭")
    time.sleep(1.2)
    img = capture()
    if img is None:
        print("캡처 실패, 중단")
        return "fail"
    hr = dot_ratio(img, DOT_HERO, "any")
    for _ in range(3):                      # 점이 빨강 <-> 주황으로 깜빡이므로 몇 번 더 확인
        if hr >= DOT_THR:
            break
        time.sleep(0.7)
        img = capture()
        if img is not None:
            hr = dot_ratio(img, DOT_HERO, "any")
    print("영입 버튼 점 비율:", round(hr, 3))
    if hr < DOT_THR and not force:
        print("영입 버튼에 점 없음 → 쿨타임, 남은 시간 확인하러 영입 창 열기")        # patch222
    tap("영입")
    time.sleep(1.5)
    img = capture()
    if img is None:
        print("캡처 실패, 중단")
        return "fail"
    cv2.imwrite(os.path.join(BASE, "shots", "recruit_screen.png"), img)
    if not hire_open(img):                                           # patch222: 다른 창(길드 등)이 덮고 있으면 숫자를 못 읽음
        time.sleep(0.8)
        img = capture()
        if img is None or not hire_open(img):
            print("고용 화면이 아님(다른 창이 덮고 있음) → 이번엔 중단, 곧 다시 시도")
            return "fail"
    rr = dot_ratio(img, DOT_REFRESH, "any")
    for _ in range(3):
        if rr >= DOT_THR:
            break
        time.sleep(0.7)
        img = capture()
        if img is not None:
            rr = dot_ratio(img, DOT_REFRESH, "any")
    print("새로고침 점 비율:", round(rr, 3))
    if rr < DOT_THR:
        try:
            last_wait, last_note = timer_wait(img)                   # patch222
        except Exception as e:
            last_wait, last_note = None, "오류 %r" % (e,)
        print("빨간 점 없음(쿨타임 중) → 새로고침 안 함, 닫기 / 남은 시간 %s초 (%s)" % (last_wait, last_note))
        tap("닫기X")
        return "cooldown"
    print("무료 새로고침 가능 → 새로고침 → 훈장구매 → 닫기")
    tap("새로고침")
    time.sleep(1.5)
    img2 = capture()
    if img2 is not None:
        cv2.imwrite(os.path.join(BASE, "shots", "recruit_after_refresh.png"), img2)
    tap("훈장구매")
    time.sleep(1.5)
    try:
        gem_left()                                       # patch204
    except Exception as e:
        print("보석 영웅 확인 오류:", e)
    tap("닫기X")
    return "done"


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
    if "mark" in sys.argv[1:]:
        mark()
    elif "timer" in sys.argv[1:]:          # patch222: py recruit.py timer  (고용 화면을 열어 둔 상태에서 숫자만 읽기)
        print(timer_wait(capture()))
    else:
        recruit(force="force" in sys.argv[1:])