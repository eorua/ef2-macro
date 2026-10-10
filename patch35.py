# patch35: 시작 시 ADB 가 안 잡혀도 오환2 창이 떠 있으면 BlueStacks 를 재시작하지 않음
import shutil, glob, sys
F = "main.py"
s = open(F, encoding="utf-8").read()
if "def _bs_window" in s:
    print("patch35 이미 적용됨"); sys.exit()
OLD = "    if GO and not adb_alive(tries=3):\n"
ANCH = "def after_restart_setup(st):"
if s.count(OLD) != 1 or s.count(ANCH) != 1:
    print("앵커 불일치", s.count(OLD), s.count(ANCH)); sys.exit(1)
FUNC = '''def _bs_window():
    """오환2 BlueStacks 창이 떠 있으면 True (확인이 안 되면 건드리지 않도록 True)"""
    try:
        pids = bsrestart.find_pids()
    except Exception as e:
        log("오환2 창 확인 오류: %r -> 재시작하지 않고 진행" % (e,))
        return True
    if pids:
        log("ADB 응답은 없지만 오환2 창이 있음 -> 재시작하지 않고 진행")
        return True
    return False


'''
s = s.replace(OLD, "    if GO and not adb_alive(tries=3) and not _bs_window():\n")
s = s.replace(ANCH, FUNC + ANCH)
n = len(glob.glob(F + ".bak*")) + 1
bak = f"{F}.bak{n:02d}"
shutil.copy(F, bak)
open(F, "w", encoding="utf-8").write(s)
print("patch35 적용 완료 (백업 " + bak + ")")
