# patch96: wavecall 톱니바퀴 좌표를 왼쪽 아래(웨이브 호출 옆) 톱니로 수정
import os, sys, shutil
BASE = r"C:\macro" if os.name == "nt" else "."
p = os.path.join(BASE, "wavecall.py")
src = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in src
s = src.replace("\r\n", "\n")
old = "GEAR = (662, 112)          # 메인 화면 톱니바퀴\n"
new = "GEAR = (170, 642)          # 왼쪽 아래 톱니(웨이브 호출/황혼의 부름 옆) - 오른쪽 위 환경설정 톱니 아님\n"
if new in s:
    print("이미 적용됨"); sys.exit(0)
if s.count(old) != 1:
    print("앵커 불일치:", s.count(old)); sys.exit(1)
s = s.replace(old, new)
compile(s, "wavecall.py", "exec")
n = 1
while os.path.exists(p + ".bak%02d" % n): n += 1
shutil.copy(p, p + ".bak%02d" % n)
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("patch96 적용 완료 (GEAR=170,642)")
