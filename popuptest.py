import os, time, cv2
from wave import capture, BASE

TITLE_ROI = (0.25, 0.19, 0.75, 0.26)
BTN_ROI = (0.25, 0.52, 0.75, 0.62)


def match(img, name, roi):
    tpl = cv2.imread(os.path.join(BASE, "tpl", name))
    if tpl is None:
        return 0.0, (0, 0)
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(roi[0] * W), int(roi[1] * H), int(roi[2] * W), int(roi[3] * H)
    sub = img[y1:y2, x1:x2]
    res = cv2.matchTemplate(sub, tpl, cv2.TM_CCOEFF_NORMED)
    _, s, _, loc = cv2.minMaxLoc(res)
    return float(s), (x1 + loc[0] + tpl.shape[1] // 2, y1 + loc[1] + tpl.shape[0] // 2)


print("오프라인 팝업 감지 테스트 (읽기만 함, 중지: Ctrl + C)")
while True:
    img = capture()
    if img is None:
        print("캡처 실패")
    else:
        ts, _ = match(img, "title_offline.png", TITLE_ROI)
        bs, pos = match(img, "btn_offline_ok.png", BTN_ROI)
        print(f"제목={ts:.2f} 확인버튼={bs:.2f} 위치={pos}", "-> 팝업 감지!" if ts >= 0.85 and bs >= 0.90 else "")
    time.sleep(1)