# patch77.py - release_tail 속도 개선 (patch75, 76 다음에 실행)
#   * 평소(슬롯 10/10)에는 해제 사이에 확인용 스와이프를 하지 않고 짧게(0.3초) 기다린 뒤 3번째 줄만 확인
#   * 3번째 줄이 비어 보일 때만 '맨 아래로 다시 밀고' 재확인 (그래도 비면 중단)
#   * 10/10 이 아닐 때는 예전처럼 매번 '스크롤 가능한지' 확인해서 남길 3명을 보호
#   * 스크롤/상세창 대기 시간도 줄임
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(HERE, "barracks.py")
PAIRS = [
    ("        if fixed is None or k >= fixed - 2:\n", "        if fixed is None:\n"),
    ('        img = _settle()\n        if img is None:\n            return False\n        if not hero_row_filled(img, 3):\n            log("3번째 줄이 비었음 -> 해제 중단"); return done > 0\n',
     '        img = snap(0.3) if (fixed is not None and done > 0) else _settle()\n        if img is None:\n            return False\n'
     '        if not hero_row_filled(img, 3):\n            log("3번째 줄이 비었음 -> 맨 아래로 다시 밀고 재확인")\n'
     '            if not scroll_bottom():\n                return False\n            img = _settle()\n'
     '            if img is None or not hero_row_filled(img, 3):\n                log("3번째 줄이 여전히 비었음 -> 해제 중단"); return done > 0\n'),
    ("    prev = snap(0.2)\n    for _ in range(max_swipes):\n        swipe(360, 1150, 940, 350)\n        cur = snap(0.5)\n",
     "    prev = snap(0.1)\n    for _ in range(max_swipes):\n        swipe(360, 1150, 940, 250)\n        cur = snap(0.35)\n"),
    ('        tap((HERO_ROW_X, hero_row_y(3)), "맨 아래 영웅")\n        img = preset.wait_for(detail_open, 3.0, first=0.2, step=0.15)\n',
     '        tap((HERO_ROW_X, hero_row_y(3)), "맨 아래 영웅")\n        img = preset.wait_for(detail_open, 3.0, first=0.12, step=0.1)\n'),
    ('        tap(BTN_RELEASE, "해제")\n        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.25, step=0.15)\n        if img is None or detail_open(img):\n            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False\n        done += 1\n',
     '        tap(BTN_RELEASE, "해제")\n        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.12, step=0.1)\n        if img is None or detail_open(img):\n            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False\n        done += 1\n'),
]


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    s = open(BK, encoding="utf-8").read()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    if "맨 아래로 다시 밀고 재확인" in s:
        print("barracks.py 는 이미 최신"); return 0
    if "def _settle(" not in s:
        print("patch75, 76 을 먼저 적용하세요"); return 1
    bad = [i for i, (o, n) in enumerate(PAIRS) if s.count(o) != 1]
    if bad:
        print("barracks.py 앵커 불일치:", bad, "-> barracks.py 를 올려 주세요"); return 1
    print("barracks.py 백업:", backup(BK))
    for o, n in PAIRS:
        s = s.replace(o, n, 1)
    open(BK, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("barracks.py 패치 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
