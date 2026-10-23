"""drum.py - 고레벨 단계 2단계 뒤: 전장의북 2마리 훈장 강화 2000 (patch171, 사용자 요청 10-18)
  전장의북에도 '사거리 증가 / 공속 증가' 가 있어 훈장으로 키움. 이후 전체 레벨업 한 번은 main 에서

  py drum.py look     영웅 목록에서 전장의북 줄과 훈장 숫자만 출력 (누르지 않음)
  py drum.py go       실제로 올림 (영웅 탭 목록이 보이는 상태)

방법: 목록에서 '전장' 글자로 줄을 찾음 -> 상세창 -> 초상화 위 '+숫자'(훈장)를 글자로 읽음
      -> 2000 미만이면 '강화' 3연타 -> 위 메뉴 맨 위 버튼(다음 1000 단위까지) -> 다시 읽기 (최대 3번)
      숫자가 안 바뀌면(훈장 부족 등) 그만. 처음 몇 판은 메뉴 화면을 shots\\drum_menu_*.png 로 남김
"""
import os, re, sys, time
import cv2
import preset
import barracks as B
import newspirit as N

TARGET = 2000
GO = "go" in sys.argv[1:]


def log(*a):
    print(*a, flush=True)


def _words(img):
    try:
        import ocrx
        return ocrx.words(img) or []
    except Exception:
        return []


def rows_ext(img):
    """patch203: newspirit.rows_of 와 같은 방식이되 목록 맨 아래 줄까지 (rows_of 는 y 1210 아래를 버려서
    목록 마지막 줄인 두 번째 전장의북을 한 번도 못 찾았음)"""
    y0, y1 = 880, 1262
    h = N._hsv(img, 10, y0, 30, y1)
    f = ((h[..., 0] >= 18) & (h[..., 0] <= 35) & (h[..., 1] > 130) & (h[..., 2] > 150)).mean(1)
    out = []
    for i in range(1, len(f) - 3):
        if f[i] >= 0.5 and f[i + 3] < 0.15 and (not out or y0 + i - out[-1] > 20):
            out.append(y0 + i)
    return [b - 52 for b in out if b - 82 >= 926]


def drum_rows(img):
    """목록에서 전장의북 줄의 기준 y (newspirit.rows_of 와 같은 기준). patch203: 글자와 가장 가까운 줄로"""
    rows = rows_ext(img)
    out = []
    for t, x, y, w, h in _words(img):
        if "전장" in t and x < 500:
            near = [r for r in rows if abs(r - (y + 8)) <= 30]
            if near:
                r = min(near, key=lambda r: abs(r - (y + 8)))
            elif 926 <= y + 8 <= 1195:                    # patch213: 마지막 줄은 초상화 아래 테두리가 탭에 가려 줄을 못 찾음 -> 글자 위치로
                r = int(y + 8)
            else:
                continue
            if all(abs(r - o) > 30 for o in out):
                out.append(r)
    return sorted(out)


def medal_value(img):
    """상세창 초상화 위 '+1234' -> 1234. 못 읽으면 None, 표시가 없으면 0"""
    c = img[290:340, 40:160]
    c = cv2.resize(c, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    txt = "".join(w[0] for w in _words(c)).replace(" ", "")
    m = re.search(r"\+?(\d{1,5})", txt)
    if m:
        return int(m.group(1))
    return 0 if N._digits(img, 55, 295, 140, 335) == 0 else None


def up_one(y, k):
    """줄 y 의 전장의북 훈장을 TARGET 까지. 결과 문자열"""
    img = B.capture()
    x = B.HERO_ROW_X
    if img is not None and N._menu_on_row(img, y):
        x = 80
    B.tap((x, y + 10), "전장의북 상세")
    img = preset.wait_for(B.detail_open, 3.0, first=0.2, step=0.15)
    if img is None or not B.detail_open(img):
        log("상세창이 안 열림")
        return "nodetail"
    btn = N.MEDAL_BTN
    if N._ratio(img, btn[0] - 60, btn[1] - 10, btn[0] + 60, btn[1] + 10, "green") < 0.4:
        B.tap(B.TAB_DETAIL, "상세 탭")
        time.sleep(0.6)
        img = B.capture()
    res = "fail"
    try:
        v = medal_value(img)
        log("전장의북 %d: 훈장 %s" % (k, v))
        if v is not None and v >= TARGET:
            return "already"
        if v is None:                                # 못 읽었는데 올리면 2000 넘게 올릴 수 있음 -> 건드리지 않음
            log("  훈장 숫자를 못 읽음 -> 건너뜀 (shots\\drum_unread.png)")
            N._save(img, "drum_unread.png")
            return "unread"
        # 사용자 방식: '강화' 3번 눌러 메뉴를 펼치고 맨 위(1000짜리)를 두 번 연속. 훈장이 부족하면(버튼이 초록이 아님) 그냥 끝
        img = B.capture()
        if img is None or N._ratio(img, btn[0] - 60, btn[1] - 10, btn[0] + 60, btn[1] + 10, "green") < 0.4:
            log("강화 버튼을 못 찾음")
            return "fail"
        preset.tap_burst(btn, "훈장 강화", 3)
        time.sleep(0.7)
        top = N.MEDAL_TOP
        pressed = 0
        for k2 in range(2):
            img = B.capture()
            N._save(img, "drum_menu_%d.png" % k2)
            if img is None or N._ratio(img, top[0] - 60, top[1] - 10, top[0] + 60, top[1] + 10, "green") < 0.4:
                log("  1000짜리 버튼이 초록이 아님 (훈장 부족) -> 끝")
                break
            B.tap(top, "훈장 1000짜리 (%d/2)" % (k2 + 1))
            pressed += 1
            time.sleep(0.8)
        nv = medal_value(B.capture())
        log("  훈장 %s -> %s (1000짜리 %d번)" % (v, nv, pressed))
        res = "done" if pressed == 2 else ("partial" if pressed else "nomedal")
    finally:
        B.tap(B.DETAIL_X, "상세창 닫기")
        preset.wait_for(lambda im: not B.detail_open(im), 3.0, first=0.3, step=0.15)
    return res


def upgrade(max_views=6):
    """전장의북 훈장 TARGET 까지. 목록을 위에서부터 내리며 '전장' 줄마다 상세창을 열어 확인 (이미 TARGET 이면 그냥 닫음)
    실패해도 고레벨 단계는 계속"""
    if not GO:
        return True
    if not B.open_hero_tab():
        log("영웅 탭을 못 열음")
        return False
    res = []
    try:
        # patch203: 전장의북은 목록 맨 아래 두 줄 -> 끝까지 내린 화면에서 한 번에 찾음
        #   (화면마다 찾으면 같은 북을 두 번 올릴 수 있고, 마지막 줄은 아예 못 찾았음)
        last = None
        for img, top in N._views(max_views):
            last = img
        if last is None:
            log("영웅 목록 화면을 못 받음")
            return False
        N._save(last, "drum_list.png")
        ys = drum_rows(last)
        log("목록 맨 아래 화면의 전장의북 줄: %s (shots\\drum_list.png)" % ys)
        for y in ys[:2]:
            r = up_one(y, len(res) + 1)
            res.append(r)
            log("전장의북 줄 y=%d 훈장: %s" % (y, r))
            if r == "nomedal":
                break
    finally:
        B.fc_stop()
    log("전장의북 훈장 강화 끝: %s" % res)
    return sum(r in ("done", "already") for r in res) >= 2


if __name__ == "__main__":
    preset.GO = GO
    B.GO = True
    if not GO:
        for img, top in N._views():
            log("== 화면:", "맨 위" if top else "아래", "전장의북 줄:", drum_rows(img))
    else:
        log("결과:", upgrade())
