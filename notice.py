"""notice.py - 공지(NOTICE) 팝업: '오늘 하루 보지 않기' 체크 후 X 로 닫기
  py notice.py       현재 화면에서 공지 팝업이 보이는지만 확인 (클릭 안 함)
  py notice.py go    보이면 체크 + X 클릭
"""
import sys, time
import cv2, numpy as np
import daily as D

GO = "go" in sys.argv[1:]
X_ROI = (575, 125, 630, 195)        # 공지 팝업 우상단 빨간 X (원본 720x1280 기준)
X_CENTER = (607, 158)
CHECK_PT = (80, 1135)               # '오늘 하루 보지 않기' 체크박스
ROW_TEXT = (120, 1115, 330, 1155)   # 체크박스 옆 글자 줄
ROW_BOX = (60, 1115, 105, 1155)
_last_check = 0.0


def detect(img):
    """공지 팝업이면 닫기(X) 좌표 (x, y), 아니면 None"""
    if img is None or img.shape[0] < 1200:
        return None
    x1, y1, x2, y2 = X_ROI
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    m = ((h <= 10) | (h >= 170)) & (s >= 120) & (v >= 90)
    if int(m.sum()) < 800:
        return None
    ys, xs = np.nonzero(m)
    cx, cy = xs.mean() + x1, ys.mean() + y1
    if abs(cx - X_CENTER[0]) > 8 or abs(cy - X_CENTER[1]) > 14:
        return None                  # 통합 프리셋 등 다른 팝업의 X 는 위치가 달라 걸러짐
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    a, b, c, d = ROW_TEXT
    if int((g[b:d, a:c] > 150).sum()) < 80:
        return None                  # 아래쪽 '오늘 하루 보지 않기' 글자 줄이 없으면 아님
    a, b, c, d = ROW_BOX
    box = g[b:d, a:c]
    if int(((box > 90) & (box < 200)).sum()) < 25:
        return None
    return X_CENTER


def check_today():
    """'오늘 하루 보지 않기' 체크 (60초 안에 이미 눌렀으면 다시 누르지 않음: 체크가 풀리는 것 방지)"""
    global _last_check
    if time.time() - _last_check < 60:
        return False
    _last_check = time.time()
    if GO:
        D.tap(CHECK_PT, 0.6)
    return True


def close(go=None):
    img = D.cap()
    pos = detect(img)
    if pos is None:
        return False
    if check_today():
        pass
    D.tap(pos, 1.0)
    return True


if __name__ == "__main__":
    img = D.cap()
    pos = detect(img)
    if pos is None:
        print("공지 팝업이 보이지 않음")
    elif not GO:
        print("공지 팝업 감지: 체크 %s 누른 뒤 X %s 를 누를 예정 (시험 모드, 클릭 안 함)" % (CHECK_PT, pos))
    else:
        print("공지 팝업 닫는 중")
        close()
