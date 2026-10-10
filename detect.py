import subprocess, time, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]

def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                         capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)

def score(screen, name):
    tpl = cv2.imread(os.path.join(BASE, "tpl", name))
    if tpl is None:
        return 0.0
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    return float(cv2.minMaxLoc(res)[1])

print("감지 시작 (중지: Ctrl + C)")
while True:
    s = capture()
    g = score(s, "btn_green.png")
    t = score(s, "title_rebirth.png")
    print(f"green={g:.2f}  title_rebirth={t:.2f}")

    # 초록 버튼은 보이는데 '환생하기' 제목이 없으면 성 함락 팝업으로 간주
    if g >= 0.85 and t < 0.70:
        path = os.path.join(BASE, "shots", "fall_auto.png")
        cv2.imwrite(path, s)
        print("성 함락 추정 화면 저장:", path)
        break
    time.sleep(1)