"""wavecall.py - 웨이브 호출 AUTO 자동 끄기/켜기 (설정 톱니바퀴 > 웨이브 호출 탭 > AUTO)

  py wavecall.py look        지금 화면 상태만 출력 (누르지 않음)
  py wavecall.py off go      AUTO 끄기 한 번 실행
  py wavecall.py on go       AUTO 켜기 한 번 실행

main.py 연결: 웨이브가 OFF_WAVE 이상이면 AUTO 끄기, 환생해서 ON_WAVE 미만으로 내려오면 다시 켜기
"""
import os, sys, time
import cv2, numpy as np

BASE = r"C:\macro"
sys.path.insert(0, BASE)
import preset

OFF_WAVE = 7200            # 이 웨이브 이상이면 AUTO 끔
ON_WAVE = 6000             # 환생 뒤 이 웨이브 미만이면 AUTO 다시 켬
GEAR = (170, 642)          # 왼쪽 아래 톱니(웨이브 호출/황혼의 부름 옆) - 오른쪽 위 환경설정 톱니 아님
DLG_X = (631, 213)         # 설정창 빨간 X
TAB_WAVE = (215, 270)      # '웨이브 호출' 탭
AUTO_BTN = (620, 332)      # AUTO 알약 버튼
ROI_PILL = (590, 320, 650, 346)
ROI_TAB = (150, 258, 280, 284)


def log(*a):
    print(time.strftime("[%H:%M:%S] wavecall:"), *a, flush=True)


_T = {}


def _score(img, name, roi):
    """patch103: 템플릿 점수 (파일이 없으면 0)"""
    if name not in _T:
        _T[name] = cv2.imread(os.path.join(BASE, "tpl", name))
    t = _T[name]
    if t is None or img is None:
        return 0.0
    x1, y1, x2, y2 = roi
    sub = img[y1:y2, x1:x2]
    if sub.shape[0] < t.shape[0] or sub.shape[1] < t.shape[1]:
        return 0.0
    return float(cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED).max())


def dlg_open(img):
    """설정창이 열려 있는지: 빨간 X + '설정' 제목 그림 (patch103)"""
    return _x_red(img) and _score(img, "wc_title.png", (280, 170, 440, 255)) >= 0.8


def _x_red(img):
    """설정창 빨간 X 버튼이 보이는지 (X 는 흰 글자 + 빨간 테두리라서 느슨한 빨강 기준)"""
    x, y = DLG_X
    hsv = cv2.cvtColor(img[y - 14:y + 15, x - 14:x + 15], cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (0, 100, 80), (10, 255, 255)) | cv2.inRange(hsv, (170, 100, 80), (180, 255, 255))
    return float(m.mean()) / 255.0 >= 0.3


def tab_selected(img):
    x1, y1, x2, y2 = ROI_TAB
    b, g, r = img[y1:y2, x1:x2].reshape(-1, 3).mean(0)
    # patch103: 본문 머리(호른 아이콘 + '웨이브 호출') 그림까지 맞아야 함 (황혼의 부름 탭은 0.46)
    return r - b >= 40 and _score(img, "wc_head.png", (40, 280, 320, 390)) >= 0.8


def auto_on(img):
    """AUTO 알약 안의 주황 점 개수로 켜짐 판별 (켜짐 약 140, 꺼짐 0)"""
    x1, y1, x2, y2 = ROI_PILL
    hsv = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    n = int(((h >= 8) & (h <= 25) & (s >= 150) & (v >= 150)).sum())
    return n >= 60, n


def grab(wait=0.0):
    if wait:
        time.sleep(wait)
    img = preset.capture()
    if img is None:
        raise RuntimeError("화면 캡처 실패")
    return img


def close_dialog():
    for _ in range(3):
        img = grab()
        if not dlg_open(img):
            return True
        preset.tap(DLG_X, "설정창 닫기")
        time.sleep(0.8)
    return not dlg_open(grab())


def _open():
    """설정창을 열고 웨이브 호출 탭까지. 성공하면 화면, 실패하면 None"""
    img = grab()
    if not dlg_open(img):                       # patch103: 다른 창이 떠 있으면 먼저 닫음
        try:
            import closer
            if closer.close_buttons(img):
                log("다른 창이 떠 있음 -> 먼저 닫음")
                closer.close_all()
                img = grab(0.5)
        except Exception as e:
            log("창 정리 생략:", repr(e))
    if not dlg_open(img):
        for _ in range(2):
            preset.tap(GEAR, "설정 열기")
            img = grab(1.0)
            if dlg_open(img):
                break
        else:
            log("설정창이 열리지 않음")
            return None
    if not tab_selected(img):
        preset.tap(TAB_WAVE, "웨이브 호출 탭")
        img = grab(0.7)
        if not tab_selected(img):
            log("웨이브 호출 탭 선택 확인 실패")
            close_dialog()
            return None
    return img


def _read(img):
    """AUTO 상태를 두 번 읽어 같을 때만 (patch109)"""
    on, n = auto_on(img)
    img_b = grab(0.4)
    if auto_on(img_b)[0] != on:
        img_b = grab(0.6)
        on, n = auto_on(img_b)
    return on, n, img_b


def set_auto(want_on):
    """웨이브 호출 AUTO 를 want_on 상태로 맞춤. 성공하면 True
    patch151: 눌렀는데 설정창의 표시만 안 바뀌는 경우가 많음(실제로는 바뀜).
              그때 다시 누르면 도로 꺼지거나 켜지므로, 창을 닫았다 다시 열어서 실제 상태를 확인함"""
    try:
        img = _open()
        if img is None:
            return False
        for attempt in range(3):
            on, n, img = _read(img)
            if on == want_on:
                log("AUTO %s 상태 확인 (주황 %d)" % ("켜짐" if on else "꺼짐", n))
                close_dialog()
                return True
            if not (dlg_open(img) and tab_selected(img)):      # patch103: 누르기 직전 다시 확인
                log("설정창의 웨이브 호출 탭이 아님 -> AUTO 안 누름")
                close_dialog()
                return False
            preset.tap(AUTO_BTN, "AUTO 누르기")
            t0 = time.time()
            img = grab(0.5)
            while auto_on(img)[0] != want_on and time.time() - t0 < 2.0:
                img = grab(0.3)
            if auto_on(img)[0] == want_on:
                continue                                       # 다음 바퀴에서 두 번 읽어 확인
            log("눌렀는데 표시가 안 바뀜 -> 창을 닫았다 다시 열어 실제 상태 확인")
            close_dialog()
            time.sleep(0.5)
            img = _open()
            if img is None:
                return False
        on, n, img = _read(img)
        if on == want_on:
            log("AUTO %s 상태 확인 (주황 %d)" % ("켜짐" if on else "꺼짐", n))
            close_dialog()
            return True
        log("AUTO 상태를 바꾸지 못함")
        try:                                               # patch109: 실패 화면 저장
            os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
            p = os.path.join(BASE, "shots", time.strftime("wc_fail_%m%d_%H%M%S.png"))
            cv2.imwrite(p, img)
            log("화면 저장:", p)
        except Exception:
            pass
        close_dialog()
        return False
    except Exception as e:
        log("오류:", repr(e))
        try:
            close_dialog()
        except Exception:
            pass
        return False


def tick(st, w):
    """main 루프에서 호출. 상태를 바꿨거나 시도했으면 True (state 저장 필요)"""
    if w is None:
        return False
    off = bool(st.get("wc_off", False))
    # patch224: 사용자 요청 - AUTO 를 끄지 않음 (항상 켜 둠). 예전에 꺼 둔 상태면 다시 켜기만 함
    if off:
        want_on = True
    else:
        st.pop("wc_low_since", None)
        return False
    now = time.time()
    if now < st.get("wc_next", 0):
        return False
    log("웨이브 %d -> 웨이브 호출 AUTO %s 시도" % (w, "켜기" if want_on else "끄기"))
    if set_auto(want_on):
        st["wc_off"] = not want_on
        st.pop("wc_low_since", None)
        st["wc_fail"] = 0
        st["wc_next"] = 0
    else:
        st["wc_fail"] = st.get("wc_fail", 0) + 1
        st["wc_next"] = now + (120 if st["wc_fail"] < 3 else 1800)
    return True


if __name__ == "__main__":
    preset.GO = "go" in sys.argv[1:]
    img = grab()
    print("설정창 열림:", dlg_open(img), "/ 웨이브 호출 탭 선택:", tab_selected(img), "/ AUTO:", auto_on(img))
    if "off" in sys.argv[1:]:
        print("결과:", set_auto(False))
    elif "on" in sys.argv[1:]:
        print("결과:", set_auto(True))
