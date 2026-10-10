import os, cv2

BASE = r"C:\macro"
src = os.path.join(BASE, "shots", "offline.png")
img = cv2.imread(src)
if img is None:
    print("파일이 없습니다:", src)
else:
    print("원본 크기:", img.shape)
    os.makedirs(os.path.join(BASE, "tpl"), exist_ok=True)
    cuts = {
        "title_offline.png": (285, 268, 435, 308),     # x1, y1, x2, y2  '오프라인 전투' 제목
        "btn_offline_ok.png": (252, 708, 470, 768),    # '확인' 버튼
    }
    for name, (x1, y1, x2, y2) in cuts.items():
        cv2.imwrite(os.path.join(BASE, "tpl", name), img[y1:y2, x1:x2])
        print("저장:", os.path.join(BASE, "tpl", name))