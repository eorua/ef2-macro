import os, subprocess, sys, time, datetime
import numpy as np
import cv2

ADB_EXE = r"C:\platform-tools\adb.exe"
DEV = "127.0.0.1:5585"
OUT = os.path.join(r"C:\macro", "shots", "watch")
INTERVAL = float(sys.argv[1]) if len(sys.argv) > 1 else 3      # 몇 초마다 확인
MINUTES = float(sys.argv[2]) if len(sys.argv) > 2 else 10      # 몇 분 동안 기록
DIFF_THR = 4.0                                                  # 화면 변화 민감도 (낮을수록 민감)


def capture():
    try:
        r = subprocess.run([ADB_EXE, "-s", DEV, "exec-out", "screencap", "-p"], capture_output=True, timeout=15)
    except Exception:
        return None
    if not r.stdout:
        return None
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)


def small(img):
    return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (72, 128)).astype(np.float32)


def main():
    os.makedirs(OUT, exist_ok=True)
    logf = open(os.path.join(OUT, "timeline.txt"), "a", encoding="utf-8")

    def note(msg):
        line = datetime.datetime.now().strftime("%H:%M:%S ") + msg
        print(line)
        logf.write(line + "\n")
        logf.flush()

    note(f"기록 시작 ({INTERVAL}초 간격, {MINUTES}분) - 화면이 바뀔 때만 저장")
    end = time.time() + MINUTES * 60
    prev = None
    down = False
    saved = 0
    while time.time() < end:
        img = capture()
        if img is None:
            if not down:
                note("ADB 응답 없음 (BlueStacks 꺼짐/부팅 중)")
                down = True
            subprocess.run([ADB_EXE, "connect", DEV], capture_output=True)
            time.sleep(INTERVAL)
            continue
        if down:
            note("ADB 다시 연결됨")
            down = False
        cur = small(img)
        if prev is None or float(np.abs(cur - prev).mean()) >= DIFF_THR:
            name = datetime.datetime.now().strftime("%H%M%S") + ".png"
            cv2.imwrite(os.path.join(OUT, name), img)
            saved += 1
            note(f"저장 {name}")
        prev = cur
        time.sleep(INTERVAL)
    note(f"기록 종료 (저장 {saved}장)")


if __name__ == "__main__":
    main()