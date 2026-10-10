# opt.py - 매크로 옵션 켜고 끄기 (C:\\macro 에서 실행)
#   py opt.py show            현재 상태 보기
#   py opt.py fall on|off     성 함락 시 이어하기 사용 (off 면 바로 환생)
import os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
NAMES = {"fall": ("fall_continue", "성 함락 시 이어하기")}


def path(key):
    return os.path.join(BASE, "opt_%s.on" % NAMES[key][0])


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] in NAMES and a[1] in ("on", "off"):
        p = path(a[0])
        if a[1] == "on":
            open(p, "w").write("on")
        elif os.path.exists(p):
            os.remove(p)
        print("%s: %s" % (NAMES[a[0]][1], a[1].upper()))
        return
    for k in NAMES:
        print("%-4s %s : %s" % (k, NAMES[k][1], "ON" if os.path.exists(path(k)) else "OFF"))
    if a and a[0] != "show":
        print("사용법: py opt.py fall on|off")


main()
