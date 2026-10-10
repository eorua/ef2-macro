# patch37: 정체 환생 기준을 90초 -> 180초 로 늘리고, 정체 감시 상황을 로그에 남김
import shutil, glob, sys
F = "main.py"
s = open(F, encoding="utf-8").read()
if "정체 감시:" in s:
    print("patch37 이미 적용됨"); sys.exit()
A1 = "STUCK_SEC = 90 "
A2 = "            wx = wave.read_wave(img, exact=True)\n"
A3 = '                log(f"웨이브 {wx} 에서 {STUCK_SEC}초 이상 정체 → 환생 시도")\n'
for a in (A1, A2, A3):
    if s.count(a) != 1:
        print("앵커 불일치:", a[:40], s.count(a)); sys.exit(1)
s = s.replace(A1, "STUCK_SEC = 180")
s = s.replace(A2, A2 + (
    '            if stuck.best and time.time() - stuck.since >= 45 and time.time() - getattr(stuck, "logged", 0) >= 30:\n'
    '                stuck.logged = time.time()\n'
    '                log("정체 감시: 웨이브 %s (최고 %s) %d초째 변화 없음" % (wx, stuck.best, int(time.time() - stuck.since)))\n'))
s = s.replace(A3, '                log(f"웨이브 {wx} (최고 {stuck.best}) 에서 {int(time.time() - stuck.since)}초 정체 → 환생 시도")\n')
n = len(glob.glob(F + ".bak*")) + 1
bak = f"{F}.bak{n:02d}"
shutil.copy(F, bak)
open(F, "w", encoding="utf-8").write(s)
print("patch37 적용 완료 (백업 " + bak + ")")
