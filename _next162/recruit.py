import subprocess, sys, time, os, cv2, numpy as np

BASE = r"C:\macro"
import dev                   # patch162: 공통 ADB
from dev import ADB
GO = "go" in sys.argv[1:]

# 클릭 좌표 (720x1280 기준)
P = {
    "영입":     (650, 790),
    "새로고침": (465, 790),
    "훈장구매": (585, 790),
    "닫기X":    (674, 790),
    "확인(금지)": (266, 632),
    "취소":     (452, 632),
    "성탭":     (302, 1240),
    "영웅탭":   (185, 1240),
}
# 점 위치 (중심 x, y) - 영웅 탭의 '영입' 주황 점 / 고용 화면의 '새로고침' 빨간 점
DOT_HERO = (608, 768)
DOT_REFRESH = (420, 768)
DOT_R = 14          # 검사 상자 반지름(px)
DOT_THR = 0.06      # 이 비율 이상이면 점이 있다고 판단


def capture():
    return dev.capture()            # patch162


def tap(name):
    x, y = P[name]
    if GO:
        dev.tap(x, y)               # patch162
    print(("클릭 " if GO else "[시험] 클릭할 곳 ") + f"{name} ({x},{y})")


def dot_ratio(img, center, kind):
    x, y = center
    box = img[max(y - DOT_R, 0):y + DOT_R + 1, max(x - DOT_R, 0):x + DOT_R + 1]
    hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
    if kind == "orange":
        m = cv2.inRange(hsv, (8, 200, 230), (25, 255, 255))
    elif kind == "any":   # 점이 깜빡이며 빨강 <-> 주황으로 바뀌므로 둘 다 인정
        m = cv2.inRange(hsv, (0, 200, 200), (25, 255, 255)) | cv2.inRange(hsv, (172, 200, 200), (180, 255, 255))
    else:  # red
        m = cv2.inRange(hsv, (0, 200, 200), (8, 255, 255)) | cv2.inRange(hsv, (172, 200, 200), (180, 255, 255))
    return float(m.mean()) / 255.0


def mark():
    img = capture()
    if img is None:
        print("캡처 실패 (ADB 연결 확인)")
        return
    ro = dot_ratio(img, DOT_HERO, "orange")
    rr = dot_ratio(img, DOT_REFRESH, "any")
    print("영입 주황점 비율:", round(ro, 3), "| 새로고침 빨간점 비율:", round(rr, 3), "| 기준:", DOT_THR)
    for name, (x, y) in P.items():
        c = (0, 0, 255) if "금지" in name else (0, 255, 0)
        cv2.circle(img, (x, y), 22, c, 3)
        cv2.putText(img, name, (max(x - 60, 0), y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    for (x, y), c in ((DOT_HERO, (0, 165, 255)), (DOT_REFRESH, (255, 0, 255))):
        cv2.rectangle(img, (x - DOT_R, y - DOT_R), (x + DOT_R, y + DOT_R), c, 2)
    path = os.path.join(BASE, "shots", "mark.png")
    cv2.imwrite(path, img)
    print("저장:", path)


def recruit(force=False):
    """결과: 'done'(새로고침+훈장구매 완료) / 'cooldown'(쿨타임 중) / 'fail'(캡처 실패 등)"""
    # 영웅 탭을 계속 띄워두면 점이 갱신되지 않으므로, 성 탭으로 갔다가 영웅 탭으로 돌아온다
    tap("성탭")
    time.sleep(1.0)
    tap("영웅탭")
    time.sleep(1.2)
    img = capture()
    if img is None:
        print("캡처 실패, 중단")
        return "fail"
    hr = dot_ratio(img, DOT_HERO, "any")
    for _ in range(3):                      # 점이 빨강 <-> 주황으로 깜빡이므로 몇 번 더 확인
        if hr >= DOT_THR:
            break
        time.sleep(0.7)
        img = capture()
        if img is not None:
            hr = dot_ratio(img, DOT_HERO, "any")
    print("영입 버튼 점 비율:", round(hr, 3))
    if hr < DOT_THR and not force:
        print("영입 버튼에 점 없음 → 쿨타임, 영입 창을 열지 않음")
        return "cooldown"
    tap("영입")
    time.sleep(1.5)
    img = capture()
    if img is None:
        print("캡처 실패, 중단")
        return "fail"
    cv2.imwrite(os.path.join(BASE, "shots", "recruit_screen.png"), img)
    rr = dot_ratio(img, DOT_REFRESH, "any")
    for _ in range(3):
        if rr >= DOT_THR:
            break
        time.sleep(0.7)
        img = capture()
        if img is not None:
            rr = dot_ratio(img, DOT_REFRESH, "any")
    print("새로고침 점 비율:", round(rr, 3))
    if rr < DOT_THR:
        print("빨간 점 없음(쿨타임 중) → 새로고침 안 함, 닫기")
        tap("닫기X")
        return "cooldown"
    print("무료 새로고침 가능 → 새로고침 → 훈장구매 → 닫기")
    tap("새로고침")
    time.sleep(1.5)
    img2 = capture()
    if img2 is not None:
        cv2.imwrite(os.path.join(BASE, "shots", "recruit_after_refresh.png"), img2)
    tap("훈장구매")
    time.sleep(1.5)
    tap("닫기X")
    return "done"


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE, "shots"), exist_ok=True)
    if "mark" in sys.argv[1:]:
        mark()
    else:
        recruit(force="force" in sys.argv[1:])