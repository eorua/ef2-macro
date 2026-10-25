import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
GO = "go" in sys.argv[1:]            # go 를 붙여야 실제 클릭

# 화면 비율 ROI (x1, y1, x2, y2)
FALL_TITLE  = (0.15, 0.12, 0.85, 0.32)   # '성 함락' 제목 (patch208: 10-21 업데이트로 창이 커져 제목이 y 0.16 으로 올라감)
FALL_GREEN  = (0.03, 0.42, 0.33, 0.64)   # 왼쪽 초록 '환생' 버튼만 (빨간 버튼 제외) - patch131: 10-15 업데이트로 위치 이동
RES_TITLE   = (0.20, 0.25, 0.80, 0.48)   # '환생결과' 제목 (patch208: 넓힘)
RES_CONFIRM = (0.25, 0.45, 0.75, 0.75)   # 초록 '확인' 버튼 (patch208: 넓힘)


def capture():
    png = subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                         capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def tap(x, y):
    subprocess.run(ADB + ["shell", "input", "tap", str(int(x)), str(int(y))])


def has(name):
    return os.path.exists(os.path.join(BASE, "tpl", name))


def match(screen, name, roi):
    tpl = cv2.imread(os.path.join(BASE, "tpl", name))
    if tpl is None:
        return 0.0, (0, 0)
    H, W = screen.shape[:2]
    x1, y1, x2, y2 = int(roi[0]*W), int(roi[1]*H), int(roi[2]*W), int(roi[3]*H)
    sub = screen[y1:y2, x1:x2]
    h, w = tpl.shape[:2]
    if sub.shape[0] < h or sub.shape[1] < w:
        return 0.0, (0, 0)
    res = cv2.matchTemplate(sub, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    return float(score), (x1 + loc[0] + w // 2, y1 + loc[1] + h // 2)


def check(path):
    """저장된 이미지 한 장으로 템플릿 점수만 확인 (게임/ADB 불필요)"""
    s = cv2.imread(path)
    print("이미지 크기:", s.shape)
    for name, roi in [("title_fall.png", FALL_TITLE), ("btn_green.png", FALL_GREEN),
                      ("title_result.png", RES_TITLE), ("btn_confirm.png", RES_CONFIRM)]:
        sc, pos = match(s, name, roi)
        print(f"{name:18s} score={sc:.2f}  pos={pos}")


def wait_fall():
    print("성 함락 팝업 대기 중...")
    while True:
        s = capture()
        ts, _ = match(s, "title_fall.png", FALL_TITLE)
        gs, (gx, gy) = match(s, "btn_green.png", FALL_GREEN)
        print(f"title_fall={ts:.2f}  green={gs:.2f}  pos=({gx},{gy})")
        if ts >= 0.85 and gs >= 0.90 and gx < 0.29 * s.shape[1]:
            return gx, gy
        time.sleep(1)


def snap_reward(img, kind, st=None):
    """patch272: 환생 보상(훈장) 분석용 - 성 함락/환생결과 창을 shots\\reward 에 jpg 로 저장 (화면 가운데만)"""
    try:
        if img is None:
            return
        d = os.path.join(BASE, "shots", "reward")
        os.makedirs(d, exist_ok=True)
        w = int((st or {}).get("peak_wave") or 0)
        n = time.strftime("%m%d_%H%M%S") + "_%s_w%d.jpg" % (kind, w)
        h = img.shape[0]
        crop = img[150:1130] if h >= 1200 else img
        cv2.imwrite(os.path.join(d, n), crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    except Exception as e:
        print("[rebirth] 보상 화면 저장 실패: %r" % (e,))


def parse_result_medal(img):
    """patch272: 환생결과 팝업에서 획득한 최종 훈장 수량 판독 (예: '3.12c (x3)' 또는 '2.89c (x2)')"""
    if img is None:
        return None
    try:
        import ocrx, re
        h = img.shape[0]
        crop = img[400:850, 100:620] if h >= 1200 else img
        ws = ocrx.words(crop) or []
        line = " ".join(w[0] for w in ws)
        m = re.search(r"훈장\s*(?:\((x\d+)\))?\s*[:：]?\s*([0-9.]+\s*[a-zA-Z]+)", line)
        if m:
            mult, amt = m.group(1), m.group(2).replace(" ", "")
            return f"{amt} ({mult})" if mult else amt
        for w in ws:
            m2 = re.match(r"^[+~]?([0-9.]+[a-zA-Z]+)$", w[0].strip())
            if m2 and not m2.group(1).lower().endswith("m") and not m2.group(1).lower().endswith("h"):
                return m2.group(1)
    except Exception as e:
        print("[rebirth] 훈장 판독 오류: %r" % (e,))
    return None


def parse_fall_info(img):
    """patch272: 성 함락 / 환생하기 창에서 훈장 공식 및 지난 시간 판독
    반환: (medal_formula, time_str) - 예: ('17.2b + 1.03c', '53분')
    """
    if img is None:
        return None, None
    try:
        import ocrx, re
        ws = ocrx.words(img) or []
        line = " ".join(w[0] for w in ws)
        m_medal = re.search(r"([0-9.]+\s*[a-zA-Z]+)\s*\+\s*([0-9.]+\s*[a-zA-Z]+)", line)
        medal = ("%s + %s" % (m_medal.group(1).replace(" ", ""), m_medal.group(2).replace(" ", ""))) if m_medal else None
        m_time = re.search(r"시간\s*[:：]?\s*(\d+)\s*([MmHh])", line)
        t_str = None
        if m_time:
            num, unit = m_time.group(1), m_time.group(2).upper()
            t_str = f"{num}분" if unit == "M" else f"{num}시간"
        return medal, t_str
    except Exception as e:
        print("[rebirth] 함락 정보 판독 오류: %r" % (e,))
        return None, None


def after_click(st=None):
    ready = has("title_result.png") and has("btn_confirm.png")
    if not ready:
        print("환생결과 템플릿이 아직 없음 -> 화면을 shots\\after_XX.png 로 저장합니다")
    t0, n = time.time(), 0
    while time.time() - t0 < 25:
        s = capture()
        if not ready:
            cv2.imwrite(os.path.join(BASE, "shots", f"after_{n:02d}.png"), s)
            n += 1
            time.sleep(1)
            continue
        ts, _ = match(s, "title_result.png", RES_TITLE)
        bs, (bx, by) = match(s, "btn_confirm.png", RES_CONFIRM)
        print(f"title_result={ts:.2f}  confirm={bs:.2f}  pos=({bx},{by})")
        if ts >= 0.85 and bs >= 0.90:
            if st is not None:
                try:
                    snap_reward(s, "result", st)
                    m = parse_result_medal(s)
                    if m:
                        st["last_medal"] = m
                except Exception as e:
                    print("[rebirth] 환생결과 처리 오류: %r" % (e,))
            tap(bx, by)
            print("환생결과 '확인' 클릭 완료")
            return True
        time.sleep(0.5)
    return False


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "check":
        check(sys.argv[2])
        return
    print("실제 클릭 모드" if GO else "테스트 모드 (클릭 안 함)", "- 중지: Ctrl + C")
    gx, gy = wait_fall()
    if not GO:
        print(f"테스트 모드: ({gx},{gy}) 의 초록 '환생' 버튼을 클릭할 예정")
        return
    tap(gx, gy)
    print("환생 버튼 클릭")
    time.sleep(2)
    ok = after_click()
    print("한 사이클 완료" if ok else "환생결과 팝업 처리 없이 종료 (shots 폴더의 after_XX.png 확인)")


if __name__ == "__main__":
    main()