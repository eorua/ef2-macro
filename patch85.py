# patch85.py - '병영 편성으로 최대레벨 단계 진행' 옵션 삭제 (항상 병영 편성 방식)
import os, sys, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
PANEL = os.path.join(HERE, "panel.py")
KEY = 'opt_on("barracks_swap")'

def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst

def rw(path, fn):
    s = open(path, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    new, msg = fn(s)
    if new is None:
        print(msg); return msg.endswith("최신")
    print(os.path.basename(path), "백업:", backup(path))
    open(path, "w", encoding="utf-8", newline="").write(new.replace("\n", "\r\n") if crlf else new)
    print(os.path.basename(path), msg)
    return True

def fix_main(s):
    n = s.count(KEY)
    if n == 0:
        return None, "main.py 는 이미 최신"
    new = s.replace(KEY, "True")
    try:
        compile(new, "main.py", "exec")
    except SyntaxError as e:
        return None, "main.py 문법 오류 %r -> 중단" % (e,)
    return new, "패치 완료 (%d곳, 메인 재시작 필요)" % n

def _match_paren(s, i):
    """s[i] == '(' 의 짝 ')' 위치 (문자열 안의 괄호는 무시)"""
    depth, q = 0, None
    j = i
    while j < len(s):
        c = s[j]
        if q:
            if c == "\\":
                j += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1

def fix_panel(s):
    k = s.find('"barracks_swap"')
    if k < 0:
        return None, "panel.py 는 이미 최신"
    i = s.rfind("(", 0, k)
    j = _match_paren(s, i)
    if i < 0 or j < 0 or s[i + 1:k].strip():
        return None, "panel.py 앵커 형태 이상"
    end = j + 1
    while end < len(s) and s[end] in " \t":
        end += 1
    if end < len(s) and s[end] == ",":
        end += 1
    ls = s.rfind("\n", 0, i) + 1
    if s[ls:i].strip() == "":
        i = ls
        while end < len(s) and s[end] in " \t":
            end += 1
        if end < len(s) and s[end] == "\n" and s[ls:ls] == "":
            end += 1
    new = s[:i] + s[end:]
    try:
        compile(new, "panel.py", "exec")
    except SyntaxError as e:
        return None, "panel.py 문법 오류 %r -> 중단" % (e,)
    return new, "패치 완료 (패널은 스스로 다시 뜸)"

def main():
    ok = True
    for p, f in ((MAIN, fix_main), (PANEL, fix_panel)):
        if not os.path.exists(p):
            print(os.path.basename(p), "없음"); ok = False; continue
        ok = rw(p, f) and ok
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
