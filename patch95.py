# patch95: 웨이브 7200 이상이면 웨이브 호출 AUTO 끄기, 환생 후 다시 켜기 (wavecall.py 추가 + main.py 연결)
import os, sys, shutil, base64, zlib
BASE = r"C:\macro" if os.name == "nt" else "."
PAYLOAD = """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"""

def backup(p):
    n = 1
    while os.path.exists(p + ".bak%02d" % n): n += 1
    shutil.copy(p, p + ".bak%02d" % n)

wc = zlib.decompress(base64.b64decode(PAYLOAD.replace("\n", ""))).decode("utf-8")
compile(wc, "wavecall.py", "exec")
pm = os.path.join(BASE, "main.py")
src = open(pm, encoding="utf-8", newline="").read()
crlf = "\r\n" in src
s = src.replace("\r\n", "\n")
if "wavecall.tick" not in s:
    key = "hist.append(w)\n"
    if s.count(key) != 1:
        print("main.py 앵커 불일치:", s.count(key)); sys.exit(1)
    i = s.index(key)
    ls = s.rfind("\n", 0, i) + 1
    ind = s[ls:i]
    if ind.strip():
        print("앵커 위치가 줄 시작이 아님"); sys.exit(1)
    blk = (ind + "if GO:\n" + ind + "    try:\n" + ind + "        import wavecall\n"
           + ind + "        if wavecall.tick(st, w): save_state(st)\n"
           + ind + "    except Exception as _e:\n" + ind + "        log(\"웨이브 호출 오류:\", repr(_e))\n")
    s = s[:ls] + blk + s[ls:]
    compile(s, "main.py", "exec")
    backup(pm)
    open(pm, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("main.py 연결 완료")
else:
    print("main.py 이미 연결됨")
pw = os.path.join(BASE, "wavecall.py")
if os.path.exists(pw):
    backup(pw)
open(pw, "w", encoding="utf-8", newline="").write(wc)
print("patch95 적용 완료 (wavecall.py)")
