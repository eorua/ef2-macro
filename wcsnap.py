"""wcsnap.py - 웨이브 호출 설정창 캡처 (720x1280 원본)  사용: py wcsnap.py 이름"""
import sys, os, cv2
sys.path.insert(0, r"C:\macro")
import preset
name = sys.argv[1] if len(sys.argv) > 1 else "x"
img = preset.capture()
if img is None:
    print("캡처 실패"); sys.exit(1)
os.makedirs(r"C:\macro\shots", exist_ok=True)
p = r"C:\macro\shots\wc_%s.png" % name
cv2.imwrite(p, img)
print("저장:", p, img.shape)