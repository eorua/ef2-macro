# patch34: 좀비 HD-Player 정리 코드 제거 + 시작 시 ADB 확인을 3번 재시도 (오판으로 플레이어가 재시작되는 것 방지)
import shutil, glob, sys
F = "main.py"
s = open(F, encoding="utf-8").read()
if "def kill_stale_bluestacks" not in s:
    print("patch34 이미 적용됨"); sys.exit()

a = s.find("def adb_alive")
b = s.find("def kill_stale_bluestacks")
c = s.find("def restart_bluestacks_full")
if not (0 <= a < b < c):
    print("위치 불일치"); sys.exit(1)

NEW_ALIVE = '''def adb_alive(tries=1):
    """ADB 로 접속되고 안드로이드 부팅이 끝났는지. 실패하면 이유를 로그에 남김"""
    for i in range(tries):
        try:
            c = subprocess.run([r"C:\\platform-tools\\adb.exe", "connect", "127.0.0.1:5585"],
                               capture_output=True, text=True, timeout=15)
            r = subprocess.run(ADB + ["shell", "getprop", "sys.boot_completed"],
                               capture_output=True, text=True, timeout=15)
            if r.stdout.strip() == "1":
                return True
            why = (c.stdout + c.stderr + r.stdout + r.stderr).strip().replace("\\n", " ")[:120]
        except Exception as e:
            why = repr(e)
        log("ADB 확인 실패 (%d/%d): %s" % (i + 1, tries, why))
        if i < tries - 1:
            time.sleep(4)
    return False


'''
s = s[:a] + NEW_ALIVE + s[c:]

OLD = '''    if not adb_alive():
        log("ADB 응답 없음 -> 남은 HD-Player 정리")
        kill_stale_bluestacks()
'''
if s.count(OLD) != 1:
    print("앵커 불일치(restart_bluestacks_full)"); sys.exit(1)
s = s.replace(OLD, "")

OLD2 = "if GO and not adb_alive():"
if s.count(OLD2) != 1:
    print("앵커 불일치(시작 확인)"); sys.exit(1)
s = s.replace(OLD2, "if GO and not adb_alive(tries=3):")

n = len(glob.glob(F + ".bak*")) + 1
bak = f"{F}.bak{n:02d}"
shutil.copy(F, bak)
open(F, "w", encoding="utf-8").write(s)
print("patch34 적용 완료 (백업 " + bak + ")")
