"""inf2.py - 바뀐 '무한 랭킹전' 화면(탭 5개, 전투 버튼 3개) 처리 + 열린 화면 자동 닫기 안전장치

  py inf2.py look     지금 화면이 새 무한랭킹전인지, 전투 버튼/레벨/티켓/새로고침을 어떻게 읽는지 출력 (누르지 않음)
  py inf2.py close    열려 있으면 X 로 닫기
  py inf2.py go       실제로 무한랭킹전 진행 (무한랭킹전 화면이 열려 있는 상태에서)
daily.do_infinite 가 새 화면을 만나면 run() 을 대신 호출하고, 메인 루프가 이 화면이 열린 채 멈춰 있으면 close() 로 닫습니다.
"""
import os, re, sys, time
import cv2, numpy as np
import daily
from daily import cap, tap, log

X_ROI = (640, 395, 719, 490)          # 패널 오른쪽 위 빨간 X 가 있는 곳
X_FALLBACK = (688, 441)
BTN_AREA = (530, 840, 712, 1215)      # 상대 전투 버튼들이 있는 곳 (x1, y1, x2, y2)
REFRESH = (622, 808)
REFRESH_ROI = (550, 780, 695, 835)
TICKET_ROI = (400, 690, 500, 730)
LV_X = (135, 222)                     # 레벨 글자(Lv.78) 가로 범위
MAX_LOOPS = 14
MAX_SECONDS = 1500


def _red(img, h_hi=6, s_lo=150, v_lo=100):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (((h <= h_hi) | (h >= 172)) & (s > s_lo) & (v > v_lo)).astype(np.uint8)


def find_x(img):
    """오른쪽 위 빨간 X 버튼 중심 (x, y). 없으면 None"""
    x1, y1, x2, y2 = X_ROI
    m = _red(img[y1:y2, x1:x2])
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 34 <= w <= 64 and 34 <= h <= 64 and abs(int(w) - int(h)) <= 10 and a >= 0.4 * w * h:
            if best is None or a > best[2]:
                best = (x1 + x + w // 2, y1 + y + h // 2, a)
    return (best[0], best[1]) if best else None


def battle_buttons(img):
    """빨간 '전투' 버튼들의 중심 [(x, y)] (위에서부터)"""
    x1, y1, x2, y2 = BTN_AREA
    m = _red(img[y1:y2, x1:x2], h_hi=8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 85 <= w <= 150 and 36 <= h <= 66 and a >= 0.6 * w * h:
            out.append((x1 + x + w // 2, y1 + y + h // 2))
    out.sort(key=lambda p: p[1])
    return out


def is_open(img):
    """새 무한랭킹전 화면이 열려 있는지: 오른쪽 위 X + 전투 버튼 2개 이상"""
    if img is None:
        return False
    try:
        return find_x(img) is not None and len(battle_buttons(img)) >= 2
    except Exception:
        return False


def _ocr_text(crop, scale=3):
    """작은 조각을 키워서 OCR -> 글자 이어붙인 문자열 (OCR 불가면 None)"""
    try:
        import ocrx
        big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        big = cv2.copyMakeBorder(big, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
        ws = ocrx.words(big)
        if ws is None:
            return None
        ws.sort(key=lambda w: w[1])
        return " ".join(w[0] for w in ws)
    except Exception as e:
        log("글자 읽기 오류: %r" % (e,))
        return None


def read_level(img, cy):
    """전투 버튼 줄(cy)의 상대 레벨. 못 읽으면 None"""
    y1, y2 = max(0, cy - 40), cy - 2
    t = _ocr_text(img[y1:y2, LV_X[0]:LV_X[1]])
    if not t:
        return None
    m = re.search(r"(\d{2,3})", t.replace("O", "0").replace("o", "0"))
    if m:
        v = int(m.group(1))
        if 1 <= v <= 400:
            return v
    return None


def read_tickets(img):
    """(남은 티켓, 최대) 또는 None"""
    x1, y1, x2, y2 = TICKET_ROI
    t = _ocr_text(img[y1:y2, x1:x2])
    if not t:
        return None
    m = re.search(r"(\d+)\s*[/17|]\s*(\d+)", t)
    if m and int(m.group(2)) <= 20 and int(m.group(1)) <= int(m.group(2)):
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*/\s*(\d+)", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def free_refresh(img):
    """무료 새로고침이 남았으면 True, 없으면 False, 모르면 None"""
    x1, y1, x2, y2 = REFRESH_ROI
    t = _ocr_text(img[y1:y2, x1:x2])
    if t is None:
        return None
    if "무료" in t:
        m = re.search(r"(\d)\s*/\s*(\d)", t)
        if m and int(m.group(1)) == 0:
            return False
        return True
    return False


def snap(name):
    try:
        img = cap()
        if img is not None:
            os.makedirs(daily.SHOTS, exist_ok=True)
            cv2.imwrite(os.path.join(daily.SHOTS, name), img)
            log("화면 저장: shots\\%s" % name)
    except Exception:
        pass


def close(max_n=3):
    """무한랭킹전 화면의 X 를 눌러 닫음. 닫은 횟수 반환 (X 가 안 보이면 아무것도 안 누름)"""
    n = 0
    for _ in range(max_n):
        img = cap()
        if img is None:
            break
        xy = find_x(img)
        if xy is None:
            break
        tap(xy, 1.0)
        n += 1
    return n


def close_if_open():
    img = cap()
    if is_open(img):
        log("무한랭킹전 화면이 열려 있음 -> 닫기")
        return close()
    return 0


def _pick(lv, free, refreshes):
    """(고를 줄 번호 또는 None, 설명)"""
    for i, x in enumerate(lv):
        if x is not None and x <= daily.MY_LEVEL:
            return i, "%d번째 상대(Lv.%s)와 전투" % (i + 1, x)
    if all(x is None for x in lv):
        return 0, "레벨을 못 읽어서 맨 위 상대와 전투"
    if free and refreshes < 5:
        return None, "싸울 만한 상대 없음 -> 무료 새로고침 (%d)" % (refreshes + 1)
    return 0, "무료 새로고침 없음 -> 맨 위 상대와 전투"


def run(go, img=None):
    """새 화면 무한랭킹전. 반환 'ok' / 'empty' / 'abort' (daily.do_infinite 와 같은 규칙)"""
    t0 = time.time()
    status = "ok"
    fought = 0
    refreshes = 0
    log("무한랭킹전: 새 화면으로 인식")
    for loop in range(MAX_LOOPS):
        if loop > 0 or img is None:
            img = cap()
        if time.time() - t0 > MAX_SECONDS:
            log("무한랭킹전이 %d초를 넘김 -> 중단" % MAX_SECONDS)
            status = "abort"
            break
        if img is None or not is_open(img):
            log("무한랭킹전 화면이 아님 -> 중단")
            status = "abort"
            break
        if not daily.safe_wave_ok(img):
            status = "abort"
            break
        tk = read_tickets(img)
        btns = battle_buttons(img)
        lv = [read_level(img, cy) for _, cy in btns]
        free = free_refresh(img)
        log("티켓 %s / 상대 레벨 %s / 내 레벨 %d / 무료 새로고침 %s" % (
            ("%d/%d" % tk) if tk else "?", lv, daily.MY_LEVEL, {True: "있음", False: "없음", None: "?"}[free]))
        if not go:
            return "ok"
        if tk and tk[0] == 0:
            log("티켓 없음 -> 종료")
            status = "empty"
            break
        idx, why = _pick(lv, free, refreshes)
        log(why)
        if idx is None:
            refreshes += 1
            tap(REFRESH, 1.5)
            continue
        tap(btns[idx], 0.5)
        r = daily._inf_battle()
        if r == "ok":
            fought += 1
            refreshes = 0
            log("전투 완료 (%d회)" % fought)
            continue
        if r == "abort":
            snap("inf_battle_fail.png")
            try:
                import closer
                closer.close_all()
            except Exception:
                pass
            if fought == 0 and tk is None:
                log("전투를 시작하지 못함(티켓이 없는 것으로 봄) -> 종료")
                r = "empty"
        status = r
        break
    else:
        log("반복 한도(%d회) 도달 -> 종료" % MAX_LOOPS)
    log("무한랭킹전 종료: 전투 %d회, 상태 %s" % (fought, status))
    close()
    return status


# ---------------------------------------------------------------- 메인 루프용 안전장치
_idle = {"t": 0.0}


def idle_check(img):
    """메인 루프가 무한랭킹전 화면이 열린 채 멈춰 있으면 닫음 (20초에 한 번만 검사). 닫았으면 True"""
    now = time.time()
    if now - _idle["t"] < 20:
        return False
    _idle["t"] = now
    if is_open(img):
        log("무한랭킹전 화면이 열려 있음 -> 닫기")
        return close() > 0
    return False


_nw = {"since": None, "cool": 0.0, "snap": 0.0}
NOWAVE_SEC = 90


def nowave_watch(img, w):
    """웨이브를 NOWAVE_SEC 초 넘게 못 읽으면 열린 창을 닫아 봄. 눌렀으면 True"""
    now = time.time()
    if w is not None:
        _nw["since"] = None
        return False
    if _nw["since"] is None:
        _nw["since"] = now
        return False
    if now - _nw["since"] < NOWAVE_SEC or now < _nw["cool"]:
        return False
    _nw["cool"] = now + 45
    log("웨이브를 %d초째 못 읽음 -> 열린 창 닫기 시도" % int(now - _nw["since"]))
    if now - _nw["snap"] > 600:
        _nw["snap"] = now
        snap("nowave.png")
    n = 0
    xy = find_x(img)
    if xy is None:
        try:
            import ocrx
            xs = ocrx.red_x_buttons(img)
            xy = xs[0] if xs else None
        except Exception:
            xy = None
    if xy is not None:
        tap(xy, 1.0)
        n = 1
    else:
        try:
            import closer
            n = closer.close_all()
        except Exception as e:
            log("창 닫기 오류: %r" % (e,))
    return n > 0


if __name__ == "__main__":
    go = "go" in sys.argv
    img = cap()
    if "close" in sys.argv:
        print("닫은 횟수:", close())
    elif img is None:
        print("화면 캡처 실패")
    elif "look" in sys.argv:
        print("새 무한랭킹전 화면:", is_open(img), "/ X:", find_x(img), "/ 전투 버튼:", battle_buttons(img))
        run(False, img)
    elif go:
        print("결과:", run(True, img))
    else:
        print("사용법: py inf2.py look | go | close")
