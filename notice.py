"""notice.py - 공지(NOTICE) 팝업: '오늘 하루 보지 않기' 체크 후 X 로 닫기 (그림 찾기 방식)
  py notice.py       현재 화면에서 공지 팝업이 보이는지만 확인 (클릭 안 함)
  py notice.py go    보이면 체크 + X 클릭
공지 창은 내용 양에 따라 위아래 위치와 높이가 달라지므로, 위치 대신 그림(제목 / X / 체크박스 줄)을 화면에서 찾습니다.
"""
import sys, os, time
import cv2, numpy as np
import daily as D

GO = "go" in sys.argv[1:]
TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tpl")
THR_TITLE, THR_X, THR_CHECK = 0.75, 0.70, 0.70
CHECK_OFF = (22, 22)                # notice_check.png 왼쪽 위에서 체크박스 중심까지
_last_check = 0.0
_check_pt = None
_cache = {}


def _tpl(name):
    if name not in _cache:
        p = os.path.join(TPL, name)
        _cache[name] = cv2.imread(p) if os.path.exists(p) else None
    return _cache[name]


def _find(img, name, roi):
    """roi=(x1,y1,x2,y2) 안에서 그림 name 을 찾아 (점수, 왼쪽위 x, y). 그림이 없으면 (0,0,0)"""
    t = _tpl(name)
    if t is None:
        return 0.0, 0, 0
    x1, y1, x2, y2 = roi
    H, W = img.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
    band = img[y1:y2, x1:x2]
    if band.shape[0] < t.shape[0] or band.shape[1] < t.shape[1]:
        return 0.0, 0, 0
    r = cv2.matchTemplate(band, t, cv2.TM_CCOEFF_NORMED)
    _, mx, _, loc = cv2.minMaxLoc(r)
    return float(mx), x1 + loc[0], y1 + loc[1]


def detect(img):
    """공지 팝업이면 닫기(X) 중심 좌표 (x, y), 아니면 None. 체크박스 위치도 함께 기억"""
    global _check_pt
    if img is None or img.shape[0] < 1200:
        return None
    s, tx, ty = _find(img, "notice_title.png", (260, 80, 520, 900))
    if s < THR_TITLE:
        return None
    t = _tpl("notice_title.png")
    ty_c = ty + t.shape[0] // 2
    s, xx, xy = _find(img, "notice_x.png", (520, ty_c - 45, 720, ty_c + 45))
    if s < THR_X:
        return None
    xt = _tpl("notice_x.png")
    pos = (xx + xt.shape[1] // 2, xy + xt.shape[0] // 2)
    s, cx, cy = _find(img, "notice_check.png", (30, ty_c + 200, 360, 1260))
    _check_pt = (cx + CHECK_OFF[0], cy + CHECK_OFF[1]) if s >= THR_CHECK else None
    return pos


def check_today():
    """'오늘 하루 보지 않기' 체크 (60초 안에 이미 눌렀으면 다시 누르지 않음: 체크가 풀리는 것 방지)"""
    global _last_check
    if time.time() - _last_check < 60:
        return False
    _last_check = time.time()
    if _check_pt is None:
        return False
    if GO:
        D.tap(_check_pt, 0.6)
    return True


def close(go=None):
    img = D.cap()
    pos = detect(img)
    if pos is None:
        return False
    check_today()
    D.tap(pos, 1.0)
    return True


if __name__ == "__main__":
    img = D.cap()
    pos = detect(img)
    if pos is None:
        print("공지 팝업이 보이지 않음")
    elif not GO:
        print("공지 팝업 감지: 체크 %s 를 누른 뒤 X %s 를 누를 예정 (시험 모드, 클릭 안 함)" % (_check_pt, pos))
    else:
        print("공지 팝업 닫는 중 (체크 %s, X %s)" % (_check_pt, pos))
        close()
