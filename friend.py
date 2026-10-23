"""friend.py - 친구 창: 하루 한 번 '모두 보내기' + 아이콘에 빨간 점이 뜨면 '모두 받기'
  py friend.py look      지금 화면에서 친구 아이콘 점 비율만 출력
  py friend.py go        친구 창을 열어 보내기/받기 실행
버튼은 위치 대신 글자(윈도우 OCR)로 찾음: '모두 보내기' / '모두 받기', 상태 글자 '보냈어요' / '선물 없음'
"""
import sys, os, re, time
import cv2
import daily

ICON = (669, 437)                     # 오른쪽 HUD 아래쪽 두 사람 모양 아이콘 (펼친 상태) (patch213: 예전 662, 500)
DOT_ROI = (674, 406, 700, 430)        # 아이콘 오른쪽 위 빨간 점
DOT_THR = 0.08
FRIEND_TAB_X = 155                    # '친구' 탭 x (같은 줄의 '받은 요청' 글자 y 를 씀)
SHOTS = r"C:\macro\shots"


def log(*a):
    print(time.strftime("[%H:%M:%S] friend:"), *a, flush=True)


def shot(name, img):
    try:
        os.makedirs(SHOTS, exist_ok=True)
        cv2.imwrite(os.path.join(SHOTS, name), img)
    except Exception:
        pass


def dot(img):
    return daily.ratio(img, DOT_ROI, "dot")


def _words(img):
    import ocrx
    return ocrx.words(img) or []


def _find(ws, key, ymax=None):
    for t, x, y, w, h in ws:
        if key in t and (ymax is None or y <= ymax):
            return (x, y)
    return None


def _joined(ws):
    return " ".join(w[0] for w in ws)


def _close():
    """친구 창 닫기: 빨간 X -> 없으면 뒤로가기"""
    import ocrx
    for _ in range(3):
        img = daily.cap()
        if img is None:
            return
        xs = ocrx.red_x_buttons(img)
        if not xs:
            return
        daily.tap(xs[0], 0.9)
    daily.adb("shell", "input", "keyevent", "4")


def _ok_popup():
    """보내기/받기 뒤에 뜬 확인 창이 있으면 '확인' 누름"""
    img = daily.cap()
    if img is None:
        return
    p = _find(_words(img), "확인")
    if p:
        log("확인 창 -> 확인", p)
        daily.tap(p, 0.9)


def _gift_info(ws, p):
    """patch199: '모두 받기' 버튼 근처의 '+190' 같은 보석 표시와 빨간 숫자(받을 개수)"""
    gem, cnt = None, None
    for t, x, y, w, h in ws:
        if abs(y - p[1]) > 90 or abs(x - p[0]) > 200:
            continue
        m = re.search(r"\+\s*(\d+)", t)
        if m and gem is None:
            gem = int(m.group(1))
        elif t.strip().isdigit() and y < p[1] and cnt is None:
            cnt = int(t.strip())
    return gem, cnt


def run(send=True, force=False):
    """반환: {'opened': 창을 열었는지, 'sent': 오늘 보내기 끝(이미 보냄 포함), 'got': 받기 눌렀는지}"""
    res = {"opened": False, "sent": False, "got": False}
    daily.close_panels()
    try:
        import hud
        hud.ensure()
    except Exception as e:
        log("HUD 확인 오류:", e)
    img = daily.cap()
    if img is None:
        return res
    dr = dot(img)
    log("친구 아이콘 점 비율 %.2f" % dr)
    has_dot = dr >= DOT_THR
    if not (send or has_dot or force):
        return res
    daily.tap(ICON, 1.6)
    img = daily.cap()
    ws = _words(img) if img is not None else []
    txt = _joined(ws)
    if "친구" not in txt or ("모두" not in txt and "선물" not in txt):
        log("친구 창이 아님 (shots\\friend_nav.png):", txt[:80])
        if img is not None:
            shot("friend_nav.png", img)
        _close()
        return res
    res["opened"] = True
    tab = _find(ws, "받은")                      # '받은 요청' 탭과 같은 줄의 왼쪽이 '친구' 탭
    if tab and tab[1] < 400:
        daily.tap((FRIEND_TAB_X, tab[1]), 1.0)
        img = daily.cap()
        ws = _words(img) if img is not None else ws
        txt = _joined(ws)
    # 보내기
    if send:
        if "보냈" in txt:
            log("오늘 이미 다 보냄")
            res["sent"] = True
        else:
            p = _find(ws, "보내기", ymax=640)
            if p:
                log("모두 보내기", p)
                daily.tap(p, 1.5)
                _ok_popup()
                res["sent"] = True
            else:
                log("'모두 보내기' 글자를 못 찾음")
    # 받기 (patch199: 창을 열었으면 항상 '모두 받기' 시도, 보석 수와 결과를 기록)
    p = _find(ws, "받기", ymax=640)
    if p:
        gem, cnt = _gift_info(ws, p)
        if True:                                     # 보석 글자를 못 읽어도 누름 (선물이 없으면 눌러도 그만)
            daily.tap(p, 1.5)
            _ok_popup()
            img2 = daily.cap()
            ws2 = _words(img2) if img2 is not None else []
            p2 = _find(ws2, "받기", ymax=640)
            gem2 = _gift_info(ws2, p2)[0] if p2 else None
            res["got"] = True
            res["gems"] = gem
            res["left"] = gem2
            log("모두 받기: 보석 %s (%s개) -> 받은 뒤 남은 표시 %s" % ("?" if gem is None else "+%d" % gem, "?" if cnt is None else cnt, "없음" if not gem2 else "+%d" % gem2))
    else:
        log("'모두 받기' 글자를 못 찾음 (shots\\friend_nogift.png)")
        if img is not None:
            shot("friend_nogift.png", img)
    img = daily.cap()
    if img is not None:
        shot("friend_after.png", img)
    _close()
    return res


if __name__ == "__main__":
    if "go" in sys.argv[1:]:
        log("결과:", run(send=True, force=True))
    else:
        img = daily.cap()
        log("친구 아이콘 점 비율 %.2f (기준 %.2f)" % (dot(img), DOT_THR))
