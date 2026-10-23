"""dev.py - 블루스택(ADB) 공통 함수 (patch162)
모든 모듈이 여기의 ADB 경로/기기 번호와 함수를 씀. 기기 주소를 바꿀 때는 이 파일만 고치면 됨.
- 모든 adb 호출에 시간 제한(멈춰도 매크로 전체가 서지 않게) + 콘솔 창 안 띄움
- 실패하거나 시간이 넘으면 예외 대신 빈 결과(returncode -1)를 돌려줌
"""
import subprocess
import cv2
import numpy as np

ADB_EXE = r"C:\platform-tools\adb.exe"
SERIAL = "127.0.0.1:5585"
ADB = [ADB_EXE, "-s", SERIAL]
NOWIN = 0x08000000                      # CREATE_NO_WINDOW


def run(args, timeout=20, text=False, serial=True):
    """adb [-s SERIAL] args... 실행. subprocess.CompletedProcess 를 돌려줌 (실패/시간 초과면 returncode -1, 빈 출력)"""
    cmd = (ADB if serial else [ADB_EXE]) + [str(a) for a in args]
    try:
        return subprocess.run(cmd, capture_output=True, text=text, timeout=timeout, creationflags=NOWIN)
    except Exception as e:
        empty = "" if text else b""
        return subprocess.CompletedProcess(cmd, -1, empty, (str(e) if text else str(e).encode()))


def capture(timeout=20):
    """화면 캡처 (BGR). 실패하면 None"""
    png = run(["exec-out", "screencap", "-p"], timeout=timeout).stdout
    if not png:
        return None
    try:
        return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def tap(x, y, timeout=15):
    return run(["shell", "input", "tap", int(x), int(y)], timeout=timeout)


def swipe(x1, y1, x2, y2, ms=600, mode="swipe", timeout=20):
    return run(["shell", "input", mode, int(x1), int(y1), int(x2), int(y2), int(ms)], timeout=timeout)


def shell(cmd, timeout=60):
    """adb shell 'cmd' (여러 명령을 한 번에)"""
    return run(["shell", cmd], timeout=timeout)


def keyevent(code, timeout=15):
    return run(["shell", "input", "keyevent", int(code)], timeout=timeout)


def connect(timeout=15):
    return run(["connect", SERIAL], timeout=timeout, text=True, serial=False)
