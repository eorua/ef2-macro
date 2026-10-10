import subprocess, sys, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True).stdout
    if not png:
        return None
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "grid"
    img = capture()
    if img is None:
        print("캡처 실패 (ADB 연결 확인)")
        return
    os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
    raw = os.path.join(BASE, "shots", f"{name}.png")
    cv2.imwrite(raw, img)                       # 원본(템플릿 제작용)
    h, w = img.shape[:2]
    g = img.copy()
    for x in range(0, w, 50):
        major = x % 100 == 0
        cv2.line(g, (x, 0), (x, h), (0, 255, 255) if major else (200, 200, 200), 1)
        if major:
            cv2.putText(g, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            cv2.putText(g, str(x), (x + 2, h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    for y in range(0, h, 50):
        major = y % 100 == 0
        cv2.line(g, (0, y), (w, y), (0, 255, 255) if major else (200, 200, 200), 1)
        if major:
            cv2.putText(g, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
            cv2.putText(g, str(y), (w - 40, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    out = os.path.join(BASE, "shots", f"{name}_grid.png")
    cv2.imwrite(out, g)
    print("저장:", raw, "/", out, img.shape)


if __name__ == "__main__":
    main()