import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
from dev import ADB          # patch162
GO = "go" in sys.argv[1:]            # go 를 붙여야 실제 클릭

# 화면 비율 ROI (x1, y1, x2, y2)
FALL_TITLE  = (0.15, 0.18, 0.85, 0.32)   # '성 함락' 제목
FALL_GREEN  = (0.03, 0.42, 0.33, 0.64)   # 왼쪽 초록 '환생' 버튼만 (빨간 버튼 제외) - patch131: 10-15 업데이트로 위치 이동
RES_TITLE   = (0.25, 0.35, 0.75, 0.48)   # '환생결과' 제목
RES_CONFIRM = (0.30, 0.52, 0.70, 0.68)   # 초록 '확인' 버튼


def capture():
    import dev                      # patch162
    return dev.capture()


def tap(x, y):
    import dev                      # patch162
    dev.tap(x, y)


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


def after_click():
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