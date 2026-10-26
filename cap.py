import subprocess, sys, cv2, numpy as np, time

ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]

png = subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                     capture_output=True).stdout
img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)

tstr = time.strftime("%Y%m%d_%H%M%S")
if len(sys.argv) > 1:
    name = sys.argv[1]
    path = rf"C:\macro\shots\{name}.png"
    cv2.imwrite(path, img)
    print("저장 완료:", path, img.shape)
else:
    path_main = rf"C:\macro\shots\shot.png"
    path_hist = rf"C:\macro\shots\cap_{tstr}.png"
    cv2.imwrite(path_main, img)
    cv2.imwrite(path_hist, img)
    print("저장 완료:", path_main, "및", path_hist, img.shape)
