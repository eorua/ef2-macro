# patch36: 메인을 중지(taskkill /T)해도 BlueStacks 가 같이 꺼지지 않도록, 부모-자식 관계를 끊어서 실행
import shutil, glob, sys
F = "bsrestart.py"
s = open(F, encoding="utf-8").read()
if "start" in s and '"cmd", "/c", "start"' in s:
    print("patch36 이미 적용됨"); sys.exit()
OLD = 'subprocess.Popen([PLAYER, "--instance", INSTANCE], creationflags=flags)'
if s.count(OLD) != 1:
    print("앵커 불일치:", s.count(OLD)); sys.exit(1)
NEW = 'subprocess.Popen(["cmd", "/c", "start", "", PLAYER, "--instance", INSTANCE], creationflags=0x08000000)'
s = s.replace(OLD, NEW)
n = len(glob.glob(F + ".bak*")) + 1
bak = f"{F}.bak{n:02d}"
shutil.copy(F, bak)
open(F, "w", encoding="utf-8").write(s)
print("patch36 적용 완료 (백업 " + bak + ")")
