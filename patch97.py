# patch97: wave.py 숫자 묶음 간격 기준 100 -> 50  ('+1' 표시의 1이 웨이브 자릿수로 섞여 41700 같은 값이 나오던 오독 수정)
import os, sys, shutil
BASE = r"C:\macro" if os.name == "nt" else "."
p = os.path.join(BASE, "wave.py")
src = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in src
s = src.replace("\r\n", "\n")
old = "        if c[0] - (prev[0] + prev[2]) > 100:\n"
new = "        if c[0] - (prev[0] + prev[2]) > 50:\n"
if new in s and old not in s:
    print("이미 적용됨"); sys.exit(0)
if s.count(old) != 1:
    print("앵커 불일치:", s.count(old)); sys.exit(1)
s = s.replace(old, new)
compile(s, "wave.py", "exec")
n = 1
while os.path.exists(p + ".bak%02d" % n): n += 1
shutil.copy(p, p + ".bak%02d" % n)
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("patch97 적용 완료 (wave.py)")
