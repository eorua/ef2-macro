# patch75.py - 병영 편성: 불의정령 3마리를 남기고 (맨 아래부터) 7명 해제 (C:\macro 에서 py patch75.py)
#   * 1단계: 불의정령 3 + 골렘 7 / 2단계: 불의정령 3 + 드루이드 6 + 전장의북 1 (불의정령 새로 배치 안 함 -> 남긴 3마리 레벨 유지)
#   * 해제 방법: 영웅 목록을 맨 아래까지 스크롤하면 마지막 영웅이 3번째 줄 자리에 옴 -> 그 줄을 7번 해제 (목록이 알아서 아래로 채워짐)
#       - 슬롯이 10/10 이면 정확히 7번, 아니면 매번 '스크롤 가능한지' 확인해서 3명이 남으면 멈춤 (남길 3명은 절대 안 누름)
#   * 시험:  py barracks.py release go  (영웅 목록에서 3명만 남기고 해제)
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(HERE, "barracks.py")

O_KEEP = "KEEP = 2                            # 위에서 남길 영웅 수\n"
N_KEEP = "KEEP = 3                            # 위에서 남길 영웅 수 (불의정령 3마리)\n"
O_TOPUP = "def topup(key, tries=3):\n"
N_TAIL = '''LIST_ROI = (60, 925, 580, 1195)      # 영웅 목록이 보이는 영역


def _list_moved(a, b, thr=6.0):
    ga = cv2.cvtColor(a[LIST_ROI[1]:LIST_ROI[3], LIST_ROI[0]:LIST_ROI[2]], cv2.COLOR_BGR2GRAY).astype(np.int16)
    gb = cv2.cvtColor(b[LIST_ROI[1]:LIST_ROI[3], LIST_ROI[0]:LIST_ROI[2]], cv2.COLOR_BGR2GRAY).astype(np.int16)
    return float(np.abs(ga - gb).mean()) > thr


def scroll_bottom(max_swipes=4):
    """영웅 목록을 더 안 움직일 때까지 위로 밀어 맨 아래로 보냄"""
    prev = snap(0.2)
    for _ in range(max_swipes):
        swipe(360, 1150, 940, 350)
        cur = snap(0.5)
        if prev is None or cur is None:
            return False
        if not _list_moved(prev, cur):
            return True
        prev = cur
    return True


def release_tail(keep=KEEP, total=10):
    """맨 아래로 스크롤하면 마지막 영웅이 3번째 줄 자리에 옴 -> 그 줄을 해제 (목록이 아래로 채워짐). keep 명이 남으면 멈춤"""
    if not open_hero_tab():
        return False
    img = snap(0.15)
    if img is None:
        return False
    fixed = total - keep if is_full(img) else None       # 10/10 이면 정확히 7번
    if not scroll_bottom():
        return False
    done = 0
    for k in range(total - keep):
        if fixed is None:
            before = snap(0.2)
            swipe(360, 1000, 1100, 250)                  # 살짝 내려 봄: 안 움직이면 목록이 3줄 이하
            after = snap(0.5)
            if before is None or after is None:
                return False
            if not _list_moved(before, after):
                log(f"목록이 더 안 움직임 -> 해제 완료 ({done}명 해제)")
                return True
            if not scroll_bottom():
                return False
        img = snap(0.15)
        if img is None:
            return False
        if not hero_row_filled(img, 3):
            log("3번째 줄이 비었음 -> 해제 중단"); return done > 0
        tap((HERO_ROW_X, hero_row_y(3)), "맨 아래 영웅")
        img = preset.wait_for(detail_open, 3.0, first=0.2, step=0.15)
        if img is None or not detail_open(img):
            log("상세창이 안 열림 -> 중단"); return False
        tap(BTN_RELEASE, "해제")
        img = preset.wait_for(lambda im: not detail_open(im), 3.0, first=0.25, step=0.15)
        if img is None or detail_open(img):
            log("해제 후에도 상세창이 열려 있음 -> 중단"); return False
        done += 1
    log(f"해제 완료 ({done}명 해제)")
    return True


def topup(key, tries=3):
'''
O_P1 = '    """2명만 남기고 골렘(부족하면 죽음의 손)으로 채움"""\n    if not release_rest():\n'
N_P1 = '    """3명만 남기고 골렘(부족하면 죽음의 손)으로 채움"""\n    if not release_tail():\n'
O_P2 = '    """3번째 줄부터 해제하고 드루이드 6, 전장의북 1, 불의정령 1 로 채움 (빈 슬롯은 드루이드로 보충)"""\n    if not release_rest():\n        return False\n    deploy("druid", 6)\n    deploy("drum", 1)\n    deploy("spirit", 1)\n'
N_P2 = '    """3명(불의정령)만 남기고 해제한 뒤 드루이드 6, 전장의북 1 로 채움 (빈 슬롯은 드루이드로 보충)"""\n    if not release_tail():\n        return False\n    deploy("druid", 6)\n    deploy("drum", 1)\n'
O_CLI = '    elif cmd == "release":\n        release_rest()\n'
N_CLI = '    elif cmd == "release":\n        release_tail()\n'
PAIRS = [(O_KEEP, N_KEEP), (O_TOPUP, N_TAIL), (O_P1, N_P1), (O_P2, N_P2), (O_CLI, N_CLI)]


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
    if "def release_tail(" in s:
        print("barracks.py 는 이미 최신"); return 0
    bad = [i for i, (o, n) in enumerate(PAIRS) if s.count(o) != 1]
    if bad:
        print("barracks.py 앵커 불일치:", bad, "-> barracks.py 를 올려 주세요"); return 1
    print("barracks.py 백업:", backup(BK))
    for o, n in PAIRS:
        s = s.replace(o, n, 1)
    open(BK, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
    print("barracks.py 패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
