"""spirit.py - 정령의 고원 일일 소탕 (patch164)
  py spirit.py look     지금 화면(즐겨찾기 창)에서 읽은 값만 출력 (아무것도 안 누름)
  py spirit.py go       실제 실행 (펫 아이콘 -> 정령의 고원 -> 즐겨찾기 -> 티켓 구매 -> Max 소탕)

규칙 (사용자 지정)
  - 티켓 구매(3장씩): 다이아 100 / 200 / 200 / 400 / 400 / 800. 800 짜리는 구매 직전 다이아가 1000 이하이면 안 삼
    창에 뜬 가격이 이 순서의 '다음 가격'과 다르면(이미 직접 산 경우 등) 취소하고 구매 중단 -> 더 비싸게 사는 일 없음
  - 소탕은 Max 로, 즐겨찾기 펫을 읽는 순서대로. 빨간 테두리(최고 등급) 펫은 맨 마지막(티켓이 남을 때만)
  - 펫마다 하루 (0/6) 제한 -> 버튼이 회색이면 건너뜀. 티켓이 0 이면 끝
위치는 10-18 사용자 영상(720x1280) 기준
"""
import os, re, sys, time
import cv2, numpy as np
import daily

PET_ICON = (597, 292)            # 오른쪽 HUD 요정 모양 (펫) (patch213: 예전 590, 343)
TAB_PLATEAU = (364, 1240)        # 펫 창 아래 탭 '정령의 고원'
FAV_BTN = (628, 393)             # 정령의 고원 오른쪽 위 '즐겨찾기'
BUY_BTN = (588, 393)             # 즐겨찾기 창 '구매'
FAV_X = (680, 393)               # 즐겨찾기 창 X
MAX_TAB = (530, 457)
DLG_OK = (270, 487)              # 구매 확인 창 [확인]
DLG_CANCEL = (450, 487)          # [취소]
DLG_OK_ROI = (200, 465, 340, 510)
DLG_CANCEL_ROI = (380, 465, 520, 510)
ICON_X = (66, 410)               # 칸 아이콘 가운데 x (왼쪽, 오른쪽)
ICON_LEFT = (27, 371)            # 아이콘 테두리 왼쪽 x
BTN_X = (276, 618)               # [소탕] 버튼 x
ROW_Y = (545, 655, 765, 875)     # 칸 아이콘 가운데 y (4줄)
PRICES = (100, 200, 200, 400, 400, 800)
MIN_DIA_FOR_800 = 1000
FIRST_DAY = "2026-10-19"         # 10-18 은 사용자가 직접 함
GO = False


def log(*a):
    daily.log("[고원]", *a)


def _cap():
    img = daily.cap()
    if img is None:
        raise RuntimeError("캡처 실패")
    return img


def _tap(pt, wait=1.0):
    if GO:
        daily.tap(pt, wait)
    else:
        log("[시험] 누를 곳", pt)


def _words(img):
    import ocrx
    return ocrx.words(img) or []


def _find(ws, key, box=None):
    for t, x, y, w, h in ws:
        if key in t and (box is None or (box[0] <= x <= box[2] and box[1] <= y <= box[3])):
            return (x, y)
    return None


def tickets(ws):
    """(남은 기본 티켓, 추가 티켓). 못 읽으면 None"""
    base = extra = None
    for t, x, y, w, h in ws:
        if x > 260 or not 390 <= y <= 430:
            continue
        m = re.search(r"(\d+)\s*/\s*(\d+)", t)
        if m and base is None:
            base = int(m.group(1))
        m2 = re.search(r"\+\s*(\d+)", t)
        if m2:
            extra = int(m2.group(1))
    if base is None:
        return None
    return base, (extra or 0)


def diamonds(ws):
    for t, x, y, w, h in ws:
        if 300 <= x <= 420 and 320 <= y <= 356:
            d = re.sub(r"[^\d]", "", t)
            if d:
                return int(d)
    return None


def dialog_open(img):
    return daily.ratio(img, DLG_OK_ROI, "green") >= 0.35 and daily.ratio(img, DLG_CANCEL_ROI, "red") >= 0.35


def fav_open(ws):
    return _find(ws, "즐겨", (0, 370, 250, 420)) is not None


def red_frame(img, col, row):
    """아이콘 테두리가 빨강(최고 등급)인지"""
    x0, y = ICON_LEFT[col], ROW_Y[row]
    hsv = cv2.cvtColor(img[y - 30:y + 30, x0:x0 + 5], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    e = hsv[hsv[:, 1] > 120]
    if len(e) < 60:
        return False
    h = float(np.median(e[:, 0]))
    return h <= 10 or h >= 170


def btn_active(img, col, row):
    """[소탕] 글자가 주황(활성)인지 - 0/6 이면 회색"""
    x, y = BTN_X[col], ROW_Y[row]
    c = cv2.cvtColor(img[y - 5:y + 35, x - 60:x + 60], cv2.COLOR_BGR2HSV)
    m = (c[..., 0] >= 5) & (c[..., 0] <= 25) & (c[..., 1] >= 150) & (c[..., 2] >= 150)
    return float(m.mean()) >= 0.04          # 활성 약 0.10, 회색(0/6 또는 티켓 없음) 0


def slot_used(img, col, row):
    """칸에 펫이 있는지 (아이콘 가운데가 배경색이 아님)"""
    x, y = ICON_X[col], ROW_Y[row]
    c = img[y - 25:y + 25, x - 25:x + 25]
    return float(cv2.cvtColor(c, cv2.COLOR_BGR2HSV)[..., 1].mean()) > 60


def open_fav():
    try:
        import hud
        hud.ensure()
    except Exception as e:
        log("HUD 확인 오류:", repr(e))
    _tap(PET_ICON, 1.6)
    img = _cap()
    ws = _words(img)
    if _find(ws, "펫 메인") is None and _find(ws, "고원") is None:   # patch213: 새 위치가 아니면 예전 위치로 한 번 더
        log("펫 창이 안 열림 (새 위치) -> 예전 위치 (590, 343) 로 다시")
        daily.close_panels()
        _tap((590, 343), 1.6)
        img = _cap()
        ws = _words(img)
    if _find(ws, "펫 메인") is None and _find(ws, "고원") is None:
        log("펫 창이 안 열림:", " ".join(w[0] for w in ws)[:80])
        cv2.imwrite(os.path.join(daily.SHOTS, "spirit_nav.png"), img)
        return None
    p = _find(ws, "고원", (250, 1200, 480, 1280))
    _tap(p or TAB_PLATEAU, 1.4)
    img = _cap()
    ws = _words(img)
    p = _find(ws, "즐겨", (500, 370, 720, 420))
    _tap(p or FAV_BTN, 1.4)
    img = _cap()
    ws = _words(img)
    if not fav_open(ws):
        log("즐겨찾기 창이 안 열림")
        cv2.imwrite(os.path.join(daily.SHOTS, "spirit_nav.png"), img)
        return None
    return ws


def buy(n_bought):
    """오늘 산 횟수 n_bought 에서 이어서 구매. 새로 산 횟수 반환"""
    got = 0
    while n_bought + got < len(PRICES):
        want = PRICES[n_bought + got]
        img = _cap()
        dia = diamonds(_words(img))
        if want == 800 and (dia is None or dia <= MIN_DIA_FOR_800):
            log("800 다이아 구매 건너뜀 (다이아 %s)" % dia)
            break
        _tap(BUY_BTN, 1.0)
        img = _cap()
        if not dialog_open(img):
            log("구매 창이 안 뜸 -> 구매 끝")
            break
        ws = _words(img)
        txt = " ".join(w[0] for w in ws)
        price = None
        for t, x, y, w, h in ws:
            if 380 <= y <= 450 and 250 <= x <= 470:
                d = re.sub(r"[^\d]", "", t)
                if d:
                    price = int(d)
        if "구매" not in txt or price != want:
            log("구매 창 가격 %s (예상 %d) -> 취소하고 구매 중단" % (price, want))
            _tap(DLG_CANCEL, 1.0)
            break
        _tap(DLG_OK, 1.5)
        got += 1
        log("티켓 3장 구매 (%d다이아, 오늘 %d번째)" % (price, n_bought + got))
    return got


def sweep():
    _tap(MAX_TAB, 0.8)
    time.sleep(1.5)                           # 구매 알림 글자가 사라질 때까지
    img = _cap()
    order = []
    reds = []
    for r in range(4):
        for c in range(2):                    # 빈 칸은 버튼이 없어서 아래에서 자동으로 건너뜀
            (reds if red_frame(img, c, r) else order).append((c, r))
    done = 0
    for c, r in order + reds:
        time.sleep(1.5)                       # 앞 소탕 알림 글자가 사라질 때까지
        img = _cap()
        if dialog_open(img):
            log("예상 못 한 확인 창 -> 취소")
            _tap(DLG_CANCEL, 1.0)
            break
        tk = tickets(_words(img))
        if tk is not None and tk[0] + tk[1] <= 0:
            log("티켓 0 -> 소탕 끝")
            break
        if not btn_active(img, c, r):
            continue
        _tap((BTN_X[c], ROW_Y[r] + 15), 1.2)
        done += 1
        log("소탕 (%s열 %d줄%s), 티켓 %s" % ("왼" if c == 0 else "오른", r + 1, ", 빨강" if (c, r) in reds else "", tk))
        img = _cap()
        if dialog_open(img):
            log("소탕 뒤 확인 창 -> 취소하고 끝")
            _tap(DLG_CANCEL, 1.0)
            break
    return done


def run(d):
    """daily 에서 호출. d = 오늘 기록(dict). 끝났으면 True"""
    if daily.game_day() < FIRST_DAY:
        return True
    ws = open_fav()
    if ws is None:
        return False
    try:
        got = buy(d.get("sp_buys", 0))
        d["sp_buys"] = d.get("sp_buys", 0) + got
        n = sweep()
        log("정령의 고원 끝: 구매 %d번, 소탕 %d번" % (got, n))
        try:
            cv2.imwrite(os.path.join(daily.SHOTS, "spirit_after.png"), _cap())
        except Exception:
            pass
        return True
    finally:
        _tap(FAV_X, 1.0)
        daily.close_panels()


if __name__ == "__main__":
    GO = "go" in sys.argv[1:]
    img = _cap()
    ws = _words(img)
    print("즐겨찾기 창:", fav_open(ws), "/ 티켓:", tickets(ws), "/ 다이아:", diamonds(ws), "/ 확인창:", dialog_open(img))
    for r in range(4):
        for c in range(2):
            print("칸 %d,%d 펫 %s 빨강 %s 소탕가능 %s" % (c, r, slot_used(img, c, r), red_frame(img, c, r), btn_active(img, c, r)))
    if GO:
        dd = {}
        FIRST_DAY = "0000"
        print("결과:", run(dd), dd)
