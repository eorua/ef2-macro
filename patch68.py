# patch68.py - soul.py 의 'dig_3.png 를 못 읽음' 경고 메시지 제거 (C:\macro 에서 py patch68.py)
import os, sys, shutil
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soul.py")
OLD = '            t = cv2.imread(os.path.join(TPLDIR, "dig_%s.png" % d), cv2.IMREAD_GRAYSCALE)\n'
NEW = ('            path = os.path.join(TPLDIR, "dig_%s.png" % d)\n'
       '            if not os.path.exists(path):\n'
       '                continue\n'
       '            t = cv2.imread(path, cv2.IMREAD_GRAYSCALE)\n')
s = open(P, encoding="utf-8").read()
crlf = "\r\n" in s
s = s.replace("\r\n", "\n")
if "if not os.path.exists(path):\n                continue" in s:
    print("이미 적용됨"); sys.exit(0)
if s.count(OLD) != 1:
    print("앵커 불일치", s.count(OLD)); sys.exit(1)
n = 1
while os.path.exists("%s.bak%02d" % (P, n)):
    n += 1
shutil.copy2(P, "%s.bak%02d" % (P, n))
s = s.replace(OLD, NEW)
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("패치 완료")
