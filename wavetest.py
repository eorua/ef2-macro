import os, time, cv2
from wave import capture, read_wave, BASE

os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
saved = 0
print("웨이브 읽기 + 실패 화면 저장 테스트 (중지: Ctrl + C)")
while True:
    img = capture()
    if img is None:
        print("캡처 실패 (ADB 연결 확인)")
        time.sleep(1)
        continue
    w = read_wave(img)
    print("현재 웨이브:", w)
    if w is None and saved < 12:
        top = img[0:int(img.shape[0] * 0.20)]
        path = os.path.join(BASE, "shots", f"wave_fail_{saved:02d}.png")
        cv2.imwrite(path, top)
        saved += 1
        print("  -> 실패 화면 저장:", path)
    time.sleep(1)