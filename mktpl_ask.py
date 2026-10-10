import cv2, os, sys
import numpy as np

BASE = r"C:\macro"
name = sys.argv[1] if len(sys.argv) > 1 else "003556"
path = os.path.join(BASE, "shots", "watch", name + ".png")
img = cv2.imread(path)
if img is None:
    print("파일을 못 찾음:", path)
    sys.exit(1)
print("이미지 크기:", img.shape)


def ratio(roi, lo, hi, lo2=None, hi2=None):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, lo, hi)
    if lo2 is not None:
        m = m | cv2.inRange(hsv, lo2, hi2)
    return float(m.mean()) / 255


g = ratio((160, 650, 290, 706), (40, 120, 90), (85, 255, 255))
r = ratio((320, 650, 560, 706), (0, 150, 90), (8, 255, 255), (172, 150, 90), (180, 255, 255))
print(f"왼쪽 초록 버튼 비율: {g:.2f} | 오른쪽 빨간 버튼 비율: {r:.2f}")
if g < 0.4 or r < 0.4:
    print("→ 이 파일은 '환생하기' 창이 아닌 것 같습니다. 다른 파일 이름으로 다시 시도하세요 (예: py mktpl_ask.py 003549)")
    sys.exit(1)

os.makedirs(os.path.join(BASE, "tpl"), exist_ok=True)
cv2.imwrite(os.path.join(BASE, "tpl", "title_ask.png"), img[270:306, 300:420])
cv2.imwrite(os.path.join(BASE, "tpl", "btn_ask_green.png"), img[648:708, 156:290])
print("tpl\\title_ask.png, tpl\\btn_ask_green.png 저장 완료")

import rebirth
ts, _ = rebirth.match(img, "title_ask.png", (0.30, 0.19, 0.70, 0.27))
gs, pos = rebirth.match(img, "btn_ask_green.png", (0.15, 0.48, 0.44, 0.60))
print(f"검증: 제목 점수 {ts:.2f}, 초록 환생 버튼 점수 {gs:.2f}, 클릭 위치 {pos}  (둘 다 1.00 근처, 위치 x≈223 이면 정상)")