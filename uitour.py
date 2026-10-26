# -*- coding: utf-8 -*-
"""uitour.py - 오환2 매크로 핵심 화면 & 버튼 UI 점검 투어 진단 도구 (patch292)
게임 업데이트 후 UI 위치나 버튼 좌표가 변경되었는지 확인하기 위해,
매크로가 사용하는 주요 탭과 화면들을 1바퀴 돌며 현재 타겟 좌표를 시각화(오버레이)하여 캡처합니다.

사용법:
  py uitour.py        # 시험 모드 (현재 화면만 캡처 및 표시)
  py uitour.py go     # 실제 전체 화면 투어 실행 (탭 및 주요 팝업 열기/닫기)
"""
import os, sys, time, subprocess
import cv2, numpy as np

BASE = r"C:\macro"
ADB = [r"C:\platform-tools\adb.exe", "-s", __import__("adbport").DEV]
TOUR_DIR = os.path.join(BASE, "shots", "uitour")
GO = "go" in sys.argv[1:]

# 6대 하단 탭 좌표 (720x1280)
TABS = {
    "1_quest":  ("퀘스트 탭", (68, 1240)),
    "2_hero":   ("영웅 탭",   (185, 1240)),
    "3_castle": ("성 탭",     (302, 1240)),
    "4_relic":  ("유물 탭",   (420, 1240)),
    "5_battle": ("전투 탭",   (535, 1245)),
    "6_shop":   ("상점 탭",   (650, 1245)),
}


def log(*a):
    print(time.strftime("[%H:%M:%S] uitour:"), *a, flush=True)


def capture():
    try:
        png = subprocess.run(ADB + ["exec-out", "screencap", "-p"],
                             capture_output=True, timeout=10).stdout
        if not png:
            return None
        return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    except Exception as e:
        log("캡처 실패:", e)
        return None


def tap(pt, label=""):
    x, y = int(pt[0]), int(pt[1])
    log(("클릭 " if GO else "[시험] 클릭 ") + f"{label} ({x}, {y})")
    if GO:
        subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)])


def draw_target(img, pt, label="", color=(0, 255, 0), r=18):
    """클릭 타겟 점에 원 + 십자선 + 텍스트 오버레이"""
    x, y = int(pt[0]), int(pt[1])
    cv2.circle(img, (x, y), r, color, 2)
    cv2.line(img, (x - r - 5, y), (x + r + 5, y), color, 1)
    cv2.line(img, (x, y - r - 5), (x, y + r + 5), color, 1)
    if label:
        cv2.putText(img, label, (max(5, x - 60), max(20, y - r - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(img, label, (max(5, x - 60), max(20, y - r - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def draw_roi(img, roi, label="", color=(0, 255, 255)):
    """ROI 영역 상자 + 텍스트 오버레이"""
    x1, y1, x2, y2 = roi
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    if label:
        cv2.putText(img, label, (x1 + 4, max(18, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
        cv2.putText(img, label, (x1 + 4, max(18, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def save_tour_shot(img, name):
    os.makedirs(TOUR_DIR, exist_ok=True)
    p = os.path.join(TOUR_DIR, f"{name}.png")
    cv2.imwrite(p, img)
    log(f"저장 완료: {p}")
    return p


def run_tour():
    log("=== 오환2 UI 점검 투어 시작 ===")
    os.makedirs(TOUR_DIR, exist_ok=True)

    # 1. 퀘스트 탭 점검
    log("▶ 1. 퀘스트 탭 점검")
    tap(TABS["1_quest"][1], "퀘스트 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["1_quest"][1], "TAB_QUEST", (0, 255, 0))
        draw_roi(ov, (500, 725, 715, 765), "GOLD_ROI (골드)", (0, 215, 255))
        draw_roi(ov, (550, 850, 700, 1150), "UPGRADE_BTNS", (255, 150, 0))
        save_tour_shot(ov, "01_tab_quest")

    # 2. 영웅 탭 점검
    log("▶ 2. 영웅 탭 점검")
    tap(TABS["2_hero"][1], "영웅 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["2_hero"][1], "TAB_HERO", (0, 255, 0))
        draw_target(ov, (326, 790), "BTN_PLUS (+)", (0, 255, 255))
        draw_target(ov, (131, 778), "HERO_AUTO (• AUTO)", (0, 200, 255))
        draw_target(ov, (650, 790), "BTN_HIRE (영입)", (255, 100, 100))
        draw_roi(ov, (594, 754, 622, 782), "DOT_HERO (영입점)", (0, 165, 255))
        save_tour_shot(ov, "02_tab_hero")

    # 3. 영웅 고용 팝업 점검 (영웅 탭에서 영입 클릭)
    log("▶ 3. 영웅 고용 팝업 점검")
    if GO:
        tap((650, 790), "영입 버튼")
        time.sleep(1.5)
        im = capture()
        if im is not None:
            ov = im.copy()
            draw_target(ov, (465, 790), "새로고침", (0, 255, 0))
            draw_target(ov, (585, 790), "훈장구매", (0, 255, 255))
            draw_target(ov, (674, 790), "닫기X", (0, 0, 255))
            draw_roi(ov, (406, 754, 434, 782), "DOT_REFRESH (새로고침점)", (255, 0, 255))
            # 4대 영웅 보석 구매 버튼 줄
            for i in range(4):
                y = 868 + 90 * i
                draw_target(ov, (625, y), f"보석구매_{i+1}", (255, 180, 50), r=12)
            save_tour_shot(ov, "03_popup_recruit")
            tap((674, 790), "닫기X")
            time.sleep(1.0)

    # 4. 성 탭 점검
    log("▶ 4. 성 탭 점검")
    tap(TABS["3_castle"][1], "성 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["3_castle"][1], "TAB_CASTLE", (0, 255, 0))
        draw_target(ov, (350, 340), "CASTLE_CLICK (영웅배치)", (0, 255, 255))
        save_tour_shot(ov, "04_tab_castle")

    # 5. 유물 탭 점검
    log("▶ 5. 유물 탭 점검")
    tap(TABS["4_relic"][1], "유물 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["4_relic"][1], "TAB_RELIC", (0, 255, 0))
        save_tour_shot(ov, "05_tab_relic")

    # 6. 전투 탭 점검
    log("▶ 6. 전투 탭 점검")
    tap(TABS["5_battle"][1], "전투 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["5_battle"][1], "TAB_BATTLE", (0, 255, 0))
        draw_target(ov, (300, 870), "ROW_DUNGEON (던전)", (0, 255, 255))
        draw_target(ov, (300, 1060), "ROW_RANKING (일일랭킹전)", (0, 200, 255))
        save_tour_shot(ov, "06_tab_battle")

    # 7. 상점 탭 점검
    log("▶ 7. 상점 탭 점검")
    tap(TABS["6_shop"][1], "상점 탭")
    time.sleep(1.2 if GO else 0.2)
    im = capture()
    if im is not None:
        ov = im.copy()
        draw_target(ov, TABS["6_shop"][1], "TAB_SHOP", (0, 255, 0))
        draw_target(ov, (515, 790), "AD_TAB (광고패키지탭)", (0, 255, 255))
        save_tour_shot(ov, "07_tab_shop")

    # 8. 공방 및 이벤트 진입 확인
    log("▶ 8. 공방 로비 점검")
    if GO:
        try:
            import hexa
            hexa.load_cfg()
            hexa.find_serial()
            ok_f, _ = hexa.ensure_forge_open()
            if ok_f:
                time.sleep(1.0)
                im_f = capture()
                if im_f is not None:
                    ov = im_f.copy()
                    draw_target(ov, (360, 1168), "BTN_START/CONT (1168)", (0, 255, 0))
                    draw_target(ov, (110, 212), "TAB_FORGE (공방)", (0, 255, 255))
                    draw_target(ov, (638, 120), "BTN_CLOSE (X)", (0, 0, 255))
                    save_tour_shot(ov, "08_popup_forge_lobby")
                hexa.close_event()
                time.sleep(1.0)
        except Exception as e:
            log("공방 점검 중 오류:", e)

    # 9. 복귀: 기본 대기화면인 퀘스트 탭으로 복귀
    log("▶ 9. 기본 대기화면(퀘스트 탭) 복귀")
    tap(TABS["1_quest"][1], "퀘스트 탭 복귀")
    time.sleep(0.8 if GO else 0.2)

    log("=== UI 점검 투어 완료! 저장 폴더: %s ===" % TOUR_DIR)
    if GO:
        try:
            os.startfile(TOUR_DIR)
        except Exception:
            pass
    return True


if __name__ == "__main__":
    run_tour()
