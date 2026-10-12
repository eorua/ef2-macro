# patch82.py - 중간 단계(5000~6200)에서 영웅 프리셋은 건드리지 않고 유물만 바꿔 일괄 레벨업
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
A1 = '    ok = preset.set_presets("최대레벨", "영웅강화골드")\n    if not ok:\n        return False\n    bulk_ok = preset.bulk_levelup()\n    final_ok = preset.set_presets("기본", "시간")\n'
B1 = '    ok = preset.set_presets(None, "영웅강화골드")\n    if not ok:\n        return False\n    bulk_ok = preset.bulk_levelup()\n    final_ok = preset.set_presets(None, "시간")\n'

def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst

def main():
    s = open(MAIN, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if B1 in s:
        print("main.py 는 이미 최신"); return 0
    if s.count(A1) != 1:
        print("main.py 앵커 불일치", s.count(A1)); return 1
    print("main.py 백업:", backup(MAIN))
    s = s.replace(A1, B1, 1)
    open(MAIN, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("main.py 패치 완료 (메인 재시작 필요)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
