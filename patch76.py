# patch76.py - release_tail 보완: 해제 직후 목록이 움직이는 중에 3번째 줄을 검사해서 '비었음'으로 중단하던 문제 (patch75 다음에 실행)
#   * 원인(추정): 마지막(7번째) 해제 직전, 앞선 해제 뒤 목록이 아래로 채워지는 애니메이션 중에 한 번 찍은 화면으로 판단함
#   * 수정 1: 화면이 멈출 때까지(연속 두 장이 같을 때까지) 기다린 뒤 검사
#   * 수정 2: 마지막 2번은 슬롯이 10/10 이어도 '목록이 아직 스크롤되는지(4명 이상)' 확인하고 해제 -> 남길 3명을 누를 위험 방지
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(HERE, "barracks.py")

O_DEF = "def release_tail(keep=KEEP, total=10):\n"
N_DEF = '''def _settle(tries=6):
    """목록이 멈출 때까지(연속 두 장이 같을 때까지) 기다린 뒤 그 화면을 돌려줌"""
    prev = snap(0.2)
    for _ in range(tries):
        cur = snap(0.25)
        if prev is None or cur is None:
            return cur
        if not _list_moved(prev, cur, 3.0):
            return cur
        prev = cur
    return prev


def release_tail(keep=KEEP, total=10):
'''
O_CHK = "        if fixed is None:\n            before = snap(0.2)\n            swipe(360, 1000, 1100, 250)                  # 살짝 내려 봄: 안 움직이면 목록이 3줄 이하\n            after = snap(0.5)\n"
N_CHK = "        if fixed is None or k >= fixed - 2:\n            before = _settle()\n            swipe(360, 1000, 1100, 250)                  # 살짝 내려 봄: 안 움직이면 목록이 3줄 이하\n            after = _settle()\n"
O_SNAP = '        img = snap(0.15)\n        if img is None:\n            return False\n        if not hero_row_filled(img, 3):\n'
N_SNAP = '        img = _settle()\n        if img is None:\n            return False\n        if not hero_row_filled(img, 3):\n'
PAIRS = [(O_DEF, N_DEF), (O_CHK, N_CHK), (O_SNAP, N_SNAP)]


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
    if "def _settle(" in s:
        print("barracks.py 는 이미 최신"); return 0
    if "def release_tail(" not in s:
        print("patch75 를 먼저 적용하세요"); return 1
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
