# patch49.py - 병영 편성 방식의 일괄 레벨업을 1라운드만 돌리도록 (C:\macro 에서 py patch49.py)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "main.py")
A = '    if not preset.bulk_levelup():\n        return _barracks_fallback("일괄 레벨업")\n'
B = '    if not preset.bulk_levelup(max_rounds=1):\n        return _barracks_fallback("일괄 레벨업")\n'


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(MAIN):
        print("main.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    s = open(MAIN, encoding="utf-8").read()
    if B in s:
        print("main.py 는 이미 최신"); return 0
    if s.count(A) != 1:
        print("앵커 불일치 (patch48 을 먼저 적용했나요?) -> main.py 를 올려 주세요"); return 1
    print("main.py 백업:", backup(MAIN))
    open(MAIN, "w", encoding="utf-8").write(s.replace(A, B, 1))
    print("패치 완료: 병영 편성 방식은 일괄 레벨업 1라운드만 진행 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
