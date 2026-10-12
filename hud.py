"""hud.py - 오른쪽 HUD 메뉴(퀘스트/길드 아이콘 줄)가 접혀 있거나 창에 가려졌을 때 복구
  펼침 상태: 메뉴 왼쪽에 ▶ 토글 (519,186)   접힘 상태: 오른쪽 끝에 ◀ 토글 (691,186)
  py hud.py            지금 상태만 출력 (누르지 않음)
  py hud.py go         필요하면 펼치거나 가린 창을 닫아서 펼침 상태로 만듦
"""
import sys, time
import cv2, numpy as np
import preset

TOGGLE_FOLD = (691, 186)                 # 접힌 상태의 ◀
TOGGLE_OPEN = (519, 186)                 # 펼친 상태의 ▶
ROI_FOLD = (672, 166, 716, 208)          # x1,y1,x2,y2
ROI_OPEN = (503, 166, 537, 208)


def _fill(img, roi):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((h >= 18) & (h <= 45) & (s >= 40) & (s <= 150) & (v >= 170)).astype(np.uint8)


def _arrow(img, roi, point_left):
    """토글 화살표(연두~살구색 삼각형 + 검은 테두리) 인식. point_left=True 면 ◀ 모양"""
    m = _fill(img, roi)
    n = int(m.sum())
    if not (45 <= n <= 160):
        return False
    ys, xs = np.nonzero(m)
    w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    if not (7 <= w <= 16 and 12 <= h <= 22):
        return False
    mid = (xs.min() + xs.max()) / 2.0
    left, right = int((xs <= mid).sum()), int((xs > mid).sum())
    return (left < right) if point_left else (left > right)


def state(img):
    """'open'(펼침) / 'fold'(접힘) / None(둘 다 안 보임 = 다른 창이 가림 등)"""
    if _arrow(img, ROI_OPEN, point_left=False):
        return "open"
    if _arrow(img, ROI_FOLD, point_left=True):
        return "fold"
    return None


def ensure(close=True, tries=3):
    """오른쪽 메뉴를 펼친 상태로 만듦. 성공하면 True.
    접힘 -> ◀ 를 눌러 펼침 / 안 보임 -> (close=True 면) 떠 있는 창 닫기 후 재확인"""
    closed = False
    for _ in range(tries):
        img = preset.capture()
        if img is None:
            return False
        st = state(img)
        if st == "open":
            return True
        if st == "fold":
            print("[hud] 오른쪽 메뉴가 접혀 있음 -> 펼침")
            preset.tap(TOGGLE_FOLD, "메뉴 펼치기 ◀")
            time.sleep(0.8)
            continue
        if close and not closed:
            print("[hud] 오른쪽 메뉴/토글이 안 보임 -> 떠 있는 창 닫기")
            closed = True
            import closer
            closer.close_all()
            time.sleep(0.6)
            continue
        time.sleep(0.6)
    img = preset.capture()
    return img is not None and state(img) == "open"


if __name__ == "__main__":
    img = preset.capture()
    print("현재 상태:", state(img) if img is not None else "캡처 실패")
    if "go" in sys.argv[1:]:
        preset.GO = True
        print("결과:", "펼침 확인" if ensure() else "실패")
