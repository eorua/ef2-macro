import subprocess, sys, time
import numpy as np
import cv2

ADB_EXE = r"C:\platform-tools\adb.exe"
DEV = "127.0.0.1:5585"
GO = "go" in sys.argv[1:]

TAB_HERO = (185, 1240)
TAB_RELIC = (418, 1240)
PRESET_BTN = {"영웅": (410, 790), "유물": (288, 790)}
# 프리셋 줄이 펼쳐지면 나타나는 초록 '저장' 버튼 영역 (x1, y1, x2, y2)
SAVE_ROI = {"영웅": (590, 885, 690, 915), "유물": (450, 890, 550, 920)}
GREEN_THR = 0.30


def adb(args, timeout=20, raw=False):
    r = subprocess.run([ADB_EXE, "-s", DEV] + args, capture_output=True, timeout=timeout)
    return r.stdout if raw else r.stdout.decode("utf-8", "ignore")


def capture():
    try:
        data = adb(["exec-out", "screencap", "-p"], raw=True)
    except Exception:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def tap(p):
    adb(["shell", "input", "tap", str(p[0]), str(p[1])])


def green_ratio(img, roi):
    x1, y1, x2, y2 = roi
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (35, 100, 80), (85, 255, 255))
    return float(m.mean() / 255.0)


def is_active(name, img=None):
    img = img if img is not None else capture()
    if img is None:
        return None
    return green_ratio(img, SAVE_ROI[name]) >= GREEN_THR


def activate_one(name):
    """해당 탭(영웅/유물)에서 프리셋 줄이 안 보이면 '프리셋' 버튼을 눌러 펼침. 토글이라 이미 펼쳐져 있으면 누르지 않음"""
    tap(TAB_HERO if name == "영웅" else TAB_RELIC)
    time.sleep(1.0)
    for _ in range(3):
        a = is_active(name)
        if a is None:
            return False
        if a:
            return True
        tap(PRESET_BTN[name])
        time.sleep(1.0)
    return bool(is_active(name))


def activate_presets():
    """재시작 후 영웅/유물 프리셋 활성화. 둘 다 성공하면 True (끝나면 영웅 탭에 머무름)"""
    ok_r = activate_one("유물")
    ok_h = activate_one("영웅")
    return ok_h and ok_r


if __name__ == "__main__":
    img = capture()
    if img is None:
        print("캡처 실패")
        sys.exit(1)
    for n in ("영웅", "유물"):
        print(f"{n} 저장버튼 초록 비율: {green_ratio(img, SAVE_ROI[n]):.2f}  (현재 화면 기준, {GREEN_THR} 이상이면 활성)")
    if GO:
        print("활성화 결과:", "성공" if activate_presets() else "실패")