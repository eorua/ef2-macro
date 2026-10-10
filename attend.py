import cv2, numpy as np, subprocess, sys, time, os

ADB = r"C:\platform-tools\adb.exe"
DEV = "127.0.0.1:5585"
TPL = r"C:\macro\tpl"
GO = "go" in sys.argv

def cap():
    r = subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], capture_output=True)
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

def tap(x, y):
    subprocess.run([ADB, "-s", DEV, "shell", "input", "tap", str(x), str(y)])

def find(img, name, roi):
    H, W = img.shape[:2]
    x1, y1, x2, y2 = int(roi[0]*W), int(roi[1]*H), int(roi[2]*W), int(roi[3]*H)
    t = cv2.imread(os.path.join(TPL, name))
    res = cv2.matchTemplate(img[y1:y2, x1:x2], t, cv2.TM_CCOEFF_NORMED)
    _, s, _, loc = cv2.minMaxLoc(res)
    th, tw = t.shape[:2]
    return s, (x1 + loc[0] + tw // 2, y1 + loc[1] + th // 2)

TITLE_ROI = (0.30, 0.03, 0.70, 0.09)
BTN_ROI   = (0.20, 0.56, 0.80, 0.66)
X_ROI     = (0.80, 0.03, 0.97, 0.09)

def handle():
    img = cap()
    s, _ = find(img, "title_attendance.png", TITLE_ROI)
    print("제목 점수: %.2f" % s)
    if s < 0.85:
        print("출석 팝업 아님")
        return False
    sb, pb = find(img, "btn_attendance.png", BTN_ROI)
    print("받기 버튼 점수: %.2f 위치 %s" % (sb, pb))
    if GO and sb >= 0.80:
        tap(*pb)
        time.sleep(1.5)
        img = cap()
        s2, _ = find(img, "title_attendance.png", TITLE_ROI)
        print("받기 후 제목 점수: %.2f" % s2)
        if s2 >= 0.85:
            sx, px = find(img, "btn_attendance_x.png", X_ROI)
            print("X 점수: %.2f 위치 %s" % (sx, px))
            if sx >= 0.80:
                tap(*px)
                time.sleep(1.0)
                print("X 클릭")
        else:
            print("받기만으로 팝업 닫힘")
    return True

if __name__ == "__main__":
    handle()