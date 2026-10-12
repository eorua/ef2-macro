# patch94: maint.detect 오탐 방지 (메일함 '임시 점검 보상' 글자에 반응하던 문제)
import os, sys, shutil, re
BASE = r"C:\macro" if os.name == "nt" else "."
p = os.path.join(BASE, "maint.py")
src = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in src
s = src.replace("\r\n", "\n")
if "def _is_maint_text" in s:
    print("이미 적용됨"); sys.exit(0)
old = '        hit = ("점검" in text) or ("KST" in text.upper()) or ("서버" in text)\n'
if s.count(old) != 1:
    print("앵커 불일치:", s.count(old)); sys.exit(1)
s = s.replace(old, '        hit = _is_maint_text(text)\n')
anchor = "def save_shot(img, tag):"
if s.count(anchor) != 1:
    print("앵커2 불일치"); sys.exit(1)
func = '''def _is_maint_text(text):
    """점검 팝업 글자인지. 메일함/보상 같은 화면 속 '점검 보상' 글자는 제외"""
    t = text.replace(" ", "")
    for bad in ("모두받기", "메일함", "점검보상", "보상"):
        if bad in t:
            return False
    if parse_end(text) is not None:
        return True
    return ("서버점검" in t) or ("점검중" in t) or ("점검안내" in t) or ("점검" in t and "KST" in t.upper())


'''
s = s.replace(anchor, func + anchor)
compile(s, "maint.py", "exec")
if os.path.exists(p):
    n = 1
    while os.path.exists(p + ".bak%02d" % n): n += 1
    shutil.copy(p, p + ".bak%02d" % n)
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("patch94 적용 완료 (maint.py)")
