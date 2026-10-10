import cv2, sys, os
src = sys.argv[1] if len(sys.argv) > 1 else r"C:\macro\shots\attendance.png"
img = cv2.imread(src)
if img is None:
    sys.exit("이미지를 못 읽음: " + src)
h, w = img.shape[:2]
print("원본 크기:", w, "x", h)
if (w, h) != (720, 1280):
    sys.exit("720x1280 ADB 원본이 아님. grid.py로 만든 원본 파일을 지정하세요.")
os.makedirs(r"C:\macro\tpl", exist_ok=True)
crops = {
    "title_attendance.png": (290, 55, 430, 100),    # "출석 보상" 제목
    "btn_attendance.png":   (200, 750, 310, 802),   # 받기 버튼 왼쪽 면 (글자 제외)
    "btn_attendance_x.png": (610, 57, 652, 97),     # 닫기 X
}
for name, (x1, y1, x2, y2) in crops.items():
    cv2.imwrite(os.path.join(r"C:\macro\tpl", name), img[y1:y2, x1:x2])
    print("생성:", name)