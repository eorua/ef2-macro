# patch80.py - py arrange.py go 가 판별만 하고 끝나던 문제 수정 (patch79 다음)
#   * 원인: 'go' 만 붙이면 명령어가 비어 있어서 기본값(look)으로 처리됨
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ARR = os.path.join(HERE, "arrange.py")
OLD = '    cmd = cmd[0] if cmd else "look"\n    if cmd == "look":\n'
NEW = '    cmd = cmd[0] if cmd else ("run" if GO else "look")\n    if cmd == "look":\n'


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(ARR):
        print("arrange.py 가 없습니다 (patch79 먼저)"); return 1
    s = open(ARR, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if NEW in s:
        print("arrange.py 는 이미 최신"); return 0
    if s.count(OLD) != 1:
        print("arrange.py 앵커 불일치", s.count(OLD)); return 1
    print("arrange.py 백업:", backup(ARR))
    s = s.replace(OLD, NEW, 1)
    open(ARR, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("arrange.py 패치 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
