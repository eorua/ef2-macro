# patch51.py - 공지(NOTICE) 팝업 인식 개선 + 복귀 중 막힌 창 자동 닫기 (C:\macro 에서 py patch51.py)
#  원인: 공지 창의 '오늘 하루 보지 않기' 줄이 예전보다 위(창이 짧아짐)에 있어서 공지로 인식하지 못함
#   -> 줄 위치를 화면에서 찾도록 바꿈 (예전 위치도 그대로 인정)
#   -> 복귀 중 웨이브가 안 보이면 10초마다 화면의 빨간 X 를 찾아 닫음 (closer.py 필요: patch50)
import os, sys, shutil, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
NOTICE = os.path.join(HERE, "notice.py")
MAIN = os.path.join(HERE, "main.py")

OLD_ROW = '''    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    a, b, c, d = ROW_TEXT
    if int((g[b:d, a:c] > 150).sum()) < 80:
        return None                  # 아래쪽 '오늘 하루 보지 않기' 글자 줄이 없으면 아님
    a, b, c, d = ROW_BOX
    box = g[b:d, a:c]
    if int(((box > 90) & (box < 200)).sum()) < 25:
        return None
    return X_CENTER
'''

NEW_ROW = '''    global _row_y
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    row = find_row(g)
    if row is None:                  # 예전 창 모양(고정 위치)도 인정
        a, b, c, d = ROW_TEXT
        ok = int((g[b:d, a:c] > 150).sum()) >= 80
        a, b, c, d = ROW_BOX
        box = g[b:d, a:c]
        ok = ok and int(((box > 90) & (box < 200)).sum()) >= 25
        if not ok:
            return None              # 아래쪽 '오늘 하루 보지 않기' 줄이 없으면 아님
        row = CHECK_PT[1]
    _row_y = row
    return X_CENTER
'''

FIND_ROW = '''_row_y = None


def find_row(g):
    """'오늘 하루 보지 않기' 줄의 중심 y. 공지 창 높이가 달라져도 아래쪽부터 찾음. 없으면 None"""
    H = g.shape[0]
    for y in range(min(1200, H - 45), 900, -4):
        if int((g[y:y + 40, 120:330] > 150).sum()) < 80:
            continue
        seg = g[y - 10:y + 50, 120:330]
        rows = np.nonzero((seg > 150).sum(axis=1) >= 3)[0]
        if len(rows) == 0:
            continue
        cy = y - 10 + int(np.median(rows))
        box = g[cy - 20:cy + 20, 60:105]
        if int(((box > 90) & (box < 200)).sum()) < 25:
            continue
        return cy
    return None


def detect(img):
'''

A_CHECK = '        D.tap(CHECK_PT, 0.6)\n'
B_CHECK = '        D.tap((CHECK_PT[0], _row_y or CHECK_PT[1]), 0.6)\n'

A_INIT = '    last_check = 0\n    relaunch = 0\n'
B_INIT = '    last_check = 0\n    last_x = 0\n    relaunch = 0\n'
A_GOOD = '        good = 0\n        # 웨이브가 안 보이는데 게임 화면도 아니면(홈 화면 등) 게임을 다시 실행\n'
B_GOOD = ('        good = 0\n'
          '        if time.time() - last_x >= 10:        # 어떤 창이 가리고 있을 수 있음 -> 빨간 X 를 찾아 닫기\n'
          '            last_x = time.time()\n'
          '            try:\n'
          '                import closer\n'
          '                nx = closer.close_all(2)\n'
          '                if nx:\n'
          '                    log("복귀 중 열린 창 %d개 닫음" % nx)\n'
          '                    time.sleep(1.5)\n'
          '                    continue\n'
          '            except Exception as e:\n'
          '                log("창 닫기 오류: %r" % (e,))\n'
          '        # 웨이브가 안 보이는데 게임 화면도 아니면(홈 화면 등) 게임을 다시 실행\n')


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    for p in (NOTICE, MAIN):
        if not os.path.exists(p):
            print(os.path.basename(p), "가 없습니다. C:\\macro 에서 실행하세요."); return 1
    ns = open(NOTICE, encoding="utf-8").read()
    ms = open(MAIN, encoding="utf-8").read()
    n_done = "def find_row(" in ns
    m_done = "last_x = 0" in ms
    if not n_done:
        if ns.count(OLD_ROW) != 1 or ns.count(A_CHECK) != 1 or ns.count("def detect(img):\n") != 1:
            print("notice.py 앵커 불일치 -> notice.py 를 올려 주세요"); return 1
    if not m_done:
        if not os.path.exists(os.path.join(HERE, "closer.py")):
            print("먼저 patch50.py 를 적용하세요 (closer.py)"); return 1
        if ms.count(A_INIT) != 1 or ms.count(A_GOOD) != 1:
            print("main.py 앵커 불일치 -> main.py 를 올려 주세요"); return 1
    if not n_done:
        out = ns.replace(OLD_ROW, NEW_ROW, 1).replace("def detect(img):\n", FIND_ROW, 1).replace(A_CHECK, B_CHECK, 1)
        print("notice.py 백업:", backup(NOTICE))
        open(NOTICE, "w", encoding="utf-8").write(out)
        print("notice.py 패치 완료")
    else:
        print("notice.py 는 이미 최신")
    if not m_done:
        out = ms.replace(A_INIT, B_INIT, 1).replace(A_GOOD, B_GOOD, 1)
        print("main.py 백업:", backup(MAIN))
        open(MAIN, "w", encoding="utf-8").write(out)
        print("main.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    else:
        print("main.py 는 이미 최신")
    return 0


if __name__ == "__main__":
    sys.exit(main())
