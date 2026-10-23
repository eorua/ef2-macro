"""newspirit.py - 고레벨 단계 2단계에서 새로 넣은 불의정령 2마리를 '훈장 강화 1000 + 골드 레벨 1000' 으로 올림
  (불의정령 1000레벨 스킬 '모든 병사의 공격거리 증가' 용. 강화 1000 이면 효과 2배)

  py newspirit.py look      영웅 탭 목록(맨 위/맨 아래)에서 불정 줄과 강화·레벨 자릿수만 출력 (누르지 않음)
  py newspirit.py go        실제로 올림 (영웅 목록이 보이는 상태에서)

방법 (사용자 확인)
  훈장: 상세창 '강화' 3연타 -> 위로 메뉴 (+N:1000까지 / 100까지 / 10까지) -> 맨 위 버튼
  골드: 영웅 탭 '+'(일괄 레벨업) 창 -> 전체 선택 -> '+1000' 2번
  이미 1000 이상(초상화의 +숫자 / Lv.숫자 가 4자리 이상)이면 건드리지 않음
"""
import os, sys, time
import cv2, numpy as np
import preset
import barracks as B

GO = "go" in sys.argv[1:]
SHOTS = r"C:\macro\shots"
MEDAL_BTN = (240, 1222)          # 상세창 '강화'
MEDAL_TOP = (240, 976)           # 3연타 뒤 뜨는 메뉴 맨 위 (1000까지)
GOLD_PLUS_X = 640                # 목록 줄의 '+1'
GOLD_TOP_X = 230                 # 3연타 뒤 뜨는 메뉴 맨 왼쪽 (1000까지)


def log(*a):
    print(*a, flush=True)


def _hsv(img, x1, y1, x2, y2):
    return cv2.cvtColor(img[max(0, y1):y2, max(0, x1):x2], cv2.COLOR_BGR2HSV)


def is_spirit(img, y):
    """목록 줄 초상화가 붉은 머리(불의정령)면 True"""
    h = _hsv(img, 25, y - 20, 140, y + 45)
    H, S, V = h[..., 0], h[..., 1], h[..., 2]
    return float((((H <= 12) | (H >= 170)) & (S > 120) & (V > 90)).mean()) >= 0.12


def _digits(img, x1, y1, x2, y2):
    """흰/노란 글자 중 숫자 크기(높이 12~17) 덩어리 수"""
    h = _hsv(img, x1, y1, x2, y2)
    m = (((h[..., 1] < 60) & (h[..., 2] > 200)) |
         ((h[..., 0] >= 18) & (h[..., 0] <= 35) & (h[..., 1] > 120) & (h[..., 2] > 180))).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    return sum(1 for s in st[1:] if 12 <= s[3] <= 17 and 4 <= s[2] <= 12)


def medal_digits(img, y):
    return _digits(img, 55, y - 25, 140, y + 5)              # 초상화 위 '+4271'


def gold_digits(img, y):
    return max(0, _digits(img, 30, y + 22, 135, y + 52) - 1)   # 초상화 아래 'Lv.2379' (L 제외)


def _ratio(img, x1, y1, x2, y2, kind):
    h = _hsv(img, x1, y1, x2, y2)
    H, S, V = h[..., 0], h[..., 1], h[..., 2]
    if kind == "green":
        m = (H >= 35) & (H <= 75) & (S > 120) & (V > 110)
    else:                                                    # 갈색 버튼 (목록 바탕보다 밝음)
        m = (H >= 5) & (H <= 25) & (S > 100) & (V > 90)
    return float(m.mean())


def _save(img, name):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name), img)
    except Exception:
        pass


def rows_of(img):
    """보이는 줄의 기준 y 목록 (초상화 아래 노란 테두리로 찾음 -> 스크롤 위치와 무관). 초상화가 다 보이는 줄만"""
    y0, y1 = 880, 1215
    h = _hsv(img, 10, y0, 30, y1)
    f = ((h[..., 0] >= 18) & (h[..., 0] <= 35) & (h[..., 1] > 130) & (h[..., 2] > 150)).mean(1)
    out = []
    for i in range(1, len(f) - 3):
        if f[i] >= 0.5 and f[i + 3] < 0.15 and (not out or y0 + i - out[-1] > 20):
            out.append(y0 + i)
    # 초상화 위쪽(강화 숫자 '+1000')까지 다 보이는 줄만: 목록 머리 아래(926) 에 가려지면 숫자를 0자리로 잘못 읽음
    # (10-14 23:46 y=943 줄의 +1000 을 0자리로 읽어 +2003 까지 올린 원인)
    return [b - 52 for b in out if b - 82 >= 926 and b <= 1210]


def _targets(img, top=None):
    """이 화면에서 아직 1000이 안 된 불정 줄 [(y, 훈장자릿수, 골드자릿수)]
    (기존 불정 2마리는 훈장·골드 모두 4자리 이상이라 저절로 빠짐)"""
    out = []
    for y in rows_of(img):
        if not is_spirit(img, y):
            continue
        md, gd = medal_digits(img, y), gold_digits(img, y)
        if md < 4 or gd < 4:
            out.append((y, md, gd))
    return out


def _views(max_steps=6):
    """맨 위부터 두 줄씩 내리며 화면을 차례로 돌려줌 (img, 맨위여부)"""
    img = B._list_to_top()
    if img is None:
        return
    yield img, True
    for _ in range(max_steps):
        B.swipe_hold(360, 1150, 970)
        cur = B._settle()
        if cur is None or not B._list_moved(img, cur, 3.0):
            return                                       # 맨 아래
        img = cur
        yield img, False


def _menu_on_row(img, y):
    return _ratio(img, GOLD_TOP_X - 40, y, GOLD_TOP_X + 40, y + 20, "brown") >= 0.5


def gold_up(y):
    """+1 3연타 -> 메뉴 맨 왼쪽(1000까지) 2번 (사용자: 1000짜리 한두 번이면 충분)"""
    preset.tap_burst((GOLD_PLUS_X, y + 10), "골드 +1", 3)
    time.sleep(0.7)
    img = B.capture()
    if img is None:
        return False
    if not _menu_on_row(img, y):
        log("골드 메뉴가 안 보임 -> 건너뜀")
        _save(img, "ns_gold_nomenu.png")
        return False
    B.tap((GOLD_TOP_X, y + 10), "골드 1000까지")
    time.sleep(0.6)
    B.tap((GOLD_TOP_X, y + 10), "골드 1000까지(2번째)")
    time.sleep(0.6)
    return True


def medal_up(y):
    img = B.capture()
    x = B.HERO_ROW_X
    if img is not None and _menu_on_row(img, y):
        x = 80                                       # 골드 메뉴가 줄을 가리고 있으면 초상화를 눌러 상세창
    B.tap((x, y + 10), "새 불정 상세")
    img = preset.wait_for(B.detail_open, 3.0, first=0.2, step=0.15)
    if img is None or not B.detail_open(img):
        log("상세창이 안 열림")
        if img is not None:
            _save(img, "ns_nodetail.png")
        return False
    if _ratio(img, MEDAL_BTN[0] - 60, MEDAL_BTN[1] - 10, MEDAL_BTN[0] + 60, MEDAL_BTN[1] + 10, "green") < 0.4:
        B.tap(B.TAB_DETAIL, "상세 탭")                        # 초월 탭이면 강화 버튼이 없음
        time.sleep(0.6)
        img = B.capture()
    ok = False
    nd = _digits(img, 55, 295, 140, 335) if img is not None else 9
    if nd >= 4:                                      # 10-14 23:46: +1000 불정을 또 올려 +2003 이 된 사고 -> 상세창에서 한 번 더 확인
        log("상세창 초상화 강화 숫자가 %d자리(1000 이상) -> 누르지 않고 닫음" % nd)
        _save(img, "ns_medal_already.png")
        B.tap(B.DETAIL_X, "상세창 닫기")
        preset.wait_for(lambda im: not B.detail_open(im), 3.0, first=0.3, step=0.15)
        return "already"
    if img is not None and _ratio(img, MEDAL_BTN[0] - 60, MEDAL_BTN[1] - 10, MEDAL_BTN[0] + 60, MEDAL_BTN[1] + 10, "green") >= 0.4:
        preset.tap_burst(MEDAL_BTN, "훈장 강화", 3)
        time.sleep(0.7)
        img = B.capture()
        if img is not None and _ratio(img, MEDAL_TOP[0] - 60, MEDAL_TOP[1] - 10, MEDAL_TOP[0] + 60, MEDAL_TOP[1] + 10, "green") >= 0.4:
            B.tap(MEDAL_TOP, "훈장 1000까지")
            time.sleep(0.8)
            ok = True
        else:
            log("훈장 메뉴 맨 위 버튼이 초록이 아님(훈장 부족?) -> 건너뜀")
            if img is not None:
                _save(img, "ns_medal_nomenu.png")
    else:
        log("강화 버튼을 못 찾음")
    B.tap(B.DETAIL_X, "상세창 닫기")
    preset.wait_for(lambda im: not B.detail_open(im), 3.0, first=0.3, step=0.15)
    return ok


def bulk_gold(times=2):
    """골드 레벨: 영웅 탭 '+'(일괄 레벨업) 창 -> 전체 선택 -> '+1000' 을 times 번 (사용자 방식)"""
    preset.tap(preset.TAB_HERO, "영웅 탭")
    time.sleep(0.6)
    preset.tap(preset.BTN_PLUS, "+")
    img = preset.wait_for(preset.bulk_open, 5.0, first=0.4, step=0.25)
    if img is None or not preset.bulk_open(img):
        log("일괄 레벨업 창이 안 열림")
        return False
    for _ in range(3):
        if preset.all_checked(img):
            break
        preset.tap(preset.BULK_ALL, "전체 선택(1)")
        time.sleep(0.4)
        preset.tap(preset.BULK_ALL, "전체 선택(2)")
        img = preset.wait_for(preset.all_checked, 1.5, first=0.25, step=0.2)
        if img is None:
            break
    ok = img is not None and preset.all_checked(img)
    if ok:
        name, pt = preset.BULK_BTNS[0]                  # '+1000'
        for k in range(times):
            preset.tap(pt, "%s (%d/%d)" % (name, k + 1, times))
            time.sleep(0.6)
    else:
        log("전체 선택 실패 -> 골드 레벨업 안 함")
    preset.tap(preset.BULK_X, "X")
    preset.wait_for(lambda im: not preset.bulk_open(im), 2.5, first=0.3, step=0.25)
    return ok


def upgrade(max_steps=6):
    """새 불정: 골드 레벨은 '+' 창에서 +1000 두 번, 훈장은 상세창에서 1000까지. 다 되면 True (실패해도 고레벨 단계는 계속)"""
    if not GO:
        return True
    # patch142: 골드 레벨은 '+' 창 대신 영웅 AUTO 5초로 (이 시점 유물 프리셋은 영웅강화골드)
    try:
        r = preset.auto_levelup(5.0)
        log("골드 레벨: 영웅 AUTO 5초 -> %s" % {True: "완료", False: "AUTO 끄기 실패!", None: "AUTO 반응 없음"}[r])
        if r is None:
            log("골드 레벨: AUTO 대신 '+' 창에서 +1000 x2 -> " + ("완료" if bulk_gold(2) else "실패"))
    except Exception as e:
        log("영웅 AUTO 오류: %r" % (e,))
    try:                                                 # 다음 판에 원인을 보려고 결과 화면 저장
        import cv2 as _cv
        _im = preset.capture()
        if _im is not None:
            _cv.imwrite(r"C:\macro\shots\ns_gold_after.png", _im)
    except Exception:
        pass
    if not B.open_hero_tab():
        log("영웅 탭을 못 열음")
        return False
    worked, fails = 0, 0
    left = []
    try:
        for _ in range(max_steps):
            found = None
            for img, top in _views():
                t = [x for x in _targets(img, top) if x[1] < 4]      # 훈장이 1000 미만인 불정
                if t:
                    found = t[0]
                    break
            if found is None:
                break
            y, md, gd = found
            log("새 불정 줄 y=%d (훈장 %d자리, 골드 레벨 %d자리) -> 훈장 강화" % (y, md, gd))
            _save(img, "ns_target.png")
            ok = medal_up(y)
            if ok == "already":
                log("목록에서는 1000 미만으로 읽었는데 상세창은 1000 이상 -> 목록 판독 오류, 훈장 단계 중단")
                break
            worked += 1
            fails = 0 if ok else fails + 1
            if fails >= 2:
                log("훈장 강화가 두 번 연속 실패 -> 그만")
                break
        for im, top in _views():
            left += _targets(im, top)
            if left:
                _save(im, "ns_left.png")
                break
    finally:
        B.fc_stop()
    if left:
        log("아직 1000이 안 된 불정이 남음: %s" % left)
        return False
    log("새 불정 강화 끝 (훈장 작업 %d번)" % worked)
    return True


if __name__ == "__main__":
    preset.GO = GO
    B.GO = True                      # 목록 스크롤만 허용 (누르기는 preset.GO 로 막힘)
    if "look" in sys.argv[1:] or not GO:
        for img, top in _views():
            rows = rows_of(img)
            log("== %s 화면" % ("맨 위" if top else "아래로 내린"))
            for i, y in enumerate(rows):
                log("  줄 y=%d 불정=%s 훈장자릿수=%d 골드자릿수=%d" % (y, is_spirit(img, y), medal_digits(img, y), gold_digits(img, y)))
            log("  올릴 대상:", _targets(img, top))
    else:
        print("결과:", upgrade())
