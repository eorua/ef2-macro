import subprocess, sys, cv2, numpy as np

ADB = [r"C:\platform-tools\adb.exe", "-s", "127.0.0.1:5585"]

png = subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                     capture_output=True).stdout
img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
name = sys.argv[1] if len(sys.argv) > 1 else "shot"
path = rf"C:\macro\shots\{name}.png"
cv2.imwrite(path, img)
print("저장 완료:", path, img.shape)