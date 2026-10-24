"""emucheck.py - 에뮬레이터(BlueStacks / 뮤뮤) 연결·화면·캡처·터치 점검 (patch250)
  emu.json 에 정한 에뮬레이터(adbport.EMU) 기준으로 확인. 기본은 읽기만 하고 아무것도 누르지 않음.

  py emucheck.py                     ADB 연결 / 해상도·DPI / 게임 설치·포커스 / screencap / 웨이브 인식
  py emucheck.py fast                + fastcam(scrcpy) 실시간 화면 수신 속도·크기 확인
  py emucheck.py touch X Y           터치 시험 계획만 출력 (누르지 않음)
  py emucheck.py touch X Y go        ADB input tap 으로 (X, Y) 1번 누르고 전/후 화면 비교
  py emucheck.py ftouch X Y go       fastcam(scrcpy) 터치로 (X, Y) 1번 누르고 전/후 화면 비교
  py emucheck.py tab [go]            하단 탭(퀘스트<->영웅) 전환으로 ADB 터치 전달 확인 후 원래 탭 복귀 (가장 확실)
  py emucheck.py ftab [go]           같은 시험을 fastcam(scrcpy) 터치로
  결과 그림: shots\\emucheck_*.png
  ※ 터치 좌표는 720x1280 기준. 게임에 영향 없는 빈 곳(예: 열린 창이 없는 배경)을 직접 골라 주세요.
"""
import os, sys, time, subprocess
import numpy as np
import cv2
import adbport

ADB_EXE = adbport.ADB_EXE
DEV = adbport.DEV
BASE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(BASE, "shots")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
W, H = 720, 1280
GO = "go" in sys.argv[1:]
OK, NG, WARN = "[정상]", "[문제]", "[주의]"
results = []


def adb(*a, timeout=15, raw=False):
    try:
        r = subprocess.run([ADB_EXE, "-s", DEV, *a], capture_output=True, timeout=timeout, creationflags=NOWIN)
    except Exception as e:
        return b"" if raw else "ERR %r" % (e,)
    return r.stdout if raw else (r.stdout + r.stderr).decode("utf-8", "ignore").strip()


def adb0(*a, timeout=15):
    try:
        r = subprocess.run([ADB_EXE, *a], capture_output=True, timeout=timeout, creationflags=NOWIN)
        return (r.stdout + r.stderr).decode("utf-8", "ignore").strip()
    except Exception as e:
        return "ERR %r" % (e,)


def say(tag, msg):
    results.append((tag, msg))
    print(tag, msg)


def save(name, img):
    os.makedirs(SHOTS, exist_ok=True)
    p = os.path.join(SHOTS, "emucheck_%s.png" % name)
    cv2.imwrite(p, img)
    return p


def screencap():
    t = time.perf_counter()
    data = adb("exec-out", "screencap", "-p", raw=True, timeout=20)
    dt = time.perf_counter() - t
    if not data:
        return None, dt
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR), dt


# ---------------------------------------------------------------- 1. 연결
def check_connect():
    print("== 1. 연결 ==")
    print("에뮬레이터:", adbport.EMU_NAME, "/ emu.json:", "있음" if os.path.exists(adbport.EMU_CFG) else "없음(기본 BlueStacks)")
    if adbport.IS_MUMU:
        mgr = adbport.mumu_manager()
        info = adbport.mumu_info()
        say(OK if mgr else WARN, "MuMuManager: %s" % (mgr or "못 찾음 -> 연결은 되지만 자동 재시작/종료 불가"))
        if info:
            keys = ("name", "adb_host_ip", "adb_port", "is_process_started", "is_android_started", "player_state")
            print("   MuMuManager info:", {k: info.get(k) for k in keys if k in info})
    global DEV
    DEV = adbport.sync(print, scan=True)
    print("adb 버전:", adb0("version").splitlines()[0] if adb0("version") else "?")
    print("adb devices:", " | ".join(adb0("devices").splitlines()[1:]) or "(없음)")
    st = adb("get-state")
    say(OK if st == "device" else NG, "ADB %s 상태: %s" % (DEV, st or "응답 없음"))
    if st != "device":
        print("   -> 뮤뮤 설정 > 기타(또는 개발자 옵션)에서 ADB 디버깅 허용, 포트 확인 후 'py adbport.py scan'")
        return False
    boot = adb("shell", "getprop", "sys.boot_completed")
    say(OK if boot == "1" else NG, "안드로이드 부팅 완료: %s" % boot)
    print("   기기: %s / Android %s / ABI %s" % (adb("shell", "getprop", "ro.product.model"),
                                              adb("shell", "getprop", "ro.build.version.release"),
                                              adb("shell", "getprop", "ro.product.cpu.abi")))
    return True


# ---------------------------------------------------------------- 2. 해상도 / DPI / 게임
def check_display():
    print("== 2. 해상도 / DPI / 게임 ==")
    size = adb("shell", "wm", "size")
    dens = adb("shell", "wm", "density")
    print("   wm size   :", size.replace("\n", " / "))
    print("   wm density:", dens.replace("\n", " / "))
    cur = size.splitlines()[-1].split(":")[-1].strip() if size else ""
    if cur == "%dx%d" % (W, H):
        say(OK, "해상도 %s (기존 BlueStacks 기준과 같음)" % cur)
    elif cur == "%dx%d" % (H, W):
        say(WARN, "해상도 %s (가로 기준) -> 실제 캡처가 세로 720x1280 인지 아래 3번에서 확인" % cur)
    else:
        say(NG, "해상도 %s -> 뮤뮤 설정에서 720x1280(세로/휴대폰 모드)로 맞춰야 좌표가 맞음" % (cur or "?"))
    pkg = adb("shell", "pm", "path", adbport.PKG)
    say(OK if adbport.PKG in pkg else NG, "오환2 설치: %s" % ("있음" if adbport.PKG in pkg else "없음"))
    foc = adb("shell", "dumpsys", "window")          # Android 15 는 'windows' 하위 출력에 mCurrentFocus 가 없음
    line = next((l.strip() for l in foc.splitlines() if "mCurrentFocus" in l or "mFocusedApp" in l), "")
    say(OK if adbport.PKG in line else WARN, "현재 앞 화면: %s" % (line or "?"))


# ---------------------------------------------------------------- 3. screencap
def check_screencap():
    print("== 3. ADB screencap ==")
    times, img = [], None
    for _ in range(3):
        img, dt = screencap()
        times.append(dt)
    if img is None:
        say(NG, "screencap 실패 (빈 데이터)")
        return None
    h, w = img.shape[:2]
    say(OK if (w, h) == (W, H) else NG, "캡처 크기 %dx%d (기대 %dx%d), 평균 %.2f초" % (w, h, W, H, sum(times) / len(times)))
    if img.mean() < 3:
        say(WARN, "화면이 거의 검정 -> 뮤뮤 렌더링 모드(DirectX/Vulkan) 변경 또는 화면 켜짐 확인")
    print("   저장:", save("screencap", img))
    try:
        import wave
        wv = wave.read_wave(img)
        say(OK if wv else WARN, "웨이브 인식: %s" % (wv if wv else "못 읽음 (전투 화면이 아니면 정상)"))
    except Exception as e:
        say(WARN, "웨이브 인식 오류: %r" % (e,))
    return img


# ---------------------------------------------------------------- 4. fastcam
def start_cam():
    import fastcam
    fastcam.SERIAL = DEV
    return fastcam.FastCam(max_fps=60, scid="0e2f0a0c", port=27198).start()      # main 쪽(27199)과 겹치지 않게


def check_fastcam(ref=None):
    print("== 4. fastcam (scrcpy 서버) ==")
    try:
        cam = start_cam()
    except Exception as e:
        say(NG, "fastcam 시작 실패: %r (shots\\fastcam_server.txt 확인)" % (e,))
        return
    try:
        _, _, n0 = cam.latest()
        t0 = time.perf_counter()
        time.sleep(2.0)
        img, _, n1 = cam.latest()
        fps = (n1 - n0) / (time.perf_counter() - t0)
        h, w = img.shape[:2]
        say(OK if (w, h) == (W, H) else NG, "fastcam 화면 %dx%d (scrcpy 보고 %dx%d)" % (w, h, cam.w, cam.h))
        say(OK if fps >= 5 else WARN, "fastcam 수신 %.1f장/초 (화면 변화가 없으면 낮게 나올 수 있음)" % fps)
        print("   저장:", save("fastcam", img))
        if ref is not None and ref.shape == img.shape:
            d = float(np.abs(ref.astype(np.int16) - img.astype(np.int16)).mean())
            say(OK if d < 25 else WARN, "screencap 과 fastcam 화면 차이 평균 %.1f (움직이는 화면이면 커질 수 있음)" % d)
    finally:
        cam.stop()


# ---------------------------------------------------------------- 5. 터치
def _xy():
    a = sys.argv[1:]
    k = a.index("touch") if "touch" in a else a.index("ftouch")
    try:
        x, y = int(a[k + 1]), int(a[k + 2])
    except (IndexError, ValueError):
        raise SystemExit("좌표가 필요함: py emucheck.py touch X Y [go]")
    if not (0 <= x < W and 0 <= y < H):
        raise SystemExit("좌표는 0~%d, 0~%d 사이 (720x1280 기준)" % (W - 1, H - 1))
    return x, y


def check_touch(use_fast):
    x, y = _xy()
    how = "fastcam(scrcpy) 터치" if use_fast else "ADB input tap"
    print("== 5. 터치 (%s) ==" % how)
    if not GO:
        print("[시험] 실제로는 화면 터치 표시(show_touches)를 잠깐 켜고 (%d, %d) 를 1번 누른 뒤 전/후 화면을 비교합니다." % (x, y))
        print("       누르려면 끝에 go 를 붙이세요. 게임에 영향 없는 빈 곳을 고르세요.")
        return
    old = adb("shell", "settings", "get", "system", "show_touches").strip()
    adb("shell", "settings", "put", "system", "show_touches", "1")
    cam = None
    try:
        if use_fast:
            cam = start_cam()
            before = cam.latest()[0].copy()
            n = cam.latest()[2]
            cam.touch(0, x, y)                  # 누른 채로 잠깐 유지해야 표시 점이 화면에 찍힘
            cam.wait_new(n, 1.0)
            time.sleep(0.15)
            after = cam.latest()[0].copy()
            cam.touch(1, x, y)
        else:
            before, _ = screencap()
            # 제자리 swipe 1.5초 = 누른 채 유지 -> 누르고 있는 동안 캡처해야 터치 표시 점이 찍힘
            p = subprocess.Popen([ADB_EXE, "-s", DEV, "shell", "input", "swipe", str(x), str(y), str(x), str(y), "1500"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NOWIN)
            time.sleep(0.5)
            after, _ = screencap()
            p.wait(timeout=10)
        if before is None or after is None:
            say(NG, "터치 전/후 화면을 못 받음")
            return
        print("   저장:", save("touch_before", before), "/", save("touch_after", after))
        r0 = 30
        crop = lambda im: im[max(0, y - r0):y + r0, max(0, x - r0):x + r0].astype(np.int16)
        d_near = float(np.abs(crop(before) - crop(after)).mean())
        d_all = float(np.abs(before.astype(np.int16) - after.astype(np.int16)).mean())
        if d_near > max(8.0, d_all * 2):
            say(OK, "%s 전달 확인: 누른 곳 주변 변화 %.1f (전체 %.1f)" % (how, d_near, d_all))
        else:
            say(WARN, "%s 결과 판단 애매: 누른 곳 변화 %.1f / 전체 %.1f -> emucheck_touch_after.png 에 흰 점이 찍혔는지 눈으로 확인"
                % (how, d_near, d_all))
    finally:
        if cam:
            cam.stop()
        adb("shell", "settings", "put", "system", "show_touches", old if old in ("0", "1") else "0")


# ---------------------------------------------------------------- 6. 하단 탭 전환 터치 (patch252)
def tab_index(img):
    """하단 6개 탭 중 밝게 강조된 탭 번호 (0=퀘스트 1=영웅 2=성 3=유물 4=전투 5=상점). 애매하면 None"""
    if img is None or img.shape[:2] != (H, W):
        return None
    v = cv2.cvtColor(img[1210:1275], cv2.COLOR_BGR2HSV)[:, :, 2].astype(np.float32)
    cells = [float(v[:, i * 120 + 15:i * 120 + 105].mean()) for i in range(6)]
    order = sorted(range(6), key=lambda i: -cells[i])
    return order[0] if cells[order[0]] - cells[order[1]] >= 15 else None


def check_tab(use_fast):
    how = "fastcam(scrcpy) 터치" if use_fast else "ADB input tap"
    print("== 6. 하단 탭 전환 (%s) ==" % how)
    img, _ = screencap()
    cur = tab_index(img)
    if cur is None:
        say(NG, "하단 탭 강조를 못 찾음 -> 게임 기본 화면(창 닫힌 상태)에서 다시 실행")
        return
    tgt = 0 if cur == 1 else 1
    names = ["퀘스트", "영웅", "성", "유물", "전투", "상점"]
    pos = lambda i: (60 + 120 * i, 1240)
    if not GO:
        print("[시험] 지금 탭: %s -> 실제로는 %s 탭 %s 을 누르고 확인한 뒤 %s 탭으로 되돌립니다. 끝에 go" % (
            names[cur], names[tgt], pos(tgt), names[cur]))
        return
    cam = start_cam() if use_fast else None
    try:
        def tap(p):
            if cam:
                cam.tap(*p, hold=0.06)
            else:
                adb("shell", "input", "tap", str(p[0]), str(p[1]))
        tap(pos(tgt))
        time.sleep(1.2)
        img2, _ = screencap()
        got = tab_index(img2)
        save("tab_after", img2)
        say(OK if got == tgt else NG, "%s 전달: %s 탭 누름 -> 강조된 탭 %s" % (how, names[tgt], names[got] if got is not None else "?"))
        tap(pos(cur))
        time.sleep(1.2)
        back = tab_index(screencap()[0])
        say(OK if back == cur else WARN, "원래 탭 복귀: %s" % (names[back] if back is not None else "?"))
    finally:
        if cam:
            cam.stop()


if __name__ == "__main__":
    a = sys.argv[1:]
    if not check_connect():
        sys.exit(1)
    if "tab" in a or "ftab" in a:
        check_tab("ftab" in a)
    elif "touch" in a or "ftouch" in a:
        check_touch("ftouch" in a)
    else:
        check_display()
        ref = check_screencap()
        if "fast" in a:
            check_fastcam(ref)
    bad = [m for t, m in results if t == NG]
    print("\n== 요약: %s ==" % ("문제 없음" if not bad else "문제 %d건" % len(bad)))
    for m in bad:
        print("  -", m)
