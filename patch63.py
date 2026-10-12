# patch63.py - 일괄 레벨업: 버튼 비용 표시로 최대 레벨/골드 부족을 구분해서 불필요한 클릭 없이 종료 (C:\macro 에서 py patch63.py)
#  * 네 버튼(+1000/+100/+10/+1)의 비용이 모두 0 이면 = 전부 최대 레벨 -> 더 누르지 않고 바로 닫음
#  * 버튼이 회색(골드 부족)이면 그 단위는 건너뛰고 더 작은 단위로 이동 (+1000 -> +100 -> +10 -> +1)
#  * 눌러도 레벨이 안 오르면(렉 등) 3번 연속에서 중단하는 안전장치는 그대로 유지
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PRESET = os.path.join(HERE, "preset.py")

HELP_ANCHOR = "def bulk_levelup(max_rounds=3, max_press=40):\n"
HELP = '''def _btn_x(i):
    return BULK_BTNS[i][1][0]


def btn_active(img, i):
    """일괄 레벨업 버튼이 갈색(누를 수 있음)이면 True, 회색(골드 부족)이면 False"""
    x = _btn_x(i)
    hsv = cv2.cvtColor(img[1116:1124, x - 55:x + 55], cv2.COLOR_BGR2HSV)
    return float(np.median(hsv[..., 1])) >= 60


def cost_is_zero(img, i):
    """버튼 아래 비용 글자가 '0' 한 글자뿐이면 True (올릴 레벨이 없음)"""
    x = _btn_x(i)
    hsv = cv2.cvtColor(img[1148:1174, x - 55:x + 60], cv2.COLOR_BGR2HSV)
    m = (hsv[..., 2] > 190) & (hsv[..., 1] < 110)
    n = int((m.sum(axis=0) >= 2).sum())
    return 4 <= n <= 12


def levels_maxed(img):
    """체크된 영웅이 모두 최대 레벨이면 True (+1 버튼 비용이 0)"""
    return cost_is_zero(img, 3)


'''
OLD = '''    for rnd in range(1, max_rounds + 1):
        changed_round = False
        for name, pt in BULK_BTNS:
            before = level_crop(capture())
            presses = 0
            for k in range(max_press // BURST):
                tap_burst(pt, name, BURST)
                presses += BURST
                time.sleep(0.25)
                now = capture()
                if now is None or not bulk_open(now):
                    print("일괄 레벨업 창 상태 이상 → 중단"); return False
                cur = level_crop(now)
                diff = float(np.abs(cur - before).mean())
                before = cur
                if diff > thr:
                    changed_round = True
                else:
                    break
            print(f"  라운드 {rnd} {name}: {presses}회 눌러 종료")
        if not changed_round:
            break
'''
NEW = '''    maxed = False
    for rnd in range(1, max_rounds + 1):
        pressed_round = False
        for i, (name, pt) in enumerate(BULK_BTNS):
            presses = 0
            still = 0
            before = None
            why = "한도"
            for k in range(max(max_press, 300) // BURST):
                now = capture()
                if now is None or not bulk_open(now):
                    print("일괄 레벨업 창 상태 이상 → 중단"); return False
                if levels_maxed(now):
                    maxed = True
                    why = "모든 영웅 최대 레벨"
                    break
                if not btn_active(now, i):
                    why = "골드 부족(회색)"
                    break
                cur = level_crop(now)
                if before is not None:
                    if float(np.abs(cur - before).mean()) > thr:
                        still = 0
                    else:
                        still += 1
                        if still >= 3:                 # 눌러도 안 오름(렉 등) -> 안전장치
                            why = "변화 없음"
                            break
                before = cur
                tap_burst(pt, name, BURST)
                presses += BURST
                pressed_round = True
                time.sleep(0.25)
            print(f"  라운드 {rnd} {name}: {presses}회 눌러 종료 ({why})")
            if maxed:
                break
        if maxed or not pressed_round:
            break
'''


def backup(path):
    n = 1
    while os.path.exists("%s.bak%02d" % (path, n)):
        n += 1
    dst = "%s.bak%02d" % (path, n)
    shutil.copy2(path, dst)
    return dst


def main():
    if not os.path.exists(PRESET):
        print("preset.py 가 없습니다. C:\\macro 에서 실행하세요."); return 1
    s = open(PRESET, encoding="utf-8").read()
    if "def levels_maxed(" in s:
        print("preset.py 는 이미 최신"); return 0
    if s.count(OLD) != 1 or s.count(HELP_ANCHOR) != 1:
        print("앵커 불일치 (루프 %d, 함수 %d) -> preset.py 를 올려 주세요 (patch62 를 적용했다면 알려 주세요)" % (s.count(OLD), s.count(HELP_ANCHOR))); return 1
    print("preset.py 백업:", backup(PRESET))
    open(PRESET, "w", encoding="utf-8").write(s.replace(HELP_ANCHOR, HELP + HELP_ANCHOR, 1).replace(OLD, NEW, 1))
    print("패치 완료 (메인 매크로를 껐다 켜세요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
