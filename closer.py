"""closer.py - 화면에 떠 있는 창의 빨간 X(닫기) 버튼을 찾아서 닫기 (실패 복구용)

창마다 X 위치는 달라도 모양(빨간 사각형 + 흰 X)은 같으므로, 색과 모양으로 찾습니다.
  py closer.py          지금 화면에서 찾은 X 위치만 출력 (누르지 않음)
  py closer.py go       찾은 X 를 눌러 창을 모두 닫음
"""
import sys, time
import cv2, numpy as np
import preset

X_MIN, Y_MIN, Y_MAX = 600, 150, 830       # 닫기 X 가 있는 영역 (오른쪽, 창 제목줄 높이대)


def find_red_x(img, min_s=40, max_s=78):
    """빨간 사각형 안에 흰 X 가 있는 버튼들의 중심 (x, y) 목록"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = (((h <= 8) | (h >= 172)) & (s > 140) & (v > 120)).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
    out = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        if not (min_s <= w <= max_s and min_s <= hh <= max_s):
            continue
        if abs(int(w) - int(hh)) > 10 or a < 0.55 * w * hh:
            continue
        hv = hsv[y:y + hh, x:x + w]
        wf = float(((hv[..., 1] < 60) & (hv[..., 2] > 200)).mean())
        if not (0.06 <= wf <= 0.40):
            continue
        out.append((int(x + w // 2), int(y + hh // 2)))
    return out


def close_buttons(img):
    return [p for p in find_red_x(img) if p[0] >= X_MIN and Y_MIN <= p[1] <= Y_MAX]


def close_all(max_n=4):
    """보이는 닫기 X 를 하나씩 눌러 창을 닫음. 닫은 개수 반환. 안 보이면 아무것도 안 누름"""
    n = 0
    for _ in range(max_n):
        img = preset.capture()
        if img is None:
            break
        pts = close_buttons(img)
        if not pts:
            break
        pts.sort(key=lambda p: -p[1])         # 아래쪽(보통 가장 앞에 뜬 창)부터
        preset.tap(pts[0], "창 닫기 X")
        n += 1
        time.sleep(0.8)
    return n


if __name__ == "__main__":
    img = preset.capture()
    pts = close_buttons(img) if img is not None else []
    print("찾은 닫기 X:", pts)
    if "go" in sys.argv[1:]:
        print("닫은 창:", close_all())
    else:
        print("(시험 모드: 아무것도 누르지 않았습니다. 실제 실행은 맨 끝에 go)")
